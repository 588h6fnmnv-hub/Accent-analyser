"""VoiceLens Mispronunciation Detection."""

from dataclasses import dataclass

from voicelens.alignment.aligner import AlignmentResult


@dataclass
class MispronunciationResult:
    """Dataclass holding details for a likely mispronounced word."""

    word: str
    confidence: float
    score: float
    start_time: float
    end_time: float


class MispronunciationAnalyzer:
    """Detects likely mispronounced words using forced alignment and embeddings."""

    def __init__(self, threshold: float = 60.0) -> None:
        """Initializes the MispronunciationAnalyzer.

        Args:
            threshold: Scores below this threshold (0-100) are flagged.
        """
        self.threshold = threshold

    def detect(
        self, alignment: AlignmentResult, global_similarity: float
    ) -> list[MispronunciationResult]:
        """Identifies and returns words likely mispronounced, sorted worst first.

        Args:
            alignment: The forced alignment result containing word timings.
            global_similarity: Global pronunciation similarity factor (0.0 to 1.0).

        Returns:
            list[MispronunciationResult]: Sorted list of mispronounced words (lowest
                                         score first).
        """
        results = []

        for w in alignment.words:
            # Word-level score combining acoustic confidence and global similarity
            # Scale to 0-100 to make it readable
            word_score = round(w.confidence * global_similarity * 100.0, 2)
            word_score = max(0.0, min(100.0, word_score))

            # Add to results if it's below our threshold
            if word_score < self.threshold:
                results.append(
                    MispronunciationResult(
                        word=w.word,
                        confidence=round(w.confidence, 4),
                        score=word_score,
                        start_time=w.start_time,
                        end_time=w.end_time,
                    )
                )

        # Sort worst words first (by score ascending)
        results.sort(key=lambda x: x.score)
        return results


# Keep alias for backward compatibility with previous test code
MispronunciationDetector = MispronunciationAnalyzer
