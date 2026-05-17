"""
Reports Admin Module

Provides admin interface for viewing organization-wide reports including
license utilization, security posture (MFA + failed sign-ins), with
tabbed navigation, KPI cards, data tables, and CSV export.
"""

import csv
import io
import logging
from datetime import datetime
from typing import Optional

from flask import (
    abort,
    current_app,
    render_template,
    request,
    Response,
)

from app.middleware.auth import require_role
from app.models.report_cache import ReportCache

logger = logging.getLogger(__name__)


def _csv_safe(value: str) -> str:
    """Prevent CSV injection by prefixing dangerous characters with apostrophe."""
    if value and value[0] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def _validate_date(date_str: str) -> Optional[str]:
    """Validate and return ISO 8601 date string.

    Per T-08-04 threat mitigation: rejects non-ISO input before
    passing to Graph API OData filter.

    Args:
        date_str: Date string to validate.

    Returns:
        ISO formatted date string on success, None on invalid input.
    """
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.isoformat()
    except (ValueError, TypeError):
        return None


@require_role("admin")
def reports():
    """Main reports page with tabbed interface."""
    tab = request.args.get("tab", "licenses")
    if request.headers.get("HX-Request"):
        return _render_tab(tab)
    return render_template("admin/reports.html", active_tab=tab)


@require_role("admin")
def api_licenses_tab():
    """HTMX endpoint for license tab content."""
    return _render_licenses_tab()


@require_role("admin")
def api_security_tab():
    """HTMX endpoint for security tab content."""
    return _render_security_tab()


def _render_tab(tab: str) -> str:
    """Dispatch tab rendering to the appropriate handler.

    Args:
        tab: Tab identifier string.

    Returns:
        Rendered HTML partial for the requested tab.
    """
    tab_handlers = {
        "licenses": _render_licenses_tab,
        "security": _render_security_tab,
    }
    handler = tab_handlers.get(tab)
    if handler is None:
        abort(404)
    return handler()


def _render_licenses_tab() -> str:
    """Render the license utilization tab partial.

    Reads from ReportCache for KPI totals and per-SKU detail data.
    """
    totals_cache = ReportCache.get_cached("license_summary", "totals")
    sku_cache = ReportCache.get_cached("license_summary", "per_sku")

    return render_template(
        "admin/partials/_report_licenses.html",
        totals_cache=totals_cache,
        sku_cache=sku_cache,
    )


def _render_security_tab() -> str:
    """Render the security posture tab partial.

    Reads MFA data from ReportCache and failed sign-ins from
    report_sync_service with pagination support.
    """
    mfa_totals = ReportCache.get_cached("mfa_summary", "totals")
    mfa_users_without = ReportCache.get_cached("mfa_summary", "users_without")

    # Failed sign-ins with date filtering
    window = request.args.get("window", "72h")
    from_date_raw = request.args.get("from_date", "")
    to_date_raw = request.args.get("to_date", "")

    # Validate date inputs per T-08-06
    from_date = _validate_date(from_date_raw) if from_date_raw else None
    to_date = _validate_date(to_date_raw) if to_date_raw else None

    # Get sign-in data from service
    try:
        report_sync_service = current_app.container.get("report_sync_service")
        signin_data = report_sync_service.get_failed_signins(
            window=window,
            from_date=from_date,
            to_date=to_date,
        )
    except Exception as e:
        logger.error(f"Error fetching failed sign-ins: {e}", exc_info=True)
        signin_data = {"entries": [], "source": "error", "count": 0}

    # Paginate sign-in entries
    page = request.args.get("page", 1, type=int)
    per_page = 25
    entries = signin_data.get("entries", [])
    total = len(entries)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_entries = entries[start:end]

    pages = (total + per_page - 1) // per_page if total > 0 else 1
    pagination = {
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
        "has_prev": page > 1,
        "has_next": page < pages,
        "prev_num": page - 1 if page > 1 else None,
        "next_num": page + 1 if page < pages else None,
        "start_index": start + 1 if total > 0 else 0,
        "end_index": min(end, total),
    }

    return render_template(
        "admin/partials/_report_security.html",
        mfa_totals=mfa_totals,
        mfa_users_without=mfa_users_without,
        signin_entries=paginated_entries,
        signin_pagination=pagination,
        signin_source=signin_data.get("source", "unknown"),
        active_window=window,
        from_date=from_date_raw,
        to_date=to_date_raw,
    )


@require_role("admin")
def export_license_csv():
    """Export license utilization data as CSV.

    Returns CSV with metadata header rows and per-SKU detail rows.
    """
    sku_cache = ReportCache.get_cached("license_summary", "per_sku")
    if not sku_cache:
        abort(404)

    output = io.StringIO()
    writer = csv.writer(output)

    # Metadata rows
    writer.writerow(["Report: License Utilization"])
    generated_at = sku_cache.generated_at
    writer.writerow([
        f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M:%S UTC') if generated_at else 'N/A'}"
    ])
    writer.writerow([])

    # Header row
    writer.writerow([
        "SKU Name",
        "Assigned",
        "Available",
        "Consumed",
        "Utilization %",
        "Unused (30d)",
    ])

    # Data rows
    for sku in (sku_cache.data or []):
        assigned = sku.get("assigned", 0)
        available = sku.get("available", 0)
        utilization = (
            round(assigned / available * 100, 1) if available > 0 else 0.0
        )
        writer.writerow([
            _csv_safe(str(sku.get("sku_name", ""))),
            assigned,
            available,
            sku.get("consumed", 0),
            f"{utilization}%",
            sku.get("unused_30d", 0),
        ])

    csv_content = output.getvalue()
    output.close()

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=license_utilization.csv"
        },
    )


@require_role("admin")
def export_security_csv():
    """Export security posture data as CSV.

    Two sections: MFA summary (users without MFA) and failed sign-ins.
    """
    mfa_users_cache = ReportCache.get_cached("mfa_summary", "users_without")
    signin_cache = ReportCache.get_cached("signin_failures", "recent")

    if not mfa_users_cache and not signin_cache:
        abort(404)

    output = io.StringIO()
    writer = csv.writer(output)

    # Metadata rows
    writer.writerow(["Report: Security Posture"])
    generated_at = (
        mfa_users_cache.generated_at if mfa_users_cache else
        signin_cache.generated_at if signin_cache else None
    )
    writer.writerow([
        f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M:%S UTC') if generated_at else 'N/A'}"
    ])
    writer.writerow([])

    # MFA section
    writer.writerow(["--- Users Without MFA ---"])
    writer.writerow(["Display Name", "Email", "MFA Registered"])
    if mfa_users_cache and mfa_users_cache.data:
        for user in mfa_users_cache.data:
            writer.writerow([
                _csv_safe(str(user.get("userDisplayName", ""))),
                _csv_safe(str(user.get("userPrincipalName", ""))),
                "No",
            ])

    writer.writerow([])

    # Failed sign-ins section
    writer.writerow(["--- Failed Sign-ins ---"])
    writer.writerow(["User", "Email", "Timestamp", "Failure Reason", "IP Address"])
    if signin_cache and signin_cache.data:
        for entry in signin_cache.data:
            writer.writerow([
                _csv_safe(str(entry.get("userDisplayName", ""))),
                _csv_safe(str(entry.get("userPrincipalName", ""))),
                _csv_safe(str(entry.get("createdDateTime", ""))),
                _csv_safe(str(entry.get("failureReason", ""))),
                _csv_safe(str(entry.get("ipAddress", ""))),
            ])

    csv_content = output.getvalue()
    output.close()

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=security_posture.csv"
        },
    )
