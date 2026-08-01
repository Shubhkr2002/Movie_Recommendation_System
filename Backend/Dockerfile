# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Prevents Python from writing .pyc files and buffers stdout (better logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps needed to build scientific Python wheels on slim images
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first for better Docker layer caching
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code and data
COPY app ./app
COPY data ./data

# Render (and most PaaS providers) injects $PORT at runtime; default to 8000 locally
ENV PORT=8000
EXPOSE 8000

# gunicorn manages worker processes; uvicorn workers give us ASGI/async support
CMD ["sh", "-c", "gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:${PORT} --timeout 120"]
