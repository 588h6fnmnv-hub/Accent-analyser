"""VoiceLens Whisper transcription implementation.

Original working implementation using faster-whisper.
"""

import logging
import platform
import time
from pathlib import Path
from typing import Any

# Disable tqdm multiprocessing lock to avoid "bad value(s) in fds_to_keep" error
# on macOS when running in certain thread/async contexts (e.g., Textual TUI)
# This must be done before faster_whisper imports tqdm via huggingface_hub
import os
os.environ.setdefault("TQDM_DISABLE", "1")

# Monkey-patch tqdm to disable multiprocessing lock creation
try:
    import tqdm
    tqdm.tqdm.monitor_interval = 0
    import threading
    _tqdm_threading_lock = threading.RLock()
    def patched_get_lock(cls):
        return _tqdm_threading_lock
    tqdm.tqdm.get_lock = classmethod(patched_get_lock)
    tqdm.tqdm._lock = _tqdm_threading_lock
except Exception:
    pass

# Lazy import for faster_whisper
_FASTER_WHISPER_AVAILABLE = False
_FASTER_WHISPER_ERROR_MSG = ""
WhisperModel: Any = None

try:
    from faster_whisper import WhisperModel as _WhisperModel
    WhisperModel = _WhisperModel
    _FASTER_WHISPER_AVAILABLE = True
except Exception as e:
    _FASTER_WHISPER_ERROR_MSG = str(e)


class WhisperTranscriberError(Exception):
    """Base exception for all Whisper transcription errors."""
    pass


def _get_optimal_device_and_compute_type() -> tuple[str, str]:
    """Determine the optimal device and compute type for the current platform."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    # CUDA (NVIDIA GPU) - fastest if available
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda", "float16"
    except Exception:
        pass

    # Note: faster-whisper (ctranslate2) does not support MPS/Metal on macOS
    # despite PyTorch supporting it. Use CPU with int8 for Apple Silicon.
    return "cpu", "int8"


class WhisperTranscriber:
    """Handles speech-to-text transcription using faster-whisper.

    Original working implementation with beam search for accurate transcription.
    """

    # Original transcription parameters that worked well
    TRANSCRIBE_PARAMS = {
        "language": "en",
        "beam_size": 8,
        "best_of": 8,
        "temperature": 0.0,
        "condition_on_previous_text": False,
        "vad_filter": True,
        "vad_parameters": {
            "threshold": 0.5,
            "min_speech_duration_ms": 250,
            "max_speech_duration_s": 30,
            "min_silence_duration_ms": 2000,
            "speech_pad_ms": 400,
        },
        "compression_ratio_threshold": 2.4,
        "log_prob_threshold": -1.0,
        "no_speech_threshold": 0.6,
        "initial_prompt": (
            "This is a recording of natural English speech. "
            "Transcribe exactly what is spoken including fillers like um, uh, hmm. "
            "Do not add or remove words."
        ),
        "log_progress": False,
    }

    def __init__(
        self,
        model_size: str = "base",
        device: str | None = None,
        compute_type: str | None = None,
    ) -> None:
        if not _FASTER_WHISPER_AVAILABLE:
            raise WhisperTranscriberError(
                f"faster-whisper is not available: {_FASTER_WHISPER_ERROR_MSG}. "
                "Install with 'pip install faster-whisper'."
            )

        if device is None or compute_type is None:
            auto_device, auto_compute = _get_optimal_device_and_compute_type()
            device = device or auto_device
            compute_type = compute_type or auto_compute

        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model: Any = None
        self._model_load_time: float | None = None
        self._logger = logging.getLogger(__name__)

    def _get_model(self) -> Any:
        if self._model is None:
            start_time = time.perf_counter()
            try:
                self._logger.info(
                    f"Loading Whisper model ({self.model_size}) on {self.device} "
                    f"with {self.compute_type}..."
                )

                self._model = WhisperModel(
                    model_size_or_path=self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                    local_files_only=True,
                )

                self._model_load_time = time.perf_counter() - start_time
                self._logger.info(
                    f"Whisper model ready in {self._model_load_time:.2f}s"
                )

            except Exception as e:
                raise WhisperTranscriberError(
                    f"Failed to load Whisper model '{self.model_size}': {e}"
                ) from e

        return self._model

    def transcribe(self, audio_path: Path | str) -> str:
        """Transcribe audio file to text."""
        path = Path(audio_path)

        if not path.exists():
            raise WhisperTranscriberError(
                f"Audio file does not exist: {path.resolve()}"
            )

        model = self._get_model()

        try:
            self._logger.info("Starting transcription...")
            start_time = time.perf_counter()

            params = self.TRANSCRIBE_PARAMS.copy()
            params["word_timestamps"] = False

            segments, _info = model.transcribe(str(path), **params)

            transcript_parts = []
            for segment in segments:
                transcript_parts.append(segment.text.strip())

            transcript = " ".join(transcript_parts).strip()

            transcribe_time = time.perf_counter() - start_time
            self._logger.info(f"Transcription completed in {transcribe_time:.2f}s")

            return transcript

        except Exception as e:
            raise WhisperTranscriberError(
                f"Error during Whisper transcription: {e}"
            ) from e

    def transcribe_with_timestamps(
        self, audio_path: Path | str
    ) -> tuple[str, list[dict[str, Any]]]:
        """Transcribe and return both text and word-level timestamps for alignment."""
        path = Path(audio_path)

        if not path.exists():
            raise WhisperTranscriberError(
                f"Audio file does not exist: {path.resolve()}"
            )

        model = self._get_model()

        try:
            self._logger.info("Starting transcription with timestamps...")
            start_time = time.perf_counter()

            params = self.TRANSCRIBE_PARAMS.copy()
            params["word_timestamps"] = True

            segments, _info = model.transcribe(str(path), **params)

            transcript_parts = []
            word_timestamps = []

            for segment in segments:
                transcript_parts.append(segment.text.strip())
                if hasattr(segment, "words") and segment.words:
                    for w in segment.words:
                        word_timestamps.append({
                            "word": w.word.strip(),
                            "start": w.start,
                            "end": w.end,
                            "confidence": w.probability,
                        })

            transcript = " ".join(transcript_parts).strip()

            transcribe_time = time.perf_counter() - start_time
            self._logger.info(
                f"Transcription with timestamps completed in {transcribe_time:.2f}s"
            )

            return transcript, word_timestamps

        except Exception as e:
            raise WhisperTranscriberError(
                f"Error during Whisper transcription: {e}"
            ) from e

    @property
    def model_load_time(self) -> float | None:
        return self._model_load_time

    def is_model_loaded(self) -> bool:
        return self._model is not None