# Shared base image for MyPalClara Python services
# Build context: repo root
# Usage: docker build -f services/base/Dockerfile -t clara-base:latest .

FROM python:3.12-slim

WORKDIR /app

# System dependencies (build toolchain for compiled wheels)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Poetry
RUN pip install poetry

# Dependencies
COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

# Application code
COPY mypalclara/ ./mypalclara/
COPY personalities/ ./personalities/
COPY VERSION ./

# Persistent data directories
RUN mkdir -p /data /app/clara_files
ENV DATA_DIR=/data
ENV CLARA_FILES_DIR=/app/clara_files
