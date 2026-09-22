"""VoiceLens CLI commands."""

import shutil
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Initialize rich console
console = Console()


def check_dependency(name: str, import_name: str | None = None) -> tuple[bool, str]:
    """Check if a Python package is available."""
    try:
        __import__(import_name or name)
        return True, f"{name} available"
    except Exception as e:
        return False, f"{name} not available: {e}"


def perform_system_checks() -> bool:
    """Runs system checks and prints results using Rich.

    Returns:
        bool: True if all critical checks pass, False otherwise.
    """
    console.print("\n[bold cyan]🔍 VoiceLens System Diagnosis[/bold cyan]\n")

    table = Table(title="System Checks", show_header=True, header_style="bold blue")
    table.add_column("Component", style="dim", width=30)
    table.add_column("Status", width=12)
    table.add_column("Details", justify="left")

    all_passed = True

    # Check 1: Python version
    raw_version = sys.version.split()[0]
    version_ok = tuple(map(int, raw_version.split(".")[:2])) >= (3, 12)
    table.add_row(
        "Python Runtime",
        "[green]PASSED[/green]" if version_ok else "[red]FAILED[/red]",
        f"v{raw_version} (Required >= 3.12)",
    )
    if not version_ok:
        all_passed = False

    # Check 2: Available Disk Space
    try:
        _, _, free = shutil.disk_usage(".")
        free_gb = free / (2**30)
        status = (
            "[green]PASSED[/green]" if free_gb > 1.0 else "[yellow]WARNING[/yellow]"
        )
        table.add_row(
            "Disk Space",
            status,
            f"{free_gb:.2f} GB free",
        )
        if free_gb <= 1.0:
            all_passed = False
    except Exception as e:
        table.add_row("Disk Space", "[red]FAILED[/red]", str(e))
        all_passed = False

    # Check 3: FFmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        table.add_row(
            "External Backend (FFmpeg)",
            "[green]PASSED[/green]",
            f"Found at {ffmpeg_path}",
        )
    else:
        table.add_row(
            "External Backend (FFmpeg)",
            "[yellow]WARNING[/yellow]",
            "FFmpeg not found in PATH. Optional but recommended.",
        )

    # Check 4: Core Dependencies
    core_deps = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("typer", "typer"),
        ("rich", "rich"),
        ("faster-whisper", "faster_whisper"),
        ("av", "av"),
        ("numpy", "numpy"),
        ("torch", "torch"),
        ("torchaudio", "torchaudio"),
        ("sounddevice", "sounddevice"),
    ]

    for name, import_name in core_deps:
        ok, detail = check_dependency(name, import_name)
        table.add_row(
            f"Dependency: {name}",
            "[green]PASSED[/green]" if ok else "[red]FAILED[/red]",
            detail,
        )
        if not ok:
            all_passed = False

    # Check 5: Optional ML Dependencies
    ml_deps = [
        ("speechbrain (optional)", "speechbrain"),
    ]

    for name, import_name in ml_deps:
        ok, detail = check_dependency(name, import_name)
        status = "[green]PASSED[/green]" if ok else "[yellow]OPTIONAL[/yellow]"
        table.add_row(
            f"Dependency: {name}",
            status,
            detail,
        )

    # Check 6: Whisper model initialization
    try:
        from voicelens.transcriber.whisper import WhisperTranscriber
        transcriber = WhisperTranscriber(model_size="base")
        model = transcriber._get_model()
        table.add_row(
            "Whisper Model (base)",
            "[green]PASSED[/green]",
            "Model loads successfully",
        )
    except Exception as e:
        table.add_row(
            "Whisper Model (base)",
            "[red]FAILED[/red]",
            f"Model initialization failed: {e}",
        )
        all_passed = False

    # Check 7: Microphone availability
    try:
        from voicelens.recorder.audio import AudioRecorder
        recorder = AudioRecorder()
        recorder.check_system_availability()
        table.add_row(
            "Microphone",
            "[green]PASSED[/green]",
            "Default microphone available",
        )
    except Exception as e:
        table.add_row(
            "Microphone",
            "[yellow]WARNING[/yellow]",
            f"Microphone check failed: {e}",
        )
        # Not critical, don't fail all_passed

    # Check 8: Audio backend (torchaudio)
    try:
        import torchaudio
        # Test basic torchaudio functionality
        import torch
        test_tensor = torch.zeros(1, 16000)
        torchaudio.functional.resample(test_tensor, 16000, 8000)
        table.add_row(
            "Audio Backend (torchaudio)",
            "[green]PASSED[/green]",
            f"torchaudio {torchaudio.__version__} functional",
        )
    except Exception as e:
        table.add_row(
            "Audio Backend (torchaudio)",
            "[yellow]WARNING[/yellow]",
            f"torchaudio check failed: {e}",
        )

    # Check 9: Temp directory permissions
    try:
        import tempfile
        from pathlib import Path
        temp_dir = Path(tempfile.gettempdir()) / "voicelens"
        temp_dir.mkdir(parents=True, exist_ok=True)
        test_file = temp_dir / "test_write.tmp"
        test_file.write_text("test")
        test_file.unlink()
        table.add_row(
            "Temp Directory",
            "[green]PASSED[/green]",
            f"Writable: {temp_dir}",
        )
    except Exception as e:
        table.add_row(
            "Temp Directory",
            "[red]FAILED[/red]",
            f"Cannot write to temp directory: {e}",
        )
        all_passed = False

    # Check 10: NumPy
    try:
        import numpy
        # Test basic numpy functionality
        arr = numpy.zeros(100)
        mean = arr.mean()
        table.add_row(
            "NumPy",
            "[green]PASSED[/green]",
            f"NumPy {numpy.__version__} functional",
        )
    except Exception as e:
        table.add_row(
            "NumPy",
            "[red]FAILED[/red]",
            f"NumPy check failed: {e}",
        )
        all_passed = False

    # Check 11: SpeechBrain (optional but test if available)
    try:
        from voicelens.pronunciation.speechbrain_backend import SpeechBrainBackend
        backend = SpeechBrainBackend()
        _ = backend._get_classifier()
        table.add_row(
            "SpeechBrain (optional)",
            "[green]PASSED[/green]",
            "ECAPA-TDNN model loads successfully",
        )
    except Exception as e:
        table.add_row(
            "SpeechBrain (optional)",
            "[yellow]WARNING[/yellow]",
            f"SpeechBrain unavailable: {e}",
        )
        # Not critical, don't fail all_passed

    console.print(table)

    # Summary Panel
    console.print("\n")
    if all_passed:
        console.print(
            Panel(
                "[bold green]✓ All core system checks passed successfully![/bold green]\n"
                "VoiceLens is ready to capture and analyze voice inputs.",
                title="Diagnosis Summary",
                expand=False,
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                "[bold red]✗ Some critical checks failed![/bold red]\n"
                "Please install missing dependencies and try again.",
                title="Diagnosis Summary",
                expand=False,
                border_style="red",
            )
        )
    return all_passed