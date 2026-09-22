"""VoiceLens Speech Metrics Analyzer implementation."""

import re
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Lazy imports for heavy dependencies
_TORCH_AVAILABLE = False
_TORCHAUDIO_AVAILABLE = False
_NUMPY_AVAILABLE = False
torch: Any = None
torchaudio: Any = None
np: Any = None

try:
    import torch as _torch
    torch = _torch
    _TORCH_AVAILABLE = True
except Exception:
    pass

try:
    import torchaudio as _torchaudio
    torchaudio = _torchaudio
    _TORCHAUDIO_AVAILABLE = True
except Exception:
    pass

try:
    import numpy as _np
    np = _np
    _NUMPY_AVAILABLE = True
except Exception:
    pass


class SpeechMetricsAnalyzerError(Exception):
    """Exception raised for errors in SpeechMetricsAnalyzer execution."""

    pass


@dataclass
class SpeechMetrics:
    """Dataclass holding speaker and voice metrics."""

    duration_seconds: float
    word_count: int
    words_per_minute: float
    average_words_per_sentence: float
    pause_count: int
    average_pause_duration: float
    longest_pause: float
    filler_word_count: int
    filler_words: list[str]
    # New fields
    repeated_word_count: int
    repeated_words: list[str]
    fluency_score: float
    confidence_score: float
    syllable_count: int
    average_syllables_per_word: float
    sentence_count: int


