"""VoiceLens Command Line Interface core app."""

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pathlib import Path
import json
import sys

from voicelens import __version__
from voicelens.commands.analyze import analyze_command
from voicelens.commands.doctor import perform_system_checks
from voicelens.commands.serve import serve_command
from voicelens.core.config import Config

# Initialize Rich Console
console = Console()

# Initialize Typer App
app = typer.Typer(
    name="voicelens",
    help=(
        "VoiceLens: A production-ready open-source Python CLI "
        "for audio and voice analysis."
    ),
    add_completion=False,
    no_args_is_help=False,
    invoke_without_command=True,
)


def version_callback(value: bool) -> None:
    """Callback to print the VoiceLens version and exit."""
    if value:
        console.print(
            f"[bold cyan]VoiceLens[/bold cyan] CLI version "
            f"[bold green]{__version__}[/bold green]"
        )
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Show the version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """VoiceLens: Capture, analyze, and inspect your voice and audio features."""
    if ctx.invoked_subcommand is None:
        # No subcommand provided, launch TUI
        from voicelens.tui.app import run_tui
        run_tui()


@app.command()
def doctor() -> None:
    """Run a system check to diagnose environmental issues."""
    ok = perform_system_checks()
    if not ok:
        raise typer.Exit(code=1)


@app.command()
def analyze() -> None:
    """Record audio from the default microphone and analyze speaker characteristics."""
    analyze_command()


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host address to bind."),
    port: int = typer.Option(8000, "--port", "-p", help="Port to listen on."),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload."),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of worker processes."),
) -> None:
    """Start the VoiceLens HTTP API server for local or web frontend execution."""
    serve_command(host=host, port=port, reload=reload, workers=workers)


@app.command()
def tui() -> None:
    """Launch the interactive terminal user interface."""
    from voicelens.tui.app import run_tui
    run_tui()


@app.command()
def models() -> None:
    """List available transcription models."""
    model_dir = Path(__file__).resolve().parents[1] / "whisper_cpp" / "models"
    binary_dir = Path(__file__).resolve().parents[1] / "whisper_cpp" / "bin"

    table = Table(title="VoiceLens Transcription Models", show_header=True, header_style="bold cyan")
    table.add_column("Model", style="bold")
    table.add_column("Size")
    table.add_column("Description")
    table.add_column("Status")

    models = [
        ("tiny.en", "39 MB", "Fastest, lowest accuracy"),
        ("base.en", "74 MB", "Good balance of speed/accuracy"),
        ("small.en", "244 MB", "Better accuracy"),
        ("medium.en", "769 MB", "High accuracy"),
        ("large-v3", "1550 MB", "Best accuracy, multilingual"),
    ]

    for name, size, desc in models:
        model_path = model_dir / f"ggml-{name}.bin"
        if model_path.exists():
            status = "[green]✓ Downloaded[/green]"
        else:
            status = "[dim]Not downloaded[/dim]"
        table.add_row(name, size, desc, status)

    console.print(table)

    # Check binary
    binary_path = binary_dir / "whisper-cli"
    if binary_path.exists():
        console.print(f"\n[green]✓ whisper.cpp binary found at {binary_path}[/green]")
    else:
        console.print(f"\n[red]✗ whisper.cpp binary not found at {binary_path}[/red]")

    console.print("\n[dim]Download models from: https://huggingface.co/ggerganov/whisper.cpp[/dim]")


@app.command()
def config(
    key: str | None = typer.Argument(None, help="Config key to get/set."),
    value: str | None = typer.Argument(None, help="Value to set (requires key)."),
    list_all: bool = typer.Option(False, "--list", "-l", help="List all config values."),
    reset: bool = typer.Option(False, "--reset", help="Reset to defaults."),
) -> None:
    """Manage VoiceLens configuration."""
    cfg = Config()

    if reset:
        cfg.reset()
        console.print("[green]Configuration reset to defaults[/green]")
        return

    if list_all or key is None:
        table = Table(title="VoiceLens Configuration", show_header=True, header_style="bold cyan")
        table.add_column("Key", style="bold")
        table.add_column("Value")
        for k, v in cfg.all.items():
            table.add_row(k, str(v))
        console.print(table)
        console.print(f"\n[dim]Config file: {cfg.config_path}[/dim]")
        return

    if value is None:
        # Get value
        val = cfg.get(key)
        if val is not None:
            console.print(f"{key} = {val}")
        else:
            console.print(f"[red]Key not found: {key}[/red]")
            raise typer.Exit(code=1)
    else:
        # Set value - try to parse as JSON for proper types
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = value
        cfg.set(key, parsed)
        console.print(f"[green]Set {key} = {parsed}[/green]")


if __name__ == "__main__":
    app()