"""VoiceLens Audio Recorder implementation."""

import threading
import wave
from pathlib import Path
from typing import Any

import numpy as np

# Lazy/safe import of sounddevice to avoid crash on import if PortAudio is missing
_SOUNDDEVICE_AVAILABLE = False
_SOUNDDEVICE_ERROR_MSG = ""
sd: Any = None

try:
    import sounddevice as _sd

    sd = _sd
    _SOUNDDEVICE_AVAILABLE = True
except Exception as e:
    _SOUNDDEVICE_ERROR_MSG = str(e)


class AudioRecorderError(Exception):
    """Base exception for all AudioRecorder errors."""

    pass


class AudioRecorder:
    """A thread-safe audio recorder that records audio using sounddevice."""

    def __init__(
        self,
        sample_rate: int = 44100,
        channels: int = 1,
        dtype: str = "float32",
    ) -> None:
        """Initializes the AudioRecorder with sample rate, channels, and data type."""
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self._stream: Any = None
        self._audio_data: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._recording = False

    @classmethod
    def check_system_availability(cls) -> None:
        """Helper to assert that sounddevice and input devices are available.

        Raises:
            AudioRecorderError: if PortAudio is missing or no input device exists.
        """
        if not _SOUNDDEVICE_AVAILABLE:
            msg = (
                f"Audio recording is unavailable: "
                f"{_SOUNDDEVICE_ERROR_MSG or 'sounddevice could not be imported'}. "
                f"Please make sure PortAudio is installed on your system."
            )
            raise AudioRecorderError(msg)
        try:
            devices = sd.query_devices()
            if not devices:
                raise AudioRecorderError("No audio input/output devices found.")
            # Check for at least one input device
            input_devices = [d for d in devices if d.get("max_input_channels", 0) > 0]
            if not input_devices:
                raise AudioRecorderError("No default microphone/input devices found.")
        except Exception as e:
            if not isinstance(e, AudioRecorderError):
                raise AudioRecorderError(
                    f"Failed to query system audio devices: {e}"
                ) from e
            raise

    def start_recording(self) -> None:
        """Starts a non-blocking audio recording stream.

        Raises:
            AudioRecorderError: if recorder is already running or
                                hardware is inaccessible.
        """
        self.check_system_availability()

        with self._lock:
            if self._recording:
                raise AudioRecorderError("Recording is already in progress.")

            self._audio_data = []
            self._recording = True

        def callback(
            indata: np.ndarray,
            _frames: int,
            _time_info: Any,
            status: Any,
        ) -> None:
            """Callback function invoked by sounddevice for incoming audio chunks."""
            if status:
                # We can handle status flags if needed, or ignore minor underflows
                pass
            with self._lock:
                if self._recording:
                    self._audio_data.append(indata.copy())

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                callback=callback,
            )
            self._stream.start()
        except Exception as e:
            with self._lock:
                self._recording = False
                self._stream = None
            raise AudioRecorderError(
                f"Could not open microphone/input stream. This may be due to "
                f"lack of microphone permissions or device in-use: {e}"
            ) from e

    def stop_recording(self) -> None:
        """Stops the recording stream."""
        with self._lock:
            if not self._recording:
                return
            self._recording = False

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                raise AudioRecorderError(f"Error stopping stream: {e}") from e
            finally:
                self._stream = None

    def get_duration(self) -> float:
        """Returns the current duration of the recorded audio in seconds."""
        with self._lock:
            if not self._audio_data:
                return 0.0
            # Calculate total frames recorded
            total_frames = sum(chunk.shape[0] for chunk in self._audio_data)
            return total_frames / self.sample_rate

    def save_wav(self, file_path: Path | str) -> None:
        """Saves the recorded buffer as a standard 16-bit PCM WAV file.

        Args:
            file_path: The file path to save the WAV file.

        Raises:
            AudioRecorderError: if no audio was recorded or WAV writing fails.
        """
        with self._lock:
            if not self._audio_data:
                raise AudioRecorderError("No audio data was recorded to save.")
            # Concatenate all numpy array blocks
            full_data = np.concatenate(self._audio_data, axis=0)

        # Convert float32 [-1.0, 1.0] to int16 [-32768, 32767]
        # First clip values to be safe
        clipped = np.clip(full_data, -1.0, 1.0)
        pcm_data = (clipped * 32767).astype(np.int16)

        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            with wave.open(str(path), "wb") as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(2)  # 2 bytes for 16-bit
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(pcm_data.tobytes())
        except Exception as e:
            raise AudioRecorderError(
                f"Failed to write recording to WAV file: {e}"
            ) from e
