"""SKU catalog cache service — daily refresh of /subscribedSkus from Graph.

Mirrors the `genesys_cache_db.py` pattern: stores Microsoft 365 SKU metadata in
the unified `external_service_data` table with `service_name='graph'`,
`data_type='sku'`. Provides GUID → friendly-name resolution for the UI in
Plan 03 of phase 06.

Per phase 06 D-04 / D-07: cache refreshes once per 24 hours via the existing
employee-profiles refresh loop. No new model, no new TTL layer, no new thread.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta

from flask import current_app
from sqlalchemy import text

from app.database import db
from app.services.base import BaseConfigurableService
from app.models.external_service import ExternalServiceData

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Service plan technical-name → friendly display-name mapping.
# Covers the ~50 most common plans seen in Microsoft 365 E3/E5/F1/Business
# tenants.  Unknown plans are humanized at runtime via _humanize_service_plan.
# ---------------------------------------------------------------------------
SERVICE_PLAN_FRIENDLY_NAMES: Dict[str, str] = {
    # Exchange
    "EXCHANGE_S_ENTERPRISE": "Exchange Online (Plan 2)",
    "EXCHANGE_S_STANDARD": "Exchange Online (Plan 1)",
    "EXCHANGE_S_DESKLESS": "Exchange Online Kiosk",
    "EXCHANGE_S_ARCHIVE_ADDON": "Exchange Online Archiving",
    # Teams
    "TEAMS1": "Microsoft Teams",
    "TEAMS_FREE": "Microsoft Teams (Free)",
    "TEAMS_AR_DOD": "Microsoft Teams (DoD)",
    "TEAMS_AR_GCCHIGH": "Microsoft Teams (GCC High)",
    # SharePoint
    "SHAREPOINTENTERPRISE": "SharePoint Online (Plan 2)",
    "SHAREPOINTSTANDARD": "SharePoint Online (Plan 1)",
    "SHAREPOINTWAC": "Office for the Web",
    # Office apps
    "OFFICESUBSCRIPTION": "Microsoft 365 Apps for Enterprise",
    "OFFICE_FORMS_PLAN_2": "Microsoft Forms (Plan 2)",
    # Skype / SfB
    "MCOSTANDARD": "Skype for Business Online (Plan 2)",
    "MCOIMP": "Skype for Business Online (Plan 1)",
    # Intune & EMS
    "INTUNE_A": "Microsoft Intune",
    "AAD_PREMIUM": "Microsoft Entra ID P1",
    "AAD_PREMIUM_P2": "Microsoft Entra ID P2",
    "AAD_BASIC": "Microsoft Entra ID Basic",
    "RMS_S_ENTERPRISE": "Azure Rights Management",
    "RMS_S_PREMIUM": "Azure Information Protection P1",
    "RMS_S_PREMIUM2": "Azure Information Protection P2",
    "MFA_PREMIUM": "Microsoft Entra Multifactor Authentication",
    # Power Platform
    "POWERAPPS_O365_P2": "Power Apps for Office 365",
    "POWERAPPS_O365_P3": "Power Apps for Office 365 (Plan 3)",
    "FLOW_O365_P2": "Power Automate for Office 365",
    "FLOW_O365_P3": "Power Automate for Office 365 (Plan 3)",
    "POWER_VIRTUAL_AGENTS_O365_P2": "Power Virtual Agents for Office 365",
    "CDS_O365_P2": "Common Data Service for Office 365",
    # Productivity
    "PROJECTWORKMANAGEMENT": "Microsoft Planner",
    "SWAY": "Sway",
    "YAMMER_ENTERPRISE": "Yammer Enterprise",
    "Deskless": "Microsoft StaffHub",
    "STREAM_O365_E3": "Microsoft Stream for Office 365",
    "STREAM_O365_E5": "Microsoft Stream for Office 365 E5",
    "FORMS_PLAN_E3": "Microsoft Forms (Plan E3)",
    "FORMS_PLAN_E5": "Microsoft Forms (Plan E5)",
    "WHITEBOARD_PLAN1": "Microsoft Whiteboard (Plan 1)",
    "WHITEBOARD_PLAN2": "Microsoft Whiteboard (Plan 2)",
    "WHITEBOARD_PLAN3": "Microsoft Whiteboard (Plan 3)",
    "KAIZALA_O365_P3": "Microsoft Kaizala Pro",
    "MICROSOFTBOOKINGS": "Microsoft Bookings",
    "MYANALYTICS_P2": "Viva Insights",
    # Security & Compliance
    "INFORMATION_BARRIERS": "Information Barriers",
    "CONTENT_EXPLORER": "Content Explorer",
    "DLP": "Data Loss Prevention",
    "ATP_ENTERPRISE": "Microsoft Defender for Office 365 (Plan 1)",
    "THREAT_INTELLIGENCE": "Microsoft Defender for Office 365 (Plan 2)",
    "ADALLOM_S_STANDALONE": "Microsoft Defender for Cloud Apps",
    "ATA": "Microsoft Defender for Identity",
    "MTP": "Microsoft 365 Defender",
    # Compliance
    "LOCKBOX_ENTERPRISE": "Customer Lockbox",
    "EQUIVIO_ANALYTICS": "Office 365 Advanced eDiscovery",
    "PAM_ENTERPRISE": "Privileged Access Management",
    # Misc
    "M365_LIGHTHOUSE_PARTNER_PLAN1": "Microsoft 365 Lighthouse (Partner)",
    "MICROSOFT_SEARCH": "Microsoft Search",
    "CORTEX": "Viva Topics",
    "PROJECT_O365_P2": "Project for Office 365 (Plan 2)",
    "PROJECT_O365_P3": "Project for Office 365 (Plan 3)",
    "VISIO_CLIENT_SUBSCRIPTION": "Visio (Plan 2)",
    "BI_AZURE_P2": "Power BI Pro",
    "BI_AZURE_P_2_GOV": "Power BI Pro (Government)",
    "PREMIUM_ENCRYPTION": "Microsoft 365 Advanced Message Encryption",
    "UNIVERSAL_PRINT_01": "Universal Print",
    "WIN10_PRO_ENT_SUB": "Windows 10/11 Enterprise",
    "WINDOWSUPDATEFORBUSINESS_DEPLOYMENTSERVICE": "Windows Update for Business",
    "CLIPCHAMP": "Microsoft Clipchamp",
    "LOOP_COMPONENT_1": "Microsoft Loop",
    "MESH_AVATARS_FOR_TEAMS": "Mesh Avatars for Teams",
    "MESH_AVATARS_ADDITIONAL_FOR_TEAMS": "Mesh Avatars (Additional)",
    "VIVA_LEARNING_SEEDED": "Viva Learning",
    "Nucleus": "Microsoft Viva Engage Core",
    "MCO_TEAMS_IW": "Microsoft Teams (Exploratory)",
}

# Priority ordering: plans are sorted so the most recognizable services
# appear first in the tooltip.
_PRIORITY_PLANS: List[str] = [
    "EXCHANGE_S_ENTERPRISE",
    "EXCHANGE_S_STANDARD",
    "TEAMS1",
    "SHAREPOINTENTERPRISE",
    "SHAREPOINTSTANDARD",
    "OFFICESUBSCRIPTION",
    "SHAREPOINTWAC",
    "INTUNE_A",
    "AAD_PREMIUM",
    "AAD_PREMIUM_P2",
    "RMS_S_ENTERPRISE",
    "MFA_PREMIUM",
    "ATP_ENTERPRISE",
    "THREAT_INTELLIGENCE",
]

# Pre-compiled regex for stripping trailing version suffixes during fallback
# humanization (e.g., _P1, _P2, _E3, _E5, _S1).
_VERSION_SUFFIX_RE = re.compile(r"[_\s](?:P\d+|E\d+|S\d+)$", re.IGNORECASE)

# Pre-built priority index for sorting (lower index = higher priority).
_PRIORITY_INDEX: Dict[str, int] = {
    name: idx for idx, name in enumerate(_PRIORITY_PLANS)
}
_PRIORITY_FALLBACK: int = len(_PRIORITY_PLANS)


def _humanize_service_plan(plan_name: str) -> str:
    """Return a friendly display name for a Microsoft service plan.

    Looks up *plan_name* in SERVICE_PLAN_FRIENDLY_NAMES first.  If no match
    is found, falls back to:
      1. Stripping trailing version suffixes (_P1, _P2, _E3, etc.)
      2. Replacing underscores with spaces
      3. Title-casing the result
    """
    friendly = SERVICE_PLAN_FRIENDLY_NAMES.get(plan_name)
    if friendly:
        return friendly

    # Fallback: humanize the technical name.
    cleaned = _VERSION_SUFFIX_RE.sub("", plan_name)
    return cleaned.replace("_", " ").strip().title()


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
            graph_service = current_app.container.get("graph_service")  # type: ignore[attr-defined]
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

    def get_sku_details(
        self, sku_id: str, plan_limit: int = 5
    ) -> Dict[str, Any]:
        """Return SKU name and service plans in a single DB lookup.

        Avoids the N+1 pattern of calling get_sku_name + get_service_plans
        separately for each license.

        Returns:
            ``{"name": "E3", "service_plans": {"plans": [...], "total": 8}}``
        """
        empty_plans: Dict[str, Any] = {"plans": [], "total": 0}
        try:
            entry = ExternalServiceData.get_by_service_id(
                "graph", "sku", sku_id
            )
            if entry is None:
                return {"name": None, "service_plans": empty_plans}

            name = entry.name
            if entry.raw_data is None:
                return {"name": name, "service_plans": empty_plans}

            service_plans = self._extract_service_plans(
                entry.raw_data, sku_id, plan_limit
            )
            return {"name": name, "service_plans": service_plans}

        except Exception as e:
            logger.error(
                f"Error fetching SKU details for {sku_id}: {str(e)}",
                exc_info=True,
            )
            return {"name": None, "service_plans": empty_plans}

    def get_service_plans(
        self, sku_id: str, limit: int = 5
    ) -> Dict[str, Any]:
        """Return humanized service plan names for a SKU.

        Extracts the ``servicePlans`` array from the cached Graph SKU JSON
        stored in ``external_service_data.raw_data``, filters to user-facing
        plans that are successfully provisioned, sorts by priority (well-known
        services first), then humanizes technical names.

        Returns:
            ``{"plans": ["Exchange Online (Plan 2)", ...], "total": 8}``
            where *plans* contains at most *limit* entries and *total* is the
            full count of qualifying plans.
        """
        empty: Dict[str, Any] = {"plans": [], "total": 0}
        try:
            entry = ExternalServiceData.get_by_service_id(
                "graph", "sku", sku_id
            )
            if entry is None or entry.raw_data is None:
                return empty

            return self._extract_service_plans(entry.raw_data, sku_id, limit)

        except Exception as e:
            logger.error(
                f"Error extracting service plans for SKU {sku_id}: {str(e)}",
                exc_info=True,
            )
            return empty

    def _extract_service_plans(
        self, raw_data: Dict[str, Any], sku_id: str, limit: int = 5
    ) -> Dict[str, Any]:
        """Extract, filter, sort, and humanize service plans from raw SKU data."""
        empty: Dict[str, Any] = {"plans": [], "total": 0}
        try:
            raw_plans: List[Dict[str, Any]] = raw_data.get(
                "servicePlans"
            ) or []

            filtered: List[Dict[str, Any]] = [
                p
                for p in raw_plans
                if isinstance(p, dict)
                and p.get("appliesTo") == "User"
                and p.get("provisioningStatus") == "Success"
            ]

            def _sort_key(plan: Dict[str, Any]) -> tuple:  # type: ignore[type-arg]
                name = plan.get("servicePlanName", "")
                return (
                    _PRIORITY_INDEX.get(name, _PRIORITY_FALLBACK),
                    name.lower(),
                )

            filtered.sort(key=_sort_key)

            humanized = [
                _humanize_service_plan(p.get("servicePlanName", ""))
                for p in filtered
            ]

            return {"plans": humanized[:limit], "total": len(humanized)}

        except Exception as e:
            logger.error(
                f"Error extracting service plans for SKU {sku_id}: {str(e)}",
                exc_info=True,
            )
            return empty
