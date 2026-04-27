"""SKU catalog cache service — daily refresh of /subscribedSkus from Graph.

Mirrors the `genesys_cache_db.py` pattern: stores Microsoft 365 SKU metadata in
the unified `external_service_data` table with `service_name='graph'`,
`data_type='sku'`. Provides GUID → friendly-name resolution for the UI in
Plan 03 of phase 06.

Per phase 06 D-04 / D-07: cache refreshes once per 24 hours via the existing
employee-profiles refresh loop. No new model, no new TTL layer, no new thread.
"""

import logging
from typing import Optional
from datetime import datetime, timezone, timedelta

from flask import current_app
from sqlalchemy import text

from app.database import db
from app.services.base import BaseConfigurableService
from app.models.external_service import ExternalServiceData

logger = logging.getLogger(__name__)


class SkuCatalogCache(BaseConfigurableService):
    """Database-backed Microsoft 365 SKU GUID → friendly name catalog (24h TTL)."""

    def __init__(self):
        super().__init__(config_prefix="graph")

    @property
    def refresh_period_hours(self) -> int:
        """Refresh cadence in hours (default 24, configurable via graph.sku_cache_refresh_hours)."""
        return int(self._get_config("sku_cache_refresh_hours", "24"))

    def needs_refresh(self) -> bool:
        """Return True if no SKU rows exist or the newest row is older than refresh_period_hours."""
        try:
            result = db.session.execute(
                text(
                    "SELECT MAX(updated_at) FROM external_service_data "
                    "WHERE service_name = 'graph' AND data_type = 'sku'"
                )
            ).scalar()

            if not result:
                return True  # No data, needs refresh

            last_update = result
            now = datetime.now(timezone.utc)
            if last_update.tzinfo is None:
                last_update = last_update.replace(tzinfo=timezone.utc)

            cutoff = now - timedelta(hours=self.refresh_period_hours)
            needs_update = last_update < cutoff
            logger.debug(
                f"SKU cache last updated {last_update.isoformat()}; "
                f"needs refresh: {needs_update}"
            )
            return bool(needs_update)

        except Exception as e:
            logger.error(f"Error checking SKU cache refresh status: {e}")
            return True

    def refresh(self) -> None:
        """Refresh the SKU catalog from Graph /subscribedSkus.

        Called daily by the existing employee-profiles refresh loop. Failures are
        logged and swallowed so a SKU-cache failure cannot crash the parent job.
        """
        try:
            graph_service = current_app.container.get("graph_service")
            result = graph_service.get_subscribed_skus()

            if result is None:
                logger.error("SKU refresh aborted: graph_service returned None")
                return

            # Permission-missing sentinel (D-06 graceful degradation)
            if isinstance(result, dict) and result.get("error") == "permission_missing":
                logger.error(
                    f"SKU refresh aborted: missing Graph permission "
                    f"{result.get('permission')}"
                )
                return

            count = 0
            for sku in result:
                sku_id = sku.get("skuId")
                if not sku_id:
                    continue
                ExternalServiceData.update_service_data(
                    service_name="graph",
                    data_type="sku",
                    service_id=sku_id,
                    name=sku.get("skuPartNumber"),
                    description=sku.get("displayName"),
                    raw_data=sku,
                )
                count += 1

            db.session.commit()
            logger.info(f"SKU catalog refreshed: {count} SKUs")

        except Exception as e:
            logger.error(f"Error refreshing SKU catalog: {str(e)}", exc_info=True)
            try:
                db.session.rollback()
            except Exception:
                pass
            # Do NOT re-raise — daily refresh loop must continue past a SKU-cache failure.

    def get_sku_name(self, sku_id: str) -> Optional[str]:
        """Resolve a SKU GUID to its friendly skuPartNumber, or None if unknown."""
        return ExternalServiceData.get_name_by_id("graph", "sku", sku_id)
