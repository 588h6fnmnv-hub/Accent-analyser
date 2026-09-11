"""VoiceLens CLI command: analyze."""

import sys
import tempfile
import threading
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from voicelens.pipeline import generate_clean_feedback, run_voicelens_pipeline
from voicelens.recorder.audio import AudioRecorder, AudioRecorderError
from voicelens.transcriber.whisper import WhisperTranscriberError

# Initialize Rich Console
console = Console()


def perform_analysis_recording() -> Path:
    """Handles user flow for recording audio from default microphone.

    Returns:
        Path: The path to the saved recording.wav file.

    Raises:
        AudioRecorderError: If there's an error starting/stopping the recorder.
    """
    explanation = (
        "VoiceLens will record audio from your default microphone.\n"
        "After recording, VoiceLens will automatically transcribe your audio.\n\n"
        "[bold green]Steps:[/bold green]\n"
        "1. Press [bold cyan]ENTER[/bold cyan] to start recording.\n"
        "2. Speak into your microphone.\n"
        "3. Press [bold cyan]ENTER[/bold cyan] again to stop the recording."
    )
    console.print(
        Panel(
            explanation,
            title="🎙️ [bold cyan]VoiceLens Audio Recorder & Transcriber[/bold cyan]",
            border_style="cyan",
            expand=False,
        )
    )

    recorder = AudioRecorder()
    recorder.check_system_availability()

    console.print(
        "\nPress [bold green]ENTER[/bold green] when you are ready to start..."
    )
    sys.stdin.readline()

    console.print("[bold yellow]Initializing audio stream...[/bold yellow]")
    recorder.start_recording()

    start_time = time.time()
    stop_timer = threading.Event()

    with Live(
        Text("Initializing live timer...", style="bold red"),
        refresh_per_second=10,
        transient=True,
    ) as live:

        def update_timer() -> None:
            while not stop_timer.is_set():
                elapsed = time.time() - start_time
                timer_text = (
                    f"🔴 Recording... {elapsed:.1f}s  [dim](Press ENTER to stop)[/dim]"
                )
                live.update(Text(timer_text, style="bold red"))
                time.sleep(0.1)

        timer_thread = threading.Thread(target=update_timer, daemon=True)
        timer_thread.start()

        sys.stdin.readline()
        stop_timer.set()
        timer_thread.join()

    recorder.stop_recording()
    duration = recorder.get_duration()
    console.print(
        f"[bold green]✓ Recording stopped successfully![/bold green] "
        f"Captured [bold cyan]{duration:.2f} seconds[/bold cyan] of audio."
    )

    temp_dir = Path(tempfile.gettempdir()) / "voicelens"
    temp_dir.mkdir(parents=True, exist_ok=True)
    output_path = temp_dir / "recording.wav"

    console.print("[dim]Saving audio data to WAV file...[/dim]")
    recorder.save_wav(output_path)

    return output_path


def generate_overall_feedback(
    pron_score: float | None,
    wpm: float | None,
    filler_count: int | None,
    detected_accent: str | None,
) -> str:
    """Helper to generate data-driven overall feedback formatted with Rich tags."""
    bullets = generate_clean_feedback(pron_score, wpm, filler_count, detected_accent)
    header = "[bold cyan]VoiceLens Comprehensive Assessment Feedback[/bold cyan]\n"
    return header + "\n".join(bullets)


