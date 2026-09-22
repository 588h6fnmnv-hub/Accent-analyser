"""Main entrypoint for the VoiceLens package, supporting `python -m voicelens`."""

import sys
from voicelens.cli import app

if __name__ == "__main__":
    # If no arguments provided, launch TUI
    if len(sys.argv) == 1:
        from voicelens.tui.app import run_tui
        run_tui()
    else:
        app()