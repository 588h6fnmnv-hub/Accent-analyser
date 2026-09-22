"""VoiceLens Transcription package."""

import logging
from pathlib import Path
from typing import Any

from voicelens.transcriber.whisper_cpp import WhisperCppTranscriber, WhisperCppError
from voicelens.transcriber.whisper import WhisperTranscriber, WhisperTranscriberError

logger = logging.getLogger(__name__)


class Transcriber:
    """Unified transcriber that tries whisper.cpp first, falls back to faster-whisper."""

    def __init__(
        self,
        model_size: str = "base",
        whisper_cpp_dir: Path | str | None = None,
        n_threads: int | None = None,
        language: str = "en",
    ) -> None:
        self.model_size = model_size
        self.language = language
        self._backend: Any = None
        self._backend_name: str = ""
        self._whisper_cpp_args = {
            "model_size": model_size if not model_size.endswith(".en") else model_size,
            "whisper_cpp_dir": whisper_cpp_dir,
            "n_threads": n_threads,
            "language": language,
        }
        self._faster_whisper_args = {
            "model_size": model_size,
        }
        self._whisper_cpp_failed = False

    def _get_whisper_cpp_backend(self) -> WhisperCppTranscriber:
        cpp_model = self._whisper_cpp_args["model_size"]
        if cpp_model in ("base", "small", "medium") and not cpp_model.endswith(".en"):
            cpp_model = f"{cpp_model}.en"
        return WhisperCppTranscriber(
            model_size=cpp_model,
            whisper_cpp_dir=self._whisper_cpp_args["whisper_cpp_dir"],
            n_threads=self._whisper_cpp_args["n_threads"],
            language=self._whisper_cpp_args["language"],
        )

    def _get_faster_whisper_backend(self) -> WhisperTranscriber:
        return WhisperTranscriber(model_size=self._faster_whisper_args["model_size"])

    def _try_transcribe(self, method_name: str, audio_path: Path | str, *args, **kwargs) -> Any:
        """Try transcription with fallback on failure."""
        # Try whisper.cpp first (if not already failed)
        if not self._whisper_cpp_failed:
            try:
                backend = self._get_whisper_cpp_backend()
                method = getattr(backend, method_name)
                result = method(audio_path, *args, **kwargs)
                self._backend = backend
                self._backend_name = "whisper.cpp"
                logger.info("Using whisper.cpp backend for transcription")
                return result
            except Exception as e:
                logger.warning(f"whisper.cpp {method_name} failed: {e}")
                self._whisper_cpp_failed = True

        # Fall back to faster-whisper
        try:
            backend = self._get_faster_whisper_backend()
            method = getattr(backend, method_name)
            result = method(audio_path, *args, **kwargs)
            self._backend = backend
            self._backend_name = "faster-whisper"
            logger.info("Using faster-whisper backend for transcription")
            return result
        except Exception as e:
            logger.error(f"faster-whisper {method_name} failed: {e}")
            raise TranscriberError(f"All transcription backends failed: {e}") from e

    def transcribe(self, audio_path: Path | str) -> str:
        return self._try_transcribe("transcribe", audio_path)

    def transcribe_with_timestamps(self, audio_path: Path | str) -> tuple[str, list[dict[str, Any]]]:
        return self._try_transcribe("transcribe_with_timestamps", audio_path)

    @property
    def model_load_time(self) -> float | None:
        if self._backend is not None:
            return getattr(self._backend, "model_load_time", None)
        return None

    def is_model_loaded(self) -> bool:
        if self._backend is not None:
            return getattr(self._backend, "is_model_loaded", lambda: False)()
        return False


TranscriberError = WhisperCppError

# Explicit exports
FasterWhisperTranscriber = WhisperTranscriber
FasterWhisperTranscriberError = WhisperTranscriberError
WhisperCppTranscriber = WhisperCppTranscriber
WhisperCppError = WhisperCppError
WhisperTranscriber = WhisperTranscriber
WhisperTranscriberError = WhisperTranscriberError

__all__ = [
    "Transcriber",
    "TranscriberError",
    "FasterWhisperTranscriber",
    "FasterWhisperTranscriberError",
    "WhisperCppTranscriber",
    "WhisperCppError",
    "WhisperTranscriber",
    "WhisperTranscriberError",
]