"""VoiceLens FastAPI HTTP API Server.

Exposes REST endpoints for speech audio analysis and health monitoring.
"""

import logging
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from voicelens import __version__
from voicelens.audio_converter import AudioConversionError, convert_to_wav
from voicelens.pipeline import run_voicelens_pipeline
from voicelens.transcriber import Transcriber, TranscriberError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

# Configuration from environment variables
ALLOWED_ORIGINS = os.getenv("VOICELENS_ALLOWED_ORIGINS", "*").split(",")
MAX_FILE_SIZE = int(os.getenv("VOICELENS_MAX_FILE_SIZE", "50000000"))
TARGET_SAMPLE_RATE = int(os.getenv("VOICELENS_TARGET_SAMPLE_RATE", "16000"))
WHISPER_MODEL = os.getenv("VOICELENS_WHISPER_MODEL", "base.en")
LOG_LEVEL = os.getenv("VOICELENS_LOG_LEVEL", "INFO")

# Set log level
logging.getLogger().setLevel(LOG_LEVEL)

app = FastAPI(
    title="VoiceLens API",
    description="HTTP REST API for VoiceLens voice analysis engine.",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS with configurable origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared transcriber instance - loaded once at startup
_transcriber: Transcriber | None = None


def get_transcriber() -> Transcriber:
    """Get or create the shared Transcriber instance."""
    global _transcriber
    if _transcriber is None:
        logging.getLogger(__name__).info("Initializing shared Transcriber for API...")
        _transcriber = Transcriber(model_size=WHISPER_MODEL)
    return _transcriber


@app.on_event("startup")
async def startup_event() -> None:
    """Pre-load the Whisper model on API startup."""
    logger = logging.getLogger(__name__)
    logger.info("VoiceLens API starting up...")
    logger.info(f"Configuration: model={WHISPER_MODEL}, max_file_size={MAX_FILE_SIZE}, origins={ALLOWED_ORIGINS}")
    try:
        get_transcriber()
        logger.info("VoiceLens API ready")
    except Exception as e:
        logger.error(f"Failed to initialize transcriber: {e}")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Cleanup on shutdown."""
    logger = logging.getLogger(__name__)
    logger.info("VoiceLens API shutting down...")


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@app.get("/api/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Health check endpoint to verify API server availability."""
    return HealthResponse(
        status="ok",
        service="VoiceLens API",
        version=__version__,
    )


class ErrorResponse(BaseModel):
    detail: str


@app.post(
    "/api/analyze",
    responses={
        200: {"description": "Successful analysis"},
        400: {"model": ErrorResponse, "description": "Bad request"},
        422: {"model": ErrorResponse, "description": "Unprocessable entity"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def analyze_audio(
    file: UploadFile = File(..., max_size=MAX_FILE_SIZE),
) -> dict:
    """Upload audio file (WEBM, WAV, MP3, OGG, FLAC) and run VoiceLens analysis.

    Converts incoming audio to a 16kHz mono WAV file before passing it to
    speech delivery metrics, pronunciation assessment, accent classification,
    and forced alignment modules.

    Args:
        file: Uploaded audio file via multipart/form-data.

    Returns:
        dict: Complete VoiceLens analysis results JSON matching domain contract.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided in upload request.",
        )

    # Validate file extension
    allowed_extensions = {".webm", ".wav", ".mp3", ".ogg", ".flac", ".m4a", ".mp4", ".mpeg"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format: {ext}. Supported: {', '.join(allowed_extensions)}",
        )

    tmp_raw_path: Path | None = None
    tmp_wav_path: Path | None = None

    # 1. Save uploaded bytes to raw temporary audio file
    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded audio file is empty.",
            )

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_file:
            tmp_raw_path = Path(tmp_file.name)
            tmp_file.write(content)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process uploaded file: {e}",
        ) from e

    # 2. Convert uploaded audio (e.g. .webm) to 16kHz mono WAV file
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav_file:
            tmp_wav_path = Path(tmp_wav_file.name)

        convert_to_wav(tmp_raw_path, tmp_wav_path, target_sample_rate=TARGET_SAMPLE_RATE)

    except AudioConversionError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Audio conversion failed: {e}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error converting audio: {e}",
        ) from e

    # 3. Execute VoiceLens pipeline on the converted 16kHz mono WAV file
    # Pass the shared transcriber to reuse the loaded model
    try:
        transcriber = get_transcriber()
        result = run_voicelens_pipeline(tmp_wav_path, transcriber=transcriber)
        return result
    except TranscriberError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Transcription failed: {e}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"VoiceLens analysis engine failed: {e}",
        ) from e
    finally:
        # 4. Safely clean up both temporary raw file and converted WAV file
        for p in (tmp_raw_path, tmp_wav_path):
            if p and p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass