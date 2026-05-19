# Phase 12 — Multi-stage Dockerfile for Who-Dis
# Builder stage: install ODBC driver and compile pip packages
# Runtime stage: minimal image with only runtime dependencies

# ── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Build-only tools: gnupg2 for GPG key verification, curl for key download,
# unixodbc-dev for pyodbc C extension compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
      gnupg2 curl unixodbc-dev \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
       | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
       > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into isolated prefix for clean copy to runtime
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim

# Non-root user (WD-CONT-01)
RUN groupadd -r app && useradd -r -g app -u 10001 app

WORKDIR /app

# Runtime-only system deps: unixodbc for ODBC shared libs, postgresql-client
# for pg_isready in docker-entrypoint.sh (WD-DB-02)
# NOTE: gnupg2, curl, and unixodbc-dev are NOT installed here
RUN apt-get update && apt-get install -y --no-install-recommends \
      unixodbc postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy ODBC Driver 18 binaries and registration from builder
# (avoids re-downloading and needing gnupg2/curl in runtime)
COPY --from=builder /opt/microsoft /opt/microsoft
COPY --from=builder /etc/odbcinst.ini /etc/odbcinst.ini

# Copy compiled pip packages from builder
COPY --from=builder /install /usr/local

# Copy requirements.txt first for layer cache optimization (DEVOPS-03)
COPY requirements.txt .

# Copy application source code (last to maximize cache hits on rebuilds)
COPY . .

# Place healthcheck script outside app dir for clean separation
COPY scripts/docker_healthcheck.py /usr/local/bin/healthcheck.py

RUN chmod +x ./docker-entrypoint.sh \
    && chown -R app:app /app

USER app
EXPOSE 5000

# WD-HEALTH-04 — Python urllib healthcheck replaces curl dependency
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD python /usr/local/bin/healthcheck.py || exit 1

ENV FLASK_ENV=production \
    GUNICORN_WORKERS=2 \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["./docker-entrypoint.sh"]
