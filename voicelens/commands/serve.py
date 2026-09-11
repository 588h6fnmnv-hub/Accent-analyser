"""VoiceLens CLI command: serve."""

import uvicorn


def serve_command(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
) -> None:
    """Start the VoiceLens HTTP API server using Uvicorn."""
    uvicorn.run(
        "voicelens.api.app:app",
        host=host,
        port=port,
        reload=reload,
    )
