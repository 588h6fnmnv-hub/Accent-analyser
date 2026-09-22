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
    # Additional diagnostic info
    duration: float = 0.0
    phoneme_count: int = 0


class MispronunciationAnalyzer:
    """Detects likely mispronounced words using forced alignment and embeddings."""

    def __init__(self, threshold: float = 50.0) -> None:
        """Initializes the MispronunciationAnalyzer.

        Args:
            threshold: Scores below this threshold (0-100) are flagged.
                       Lowered from 60 to 50 to reduce false negatives.
        """
        self.threshold = threshold

    def _estimate_phoneme_count(self, word: str) -> int:
        """Estimate number of phonemes in a word using simple heuristic."""
        word = word.lower().strip(".,!?;:'\"()[]{}")
        if not word:
            return 0
        
        # Simple vowel group counting as rough phoneme estimate
        vowels = "aeiouy"
        count = 0
        prev_is_vowel = False
        
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_is_vowel:
                count += 1
            prev_is_vowel = is_vowel
        
        # Add consonant clusters
        # Common consonant clusters that add phonemes
        clusters = ["ch", "sh", "th", "ph", "wh", "ck", "ng", "qu", "ts", "dg"]
        for cluster in clusters:
            if cluster in word:
                count += 1
        
        return max(1, count)

    def _compute_word_difficulty(self, word: str, duration: float, confidence: float) -> float:
        """Compute expected difficulty of a word based on linguistic features."""
        word_clean = word.lower().strip(".,!?;:'\"()[]{}")
        if not word_clean:
            return 50.0  # Neutral difficulty
        
        # Base difficulty from word length and complexity
        length = len(word_clean)
        phoneme_estimate = self._estimate_phoneme_count(word_clean)
        
        # Longer words with more phonemes are harder
        base_difficulty = min(100.0, 20.0 + length * 2.0 + phoneme_estimate * 1.5)
        
        # Adjust for common difficult patterns
        difficult_patterns = ["th", "ch", "sh", "ph", "ough", "ght", "sch", "tch", "dge"]
        for pattern in difficult_patterns:
            if pattern in word_clean.lower():
                base_difficulty += 5.0
        
        # Duration factor: very short duration for a complex word suggests mispronunciation
        if duration > 0 and phoneme_estimate > 0:
            expected_duration_per_phoneme = 0.08  # ~80ms per phoneme
            expected_duration = phoneme_estimate * expected_duration_per_phoneme
            if duration < expected_duration * 0.5:  # Less than half expected
                base_difficulty += 15.0
            elif duration > expected_duration * 2.0:  # More than double expected
                base_difficulty += 10.0
        
        return min(100.0, base_difficulty)

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
            word_str = w.word
            confidence = w.confidence
            start_time = w.start_time
            end_time = w.end_time
            duration = end_time - start_time
            phoneme_count = len(w.phonemes)
            
            # Compute word-level score combining multiple factors:
            # 1. Acoustic confidence (how well the audio matches the expected word)
            # 2. Global similarity (overall pronunciation quality)
            # 3. Expected difficulty of the word
            # 4. Duration appropriateness
            
            # Expected difficulty of this word
            expected_difficulty = self._compute_word_difficulty(word_str, duration, confidence)
            
            # Confidence component: higher confidence = better pronunciation
            confidence_component = confidence * 100
            
            # Global similarity component
            similarity_component = global_similarity * 100
            
            # Duration appropriateness (penalize too short/long)
            duration_score = 100.0
            if duration > 0:
                expected_per_phoneme = 0.08
                expected = max(0.1, phoneme_estimate * expected_per_phoneme) if (phoneme_estimate := self._estimate_phoneme_count(w.word)) > 0 else 0.5
                ratio = duration / expected
                if ratio < 0.5:
                    duration_score = max(0, 100 * (ratio / 0.5))
                elif ratio > 2.0:
                    duration_score = max(0, 100 * (2.0 / ratio))
            
            # Combine components with weights
            # Weight: confidence 30%, global similarity 30%, duration 20%, inverse difficulty 20%
            word_score = (
                0.30 * confidence_component +
                0.30 * similarity_component +
                0.20 * duration_score +
                0.20 * (100 - expected_difficulty)
            )
            word_score = max(0.0, min(100.0, round(word_score, 2)))

            # Add to results if it's below our threshold
            if word_score < self.threshold:
                results.append(
                    MispronunciationResult(
                        word=w.word,
                        confidence=round(confidence, 4),
                        score=word_score,
                        start_time=start_time,
                        end_time=end_time,
                        duration=duration,
                        phoneme_count=phoneme_count,
                    )
                )

        # Sort worst words first (by score ascending)
        results.sort(key=lambda x: x.score)
        return results


# Keep alias for backward compatibility with previous test code
MispronunciationDetector = MispronunciationAnalyzer