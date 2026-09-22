"""Smoke tests for VoiceLens CLI commands."""

import subprocess
import sys


def run_cli(*args: str) -> subprocess.CompletedProcess:
    """Run voicelens CLI command and return result."""
    return subprocess.run(
        [sys.executable, "-m", "voicelens", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_cli_help() -> None:
    """Test that CLI shows help without errors."""
    result = run_cli("--help")
    assert result.returncode == 0
    assert "VoiceLens" in result.stdout
    assert "analyze" in result.stdout
    assert "serve" in result.stdout
    assert "doctor" in result.stdout


def test_cli_version() -> None:
    """Test that CLI shows version."""
    result = run_cli("--version")
    assert result.returncode == 0
    assert "VoiceLens" in result.stdout
    assert "0.1.0" in result.stdout


def test_cli_doctor() -> None:
    """Test doctor command runs (may pass or fail depending on deps)."""
    result = run_cli("doctor")
    # Doctor returns 0 on success, 1 on failure - both are valid
    assert result.returncode in (0, 1)
    assert "VoiceLens System Diagnosis" in result.stdout


def test_cli_analyze_help() -> None:
    """Test analyze command help."""
    result = run_cli("analyze", "--help")
    assert result.returncode == 0
    assert "Record audio" in result.stdout


def test_cli_serve_help() -> None:
    """Test serve command help."""
    result = run_cli("serve", "--help")
    assert result.returncode == 0
    assert "Start the VoiceLens HTTP API server" in result.stdout
    assert "--workers" in result.stdout