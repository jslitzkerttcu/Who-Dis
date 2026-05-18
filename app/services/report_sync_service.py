"""
Report Sync Service

Aggregates license utilization and security data from Microsoft Graph
into the ReportCache model. Called by SandCastle scheduled jobs
(report_license_sync, report_security_sync).

Provides:
- sync_license_data: Fetches bulk users + SKUs, computes per-SKU summaries.
- sync_security_data: Fetches MFA registration + failed sign-ins, stores aggregates.
- get_failed_signins: Hybrid cache+live query per D-07.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from flask import current_app

from app.services.base import BaseConfigurableService
from app.utils.error_handler import handle_service_errors
from app.models.report_cache import ReportCache

logger = logging.getLogger(__name__)


class ReportSyncService(BaseConfigurableService):
    """Service for syncing report data from Graph API into ReportCache."""

    def __init__(self):
        super().__init__(config_prefix="reports")
        self._graph_service = None
        self._sku_catalog = None

    @property
    def graph_service(self):
        """Lazy-load graph_service from DI container."""
        if self._graph_service is None:
            self._graph_service = current_app.container.get("graph_service")
        return self._graph_service

    @property
    def sku_catalog(self):
        """Lazy-load sku_catalog from DI container."""
        if self._sku_catalog is None:
            self._sku_catalog = current_app.container.get("sku_catalog")
        return self._sku_catalog

    @handle_service_errors(raise_errors=False)
    def sync_license_data(self) -> Optional[Dict[str, Any]]:
        """Sync license utilization data from Graph API.

        Fetches all users with assigned licenses and the tenant SKU catalog,
        then computes per-SKU utilization summaries including 30-day unused
        detection via signInActivity.

        Stores:
        - "license_summary"/"per_sku" (ttl_hours=4): per-SKU detail list
        - "license_summary"/"totals" (ttl_hours=4): aggregate KPIs

        Returns:
            Dict with sync results metadata, or None on failure.
        """
        logger.info("Starting license data sync from Graph API")

        # Fetch all users with license assignments
        users = self.graph_service.get_all_users_with_licenses()
        if isinstance(users, dict) and "error" in users:
            logger.error(f"Permission error fetching users: {users}")
            return None

        # Fetch tenant SKU catalog
        skus = self.graph_service.get_subscribed_skus()
        if isinstance(skus, dict) and "error" in skus:
            logger.error(f"Permission error fetching SKUs: {skus}")
            return None

        if not skus:
            logger.warning("No SKUs returned from Graph API")
            return None

        # Build SKU ID -> friendly name map from sku_catalog service
        sku_name_map: Dict[str, str] = {}
        for sku in skus:
            sku_id = sku.get("skuId", "")
            # Use skuPartNumber as fallback name
            sku_name_map[sku_id] = self.sku_catalog.get_sku_name(
                sku_id
            ) or sku.get("skuPartNumber", sku_id)

        # Build per-SKU summary
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)

        # Count assigned users per SKU and detect unused
        sku_assigned: Dict[str, int] = {}
        sku_unused_30d: Dict[str, int] = {}

        for user in users:
            assigned_licenses = user.get("assignedLicenses", [])
            sign_in_activity = user.get("signInActivity", {}) or {}
            last_sign_in_str = sign_in_activity.get("lastSignInDateTime")

            # Determine if user is inactive (no sign-in in 30 days)
            is_inactive = True
            if last_sign_in_str:
                try:
                    last_sign_in = datetime.fromisoformat(
                        last_sign_in_str.replace("Z", "+00:00")
                    )
                    is_inactive = last_sign_in < thirty_days_ago
                except (ValueError, TypeError):
                    is_inactive = True

            for lic in assigned_licenses:
                sku_id = lic.get("skuId", "")
                if not sku_id:
                    continue
                sku_assigned[sku_id] = sku_assigned.get(sku_id, 0) + 1
                if is_inactive:
                    sku_unused_30d[sku_id] = sku_unused_30d.get(sku_id, 0) + 1

        # Build per-SKU detail list
        per_sku_data: List[Dict[str, Any]] = []
        total_assigned = 0
        total_unused_30d = 0

        for sku in skus:
            sku_id = sku.get("skuId", "")
            prepaid = sku.get("prepaidUnits", {})
            available = prepaid.get("enabled", 0)
            consumed = sku.get("consumedUnits", 0)
            assigned = sku_assigned.get(sku_id, 0)
            unused = sku_unused_30d.get(sku_id, 0)

            total_assigned += assigned
            total_unused_30d += unused

            per_sku_data.append({
                "sku_id": sku_id,
                "sku_name": sku_name_map.get(sku_id, sku_id),
                "available": available,
                "consumed": consumed,
                "assigned": assigned,
                "unused_30d": unused,
            })

        # Compute aggregate KPIs
        total_skus = len(per_sku_data)
        total_available = sum(s.get("available", 0) for s in per_sku_data)
        utilization_pct = (
            round(total_assigned / total_available * 100, 1)
            if total_available > 0
            else 0.0
        )

        totals_data = {
            "total_skus": total_skus,
            "total_assigned": total_assigned,
            "total_unused_30d": total_unused_30d,
            "utilization_pct": utilization_pct,
        }

        # Store in ReportCache (ttl_hours=4 per REPT-08)
        ReportCache.store("license_summary", "per_sku", per_sku_data, ttl_hours=4)
        ReportCache.store("license_summary", "totals", totals_data, ttl_hours=4)

        logger.info(
            f"License sync complete: {total_skus} SKUs, "
            f"{total_assigned} assigned, {total_unused_30d} unused 30d"
        )
        return {
            "total_skus": total_skus,
            "total_users_fetched": len(users),
            "total_assigned": total_assigned,
        }

    @handle_service_errors(raise_errors=False)
    def sync_security_data(self) -> Optional[Dict[str, Any]]:
        """Sync MFA registration and sign-in failure data from Graph API.

        Stores:
        - "mfa_summary"/"totals" (ttl_hours=1): aggregate MFA stats
        - "mfa_summary"/"users_without" (ttl_hours=1): list of users without MFA
        - "signin_failures"/"recent" (ttl_hours=1): 72h of failed sign-ins

        Returns:
            Dict with sync results metadata, or None on failure.
        """
        logger.info("Starting security data sync from Graph API")

        # --- MFA Registration ---
        mfa_details = self.graph_service.get_mfa_registration_details()
        if isinstance(mfa_details, dict) and "error" in mfa_details:
            logger.error(f"Permission error fetching MFA details: {mfa_details}")
            return None

        # Filter to member users only (exclude guests)
        member_users = [
            u for u in mfa_details
            if u.get("userType", "").lower() == "member"
        ]
        total_users = len(member_users)
        mfa_registered = sum(
            1 for u in member_users if u.get("isMfaRegistered") is True
        )
        mfa_pct = (
            round(mfa_registered / total_users * 100, 1)
            if total_users > 0
            else 0.0
        )

        users_without_mfa = [
            {
                "userPrincipalName": u.get("userPrincipalName", ""),
                "userDisplayName": u.get("userDisplayName", ""),
            }
            for u in member_users
            if u.get("isMfaRegistered") is not True
        ]

        mfa_totals = {
            "total_users": total_users,
            "mfa_registered": mfa_registered,
            "mfa_pct": mfa_pct,
        }

        ReportCache.store("mfa_summary", "totals", mfa_totals, ttl_hours=1)
        ReportCache.store(
            "mfa_summary", "users_without", users_without_mfa, ttl_hours=1,
        )

        # --- Failed Sign-ins (72h window) ---
        now = datetime.now(timezone.utc)
        from_date = (now - timedelta(hours=72)).strftime("%Y-%m-%dT%H:%M:%SZ")
        to_date = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        signin_failures = self.graph_service.get_failed_signins_bulk(
            from_date, to_date,
        )
        if isinstance(signin_failures, dict) and "error" in signin_failures:
            logger.error(
                f"Permission error fetching sign-in failures: {signin_failures}"
            )
            # Still store MFA data even if sign-ins fail
        else:
            ReportCache.store(
                "signin_failures", "recent", signin_failures, ttl_hours=1,
            )

        logger.info(
            f"Security sync complete: {total_users} users, "
            f"{mfa_registered} MFA registered, "
            f"{len(signin_failures) if isinstance(signin_failures, list) else 0} "
            f"failed sign-ins"
        )
        return {
            "total_users": total_users,
            "mfa_registered": mfa_registered,
            "signin_failures_count": (
                len(signin_failures) if isinstance(signin_failures, list) else 0
            ),
        }

    def get_failed_signins(
        self,
        window: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Hybrid query for failed sign-ins per D-07.

        For standard windows (24h, 72h, 7d, 30d): loads from ReportCache
        "signin_failures"/"recent" and filters in Python by window.

        If cache is stale or custom date range provided: calls
        graph_service.get_failed_signins_bulk() directly.

        Args:
            window: One of "24h", "72h", "7d", "30d" (optional).
            from_date: Custom start date ISO 8601 (optional).
            to_date: Custom end date ISO 8601 (optional).

        Returns:
            Dict with keys: entries (list), source ("cache" or "live"), count.
        """
        # Custom date range always goes live
        if from_date and to_date:
            entries = self.graph_service.get_failed_signins_bulk(from_date, to_date)
            if isinstance(entries, dict) and "error" in entries:
                return {"entries": [], "source": "error", "count": 0, "error": entries}
            return {"entries": entries, "source": "live", "count": len(entries)}

        # Try cache first for standard windows
        cached = ReportCache.get_cached("signin_failures", "recent")

        if cached and not cached.is_stale:
            all_entries = cached.data or []

            # Filter by window in Python
            if window:
                now = datetime.now(timezone.utc)
                window_map = {
                    "24h": timedelta(hours=24),
                    "72h": timedelta(hours=72),
                    "7d": timedelta(days=7),
                    "30d": timedelta(days=30),
                }
                delta = window_map.get(window, timedelta(hours=72))
                cutoff = now - delta
                cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

                filtered = [
                    e for e in all_entries
                    if (e.get("createdDateTime", "") >= cutoff_str)
                ]
                return {
                    "entries": filtered,
                    "source": "cache",
                    "count": len(filtered),
                }

            return {
                "entries": all_entries,
                "source": "cache",
                "count": len(all_entries),
            }

        # Cache stale or missing — fetch live
        now = datetime.now(timezone.utc)
        window_map = {
            "24h": timedelta(hours=24),
            "72h": timedelta(hours=72),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
        }
        delta = window_map.get(window or "72h", timedelta(hours=72))
        live_from = (now - delta).strftime("%Y-%m-%dT%H:%M:%SZ")
        live_to = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        entries = self.graph_service.get_failed_signins_bulk(live_from, live_to)
        if isinstance(entries, dict) and "error" in entries:
            return {"entries": [], "source": "error", "count": 0, "error": entries}
        return {"entries": entries, "source": "live", "count": len(entries)}
