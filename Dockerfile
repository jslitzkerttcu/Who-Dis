# Phase 9 — SandCastle Dockerfile for Who-Dis (WD-CONT-01..05, WD-HEALTH-04)
FROM python:3.12-slim

# Non-root user (WD-CONT-01)
RUN groupadd -r app && useradd -r -g app -u 10001 app

WORKDIR /app

# Runtime tools only — apt resolves the rest as transitive deps:
#   - curl pulls in libldap2 + libsasl2-2 (used by HEALTHCHECK)
#   - postgresql-client pulls in libpq5 (used by entrypoint schema guard)
# ldap3 is pure Python (no OpenLDAP C dep) and psycopg2-binary ships its
# own libpq, so neither needs an explicit apt entry. Per Gemini PR #28
# review — keeps the image resilient to upstream package renames
# (libldap-2.5-0 -> libldap2 churn on bookworm -> trixie).
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl postgresql-client \
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
