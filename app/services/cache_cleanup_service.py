"""Background service that prunes expired SearchCache rows on an hourly cadence.

Implements DEBT-03 per Phase 1 plan 01-02. Mirrors the lifecycle pattern of
``app/services/token_refresh_service.py`` (idempotent ``start()``, daemon
thread, app-context wrapped per-iteration body) so operators see a uniform
contract across background services.

The service exposes ``run_now()`` for the admin "Run now" route, which calls
``_cleanup()`` synchronously inside the existing Flask request context and
returns ``(deleted_count, duration_ms)``.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from flask import Flask

if TYPE_CHECKING:
    from app.container import ServiceContainer

logger = logging.getLogger(__name__)


class CacheCleanupService:
    """Hourly background pruner for expired ``SearchCache`` rows."""

    def __init__(
        self,
        container: Optional["ServiceContainer"] = None,
        app: Optional[Flask] = None,
    ) -> None:
        self.container = container
        self.app = app
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        # Run hourly per D-13 / DEBT-03.
        self.check_interval = 3600

    def init_app(self, app: Flask) -> None:
        """Bind a Flask app for the background thread's app_context wrapping."""
        self.app = app

    def start(self) -> None:
        """Start the background cleanup thread (idempotent)."""
        if self.is_running:
            logger.warning("Cache cleanup service is already running")
            return

        self.is_running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("Cache cleanup service started")

    def stop(self) -> None:
        """Signal the background thread to exit on its next loop iteration."""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Cache cleanup service stopped")

    def _run(self) -> None:
        """Main loop: cleanup → sleep, swallowing exceptions to keep cadence."""
        while self.is_running:
            try:
                if not self.app:
                    logger.warning("Cache cleanup service has no Flask app configured")
                else:
                    with self.app.app_context():
                        deleted, duration_ms = self._cleanup()
                        logger.info(
                            "Cache cleanup removed %d expired rows in %.1fms",
                            deleted,
                            duration_ms,
                        )
            except Exception as e:
                # Per T-01-02-03 (DoS mitigation): never let the thread die.
                logger.error(f"Error in cache cleanup service: {str(e)}", exc_info=True)

            time.sleep(self.check_interval)

    def _cleanup(self) -> tuple[int, float]:
        """Delete all rows where ``expires_at < now``.

        Returns:
            (deleted_count, duration_ms)
        """
        from app.database import db
        from app.models.cache import SearchCache

        start = time.perf_counter()
        deleted = SearchCache.query.filter(
            SearchCache.expires_at < datetime.utcnow()
        ).delete(synchronize_session=False)
        db.session.commit()
        duration_ms = (time.perf_counter() - start) * 1000
        return deleted, duration_ms

    def run_now(self) -> tuple[int, float]:
        """Synchronous public entry point for the admin Run-now route.

        The Flask request handler already provides an app context, so we do not
        wrap with ``app_context()`` here.
        """
        return self._cleanup()
