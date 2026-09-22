"""VoiceLens TUI - Main Application"""

import sys
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Header,
    Footer,
    Static,
    Button,
    DataTable,
    ProgressBar,
    RichLog,
    Tabs,
    TabPane,
)
from textual.screen import Screen
from textual.reactive import reactive
from textual.message import Message
from textual.events import Key
from rich.text import Text
from rich.console import Console

from voicelens import __version__
from voicelens.recorder.audio import AudioRecorder, AudioRecorderError
from voicelens.transcriber import Transcriber, TranscriberError
from voicelens.pipeline import run_voicelens_pipeline
from voicelens.tui.screens import (
    RecordingScreen,
    AnalyzingScreen,
    ResultsScreen,
    SettingsScreen,
    DoctorScreen,
    ModelsScreen,
)
from voicelens.tui.config import Config


class VoiceLensApp(App):
    """Main VoiceLens Terminal Application."""

    TITLE = "VoiceLens"
    SUB_TITLE = "Accent & Speech Intelligence"
    CSS_PATH = "app.css"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("enter", "record", "Record", show=True),
        Binding("d", "doctor", "Doctor", show=True),
        Binding("s", "settings", "Settings", show=True),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("escape", "back", "Back", show=False),
    ]

    config = reactive(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = Config()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static(id="main-content"),
            id="main-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app and show home screen."""
        self.title = "VoiceLens"
        self.sub_title = "Accent & Speech Intelligence"
        self.show_home_screen()

    def show_home_screen(self) -> None:
        """Display the home screen."""
        content = self.query_one("#main-content", Static)
        content.update(self._build_home_screen())

    def _build_home_screen(self) -> Text:
        """Build the home screen display."""
        # Check system status
        mic_status = self._check_microphone()
        model_status = self._check_model()

        text = Text()
        text.append("\n")

        # Title bar
        text.append("╭──────────────────────────────────────────────────────────────╮\n", style="dim")
        text.append("│ ", style="dim")
        text.append("VOICELENS", style="bold")
        text.append("                                  ", style="dim")
        text.append("● LOCAL   ", style="green")
        text.append(" │\n", style="dim")
        text.append("│ ", style="dim")
        text.append("Accent & Speech Intelligence", style="dim")
        text.append("                                 │\n", style="dim")
        text.append("╰──────────────────────────────────────────────────────────────╯\n\n", style="dim")

        # Status
        text.append("  Ready to analyze your voice.\n\n")

        # Action box
        text.append("  ┌──────────────────────────────────────────────────────────────┐\n", style="dim")
        text.append("│                                                              │\n", style="dim")
        text.append("│                         ", style="dim")
        text.append("ENTER", style="bold")
        text.append("                              │\n", style="dim")
        text.append("│                   Start Recording                            │\n", style="dim")
        text.append("│                                                              │\n", style="dim")
        text.append("└──────────────────────────────────────────────────────────────┘\n\n", style="dim")

        # Status panel
        text.append("  ┌─ SYSTEM ────────────────────────────────────────────────────┐\n", style="dim")
        
        status_items = [
            ("Whisper", model_status, "green" if "READY" in model_status else "yellow"),
            ("SpeechBrain", "READY", "green"),
            ("Microphone", mic_status, "green" if "READY" in mic_status else "yellow"),
        ]

        for label, value, color in status_items:
            text.append("  │ ", style="dim")
            text.append(f"{label}: ", style="dim")
            text.append(f"{value}\n", style=color)

        text.append("  └──────────────────────────────────────────────────────────────┘\n\n", style="dim")

        # Help text
        text.append("  Enter  Record    H  History    D  Doctor    S  Settings    Q  Quit", style="dim")

        return text

    def _check_microphone(self) -> str:
        """Check microphone availability."""
        try:
            recorder = AudioRecorder()
            recorder.check_system_availability()
            return "READY"
        except AudioRecorderError:
            return "UNAVAILABLE"

    def _check_model(self) -> str:
        """Check transcription model availability."""
        model_path = Path(__file__).resolve().parents[2] / "whisper_cpp" / "models" / "ggml-base.en.bin"
        if model_path.exists():
            return "READY (base.en)"
        return "NOT FOUND"

    def action_record(self) -> None:
        """Start recording workflow."""
        self.push_screen(RecordingScreen(on_complete=self.on_recording_complete))

    def action_settings(self) -> None:
        """Show settings screen."""
        self.push_screen(SettingsScreen(config=self.config))

    def action_doctor(self) -> None:
        """Run system diagnostics."""
        self.push_screen(DoctorScreen())

    def on_recording_complete(self, audio_path: Path) -> None:
        """Handle completed recording - automatically start analysis."""
        self.run_analysis(audio_path)

    def run_analysis(self, audio_path: Path) -> None:
        """Run the full analysis pipeline."""
        analyzing_screen = AnalyzingScreen(audio_path=audio_path, on_complete=self.on_analysis_complete)
        self.push_screen(analyzing_screen)

    def on_analysis_complete(self, result: dict) -> None:
        """Handle completed pipeline - show results."""
        # Generate a simple ID for the result (no persistent storage)
        import uuid
        from datetime import datetime, UTC
        analysis_id = f"vl-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"

        # Show results (no persistent storage)
        self.push_screen(ResultsScreen(result=result, analysis_id=analysis_id, storage=None))

    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()

    def action_back(self) -> None:
        """Go back to previous screen."""
        if len(self.screen_stack) > 1:
            self.pop_screen()
        else:
            self.exit()


def run_tui() -> None:
    """Entry point for the TUI application."""
    app = VoiceLensApp()
    app.run()