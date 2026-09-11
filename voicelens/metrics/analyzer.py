"""VoiceLens Speech Metrics Analyzer implementation."""

import re
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import torchaudio


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


class SpeechMetricsAnalyzer:
    """Analyzer for calculating voice, speaking rate, pauses, and speech patterns."""

    def __init__(self, silence_threshold_ratio: float = 0.02) -> None:
        """Initializes the SpeechMetricsAnalyzer.

        Args:
            silence_threshold_ratio: Amplitude threshold ratio relative to peak
                                     amplitude to classify a frame as silence.
                                     Defaults to 0.02.
        """
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
        try:
            # Use torchaudio as the primary loader to support diverse formats
            return torchaudio.load(str(path))
        except (ImportError, RuntimeError, Exception):
            # Graceful fallback for environments missing sound codecs (e.g. CI/test)
            return self._load_audio_fallback(path)

    def _estimate_pauses(
        self, signal: torch.Tensor, sample_rate: int
    ) -> tuple[int, float, float]:
        """Estimates pauses from silence in the audio signal.

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

        # Peak absolute amplitude for scale-invariant threshold
        peak_amp = float(torch.max(torch.abs(signal_1d)).item())
        threshold = max(0.002, self.silence_threshold_ratio * peak_amp)

        # 10 ms frame duration
        frame_duration = 0.01
        frame_length = int(sample_rate * frame_duration)
        if frame_length == 0:
            return 0, 0.0, 0.0

        num_frames = total_samples // frame_length
        if num_frames == 0:
            return 0, 0.0, 0.0

        # Compute average absolute amplitude for each frame
        reshaped = signal_1d[: num_frames * frame_length].view(num_frames, frame_length)
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
        # 1. Ignore silence shorter than 150 ms (0.15s)
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

    def analyze(self, audio_path: str | Path, transcript: str) -> SpeechMetrics:
        """Analyzes speech metrics from audio file and corresponding transcript.

        Args:
            audio_path: Path to the recorded audio file.
            transcript: Transcribed text of the speech.

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
            )

        # Word count
        words = clean_transcript.split()
        word_count = len(words)

        # Words Per Minute
        words_per_minute = (
            (word_count / duration_seconds) * 60.0 if duration_seconds > 0 else 0.0
        )

        # Average words per sentence
        # Split by typical sentence punctuation: . ? !
        sentences = [
            s.strip() for s in re.split(r"[.!?]+", clean_transcript) if s.strip()
        ]
        if sentences:
            sentence_word_counts = [len(s.split()) for s in sentences]
            average_words_per_sentence = sum(sentence_word_counts) / len(sentences)
        else:
            average_words_per_sentence = float(word_count)

        # Filler word count and list
        filler_patterns = [
            r"\bum\b",
            r"\buh\b",
            r"\berm\b",
            r"\bah\b",
            r"\blike\b",
            r"\byou\s+know\b",
            r"\bbasically\b",
            r"\bactually\b",
        ]
        combined_pattern = re.compile("|".join(filler_patterns), re.IGNORECASE)
        # Find all matches in the transcript
        raw_matches = combined_pattern.findall(clean_transcript)
        # Normalize to lowercase and handle multi-word space normalization
        filler_words = [re.sub(r"\s+", " ", m.lower()) for m in raw_matches]
        filler_word_count = len(filler_words)

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
        )
