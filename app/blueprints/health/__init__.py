"""Health-check blueprint (OPS-01).

Provides two unauthenticated endpoints for monitoring tooling:

- ``GET /health/live`` — shallow liveness probe; only proves the Python
  process is up, no DB or external service calls.
- ``GET /health`` — deep probe that executes ``SELECT 1`` against the
  primary database and returns latency in milliseconds. Returns HTTP 503
  if the database is unreachable.

Per phase-01 decisions D-11 and D-12 these routes MUST remain
unauthenticated and MUST NOT call LDAP, Microsoft Graph, or Genesys —
external monitors (Azure App Service, uptime checks) need a fast probe
that does not depend on Azure AD SSO or upstream identity providers.
"""

import logging
import time

from flask import Blueprint, g, jsonify
from sqlalchemy import text

from app.database import db
from app.utils.error_handler import handle_errors

logger = logging.getLogger(__name__)

health_bp = Blueprint("health", __name__)

# Static version string for now; a future phase will wire this from
# package metadata / build info.
APP_VERSION = "3.0.0-phase1"


@health_bp.route("/health/live", methods=["GET"])
@handle_errors(json_response=True)
def liveness():
    """Shallow liveness probe — process-up only, no DB."""
    return jsonify({"status": "ok"}), 200


@health_bp.route("/health", methods=["GET"])
@handle_errors(json_response=True)
def health():
    """Deep health probe with database connectivity check.

    Returns 200 with database latency when the DB is reachable, 503
    when the ``SELECT 1`` probe fails. Response body intentionally omits
    DSN, credentials, and row counts (T-01-03-01) and truncates error
    text to 200 chars.
    """
    start = time.perf_counter()
    try:
        db.session.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return jsonify(
            {
                "status": "ok",
                "database": {"connected": True, "latency_ms": latency_ms},
                "version": APP_VERSION,
                "request_id": getattr(g, "request_id", None),
            }
        ), 200
    except Exception as exc:
        logger.error("Health check DB probe failed: %s", exc, exc_info=True)
        return jsonify(
            {
                "status": "degraded",
                "database": {"connected": False, "error": str(exc)[:200]},
                "version": APP_VERSION,
                "request_id": getattr(g, "request_id", None),
            }
        ), 503
