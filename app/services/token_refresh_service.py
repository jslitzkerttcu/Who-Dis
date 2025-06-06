import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional
from flask import Flask

logger = logging.getLogger(__name__)


class TokenRefreshService:
    """Background service to automatically refresh API tokens before they expire."""

    def __init__(self, app: Optional[Flask] = None):
        self.app = app
        self.is_running = False
        self.thread = None
        self.check_interval = 300  # Check every 5 minutes

    def init_app(self, app: Flask):
        """Initialize the service with a Flask app."""
        self.app = app

    def start(self):
        """Start the background token refresh thread."""
        if self.is_running:
            logger.warning("Token refresh service is already running")
            return

        self.is_running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("Token refresh service started")

    def stop(self):
        """Stop the background token refresh thread."""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Token refresh service stopped")

    def _run(self):
        """Main loop for the background thread."""
        while self.is_running:
            try:
                self._check_and_refresh_tokens()
            except Exception as e:
                logger.error(f"Error in token refresh service: {str(e)}")

            # Sleep for the check interval
            time.sleep(self.check_interval)

    def _check_and_refresh_tokens(self):
        """Check all tokens and refresh those that are expiring soon."""
        if not self.app:
            logger.warning("No Flask app configured for token refresh service")
            return

        with self.app.app_context():
            from app.models import ApiToken
            from app.services.genesys_service import genesys_service
            from app.services.graph_service import graph_service

            # Get all tokens
            tokens = ApiToken.query.all()

            for token in tokens:
                # Check if token expires within next 10 minutes
                time_until_expiry = token.expires_at - datetime.utcnow()

                if time_until_expiry <= timedelta(minutes=10):
                    logger.info(
                        f"Token for {token.service_name} expires in {time_until_expiry}, refreshing..."
                    )

                    # Refresh based on service
                    if token.service_name == "genesys":
                        if genesys_service.refresh_token_if_needed():
                            logger.info("Successfully refreshed Genesys token")
                        else:
                            logger.error("Failed to refresh Genesys token")

                    elif token.service_name == "microsoft_graph":
                        if graph_service.refresh_token_if_needed():
                            logger.info("Successfully refreshed Graph API token")
                        else:
                            logger.error("Failed to refresh Graph API token")
                else:
                    logger.debug(
                        f"Token for {token.service_name} is valid for {time_until_expiry}"
                    )

            # Also check if Genesys cache needs refresh
            try:
                from app.services.genesys_cache_db import genesys_cache_db

                if genesys_cache_db.needs_refresh():
                    logger.info("Genesys cache needs refresh, starting refresh...")
                    results = genesys_cache_db.refresh_all()
                    logger.info(f"Genesys cache refresh results: {results}")
            except Exception as e:
                logger.error(f"Error checking/refreshing Genesys cache: {str(e)}")


# Global instance
token_refresh_service = TokenRefreshService()
