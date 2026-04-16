# Stage 1: Builder
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# Install build dependencies + libpq for PostgreSQL/psycopg2 compatibility
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Use a build cache mount to speed up re-builds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --user --upgrade pip && \
    pip install --user -r requirements.txt


# Stage 2: Final Runtime
FROM python:3.11-slim AS runtime

# Essential for 2026 security compliance: ca-certificates for external API calls
# and curl for a more robust healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/appuser/.local/bin:${PATH}"

WORKDIR /app

# 1. Security: Create a non-privileged user
RUN groupadd -r appgroup && useradd -r -g appgroup -m appuser

# 2. Copy dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local

# 3. Copy application code and logs directory
# Note: Copying the whole project context to include models, core, etc.
COPY --chown=appuser:appgroup . .

# 4. Prepare logs (ensure the appuser can write to them)
RUN mkdir -p /app/logs && chown appuser:appgroup /app/logs

# 5. Use the unprivileged user
USER appuser

# 6. Production Healthcheck (Using curl for better timeout handling)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Render/Cloud Env dynamic port support
EXPOSE 8000

# 7. Graceful execution using 'exec' form
# Added --workers 4 to handle the connection increase (291+)
# Added --timeout-keep-alive 60 for Jitsi signaling persistence
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*' --workers 4 --timeout-keep-alive 60"]