def analyze_command() -> None:
    """Record audio from default microphone and run VoiceLens analysis pipeline."""
    try:
        saved_path = perform_analysis_recording()
        console.print(
            Panel(
                f"[bold green]Success![/bold green] Recording saved to:\n"
                f"[bold cyan]{saved_path.resolve()}[/bold cyan]",
                title="💾 [bold green]File Saved[/bold green]",
                border_style="green",
                expand=False,
            )
        )

        with console.status(
            "[bold cyan]Transcribing and analyzing audio using VoiceLens...[/bold cyan]"
        ):
            res = run_voicelens_pipeline(saved_path)

        transcript = res["transcript"]["text"]
        if not transcript:
            transcript = "[italic dim]No speech detected in the recording.[/italic dim]"

        console.print(
            Panel(
                transcript,
                title="📝 [bold cyan]Transcript[/bold cyan]",
                border_style="cyan",
                expand=False,
            )
        )

        # Render Rich tables
        ui_title = "📊 [bold cyan]VoiceLens Comprehensive Audio Analysis[/bold cyan]\n"
        console.print(f"\n{ui_title}")

        accent_table = Table(
            title="Pronunciation & Accent Profile",
            show_header=True,
            header_style="bold magenta",
        )
        accent_table.add_column("Assessment Dimension", style="dim", width=25)
        accent_table.add_column("Result", justify="left")
        accent_table.add_column("Details / Confidence", justify="left")

        pred_accent = res["accent"]["predictedAccent"]
        acc_conf = res["accent"]["confidence"]
        if pred_accent != "Unknown" and acc_conf > 0.0:
            accent_table.add_row(
                "Predicted Accent",
                f"[bold green]{pred_accent}[/bold green]",
                f"Confidence: {acc_conf * 100:.1f}%",
            )
        else:
            accent_table.add_row(
                "Predicted Accent",
                "[yellow]N/A (Failed)[/yellow]",
                "[dim]Accent classification failed[/dim]",
            )

        pron_score = res["pronunciation"]["overallScore"]
        pron_sim = res["pronunciation"]["pronunciationSimilarity"]
        pron_conf = res["pronunciation"]["confidence"]

        if pron_conf > 0.0:
            accent_table.add_row(
                "Phonetic Similarity",
                f"[bold green]{pron_sim * 100.0:.1f}%[/bold green]",
                "ECAPA-TDNN embedding match factor",
            )
            accent_table.add_row(
                "Overall Score",
                f"[bold cyan]{pron_score:.1f} / 100[/bold cyan]",
                f"Confidence: {pron_conf * 100:.1f}%",
            )
        else:
            accent_table.add_row(
                "Phonetic Similarity",
                "[yellow]N/A (Failed)[/yellow]",
                "[dim]Embedding similarity failed[/dim]",
            )
            accent_table.add_row(
                "Overall Score",
                "[yellow]N/A (Failed)[/yellow]",
                "[dim]Pronunciation assessment failed[/dim]",
            )
        console.print(accent_table)

        if pron_conf > 0.0:
            score_pct = int(pron_score)
            filled_blocks = score_pct // 5
            bar = "█" * filled_blocks + "░" * (20 - filled_blocks)
            console.print(
                f"\n[bold]Overall Pronunciation Score:[/bold] "
                f"[cyan]{pron_score:.1f}/100[/cyan]  |{bar}|\n"
            )
        else:
            console.print(
                "\n[bold]Overall Pronunciation Score:[/bold] "
                "[yellow]N/A (Failed)[/yellow]\n"
            )

        metrics_table = Table(
            title="Speech Delivery Metrics",
            show_header=True,
            header_style="bold blue",
        )
        metrics_table.add_column("Speech Metric", style="dim", width=25)
        metrics_table.add_column("Value", justify="left")
        metrics_table.add_column("Interpretation", justify="left")

        m = res["metrics"]
        metrics_table.add_row(
            "Words Per Minute (WPM)",
            f"[bold cyan]{m['wordsPerMinute']:.1f}[/bold cyan]",
            "Pace speed indicator",
        )
        metrics_table.add_row(
            "Speaking Duration",
            f"{m['durationSeconds']:.2f}s",
            "Total speaking time recorded",
        )
        metrics_table.add_row(
            "Total Words",
            str(m["wordCount"]),
            f"Avg {m['averageWordsPerSentence']:.1f} words per sentence",
        )
        metrics_table.add_row(
            "Pause Count",
            f"[bold yellow]{m['pauseCount']}[/bold yellow]",
            f"Avg duration: {m['averagePauseDuration']:.2f}s",
        )
        metrics_table.add_row(
            "Longest Pause",
            f"{m['longestPause']:.2f}s",
            "Max non-speaking silent run",
        )
        console.print(metrics_table)

        f_count = m["fillerWordCount"]
        fillers_str = (
            ", ".join([f"[bold red]{f}[/bold red]" for f in m["fillerWords"]])
            if m["fillerWords"]
            else "[green]None detected[/green]"
        )
        console.print(
            f"\n[bold]Detected Filler Words:[/bold] "
            f"[bold yellow]{f_count}[/bold yellow] | {fillers_str}"
        )

        diff_table = Table(
            title="Top 10 Difficult/Mispronounced Words (Sorted Worst First)",
            show_header=True,
            header_style="bold red",
        )
        diff_table.add_column("Word", justify="left")
        diff_table.add_column("Phonetic Score", justify="left")
        diff_table.add_column("Whisper Confidence", justify="left")
        diff_table.add_column("Spoken Timeframe", justify="left")

        top_10 = res["difficultWordsList"]
        if top_10:
            for w_mis in top_10:
                diff_table.add_row(
                    f"[bold red]{w_mis['word']}[/bold red]",
                    f"{w_mis['score']:.1f} / 100",
                    f"{w_mis['confidence'] * 100:.1f}%",
                    f"{w_mis['startTime']:.2f}s - {w_mis['endTime']:.2f}s",
                )
            console.print("\n")
            console.print(diff_table)
        else:
            console.print(
                "\n[bold green]✓ No major pronunciation "
                "difficulties detected![/bold green]"
            )

        p_sc = pron_score if pron_conf > 0.0 else None
        border_col = "green" if p_sc and p_sc >= 75.0 else "yellow"
        if p_sc and p_sc < 50.0:
            border_col = "red"

        fb_str = generate_overall_feedback(
            p_sc,
            m["wordsPerMinute"],
            m["fillerWordCount"],
            pred_accent if acc_conf > 0.0 else None,
        )

        console.print("\n")
        console.print(
            Panel(
                fb_str,
                title="💡 [bold]Overall Audio Analysis Feedback[/bold]",
                border_style=border_col,
                expand=False,
            )
        )

    except AudioRecorderError as e:
        msg = (
            "[yellow]Please check your system audio settings, "
            "microphone connection, and permissions.[/yellow]"
        )
        console.print(f"\n[bold red]❌ Audio Recording Error:[/bold red] {e}\n{msg}")
        raise typer.Exit(code=1) from e
    except WhisperTranscriberError as e:
        msg = (
            "[yellow]The recording was saved successfully, "
            "but transcription failed.[/yellow]"
        )
        console.print(f"\n[bold red]❌ Transcription Error:[/bold red] {e}\n{msg}")
        raise typer.Exit(code=1) from e
    except Exception as e:
        err_msg = f"\n[bold red]❌ Unexpected Error during analysis:[/bold red] {e}"
        console.print(err_msg)
        raise typer.Exit(code=1) from e
