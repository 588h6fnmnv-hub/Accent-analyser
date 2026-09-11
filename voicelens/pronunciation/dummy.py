"""VoiceLens Pronunciation Dummy Backend."""

from pathlib import Path

from voicelens.pronunciation.backend import PronunciationBackend, PronunciationResult


class DummyBackend(PronunciationBackend):
    """Placeholder pronunciation assessment backend returning structured defaults."""

    def analyze(self, _audio_path: str | Path, _transcript: str) -> PronunciationResult:
        """Returns placeholder pronunciation assessment results.

        Args:
            _audio_path: Path to the recorded audio file.
            _transcript: Expected text transcription.

        Returns:
            PronunciationResult: Default placeholder results.
        """
        return PronunciationResult(
            overall_score=85.0,
            pronunciation_similarity=0.88,
            confidence=0.92,
            backend="dummy",
            notes=["Placeholder pronunciation assessment succeeded."],
        )
