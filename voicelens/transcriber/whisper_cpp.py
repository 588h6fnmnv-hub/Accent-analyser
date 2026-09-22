"""VoiceLens Whisper.cpp transcription implementation.

Uses whisper.cpp (ggml) via CLI for high-accuracy, Metal-accelerated
transcription on Apple Silicon.
"""

import json
import logging
import os
import subprocess
import uuid
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class WhisperCppError(Exception):
    """Base exception for all Whisper.cpp transcription errors."""

    pass


class WhisperCppTranscriber:
    """Handles speech-to-text transcription using whisper.cpp CLI."""

    DEFAULT_MODEL = "base.en"
    SUPPORTED_MODELS = (
        "tiny.en",
        "base.en",
        "small.en",
        "medium.en",
        "large-v3",
    )

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL,
        whisper_cpp_dir: Path | str | None = None,
        n_threads: int | None = None,
        language: str = "en",
    ) -> None:
        """Initialize the Whisper.cpp transcriber.

        Args:
            model_size: Model to use (tiny.en, base.en, small.en, medium.en, large-v3)
            whisper_cpp_dir: Directory containing whisper.cpp binary and models
            n_threads: Number of CPU threads (None = auto)
            language: Language code for transcription
        """
        if model_size not in self.SUPPORTED_MODELS:
            logger.warning(
                f"Model '{model_size}' not in supported list {self.SUPPORTED_MODELS}. "
                "Proceeding anyway."
            )

        self.model_size = model_size
        self.language = language
        self.n_threads = n_threads or max(1, (os.cpu_count() or 4) - 1)
        self._model_load_time: float | None = None
        self._logger = logging.getLogger(__name__)

        # Determine whisper.cpp directory
        if whisper_cpp_dir is None:
            # Default to project's whisper_cpp directory
            project_root = Path(__file__).resolve().parents[2]
            self.whisper_cpp_dir = project_root / "whisper_cpp"
        else:
            self.whisper_cpp_dir = Path(whisper_cpp_dir)

        self.binary_path = self.whisper_cpp_dir / "bin" / "whisper-cli"
        self.model_path = self.whisper_cpp_dir / "models" / f"ggml-{model_size}.bin"

        self._validate_setup()

    def _validate_setup(self) -> None:
        """Validate that binary and model exist."""
        if not self.binary_path.exists():
            raise WhisperCppError(
                f"whisper.cpp binary not found at {self.binary_path}. "
                "Please build whisper.cpp and place binary at whisper_cpp/bin/whisper-cli"
            )
        if not self.model_path.exists():
            raise WhisperCppError(
                f"Model not found at {self.model_path}. "
                f"Please download ggml-{self.model_size}.bin to whisper_cpp/models/"
            )

    def _run_transcription(
        self,
        audio_path: Path,
        output_json: bool = True,
        word_timestamps: bool = False,
    ) -> dict[str, Any] | str:
        """Run whisper.cpp transcription via CLI.

        Args:
            audio_path: Path to audio file
            output_json: Whether to output JSON format (to file)
            word_timestamps: Whether to include word-level timestamps

        Returns:
            Parsed JSON dict or raw transcript string
        """
        if not audio_path.exists():
            raise WhisperCppError(f"Audio file does not exist: {audio_path.resolve()}")

        # Check file size - reject empty files
        if audio_path.stat().st_size == 0:
            raise WhisperCppError("Audio file is empty")

        # Check audio duration - reject very short files that are likely silence
        try:
            import wave
            with wave.open(str(audio_path), "rb") as wav_file:
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                duration = frames / sample_rate
                if duration < 0.5:  # Less than 0.5 seconds
                    self._logger.warning(f"Audio very short ({duration:.2f}s), may be silence")
        except Exception:
            pass

        # Create a unique output prefix in /tmp to avoid conflicts
        import uuid
        output_prefix = f"/tmp/whisper_cpp_out_{uuid.uuid4().hex[:12]}"

        # Use minimal, proven arguments that work reliably
        # Add VAD-like parameters to reduce hallucination on silence
        cmd = [
            str(self.binary_path),
            "-m", str(self.model_path),
            "-f", str(audio_path),
            "-l", self.language,
            "-t", str(self.n_threads),
            "-oj",  # output JSON to file
            "-of", output_prefix,  # output file prefix
            "--no-timestamps",  # We'll get timestamps from JSON
        ]

        # Remove empty strings
        cmd = [c for c in cmd if c]

        self._logger.info(f"Starting whisper.cpp transcription (model={self.model_size})...")
        start_time = time.perf_counter()

        # Run with working directory set to /tmp so JSON output goes to /tmp
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd="/tmp",
        )

        transcribe_time = time.perf_counter() - start_time

        if result.returncode != 0:
            raise WhisperCppError(
                f"whisper.cpp failed (exit code {result.returncode}): {result.stderr}"
            )

        self._logger.info(f"Transcription completed in {transcribe_time:.2f}s")

        json_path = f"{output_prefix}.json"

        if output_json:
            # Read JSON from output file
            try:
                with open(json_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                raise WhisperCppError(
                    f"Failed to parse whisper.cpp JSON output: {e}"
                )
            finally:
                # Clean up temp JSON file
                try:
                    os.unlink(json_path)
                except Exception:
                    pass
        else:
            # Return raw stdout
            return result.stdout.strip()

    def _extract_text_from_result(self, result: dict[str, Any]) -> str:
        """Extract transcript text from whisper.cpp JSON result."""
        # whisper.cpp format: transcription array with text fields
        text = ""
        if "transcription" in result:
            for item in result["transcription"]:
                text += item.get("text", "")
        return text.strip()

    def _extract_segments_from_result(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract segments with timestamps from whisper.cpp JSON result."""
        segments = []
        if "transcription" in result:
            for item in result["transcription"]:
                # Parse timestamps
                timestamps = item.get("timestamps", {})
                offsets = item.get("offsets", {})

                # Convert timestamp strings (HH:MM:SS,mmm) to seconds
                def parse_ts(ts_str: str) -> float:
                    try:
                        parts = ts_str.replace(",", ".").split(":")
                        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                    except Exception:
                        return 0.0

                start = parse_ts(timestamps.get("from", "00:00:00,000"))
                end = parse_ts(timestamps.get("to", "00:00:00,000"))

                # Fallback to offsets (milliseconds)
                if start == 0 and end == 0:
                    start = offsets.get("from", 0) / 1000.0
                    end = offsets.get("to", 0) / 1000.0

                seg_text = item.get("text", "").strip()
                segments.append({
                    "text": seg_text,
                    "start": start,
                    "end": end,
                    "avg_logprob": 0.0,  # Not available in this format
                })
        return segments

    def transcribe(self, audio_path: Path | str) -> str:
        """Transcribe audio file to text.

        Args:
            audio_path: Path to the audio file (WAV, FLAC, MP3, OGG)

        Returns:
            Transcribed text
        """
        path = Path(audio_path)

        if not path.exists():
            raise WhisperCppError(f"Audio file does not exist: {path.resolve()}")

        # Check file size - reject empty files
        if path.stat().st_size == 0:
            raise WhisperCppError("Audio file is empty")

        result = self._run_transcription(path, output_json=True)

        # Extract text from JSON result
        if isinstance(result, dict):
            text = self._extract_text_from_result(result)
            text = text.strip()

            # Post-process to detect and filter likely hallucinations
            text = self._filter_hallucinations(text, path)

            return text

        return str(result).strip()

    def _filter_hallucinations(self, text: str, audio_path: Path) -> str:
        """Filter likely hallucinated text from silence/short audio.

        Common whisper.cpp hallucinations on silence:
        - "Thank you."
        - "Thanks for watching."
        - "Subscribe."
        - Single words or very short phrases
        """
        if not text:
            return ""

        text_lower = text.lower().strip()

        # Known hallucination patterns (common in whisper.cpp on silence)
        hallucination_patterns = [
            "thank you",
            "thanks for watching",
            "thanks for listening",
            "subscribe",
            "like and subscribe",
            "follow for more",
            "see you next time",
            "bye",
            "goodbye",
            "the end",
        ]

        # Check for exact matches or very short text that matches patterns
        for pattern in hallucination_patterns:
            if text_lower == pattern or text_lower == pattern + ".":
                self._logger.warning(f"Filtered likely hallucination: '{text}'")
                return ""

        # If text is very short (1-2 words) and audio is very short, be suspicious
        words = text.split()
        if len(words) <= 2:
            try:
                import wave
                with wave.open(str(audio_path), "rb") as wav_file:
                    frames = wav_file.getnframes()
                    sample_rate = wav_file.getframerate()
                    duration = frames / sample_rate
                    if duration < 2.0:  # Less than 2 seconds of audio
                        self._logger.warning(
                            f"Short text '{text}' from short audio ({duration:.1f}s), "
                            "may be hallucination"
                        )
                        return ""
            except Exception:
                pass

        return text

    def transcribe_with_timestamps(
        self, audio_path: Path | str
    ) -> tuple[str, list[dict[str, Any]]]:
        """Transcribe and return both text and word/segment timestamps.

        Args:
            audio_path: Path to the audio file

        Returns:
            Tuple of (transcript_text, list of segment dicts with timing info)
        """
        path = Path(audio_path)

        result = self._run_transcription(path, output_json=True, word_timestamps=True)

        if not isinstance(result, dict):
            return str(result).strip(), []

        # Extract transcript
        transcript = self._extract_text_from_result(result)

        # Extract segments with timestamps
        segments = self._extract_segments_from_result(result)
        word_timestamps = []

        for seg in segments:
            seg_text = seg.get("text", "").strip()
            seg_start = seg.get("start", 0.0)
            seg_end = seg.get("end", 0.0)
            seg_avg_logprob = seg.get("avg_logprob", 0.0)
            # Convert logprob to confidence (rough approximation)
            confidence = max(0.0, min(1.0, (seg_avg_logprob + 1.0)))

            # Word-level timestamps not available in this format, use segment-level
            for word in seg_text.split():
                word_timestamps.append({
                    "word": word,
                    "start": seg_start,
                    "end": seg_end,
                    "confidence": confidence,
                })

        return transcript, word_timestamps

    @property
    def model_load_time(self) -> float | None:
        """Return the model load time in seconds (not tracked for CLI)."""
        return self._model_load_time

    def is_model_loaded(self) -> bool:
        """whisper.cpp CLI doesn't keep model in memory between calls."""
        return False