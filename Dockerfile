# VoiceLens FastAPI Backend - Production Dockerfile
# Multi-stage build for smaller final image

# Stage 1: Build stage with all dependencies
FROM python:3.12-slim AS builder

# System dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml README.md ./
COPY voicelens ./voicelens
RUN pip install --no-cache-dir -e ".[ml]"

# Stage 2: Runtime stage - minimal image
FROM python:3.12-slim AS runtime

# Runtime system dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY voicelens ./voicelens
COPY pyproject.toml README.md ./

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Pre-download models at build time (critical for local_files_only=True)
# Allow downloads during build, then models are cached in the image
ENV HF_HUB_OFFLINE=0
RUN python -c "
import os
os.environ['HF_HUB_OFFLINE'] = '0'
from voicelens.transcriber import Transcriber
from voicelens.accent.classifier import AccentClassifier
try:
    Transcriber(model_size='base.en')
    print('Whisper model cached successfully')
except Exception as e:
    print(f'Whisper model cache warning: {e}')

try:
    AccentClassifier()
    print('Accent classifier cached successfully')
except Exception as e:
    print(f'Accent classifier cache warning: {e}')
"

# Expose port
EXPOSE 8000

# Run with uvicorn (single worker for model sharing)
CMD ["uvicorn", "voicelens.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]