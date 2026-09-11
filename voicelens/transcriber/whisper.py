"""VoiceLens Whisper transcription implementation."""

from pathlib import Path
from typing import Any

from faster_whisper import WhisperModel


class WhisperTranscriberError(Exception):
    """Base exception for all Whisper transcription errors."""
    pass


class WhisperTranscriber:
    """Handles speech-to-text transcription using faster-whisper."""

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "int8",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model: Any = None

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            try:
                print(f"Loading Whisper model ({self.model_size})...")

                self._model = WhisperModel(
                    model_size_or_path=self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )

                print("✓ Whisper model loaded.")

            except Exception as e:
                raise WhisperTranscriberError(
                    f"Failed to load Whisper model '{self.model_size}': {e}"
                ) from e

        return self._model

    def transcribe(self, audio_path: Path | str) -> str:
        path = Path(audio_path)

        if not path.exists():
            raise WhisperTranscriberError(
                f"Audio file does not exist: {path.resolve()}"
            )

        model = self._get_model()

        try:
            print("Starting transcription...")

            segments, _info = model.transcribe(
                str(path),
                language="en",
                beam_size=5,
                best_of=5,
                vad_filter=True,
                vad_parameters={
                    "min_silence_duration_ms": 300,
                    "speech_pad_ms": 200,
                },
                condition_on_previous_text=False,
                initial_prompt=(
                    "This recording is spoken in English. "
                    "The speaker's name may be Shalin Muhammed. "
                    "The speaker may mention Kerala, India, Malayalam, VoiceLens. "
                    "Transcribe exactly what is spoken."
                ),
            )

            transcript = " ".join(
                segment.text.strip() for segment in segments
            ).strip()

            corrections = {
                "Shah Al-Muhad": "Shalin Muhammed",
                "Shah Al Muhad": "Shalin Muhammed",
                "Sha Al Muhad": "Shalin Muhammed",
                "Shalim Muhammad": "Shalin Muhammed",
                "Shalin Mohammed": "Shalin Muhammed",
            }

            for wrong, correct in corrections.items():
                transcript = transcript.replace(wrong, correct)

            print("✓ Transcription complete.")

            return transcript

        except Exception as e:
            raise WhisperTranscriberError(
                f"Error during Whisper transcription: {e}"
            ) from e