# ── SAFAR – Coolify Deployment Dockerfile ────────────────────────────────────
# Multi-stage build: keeps the final image lean.
# Stage 1: builder — install dependencies
# Stage 2: runtime — run the application
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system deps needed to compile any C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
 && rm -rf /var/lib/apt/lists/*

# Copy requirements first (layer-cache friendly)
COPY requirements.txt .

# Install into a local prefix so we can copy cleanly
RUN pip install --upgrade pip \
 && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="SAFAR Team"
LABEL description="SAFAR – TravelTogether & Astra Safety Platform"

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Create the instance directory (SQLite fallback needs it)
RUN mkdir -p instance

# ── Environment defaults (override these in Coolify's Environment Variables UI)
# These are safe non-secret defaults; real secrets go in Coolify's env panel.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DB_PROBE=1 \
    DB_CONNECT_TIMEOUT=5

# Expose the port Coolify's reverse-proxy will route to
EXPOSE 8000

# ── Health check (Coolify uses this to know when the app is ready) ────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/')" || exit 1

# ── Startup: initialise DB tables then launch gunicorn ───────────────────────
# gunicorn flags:
#   --worker-class gthread   — same as Render config, compatible with Flask-SocketIO threading mode
#   --threads 4              — good default for a small Coolify instance; tune via GUNICORN_THREADS env var
#   --timeout 120            — generous timeout for DB probes on cold start
#   --bind 0.0.0.0:$PORT     — Coolify injects $PORT (default 8000)
CMD python -c "from app import init_db; init_db()" && \
    exec gunicorn \
      --worker-class gthread \
      --threads ${GUNICORN_THREADS:-4} \
      --workers ${GUNICORN_WORKERS:-1} \
      --timeout 120 \
      --bind "0.0.0.0:${PORT}" \
      app:app
