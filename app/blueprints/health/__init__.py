"""Health-check blueprint — SandCastle contract (WD-HEALTH-01, WD-HEALTH-02).

Three unauthenticated endpoints, all returning JSON to stdout-aware monitors:

- ``GET /health``      — shallow probe; Python process is up. Returns 200 + {"status": "healthy"}.
                          Used by SandCastle portal poller and Dockerfile HEALTHCHECK.
- ``GET /health/ready``— deep readiness probe; executes ``SELECT 1`` against the
                          primary database. 200 if DB reachable, 503 otherwise.
- ``GET /health/live`` — DEPRECATED alias for ``/health``; kept for one release for
                          any external monitor still pointing at the pre-Phase-9 path.

Per phase-01 D-11/D-12 (project-wide) these routes MUST remain unauthenticated
and MUST NOT call LDAP, Microsoft Graph, or Genesys.
"""

import logging
import time

from flask import Blueprint, g, jsonify
from sqlalchemy import text

from app.database import db
from app.utils.error_handler import handle_errors

logger = logging.getLogger(__name__)

health_bp = Blueprint("health", __name__)

APP_VERSION = "3.0.0-sandcastle"


@health_bp.route("/health", methods=["GET"])
@handle_errors(json_response=True)
def health():
    """Shallow liveness probe (WD-HEALTH-01) — process up, no DB call."""
    return jsonify({"status": "healthy"}), 200


@health_bp.route("/health/live", methods=["GET"])
@handle_errors(json_response=True)
def liveness_alias():
    """Deprecated pre-Phase-9 alias for /health. Kept one release; remove afterwards."""
    return jsonify({"status": "healthy"}), 200


@health_bp.route("/health/ready", methods=["GET"])
@handle_errors(json_response=True)
def readiness():
    """Deep readiness probe (WD-HEALTH-02) — 200 if DB reachable, 503 otherwise."""
    start = time.perf_counter()
    try:
        db.session.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return jsonify(
            {
                "status": "ready",
                "database": {"connected": True, "latency_ms": latency_ms},
                "version": APP_VERSION,
                "request_id": getattr(g, "request_id", None),
            }
        ), 200
    except Exception as exc:
        logger.error("Readiness DB probe failed: %s", exc, exc_info=True)
        return jsonify(
            {
                "status": "degraded",
                "database": {"connected": False, "error": str(exc)[:200]},
                "version": APP_VERSION,
                "request_id": getattr(g, "request_id", None),
            }
        ), 503
