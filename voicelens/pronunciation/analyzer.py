"""VoiceLens Pronunciation Assessment Coordinator API."""

from pathlib import Path

from voicelens.pronunciation.backend import PronunciationBackend, PronunciationResult
from voicelens.pronunciation.dummy import DummyBackend


class PronunciationAnalyzerError(Exception):
    """Exception raised for errors in PronunciationAnalyzer execution."""

    pass


class PronunciationAnalyzer:
    """Coordinator class serving as the public API for pronunciation assessment."""

    def __init__(self, backend: PronunciationBackend | None = None) -> None:
        """Initializes the PronunciationAnalyzer coordinator.

        Args:
            backend: Swappable pronunciation assessment backend.
                     Defaults to DummyBackend.
        """
        self.backend = backend or DummyBackend()

    def analyze(self, audio_path: str | Path, transcript: str) -> PronunciationResult:
        """Coordinates and performs pronunciation assessment using the backend.

        Args:
            audio_path: Path to the spoken audio file.
            transcript: Expected text transcription of the spoken audio.

        Returns:
            PronunciationResult: Results containing score, confidence, and notes.

        Raises:
            PronunciationAnalyzerError: If validation fails or backend errors.
        """
        path = Path(audio_path)

        # Common input validation at the coordinator level to ensure robustness
        if not path.exists():
            raise PronunciationAnalyzerError(
                f"Audio file does not exist: {path.resolve()}"
            )

        if not transcript.strip():
            raise PronunciationAnalyzerError(
                "Cannot perform pronunciation assessment on an empty transcript."
            )

        try:
            return self.backend.analyze(path, transcript)
        except Exception as e:
            if isinstance(e, PronunciationAnalyzerError):
                raise
            backend_name = self.backend.__class__.__name__
            raise PronunciationAnalyzerError(
                f"Pronunciation assessment failed via backend '{backend_name}': {e}"
            ) from e
