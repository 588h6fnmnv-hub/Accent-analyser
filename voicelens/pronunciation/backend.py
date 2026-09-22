"""VoiceLens Pronunciation Backend Interface and Data Structures."""

import abc
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PronunciationResult:
    """Dataclass holding pronunciation assessment results."""

    overall_score: float
    pronunciation_similarity: float
    confidence: float
    backend: str
    notes: list[str]


class PronunciationBackend(abc.ABC):
    """Abstract base class for pronunciation assessment backends."""

    @abc.abstractmethod
    def analyze(self, audio_path: str | Path, transcript: str) -> PronunciationResult:
        """Analyzes pronunciation of the audio relative to the transcript.

        Args:
            audio_path: Path to the recorded audio file.
            transcript: Expected text transcription of the spoken audio.

        Returns:
            PronunciationResult: Structured pronunciation assessment results.
        """
        pass
