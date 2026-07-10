FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Системные зависимости для сборки некоторых Python-пакетов
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY assistant/ ./assistant/
COPY .env.example .env.example

RUN mkdir -p /app/data /app/logs /app/assistant/cache/storage

# Непривилегированный пользователь
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

VOLUME ["/app/data", "/app/logs"]

ENTRYPOINT ["python", "-m", "assistant.main"]