class SpeechMetricsAnalyzer:
    """Analyzer for calculating voice, speaking rate, pauses, and speech patterns."""

    def __init__(self, silence_threshold_ratio: float = 0.02) -> None:
        """Initializes the SpeechMetricsAnalyzer.

        Args:
            silence_threshold_ratio: Amplitude threshold ratio relative to peak
                                     amplitude to classify a frame as silence.
                                     Defaults to 0.02.
        """
        if not _TORCH_AVAILABLE:
            raise SpeechMetricsAnalyzerError(
                "PyTorch is required for speech metrics analysis. "
                "Install with 'pip install torch'."
            )
        if not _NUMPY_AVAILABLE:
            raise SpeechMetricsAnalyzerError(
                "NumPy is required for speech metrics analysis. "
                "Install with 'pip install numpy'."
            )
        self.silence_threshold_ratio = silence_threshold_ratio

    def _load_audio_fallback(self, path: Path) -> tuple[torch.Tensor, int]:
        """Fallback WAV loader using standard library and numpy."""
        try:
            with wave.open(str(path), "rb") as wav_file:
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                sampwidth = wav_file.getsampwidth()
                n_frames = wav_file.getnframes()
                raw_data = wav_file.readframes(n_frames)

            if sampwidth == 2:  # 16-bit PCM
                data = np.frombuffer(raw_data, dtype=np.int16)
                data_float = data.astype(np.float32) / 32768.0
            elif sampwidth == 1:  # 8-bit unsigned PCM
                data = np.frombuffer(raw_data, dtype=np.uint8)
                data_float = (data.astype(np.float32) - 128.0) / 128.0
            elif sampwidth == 4:  # 32-bit PCM
                data = np.frombuffer(raw_data, dtype=np.int32)
                data_float = data.astype(np.float32) / 2147483648.0
            else:
                raise ValueError(f"Unsupported sample width: {sampwidth} bytes")

            if channels > 1:
                data_float = data_float.reshape(-1, channels).T
            else:
                data_float = data_float.reshape(1, -1)

            signal = torch.from_numpy(data_float)
            return signal, sample_rate
        except Exception as e:
            raise SpeechMetricsAnalyzerError(
                f"Failed to load WAV file '{path.name}': {e}"
            ) from e

    def _load_audio(self, path: Path) -> tuple[torch.Tensor, int]:
        """Loads WAV or audio file using torchaudio with standard library fallback."""
        if _TORCHAUDIO_AVAILABLE:
            try:
                # Use torchaudio as the primary loader to support diverse formats
                return torchaudio.load(str(path))
            except (ImportError, RuntimeError, Exception):
                # Graceful fallback for environments missing sound codecs (e.g. CI/test)
                pass
        return self._load_audio_fallback(path)

    def _estimate_pauses(
        self, signal: torch.Tensor, sample_rate: int
    ) -> tuple[int, float, float]:
        """Estimates pauses from silence in the audio signal.

        Uses adaptive thresholding based on signal statistics:
        - Ignore silence shorter than 150 ms (0.15s).
        - Consider silence longer than 400 ms (0.40s) as a pause.

        Returns:
            tuple[int, float, float]: (pause_count, avg_duration, longest_pause)
        """
        # Convert multi-channel signal to mono
        if signal.shape[0] > 1:
            signal = torch.mean(signal, dim=0, keepdim=True)

        signal_1d = signal.squeeze(0)
        total_samples = len(signal_1d)
        if total_samples == 0:
            return 0, 0.0, 0.0

        # Use adaptive threshold based on signal statistics
        # Use RMS as a more robust measure than peak
        rms = float(torch.sqrt(torch.mean(signal_1d ** 2)).item())
        # Also compute a noise floor estimate from the quietest 10% of frames
        frame_duration = 0.01
        frame_length = int(sample_rate * frame_duration)
        if frame_length == 0:
            return 0, 0.0, 0.0

        num_frames = total_samples // frame_length
        if num_frames == 0:
            return 0, 0.0, 0.0

        # Compute frame-wise RMS for adaptive thresholding
        reshaped = signal_1d[: num_frames * frame_length].view(num_frames, frame_length)
        frame_rms = torch.sqrt(torch.mean(reshaped ** 2, dim=1))
        
        # Estimate noise floor from quietest 10% of frames
        k = max(1, num_frames // 10)
        noise_floor = float(torch.kthvalue(frame_rms, k).values.item())
        signal_rms = float(torch.median(frame_rms).item())
        
        # Adaptive threshold: halfway between noise floor and signal level
        # with a minimum floor
        threshold = max(0.001, noise_floor + 0.3 * (signal_rms - noise_floor))

        # Compute frame-wise amplitudes for silence detection
        frame_amps = torch.mean(torch.abs(reshaped), dim=1)
        silent_frames = frame_amps < threshold

        # Segment continuous silent frames
        silent_runs = []
        current_run_length = 0

        for is_silent in silent_frames:
            if is_silent.item():
                current_run_length += 1
            else:
                if current_run_length > 0:
                    silent_runs.append(current_run_length)
                    current_run_length = 0
        if current_run_length > 0:
            silent_runs.append(current_run_length)

        # Convert run lengths to durations (seconds)
        silent_durations = [run * frame_duration for run in silent_runs]

        # Apply pause duration rules:
        # 1. Ignore silence shorter than 150 ms (0.15s) - likely articulation
        filtered_silences = [dur for dur in silent_durations if dur >= 0.15]

        # 2. Consider silence longer than 400 ms (0.40s) as a pause
        valid_pauses = [dur for dur in filtered_silences if dur >= 0.40]

        pause_count = len(valid_pauses)
        if pause_count > 0:
            average_pause_duration = sum(valid_pauses) / pause_count
            longest_pause = max(valid_pauses)
        else:
            average_pause_duration = 0.0
            longest_pause = 0.0

        return pause_count, round(average_pause_duration, 4), round(longest_pause, 4)

    def _count_syllables(self, word: str) -> int:
        """Estimate syllable count for a word using simple heuristic."""
        word = word.lower().strip(".,!?;:'\"()[]{}")
        if not word:
            return 0

        # Simple vowel-group counting heuristic
        vowels = "aeiouy"
        count = 0
        prev_is_vowel = False

        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_is_vowel:
                count += 1
            prev_is_vowel = is_vowel

        # Adjust for silent 'e' at end
        if word.endswith("e") and count > 1:
            count -= 1

        return max(1, count)

    def _detect_repeated_words(self, words: list[str]) -> tuple[int, list[str]]:
        """Detect repeated consecutive words (e.g., 'the the', 'and and')."""
        repeated = []
        for i in range(1, len(words)):
            if words[i].lower() == words[i - 1].lower():
                repeated.append(words[i])
        return len(repeated), repeated

    def _calculate_fluency_score(
        self,
        wpm: float,
        pause_count: int,
        filler_count: int,
        repeated_count: int,
        duration: float,
        word_count: int,
    ) -> float:
        """Calculate fluency score (0-100) based on multiple factors."""
        if word_count == 0 or duration == 0:
            return 0.0

        score = 100.0

        # Penalize speaking rate outside optimal range (110-160 WPM)
        if wpm < 110:
            score -= (110 - wpm) * 0.5
        elif wpm > 160:
            score -= (wpm - 160) * 0.3

        # Penalize pauses (per pause)
        score -= pause_count * 3.0

        # Penalize filler words (per filler)
        score -= filler_count * 2.0

        # Penalize repeated words
        score -= repeated_count * 5.0

        # Bonus for natural pace
        if 130 <= wpm <= 150:
            score += 5.0

        return max(0.0, min(100.0, round(score, 1)))

    def _calculate_confidence_score(
        self,
        transcript: str,
        duration: float,
        word_count: int,
        avg_pause: float,
    ) -> float:
        """Calculate confidence score based on speech characteristics."""
        if word_count == 0:
            return 0.0

        score = 50.0  # Base score

        # Longer utterances with more words = more confident
        if word_count > 20:
            score += 10.0
        elif word_count > 10:
            score += 5.0

        # Fewer pauses = more confident
        if avg_pause < 0.3:
            score += 10.0
        elif avg_pause < 0.5:
            score += 5.0

        # Steady speech rate
        if duration > 0:
            wps = word_count / duration
            if 2.0 <= wps <= 3.0:  # 2-3 words per second is natural
                score += 10.0

        # Transcript coherence (has punctuation structure)
        sentences = [s.strip() for s in re.split(r"[.!?]+", transcript) if s.strip()]
        if len(sentences) > 1:
            score += 5.0

        return max(0.0, min(100.0, round(score, 1)))

    def analyze(
        self,
        audio_path: str | Path,
        transcript: str,
        segment_confidences: list[float] | None = None,
    ) -> SpeechMetrics:
        """Analyzes speech metrics from audio file and corresponding transcript.

        Args:
            audio_path: Path to the recorded audio file.
            transcript: Transcribed text of the speech.
            segment_confidences: Optional list of confidence scores from transcription.

        Returns:
            SpeechMetrics: Structured computed metrics.

        Raises:
            SpeechMetricsAnalyzerError: If validation or audio processing fails.
        """
        path = Path(audio_path)
        if not path.exists():
            raise SpeechMetricsAnalyzerError(
                f"Audio file does not exist: {path.resolve()}"
            )

        # 1. Load audio and compute duration and pauses
        signal, sample_rate = self._load_audio(path)
        duration_seconds = float(signal.shape[1] / sample_rate)

        pauses = self._estimate_pauses(signal, sample_rate)
        pause_count, avg_pause, longest_pause = pauses

        # 2. Compute transcript-based metrics
        clean_transcript = transcript.strip()
        if not clean_transcript:
            return SpeechMetrics(
                duration_seconds=round(duration_seconds, 4),
                word_count=0,
                words_per_minute=0.0,
                average_words_per_sentence=0.0,
                pause_count=pause_count,
                average_pause_duration=avg_pause,
                longest_pause=longest_pause,
                filler_word_count=0,
                filler_words=[],
                repeated_word_count=0,
                repeated_words=[],
                fluency_score=0.0,
                confidence_score=0.0,
                syllable_count=0,
                average_syllables_per_word=0.0,
                sentence_count=0,
            )

        # Short recording protection: require minimum duration and word count for reliable metrics
        MIN_DURATION_FOR_METRICS = 3.0  # seconds
        MIN_WORDS_FOR_METRICS = 3
        
        words = clean_transcript.split()
        word_count = len(words)
        
        # Short recording protection: if too short or too few words, return limited metrics
        if duration_seconds < MIN_DURATION_FOR_METRICS or word_count < MIN_WORDS_FOR_METRICS:
            return SpeechMetrics(
                duration_seconds=round(duration_seconds, 4),
                word_count=word_count,
                words_per_minute=0.0,  # Not reliable for short recordings
                average_words_per_sentence=0.0,
                pause_count=pause_count,
                average_pause_duration=avg_pause,
                longest_pause=longest_pause,
                filler_word_count=0,
                filler_words=[],
                repeated_word_count=0,
                repeated_words=[],
                fluency_score=0.0,
                confidence_score=0.0,
                syllable_count=0,
                average_syllables_per_word=0.0,
                sentence_count=0,
            )

        # Words Per Minute
        words_per_minute = (
            (word_count / duration_seconds) * 60.0 if duration_seconds > 0 else 0.0
        )

        # Average words per sentence
        sentences = [
            s.strip() for s in re.split(r"[.!?]+", clean_transcript) if s.strip()
        ]
        sentence_count = len(sentences)
        if sentences:
            sentence_word_counts = [len(s.split()) for s in sentences]
            average_words_per_sentence = sum(sentence_word_counts) / len(sentences)
        else:
            average_words_per_sentence = float(word_count)
            sentence_count = 1  # At least one sentence

        # Syllable count
        syllable_count = sum(self._count_syllables(w) for w in words)
        average_syllables_per_word = (
            syllable_count / word_count if word_count > 0 else 0.0
        )

# Filler word count and list
        # Improved patterns: "well" only as filler at start of sentence or after punctuation
        # Added variants: hmm, hm, ums, hmms, uhs, erms, ahs
        # Also handle cases where fillers have trailing punctuation
        filler_patterns = [
            r"\bum\b",
            r"\buh\b",
            r"\berm\b",
            r"\bah\b",
            r"\blike\b",
            r"\byou\s+know\b",
            r"\bbasically\b",
            r"\bactually\b",
            r"\bso\b",
            r"(?:^|[,.!?])\s*(\bwell\b)(?=[\s,.!?]|$)",  # "well" at start or after punctuation (.,!?) - capture group
            r"\bright\b",
            r"\bI\s+mean\b",
            r"\byou\s+see\b",
            r"\bkind\s+of\b",
            r"\bsort\s+of\b",
            r"\bI\s+guess\b",
            r"\bI\s+think\b",
            r"\bI\b",  # Only as filler when used as hesitation
            r"\bjust\b",
            r"\breally\b",
            r"\bliterally\b",
            # Additional filler variants with flexible punctuation handling
            r"\bhmm+\b",      # hmm, hmmm, hmmmm
            r"\bhm+\b",       # hm, hmm
            r"\bums+\b",      # ums, umms
            r"\buhs+\b",      # uhs, uhs
            r"\berms+\b",     # erms, ermms
            r"\bahs+\b",      # ahs, ahhs
            # Fillers with trailing punctuation (e.g., "um,", "hmm.")
            r"\bum[.,!?]*\b",
            r"\buh[.,!?]*\b",
            r"\ber[m]+[.,!?]*\b",
            r"\bah[.,!?]*\b",
            r"\bhmm+[.,!?]*\b",
            r"\bhm+[.,!?]*\b",
        ]
        combined_pattern = re.compile("|".join(filler_patterns), re.IGNORECASE)
        # Find all matches in the transcript using finditer
        # For patterns with capture groups (like "well"), use group(1), otherwise group(0)
        raw_matches = []
        for m in combined_pattern.finditer(clean_transcript):
            if m.lastindex and m.lastindex > 0:
                # Has capture group, use group(1)
                raw_matches.append(m.group(1))
            else:
                # No capture group, use full match
                raw_matches.append(m.group(0))
        # Normalize to lowercase and handle multi-word space normalization
        filler_words = [re.sub(r"\s+", " ", m.lower()) for m in raw_matches]
        filler_word_count = len(filler_words)

        # Repeated word detection
        repeated_word_count, repeated_words = self._detect_repeated_words(words)

        # Fluency score
        fluency_score = self._calculate_fluency_score(
            wpm=words_per_minute,
            pause_count=pause_count,
            filler_count=filler_word_count,
            repeated_count=repeated_word_count,
            duration=duration_seconds,
            word_count=word_count,
        )

        # Confidence score
        confidence_score = self._calculate_confidence_score(
            transcript=clean_transcript,
            duration=duration_seconds,
            word_count=word_count,
            avg_pause=avg_pause,
        )

        return SpeechMetrics(
            duration_seconds=round(duration_seconds, 4),
            word_count=word_count,
            words_per_minute=round(words_per_minute, 4),
            average_words_per_sentence=round(average_words_per_sentence, 4),
            pause_count=pause_count,
            average_pause_duration=avg_pause,
            longest_pause=longest_pause,
            filler_word_count=filler_word_count,
            filler_words=filler_words,
            repeated_word_count=repeated_word_count,
            repeated_words=repeated_words,
            fluency_score=fluency_score,
            confidence_score=confidence_score,
            syllable_count=syllable_count,
            average_syllables_per_word=round(average_syllables_per_word, 4),
            sentence_count=sentence_count,
        )