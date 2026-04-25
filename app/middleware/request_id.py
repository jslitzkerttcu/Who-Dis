"""Request-ID propagation middleware.

Generates (or honors) an X-Request-ID per request and stamps it on every
log record via a logging.Filter. See plan 01-04 / OPS-02.
"""

import logging
import re
import uuid

from flask import Flask, g, request

logger = logging.getLogger(__name__)

# Accepts hex with optional dashes (covers UUID4 hex and dashed forms),
# 8-64 chars. Anything outside this charset is rejected and replaced with
# a server-generated UUID4 to prevent log-injection via newlines/control chars.
_UUID_HEX_RE = re.compile(r"^[0-9a-fA-F-]{8,64}$")


class RequestIdFilter(logging.Filter):
    """Injects ``g.request_id`` into every LogRecord as ``record.request_id``.

    Uses a sentinel ``"-"`` when no request context is active (e.g. log lines
    emitted from background threads or during app startup).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # Local import: filter may run outside a request/app context.
            from flask import g as _g

            record.request_id = getattr(_g, "request_id", "-")
        except RuntimeError:
            record.request_id = "-"
        return True

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return "RequestIdFilter"


def init_request_id(app: Flask) -> None:
    """Register before/after request hooks for request-ID propagation."""

    @app.before_request
    def _set_request_id() -> None:
        inbound = request.headers.get("X-Request-ID", "")
        if inbound and _UUID_HEX_RE.match(inbound):
            # Truncate defensively even though regex bounds it.
            g.request_id = inbound[:64]
        else:
            g.request_id = uuid.uuid4().hex

    @app.after_request
    def _echo_request_id(response):
        rid = getattr(g, "request_id", None)
        if rid:
            response.headers["X-Request-ID"] = rid
        return response
