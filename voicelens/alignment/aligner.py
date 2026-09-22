"""VoiceLens Forced Alignment and Word/Phoneme Timing Extraction."""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from voicelens.transcriber import Transcriber


@dataclass
class PhonemeAlignment:
    """Dataclass holding phonetic level timing alignment."""

    phoneme: str
    start_time: float
    end_time: float


@dataclass
class WordAlignment:
    """Dataclass holding word level timing alignment."""

    word: str
    start_time: float
    end_time: float
    confidence: float
    phonemes: list[PhonemeAlignment]


@dataclass
class AlignmentResult:
    """Dataclass holding full forced alignment results."""

    words: list[WordAlignment]
    notes: list[str]


def convert_word_to_phonemes(word: str) -> list[str]:
    """Helper to convert a grapheme word to basic phonetic representation."""
    cleaned = re_clean_word(word)
    if not cleaned:
        return []

    # Map English letters to basic Arpabet phonemes
    g2p_map = {
        "ch": "CH",
        "sh": "SH",
        "th": "TH",
        "ph": "F",
        "ee": "IY",
        "oo": "UW",
        "ea": "IY",
        "ou": "AW",
        "ow": "AW",
        "ae": "EY",
        "ai": "EY",
        "ay": "EY",
        "oy": "OY",
        "oi": "OY",
        "ck": "K",
    }

    phonemes = []
    i = 0
    w_len = len(cleaned)

    while i < w_len:
        # Check two-character digraphs
        if i < w_len - 1 and cleaned[i : i + 2] in g2p_map:
            phonemes.append(g2p_map[cleaned[i : i + 2]])
            i += 2
        else:
            char = cleaned[i]
            # Simple consonant and vowel mappings
            if char in "aeiouy":
                phonemes.append(char.upper() + "V")  # Vowel placeholder
            else:
                phonemes.append(char.upper() + "C")  # Consonant placeholder
            i += 1

    return phonemes


def re_clean_word(word: str) -> str:
    """Removes punctuation and returns lowercase alphabetic characters."""
    return re.sub(r"[^a-zA-Z]", "", word).lower()


class WhisperAligner:
    """Forced Aligner using Whisper word-level timestamps and phonetic fallbacks."""

    def __init__(self, transcriber: Transcriber | None = None) -> None:
        """Initializes the WhisperAligner with a transcriber backend."""
        self.transcriber = transcriber or Transcriber()
        self._logger = logging.getLogger(__name__)

    def align(self, audio_path: str | Path, transcript: str) -> AlignmentResult:
        """Runs word-level forced alignment and extracts timing information.

        Only words present in the user transcript (ignoring case/punctuation)
        are aligned. Hallucinated words are filtered out.

        Args:
            audio_path: Path to the recorded audio file.
            transcript: Transcribed reference text.

        Returns:
            AlignmentResult: Word and phoneme alignment timings.
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file does not exist: {path}")

        # Basic input validation
        if not transcript.strip():
            return AlignmentResult(words=[], notes=["Empty transcript provided."])

        # Extract and normalize valid words from the original transcript
        transcript_words = set()
        for word_candidate in re.findall(r"[a-zA-Z']+", transcript):
            cleaned = re_clean_word(word_candidate)
            if cleaned:
                transcript_words.add(cleaned)

        # Use transcriber's transcribe_with_timestamps to get word-level timestamps
        # This avoids re-running transcription and uses whisper.cpp's native timestamps
        try:
            _, word_timestamps = self.transcriber.transcribe_with_timestamps(path)
        except Exception as e:
            self._logger.warning(f"Failed to get timestamps from transcriber: {e}")
            return AlignmentResult(words=[], notes=[f"Timestamp extraction failed: {e}"])

        aligned_words = []

        for w in word_timestamps:
            word_str = w.get("word", "").strip()
            cleaned_word = re_clean_word(word_str)
            if not cleaned_word:
                continue

            # Eliminate any hallucinated tokens that do not exist in the transcript
            if cleaned_word not in transcript_words:
                continue

            # Produce estimated phoneme timings by distributing word duration
            phonemes = convert_word_to_phonemes(cleaned_word)
            phoneme_alignments = []
            num_phonemes = len(phonemes)

            start_time = w.get("start", 0.0)
            end_time = w.get("end", 0.0)
            duration = end_time - start_time

            if num_phonemes > 0 and duration > 0:
                phoneme_dur = duration / num_phonemes
                for idx, ph in enumerate(phonemes):
                    p_start = start_time + (idx * phoneme_dur)
                    p_end = p_start + phoneme_dur
                    phoneme_alignments.append(
                        PhonemeAlignment(
                            phoneme=ph,
                            start_time=round(p_start, 4),
                            end_time=round(p_end, 4),
                        )
                    )

            aligned_words.append(
                WordAlignment(
                    word=word_str,
                    start_time=round(start_time, 4),
                    end_time=round(end_time, 4),
                    # Explicitly bound confidence to 0.0 - 1.0
                    confidence=round(max(0.0, min(1.0, w.get("confidence", 0.5))), 4),
                    phonemes=phoneme_alignments,
                )
            )

        notes = [
            f"Successfully aligned {len(aligned_words)} words from audio.",
            "Phoneme alignment computed using G2P timing distributions.",
            "Timestamps from whisper.cpp transcription.",
        ]

        return AlignmentResult(words=aligned_words, notes=notes)