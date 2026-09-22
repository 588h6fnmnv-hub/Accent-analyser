"""VoiceLens TUI Screens - Redesigned Flow"""

import asyncio
import queue
import threading
import time
import tempfile
import os
import atexit
from pathlib import Path
from typing import Callable, Optional
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Static,
    Button,
    Label,
    Input,
    ProgressBar,
    RichLog,
    DataTable,
    Tabs,
    TabPane,
)
from textual.reactive import reactive
from textual.message import Message
from textual.binding import Binding
from rich.text import Text

from voicelens.recorder.audio import AudioRecorder, AudioRecorderError
from voicelens.transcriber import Transcriber, TranscriberError
from voicelens.pipeline import run_voicelens_pipeline

# Global temp file tracker for cleanup
_temp_recording_file: Optional[Path] = None


def _cleanup_temp_recording(file_path: Optional[Path]) -> None:
    """Safely delete a temporary recording file."""
    if file_path and file_path.exists():
        try:
            file_path.unlink()
        except Exception:
            pass


def _register_temp_recording(file_path: Path) -> None:
    """Register a new temp recording and clean up the previous one."""
    global _temp_recording_file
    # Clean up previous temp recording
    _cleanup_temp_recording(_temp_recording_file)
    _temp_recording_file = file_path


def _cleanup_current_temp_recording() -> None:
    """Clean up the current temp recording."""
    global _temp_recording_file
    _cleanup_temp_recording(_temp_recording_file)
    _temp_recording_file = None


# Register cleanup on exit
atexit.register(_cleanup_current_temp_recording)


