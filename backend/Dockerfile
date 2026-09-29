# Multi-stage Dockerfile for FastAPI Enterprise Backend

FROM python:3.11-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final Production Stage
FROM python:3.11-slim

WORKDIR /app

RUN groupadd -g 999 appgroup && \
    useradd -r -u 999 -g appgroup -m -d /home/appuser appuser

COPY --from=builder /install /usr/local
COPY . /app
RUN chown -R appuser:appgroup /app

ENV PYTHONPATH=/app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
