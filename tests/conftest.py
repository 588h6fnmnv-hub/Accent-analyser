"""Test configuration and fixtures for VoiceLens."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir() -> Path:
    """Provide a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def sample_wav_path(temp_dir: Path) -> Path:
    """Create a minimal valid WAV file for testing."""
    import wave

    wav_path = temp_dir / "test.wav"
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 16000)  # 1 second of silence
    return wav_path