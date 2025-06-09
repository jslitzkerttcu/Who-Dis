import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, TYPE_CHECKING
from flask import Flask

if TYPE_CHECKING:
    from app.container import ServiceContainer

from app.interfaces.token_service import ITokenService

logger = logging.getLogger(__name__)


class TokenRefreshService:
    """Background service to automatically refresh API tokens before they expire."""

    def __init__(
        self,
        container: Optional["ServiceContainer"] = None,
        app: Optional[Flask] = None,
    ):
        self.container = container
        self.app = app
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
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
            # Use dynamic service discovery if container is available
            if self.container:
                self._refresh_using_container()
            else:
                # Fallback to legacy hard-coded approach
                self._refresh_legacy()

    def _refresh_using_container(self):
        """Refresh tokens using dynamic service discovery via container."""
        from app.models.unified_cache import CacheEntry

        # Get all services that implement ITokenService
        if self.container is not None:
            token_services = self.container.get_all_by_interface(ITokenService)
        else:
            token_services = []

        for service in token_services:
            try:
                # Check if this service's token needs refresh
                token_entry = CacheEntry.get_token(service.token_service_name)

                if token_entry and hasattr(token_entry, "expires_at"):
                    now = datetime.now(timezone.utc)
                    expires_at = token_entry.expires_at

                    # Ensure timezone consistency
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)

                    time_until_expiry = expires_at - now

                    if time_until_expiry <= timedelta(minutes=10):
                        logger.info(
                            f"Token for {service.token_service_name} expires in {time_until_expiry}, refreshing..."
                        )

                        if service.refresh_token_if_needed():
                            logger.info(
                                f"Successfully refreshed {service.token_service_name} token"
                            )
                        else:
                            logger.error(
                                f"Failed to refresh {service.token_service_name} token"
                            )
                    else:
                        logger.debug(
                            f"Token for {service.token_service_name} is valid for {time_until_expiry}"
                        )

            except Exception as e:
                logger.error(
                    f"Error checking token for {getattr(service, 'token_service_name', 'unknown')}: {str(e)}"
                )

    def _refresh_legacy(self):
        """Legacy refresh method with hard-coded services."""
        from app.models.unified_cache import CacheEntry
        from app.services.genesys_service import genesys_service
        from app.services.graph_service import graph_service

        # Get all API tokens from the unified cache
        tokens = CacheEntry.query.filter_by(cache_type="api_token").all()

        for token in tokens:
            # Check if token expires within next 10 minutes
            now = datetime.now(timezone.utc)
            expires_at = token.expires_at

            # Ensure timezone consistency
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            time_until_expiry = expires_at - now

            if time_until_expiry <= timedelta(minutes=10):
                # Extract service name from cache_key
                service_name = token.cache_key
                logger.info(
                    f"Token for {service_name} expires in {time_until_expiry}, refreshing..."
                )

                # Refresh based on service
                if service_name == "genesys":
                    if genesys_service.refresh_token_if_needed():
                        logger.info("Successfully refreshed Genesys token")
                    else:
                        logger.error("Failed to refresh Genesys token")

                elif service_name == "microsoft_graph":
                    if graph_service.refresh_token_if_needed():
                        logger.info("Successfully refreshed Graph API token")
                    else:
                        logger.error("Failed to refresh Graph API token")
            else:
                logger.debug(
                    f"Token for {token.cache_key} is valid for {time_until_expiry}"
                )

            # Also check if Genesys cache needs refresh
            try:
                from app.services.genesys_cache_db import genesys_cache_db

                if genesys_cache_db.needs_refresh():
                    logger.info("Genesys cache needs refresh, starting refresh...")
                    results = genesys_cache_db.refresh_all_caches()
                    logger.info(f"Genesys cache refresh results: {results}")
            except Exception as e:
                logger.error(f"Error checking/refreshing Genesys cache: {str(e)}")

            # Also check if data warehouse cache needs refresh
            try:
                from app.services.data_warehouse_service import data_warehouse_service

                # Get cache stats to check if refresh is needed
                cache_stats = data_warehouse_service.get_cache_status()

                if cache_stats.get("needs_refresh", True):
                    logger.info(
                        "Data warehouse cache needs refresh, starting refresh..."
                    )
                    results = data_warehouse_service.refresh_cache()
                    logger.info(f"Data warehouse cache refresh results: {results}")
                else:
                    logger.debug("Data warehouse cache is up to date")
            except Exception as e:
                logger.error(
                    f"Error checking/refreshing data warehouse cache: {str(e)}"
                )


# Global instance - will be initialized with container in app factory
token_refresh_service = TokenRefreshService()
