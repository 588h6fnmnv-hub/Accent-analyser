"""VoiceLens: A production-ready open-source Python CLI for audio and voice analysis."""

import os

# Disable tqdm multiprocessing lock to avoid "bad value(s) in fds_to_keep" error
# on macOS when running in certain thread/async contexts (e.g., Textual TUI)
# Must be set before tqdm is imported (by huggingface_hub -> faster_whisper)
os.environ.setdefault("TQDM_DISABLE", "1")

from voicelens.logging_config import setup_logging

setup_logging()

__version__ = "0.1.0"