# Phase 9 — SandCastle Dockerfile for Who-Dis (WD-CONT-01..05, WD-HEALTH-04)
FROM python:3.12-slim

# Non-root user (WD-CONT-01)
RUN groupadd -r app && useradd -r -g app -u 10001 app

WORKDIR /app

# Runtime tools + ODBC Driver 18 for Azure SQL (Keystone data warehouse via pyodbc)
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl postgresql-client unixodbc-dev gnupg2 \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
       | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
       > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && apt-get purge -y gnupg2 \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Production deps only (WD-CONT-03 — no dev/test deps; image < 500 MB target)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x ./docker-entrypoint.sh \
    && chown -R app:app /app

USER app
EXPOSE 5000

# WD-HEALTH-04 — every 30s with 10s timeout, 20s start grace, 3 retries
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:5000/health || exit 1

ENV FLASK_ENV=production \
    GUNICORN_WORKERS=2 \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["./docker-entrypoint.sh"]
