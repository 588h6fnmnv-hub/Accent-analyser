"""Smoke tests for VoiceLens API endpoints."""

import subprocess
import sys
import time
import httpx
import pytest


@pytest.fixture(scope="module")
def api_server():
    """Start API server for testing."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "voicelens", "serve", "--port", "8001"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Wait for server to start
    time.sleep(3)
    yield "http://localhost:8001"
    proc.terminate()
    proc.wait(timeout=5)


def test_api_health(api_server: str) -> None:
    """Test /api/health endpoint."""
    with httpx.Client(timeout=10.0) as client:
        response = client.get(f"{api_server}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "VoiceLens API"
        assert "version" in data


def test_api_analyze_endpoint_exists(api_server: str) -> None:
    """Test that /api/analyze endpoint exists (returns 422 for missing file)."""
    with httpx.Client(timeout=10.0) as client:
        response = client.post(f"{api_server}/api/analyze")
        # Should return 422 for missing file, not 404
        assert response.status_code == 422