class RecordingScreen(Screen):
    """Screen for recording audio - ENTER starts immediately."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("enter", "toggle_recording", "Start/Stop", show=True),
    ]

    def __init__(self, on_complete: Callable[[Path], None], **kwargs):
        super().__init__(**kwargs)
        self.on_complete = on_complete
        self.recorder: Optional[AudioRecorder] = None
        self.recording = False
        self.start_time = 0.0
        self.timer_thread: Optional[threading.Thread] = None
        self.stop_timer = threading.Event()
        self.audio_level_thread: Optional[threading.Thread] = None
        self.stop_audio_level = threading.Event()
        self.current_level = 0
        self.waveform_chars = "▁▂▃▄▅▆▇█"
        self._temp_file: Optional[Path] = None

    def compose(self) -> ComposeResult:
        yield Container(
            Static(id="recording-header"),
            Static(id="recording-status"),
            Static(id="recording-waveform"),
            Static(id="recording-time"),
            Static(id="recording-help"),
            id="recording-container",
        )

    def on_mount(self) -> None:
        self.title = "VoiceLens / Recording"
        self.sub_title = ""
        # Clean up any previous temp recording before starting new one
        _cleanup_current_temp_recording()
        # Start recording immediately
        self.start_recording()

    def start_recording(self) -> None:
        """Start recording audio immediately."""
        try:
            self.recorder = AudioRecorder()
            self.recorder.check_system_availability()
            self.recorder.start_recording()
        except AudioRecorderError as e:
            self.notify(f"Recording error: {e}", severity="error")
            self.app.call_later(self.app.pop_screen)
            return

        self.recording = True
        self.start_time = time.time()
        self.stop_timer.clear()
        self.stop_audio_level.clear()

        # Update UI
        header = self.query_one("#recording-header", Static)
        header.update(Text.from_markup(
            "\n  VOICELENS / RECORDING\n"
        ))

        status = self.query_one("#recording-status", Static)
        status.update(Text.from_markup(
            "\n  [bold red]● RECORDING[/bold red]\n"
            "  Press [bold]ENTER[/bold] to stop\n"
        ))

        info = self.query_one("#recording-help", Static)
        # Get microphone name
        mic_name = "Default"
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = [d for d in devices if d.get("max_input_channels", 0) > 0]
            if input_devices:
                mic_name = input_devices[0]["name"][:30]
        except Exception:
            pass
        info.update(Text.from_markup(
            f"\n  Microphone: [dim]{mic_name}[/dim]    Sample Rate: [dim]16 kHz[/dim]\n"
        ))

        # Start timer thread
        self.timer_thread = threading.Thread(target=self._recording_timer, daemon=True)
        self.timer_thread.start()

        # Start audio level thread
        self.audio_level_thread = threading.Thread(target=self._update_audio_level, daemon=True)
        self.audio_level_thread.start()

    def action_toggle_recording(self) -> None:
        """Toggle recording state - ENTER stops recording."""
        if self.recording:
            self.stop_recording()

    def stop_recording(self) -> None:
        """Stop recording and save, then auto-transition to analysis."""
        if not self.recorder:
            return

        self.recording = False
        self.stop_timer.set()
        self.stop_audio_level.set()

        if self.timer_thread:
            self.timer_thread.join(timeout=1.0)
        if self.audio_level_thread:
            self.audio_level_thread.join(timeout=1.0)

        self.recorder.stop_recording()
        duration = self.recorder.get_duration()

        # Save to temp file
        temp_dir = Path(tempfile.gettempdir()) / "voicelens"
        temp_dir.mkdir(parents=True, exist_ok=True)
        output_path = temp_dir / f"recording_{int(time.time())}.wav"

        try:
            self.recorder.save_wav(output_path)
        except AudioRecorderError as e:
            self.notify(f"Failed to save recording: {e}", severity="error")
            self.app.call_later(self.app.pop_screen)
            return

        # Register this temp file for cleanup tracking
        _register_temp_recording(output_path)
        self._temp_file = output_path

        self.notify(f"Recording saved ({duration:.1f}s)")

        # Call completion callback - this will trigger analysis
        self.app.call_later(self.on_complete, output_path)
        self.app.pop_screen()

    def _recording_timer(self) -> None:
        """Update the timer display (recording duration)."""
        while not self.stop_timer.is_set():
            elapsed = time.time() - self.start_time
            mins = int(elapsed // 60)
            secs = elapsed % 60
            time_str = f"{mins:02d}:{secs:05.2f}"

            self.app.call_from_thread(self._update_timer_ui, time_str)
            time.sleep(0.05)

    def _update_timer_ui(self, time_str: str) -> None:
        """Update timer UI from main thread."""
        try:
            time_widget = self.query_one("#recording-time", Static)
            time_widget.update(Text.from_markup(
                f"\n  [bold]{time_str}[/bold]\n"
            ))
        except Exception:
            pass

    def _update_audio_level(self) -> None:
        """Update audio level visualization."""
        while not self.stop_audio_level.is_set() and self.recorder:
            try:
                with self.recorder._lock:
                    if self.recorder._audio_data:
                        latest = self.recorder._audio_data[-1]
                        import numpy as np
                        rms = np.sqrt(np.mean(latest.astype(np.float32) ** 2))
                        level = min(int(rms * 80), 80)
                    else:
                        level = 0
            except Exception:
                level = 0

            self.current_level = level
            self.app.call_from_thread(self._update_waveform_ui, level)
            time.sleep(0.03)

    def _update_waveform_ui(self, level: int) -> None:
        """Update waveform UI from main thread."""
        try:
            waveform = self.query_one("#recording-waveform", Static)
            bar_width = 60
            filled = int((level / 80) * bar_width)
            
            # Create animated waveform
            wave = ""
            import random
            for i in range(bar_width):
                if i < filled:
                    h = min(7, max(0, filled - i + random.randint(-2, 2)))
                    wave += self.waveform_chars[h]
                else:
                    wave += "░"
            
            waveform.update(Text.from_markup(
                f"\n  [bold]{wave}[/bold]\n"
            ))
        except Exception:
            pass

    def action_cancel(self) -> None:
        """Cancel recording."""
        if self.recording:
            self.stop_recording()
        else:
            if self._temp_file:
                _cleanup_temp_recording(self._temp_file)
                self._temp_file = None
            self.app.pop_screen()


class AnalyzingScreen(Screen):
    """Screen showing analysis progress."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("enter", "retry", "Try Again", show=False),
    ]

    def __init__(
        self,
        audio_path: Path,
        on_complete: Callable[[dict], None],
        **kwargs
    ):
        super().__init__(**kwargs)
        self.audio_path = audio_path
        self.on_complete = on_complete
        self.stage_thread: Optional[threading.Thread] = None
        self._result: Optional[dict] = None
        self._current_step = 0
        self._app_ref = None
        self._error = None
        self._result_queue: queue.Queue = queue.Queue()

    def compose(self) -> ComposeResult:
        yield Container(
            Static(id="analyzing-header"),
            Static(id="analyzing-status"),
            Static(id="analyzing-steps"),
            Static(id="analyzing-help"),
            id="analyzing-container",
        )

    def on_mount(self) -> None:
        self.title = "VoiceLens"
        self.sub_title = ""
        # Capture app reference for use in background thread
        self._app_ref = self.app
        self.start_analysis()
        # Start polling for results from background thread
        asyncio.create_task(self._poll_result_queue_loop())

    async def _poll_result_queue_loop(self) -> None:
        """Continuously poll for results from the background thread."""
        while True:
            try:
                result = self._result_queue.get_nowait()
                if result is not None:
                    await self._on_analysis_complete(result)
                    return
            except queue.Empty:
                pass
            await asyncio.sleep(0.1)

    async def _on_analysis_complete(self, result: dict) -> None:
        """Handle completed analysis on the main thread."""
        # Pop this screen first, then call callback (matches RecordingScreen pattern)
        self.app.pop_screen()
        # Call the screen's on_complete callback (which pushes ResultsScreen)
        if self.on_complete:
            try:
                self.on_complete(result)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Exception in on_complete: {e}", exc_info=True)

    def start_analysis(self) -> None:
        """Start the analysis pipeline with simple progress updates."""
        header = self.query_one("#analyzing-header", Static)
        header.update(Text.from_markup(
            "\n  VOICELENS\n"
        ))

        status = self.query_one("#analyzing-status", Static)
        status.update(Text.from_markup(
            "\n  Analyzing your voice...\n"
        ))

        help_text = self.query_one("#analyzing-help", Static)
        help_text.update(Text.from_markup(
            "\n  [bold]ESC[/bold] Cancel\n"
        ))

        # Steps per spec: Transcribing -> Analyzing speech -> Preparing results
        self.steps = [
            "Transcribing",
            "Analyzing speech",
            "Preparing results"
        ]
        self._current_step = 0
        self._update_steps_display_sync()

        # Run analysis in background thread
        self.stage_thread = threading.Thread(target=self._run_analysis_thread, daemon=True)
        self.stage_thread.start()

    async def update_steps_display(self) -> None:
        """Update the steps display with current progress (async version for thread-safe calls)."""
        self._update_steps_display_sync()

    def _update_steps_display_sync(self) -> None:
        """Update the steps display with current progress (sync version for main thread calls)."""
        steps_widget = self.query_one("#analyzing-steps", Static)
        text = Text()
        text.append("\n")
        
        for i, step in enumerate(self.steps):
            if i < self._current_step:
                text.append("  ✓ ", style="green")
                text.append(f"{step}\n", style="green")
            elif i == self._current_step:
                text.append("  ◌ ", style="yellow")
                text.append(f"{step}\n", style="bold yellow")
            else:
                text.append("  ◌ ", style="dim")
                text.append(f"{step}\n", style="dim")
        
        steps_widget.update(text)

    def _run_analysis_thread(self) -> None:
        """Run the actual pipeline with simple step updates."""
        app = self._app_ref
        if not app:
            return
    
        def schedule_sync(fn, *args, **kwargs):
            """Schedule a synchronous function on the main thread."""
            try:
                app.call_from_thread(fn, *args, **kwargs)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to schedule: {e}", exc_info=True)
    
        try:
            # Step 1: Transcribing (pipeline starts)
            # _current_step is 0, showing "Transcribing" as active (◌)
            
            # Run the pipeline - it handles transcription, alignment, accent, pronunciation, metrics
            if not self.audio_path or not self.audio_path.exists():
                raise FileNotFoundError("Audio file not found")
    
            result = run_voicelens_pipeline(self.audio_path)
            self._result = result
    
            # Pipeline complete - rapidly show all steps as done
            # Step 1: Transcribing -> ✓
            self._current_step = 1
            schedule_sync(self._update_steps_display_sync)
            time.sleep(0.15)
    
            # Step 2: Analyzing speech -> ✓
            self._current_step = 2
            schedule_sync(self._update_steps_display_sync)
            time.sleep(0.15)
    
            # Step 3: Preparing results -> ✓
            self._current_step = 3
            schedule_sync(self._update_steps_display_sync)
            time.sleep(0.2)
    
            # Clean up temp recording file after successful analysis
            _cleanup_temp_recording(self.audio_path)
    
            # Put result in queue for main thread to process
            self._result_queue.put(result)
    
        except Exception as e:
            # Clean up temp recording file on error too
            _cleanup_temp_recording(self.audio_path)
            # Store error and show it on the main thread
            self._error = str(e)
            try:
                schedule_sync(self._show_error_sync, str(e))
            except Exception:
                pass  # App context may be gone

    def _advance_step(self, step_name: str) -> None:
        """Advance to next step."""
        app = self._app_ref
        if not app:
            return
        # Mark current as done
        if self._current_step < len(self.steps):
            self._current_step += 1
        
        try:
            app.call_from_thread(self._update_steps_display_sync)
        except Exception:
            pass  # App context may be gone
        time.sleep(0.3)  # Brief pause to show progress

    def _show_error_sync(self, error_msg: str) -> None:
        """Show error on the analyzing screen."""
        try:
            status = self.query_one("#analyzing-status", Static)
            status.update(Text.from_markup(
                f"\n  [red]Analysis failed: {error_msg}[/red]\n"
            ))
            help_text = self.query_one("#analyzing-help", Static)
            help_text.update(Text.from_markup(
                "\n  [bold]ENTER[/bold] Try again  •  [bold]ESC[/bold] Home\n"
            ))
            # Update steps to show failure
            steps_widget = self.query_one("#analyzing-steps", Static)
            steps_widget.update(Text.from_markup(
                f"\n  ✗ Analysis failed\n"
            ))
            # Show retry binding
            self._error = error_msg
        except Exception:
            pass  # UI may not be ready

    def action_retry(self) -> None:
        """Retry analysis by starting a new recording."""
        if self._error is not None:
            _cleanup_temp_recording(self.audio_path)
            self.app.action_record()

    def action_cancel(self) -> None:
        """Cancel analysis."""
        _cleanup_temp_recording(self.audio_path)
        if self._app_ref:
            self._app_ref.pop_screen()


