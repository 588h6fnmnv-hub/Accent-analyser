"""VoiceLens Audio Conversion Module using PyAV."""

import wave
from pathlib import Path

import av


class AudioConversionError(Exception):
    """Exception raised when audio decoding or conversion fails."""

    pass


def convert_to_wav(
    input_path: str | Path,
    output_path: str | Path,
    target_sample_rate: int = 16000,
) -> Path:
    """Converts an audio file (WEBM, MP3, etc.) to 16kHz mono 16-bit WAV.

    Args:
        input_path: Path to the input audio file.
        output_path: Path where the converted WAV file should be written.
        target_sample_rate: Target sample rate in Hz (default: 16000).

    Returns:
        Path: Path to the converted WAV file.

    Raises:
        FileNotFoundError: If input_path does not exist.
        AudioConversionError: If no audio stream is found or decoding fails.
    """
    in_p = Path(input_path)
    out_p = Path(output_path)

    if not in_p.exists():
        raise FileNotFoundError(f"Input audio file does not exist: {in_p}")

    try:
        with av.open(str(in_p)) as container:
            audio_stream = next(
                (s for s in container.streams if s.type == "audio"), None
            )
            if audio_stream is None:
                raise AudioConversionError(
                    f"No valid audio stream found in '{in_p.name}'."
                )

            resampler = av.AudioResampler(
                format="s16",
                layout="mono",
                rate=target_sample_rate,
            )

            pcm_chunks = []
            for frame in container.decode(audio_stream):
                resampled_frames = resampler.resample(frame)
                for rf in resampled_frames:
                    pcm_chunks.append(rf.to_ndarray().tobytes())

            # Flush any buffered frames in resampler
            flushed_frames = resampler.resample(None)
            for rf in flushed_frames:
                pcm_chunks.append(rf.to_ndarray().tobytes())

        pcm_data = b"".join(pcm_chunks)
        if len(pcm_data) == 0:
            raise AudioConversionError(
                f"Decoded audio stream in '{in_p.name}' produced zero PCM frames."
            )

        out_p.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(out_p), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(target_sample_rate)
            wav_file.writeframes(pcm_data)

        return out_p

    except AudioConversionError:
        raise
    except Exception as e:
        raise AudioConversionError(
            f"Failed to convert audio file '{in_p.name}' to WAV: {e}"
        ) from e