class ResultsScreen(Screen):
    """Screen for displaying analysis results."""

    BINDINGS = [
        Binding("enter", "record_again", "Record Again", show=True),
        Binding("q", "back", "Back", show=True),
        Binding("escape", "back", "Back", show=True),
    ]

    def __init__(self, result: dict, analysis_id: str, storage=None, **kwargs):
        super().__init__(**kwargs)
        self.result = result
        self.analysis_id = analysis_id
        self.storage = storage

    def compose(self) -> ComposeResult:
        yield Container(
            Static(id="results-header"),
            ScrollableContainer(Static(id="results-content"), id="results-scroll"),
            Static(id="results-help"),
            id="results-container",
        )

    def on_mount(self) -> None:
        self.title = "VoiceLens / Results"
        self.sub_title = f"ID: {self.analysis_id}"
        self.show_results()

    def show_results(self) -> None:
        """Show the results dashboard."""
        header = self.query_one("#results-header", Static)
        header.update(self._build_header())

        content = self.query_one("#results-content", Static)
        content.update(self._build_dashboard())

        help_text = self.query_one("#results-help", Static)
        help_text.update(Text.from_markup(
            "\n  [bold]ENTER[/bold] Record Again  •  [bold]H[/bold] History  •  [bold]Q/ESC[/bold] Back"
        ))

    def _build_header(self) -> Text:
        """Build header with full transcript."""
        r = self.result
        transcript = r.get("transcript", {}).get("text", "")
        duration = r.get("audioDurationSeconds", 0)
        word_count = r.get("transcript", {}).get("wordCount", 0)

        text = Text()
        text.append("\n")
        text.append("  TRANSCRIPT", style="bold")
        text.append(" " * 50, style="dim")
        text.append(f"Duration: {duration:.1f}s  Words: {word_count}", style="dim")
        text.append("\n")
        text.append("  " + "─" * 76 + "\n", style="dim")
        
        if transcript:
            text.append(f"  {transcript}\n", style="white")
        else:
            text.append("  [No speech detected]\n", style="dim")
        
        text.append("  " + "─" * 76 + "\n", style="dim")
        return text

    def _build_dashboard(self) -> Text:
        """Build the results dashboard with all panels."""
        r = self.result
        metrics = r.get("metrics", {})
        accent = r.get("accent", {})
        pronunciation = r.get("pronunciation", {})

        text = Text()
        text.append("\n")

        # OVERALL SCORE panel - prominent at top
        overall_score = pronunciation.get("overallScore", 0)
        score_color = "green" if overall_score >= 75 else "yellow" if overall_score >= 50 else "red"
        bar_len = int(overall_score / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        
        text.append("  ┌─ OVERALL SCORE ───────────────────────────────────────────────┐\n", style="bold")
        text.append(f"  │  Score: ", style="dim")
        text.append(f"{overall_score:.1f}/100", style=f"bold {score_color}")
        text.append(f"  {bar}  │\n", style=score_color)
        text.append("  └──────────────────────────────────────────────────────────────┘\n\n", style="dim")

        # Three-column layout for ACCENT, PRONUNCIATION, SPEECH
        text.append("  ┌─ ACCENT ──────────────────┬─ PRONUNCIATION ────────────────┬─ SPEECH ─────────────────────┐\n", style="dim")
        
        # ACCENT column
        pred_accent = accent.get("predictedAccent", "Unknown")
        acc_conf = accent.get("confidence", 0) * 100
        
        # Check if accent analysis is unavailable
        accent_unavailable = (
            pred_accent == "Unknown" or 
            acc_conf == 0.0 or
            "failed" in str(accent.get("notes", [])).lower() or
            "unavailable" in str(accent.get("notes", [])).lower()
        )
        
        # PRONUNCIATION column
        pron_score = pronunciation.get("overallScore", 0)
        pron_sim = pronunciation.get("pronunciationSimilarity", 0) * 100
        backend = pronunciation.get("backend", "unknown")
        
        # SPEECH column
        wpm = metrics.get("wordsPerMinute", 0)
        words = metrics.get("wordCount", 0)
        duration = metrics.get("durationSeconds", 0)
        
        # Build three columns (simplified - side by side in text)
        text.append("  │ ", style="dim")
        if accent_unavailable:
            text.append("Accent analysis unavailable\n", style="yellow")
        else:
            text.append(f"Accent: {pred_accent}\n", style="white")
            text.append("  │ ", style="dim")
            text.append(f"Confidence: {acc_conf:.1f}%\n", style="dim")
        text.append("  │ ", style="dim")
        text.append(f"Score: {pron_score:.1f}/100\n", style="white")
        text.append("  │ ", style="dim")
        text.append(f"Similarity: {pron_sim:.1f}%\n", style="dim")
        text.append("  │ ", style="dim")
        text.append(f"Backend: {backend}\n", style="dim")
        text.append("  │ ", style="dim")
        text.append(f"WPM: {wpm:.1f}\n", style="white")
        text.append("  │ ", style="dim")
        text.append(f"Words: {words}\n", style="dim")
        text.append("  │ ", style="dim")
        text.append(f"Duration: {duration:.1f}s\n", style="dim")
        
        text.append("  └────────────────────────────┴────────────────────────────────┴──────────────────────────────┘\n\n", style="dim")

        # FILLERS & PAUSES
        fillers = r.get("fillerWordsList", [])
        pauses = metrics.get("pauseCount", 0)
        
        text.append("  ┌─ FILLERS & PAUSES ───────────────────────────────────────────┐\n", style="dim")
        if fillers:
            filler_str = ", ".join([f"{f['word']}({f['count']})" for f in fillers[:5]])
            text.append(f"  │  Fillers: {filler_str}\n", style="yellow")
        else:
            text.append(f"  │  No filler words detected\n", style="green")
        text.append(f"  │  Pauses: {pauses}\n", style="white")
        text.append("  └──────────────────────────────────────────────────────────────┘\n\n", style="dim")

        # DIFFICULT WORDS
        difficult = r.get("difficultWordsList", [])
        if difficult:
            text.append("  ┌─ DIFFICULT WORDS ──────────────────────────────────────────────┐\n", style="dim")
            for w in difficult[:10]:
                text.append(f"  │  {w['word']:<20} ", style="red")
                text.append(f"Score: {w['score']:5.1f}/100 ", style="yellow")
                text.append(f"Conf: {w['confidence']*100:5.1f}% ", style="dim")
                text.append(f"({w['startTime']:.1f}s-{w['endTime']:.1f}s)\n", style="dim")
            text.append("  └──────────────────────────────────────────────────────────────┘\n\n", style="dim")

        # INSIGHTS
        feedback = r.get("overallFeedback", [])
        text.append("  ┌─ INSIGHTS ───────────────────────────────────────────────────┐\n", style="dim")
        for item in feedback:
            if item.startswith("•"):
                item = item[1:].strip()
            if "Excellent" in item or "Good" in item or "✓" in item or "Natural" in item:
                text.append(f"  │  ✓ {item}\n", style="green")
            elif "!" in item or "Needs" in item or "High" in item or "Fast" in item or "Slow" in item:
                text.append(f"  │  ! {item}\n", style="yellow")
            else:
                text.append(f"  │  • {item}\n", style="dim")
        text.append("  └──────────────────────────────────────────────────────────────┘\n", style="dim")

        return text

    def action_record_again(self) -> None:
        """Record again - start new recording immediately."""
        self.app.action_record()

    def action_back(self) -> None:
        """Go back to home."""
        self.app.pop_screen()


class SettingsScreen(Screen):
    """Screen for configuring VoiceLens."""

    BINDINGS = [
        Binding("escape", "back", "Back", show=True),
    ]

    def __init__(self, config: "Config", **kwargs):
        super().__init__(**kwargs)
        self.config = config

    def compose(self) -> ComposeResult:
        yield Container(
            Static(id="settings-header"),
            Static(id="settings-content"),
            Static(id="settings-help"),
            id="settings-container",
        )

    def on_mount(self) -> None:
        self.title = "VoiceLens / Settings"
        self.sub_title = ""
        self.show_settings()

    def show_settings(self) -> None:
        """Display settings."""
        header = self.query_one("#settings-header", Static)
        header.update(Text.from_markup(
            "\n  VOICELENS / SETTINGS\n"
        ))

        content = self.query_one("#settings-content", Static)

        text = Text()
        text.append("\n")

        settings = [
            ("Transcription Model", self.config.get("model", "base.en")),
            ("Language", self.config.get("language", "en")),
            ("Sample Rate", f"{self.config.get('sample_rate', 16000)} Hz"),
            ("History Enabled", "Yes" if self.config.get("history_enabled", True) else "No"),
            ("Auto-save Results", "Yes" if self.config.get("auto_save", True) else "No"),
        ]

        text.append("  ┌─ CONFIGURATION ──────────────────────────────────────────────┐\n", style="dim")
        for label, value in settings:
            text.append(f"  │  {label:<30} ", style="dim")
            text.append(f"{value}  │\n", style="white")
        text.append("  └──────────────────────────────────────────────────────────────┘\n\n", style="dim")

        text.append("  Config file: ", style="dim")
        text.append(f"{self.config.config_path}\n\n", style="dim")

        text.append("  Use CLI for changes:\n", style="dim")
        text.append("    voicelens config model base.en\n", style="dim")
        text.append("    voicelens config --list\n", style="dim")

        content.update(text)

        help_text = self.query_one("#settings-help", Static)
        help_text.update(Text.from_markup(
            "\n  [bold]ESC[/bold] Back"
        ))

    def action_back(self) -> None:
        """Go back to home."""
        self.app.pop_screen()


class DoctorScreen(Screen):
    """Screen for system diagnostics."""

    BINDINGS = [
        Binding("escape", "back", "Back", show=True),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Container(
            Static(id="doctor-header"),
            RichLog(id="doctor-log", highlight=True, markup=True),
            Static(id="doctor-help"),
            id="doctor-container",
        )

    def on_mount(self) -> None:
        self.title = "VoiceLens / Doctor"
        self.sub_title = ""
        self.run_diagnostics()

    def run_diagnostics(self) -> None:
        """Run system diagnostics."""
        log = self.query_one("#doctor-log", RichLog)
        log.clear()

        header = self.query_one("#doctor-header", Static)
        header.update(Text.from_markup(
            "\n  VOICELENS / DOCTOR\n"
        ))

        log.write("[bold]SYSTEM[/bold]")

        import sys
        import shutil
        import platform

        # Python version
        raw_version = sys.version.split()[0]
        version_ok = tuple(map(int, raw_version.split(".")[:2])) >= (3, 12)
        status = "✓" if version_ok else "✗"
        log.write(f"  {status} Python             {raw_version} (required >= 3.12)")

        # Disk space
        try:
            _, _, free = shutil.disk_usage(".")
            free_gb = free / (2**30)
            status = "✓" if free_gb > 1.0 else "⚠"
            log.write(f"  {status} Disk Space         {free_gb:.2f} GB free")
        except Exception as e:
            log.write(f"  ✗ Disk Space         {e}")

        # FFmpeg
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            log.write(f"  ✓ FFmpeg             {ffmpeg_path}")
        else:
            log.write("  ⚠ FFmpeg             Not found (optional)")

        # PortAudio/sounddevice
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = [d for d in devices if d.get("max_input_channels", 0) > 0]
            if input_devices:
                log.write(f"  ✓ Microphone         {len(input_devices)} input device(s)")
                for d in input_devices:
                    log.write(f"      • {d['name'][:50]}")
            else:
                log.write("  ✗ Microphone         No input devices found")
        except Exception as e:
            log.write(f"  ✗ Microphone         {e}")

        log.write("\n[bold]DEPENDENCIES[/bold]")
        core_deps = [
            ("fastapi", "fastapi"),
            ("uvicorn", "uvicorn"),
            ("typer", "typer"),
            ("rich", "rich"),
            ("textual", "textual"),
            ("faster-whisper", "faster_whisper"),
            ("av", "av"),
            ("numpy", "numpy"),
            ("torch", "torch"),
            ("torchaudio", "torchaudio"),
            ("sounddevice", "sounddevice"),
            ("sqlite-utils", "sqlite_utils"),
        ]

        for name, import_name in core_deps:
            try:
                __import__(import_name)
                log.write(f"  ✓ {name}")
            except Exception as e:
                log.write(f"  ✗ {name}  {e}")

        # ML dependencies
        ml_deps = [
            ("speechbrain", "speechbrain"),
        ]

        log.write("\n[bold]OPTIONAL ML[/bold]")
        for name, import_name in ml_deps:
            try:
                __import__(import_name)
                log.write(f"  ✓ {name}")
            except Exception:
                log.write(f"  ⚠ {name}  (pip install voicelens[ml])")

        # Whisper.cpp
        model_path = Path(__file__).resolve().parents[2] / "whisper_cpp" / "models" / "ggml-base.en.bin"
        binary_path = Path(__file__).resolve().parents[2] / "whisper_cpp" / "bin" / "whisper-cli"
        if model_path.exists() and binary_path.exists():
            log.write(f"\n  ✓ Whisper.cpp        Model and binary found")
        else:
            log.write(f"\n  ✗ Whisper.cpp        Model or binary missing")

        # Storage
        try:
            storage_dir = Path.home() / ".local" / "share" / "voicelens"
            storage_dir.mkdir(parents=True, exist_ok=True)
            log.write(f"  ✓ Storage            {storage_dir}")
        except Exception as e:
            log.write(f"  ✗ Storage            {e}")

        help_text = self.query_one("#doctor-help", Static)
        help_text.update(Text.from_markup(
            "\n  [bold]R[/bold] Refresh  •  [bold]ESC[/bold] Back"
        ))

    def action_refresh(self) -> None:
        """Refresh diagnostics."""
        self.run_diagnostics()

    def action_back(self) -> None:
        """Go back to home."""
        self.app.pop_screen()


class ModelsScreen(Screen):
    """Screen for managing transcription models."""

    BINDINGS = [
        Binding("escape", "back", "Back", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Container(
            Static(id="models-header"),
            Static(id="models-content"),
            Static(id="models-help"),
            id="models-container",
        )

    def on_mount(self) -> None:
        self.title = "VoiceLens / Models"
        self.sub_title = ""
        self.show_models()

    def show_models(self) -> None:
        """Display available models."""
        header = self.query_one("#models-header", Static)
        header.update(Text.from_markup(
            "\n  VOICELENS / MODELS\n"
        ))

        content = self.query_one("#models-content", Static)

        text = Text()
        text.append("\n")

        models = [
            ("tiny.en", "39 MB", "Fastest, lowest accuracy"),
            ("base.en", "74 MB", "Good balance of speed/accuracy"),
            ("small.en", "244 MB", "Better accuracy"),
            ("medium.en", "769 MB", "High accuracy"),
            ("large-v3", "1550 MB", "Best accuracy, multilingual"),
        ]

        text.append("  Whisper.cpp Models (English-only variants):\n\n", style="bold")
        for name, size, desc in models:
            model_path = Path(__file__).resolve().parents[2] / "whisper_cpp" / "models" / f"ggml-{name}.bin"
            is_downloaded = model_path.exists()
            status = "✓ Downloaded" if is_downloaded else "Not downloaded"
            status_style = "green" if is_downloaded else "dim"
            
            text.append(f"  {name:<12} ", style="bold")
            text.append(f"{size:>10}  ", style="dim")
            text.append(f"{desc}\n", style="white")
            text.append(f"  {'':12} {'':10}  Status: ", style="dim")
            text.append(f"{status}\n\n", style=status_style)

        binary_path = Path(__file__).resolve().parents[2] / "whisper_cpp" / "bin" / "whisper-cli"
        if binary_path.exists():
            text.append(f"  ✓ whisper.cpp binary found\n\n", style="green")
        else:
            text.append(f"  ✗ whisper.cpp binary not found\n\n", style="red")

        text.append("  Download from: https://huggingface.co/ggerganov/whisper.cpp\n", style="dim")
        text.append("  Place .bin files in ./whisper_cpp/models/\n", style="dim")

        content.update(text)

        help_text = self.query_one("#models-help", Static)
        help_text.update(Text.from_markup(
            "\n  [bold]ESC[/bold] Back"
        ))

    def action_back(self) -> None:
        """Go back to home."""
        self.app.pop_screen()