"""
Database management functionality for admin blueprint.
Handles database health checks, table statistics, optimization, and session management.
"""

from flask import render_template, jsonify, request, Response
from app.middleware.auth import require_role
from app.database import db
from datetime import datetime, timedelta, timezone
from io import StringIO
import csv
import json
import os
import pytz
from app.utils.timezone import format_timestamp, format_timestamp_long


@require_role("admin")
def database():
    """Display database management page."""
    return render_template("admin/database.html")


@require_role("admin")
def database_health():
    """Get database health and connection stats."""
    from sqlalchemy import text

    try:
        # Check database connection
        db.session.execute(text("SELECT 1"))
        db_status = "healthy"

        # Check if we're using PostgreSQL
        db_url = str(db.engine.url)
        is_postgres = db_url.startswith("postgresql")

        if is_postgres:
            # Get PostgreSQL database size
            result = db.session.execute(
                text("SELECT pg_database_size(current_database()) as size")
            ).first()
            db_size_bytes = result.size if result else 0

            # Format size
            if db_size_bytes > 1024 * 1024 * 1024:
                db_size = f"{db_size_bytes / (1024 * 1024 * 1024):.2f} GB"
            else:
                db_size = f"{db_size_bytes / (1024 * 1024):.2f} MB"
        else:
            # For SQLite, get file size
            db_path = db_url.replace("sqlite:///", "")
            if os.path.exists(db_path):
                db_size_bytes = os.path.getsize(db_path)
                if db_size_bytes > 1024 * 1024:
                    db_size = f"{db_size_bytes / (1024 * 1024):.2f} MB"
                else:
                    db_size = f"{db_size_bytes / 1024:.2f} KB"
            else:
                db_size = "Unknown"

        # Get connection stats
        try:
            pool = db.engine.pool
            # Use getattr for dynamic attributes that mypy doesn't know about
            active_connections = getattr(pool, "checkedout", lambda: 0)()
            pool_size = getattr(pool, "size", lambda: 0)()
            pool_usage = f"{active_connections}/{pool_size}"
            overflow = getattr(pool, "overflow", lambda: 0)()
            max_connections = pool_size + overflow
        except Exception:
            # Fallback for SQLite or when pool stats aren't available
            active_connections = 1
            pool_usage = "N/A"
            max_connections = "N/A"

        # Check if this is an Htmx request
        if request.headers.get("HX-Request"):
            return _render_database_health(
                {
                    "status": db_status,
                    "database_type": "PostgreSQL" if is_postgres else "SQLite",
                    "database_size": db_size,
                    "active_connections": active_connections,
                    "pool_usage": pool_usage,
                    "max_connections": max_connections,
                }
            )

        return jsonify(
            {
                "status": db_status,
                "database_type": "PostgreSQL" if is_postgres else "SQLite",
                "database_size": db_size,
                "active_connections": active_connections,
                "pool_usage": pool_usage,
                "max_connections": max_connections,
            }
        )
    except Exception as e:
        if request.headers.get("HX-Request"):
            return _render_database_health(
                {
                    "status": "unhealthy",
                    "error": str(e),
                    "database_size": "--",
                    "active_connections": 0,
                    "pool_usage": "--",
                }
            )

        return jsonify(
            {
                "status": "unhealthy",
                "error": str(e),
                "database_size": "--",
                "active_connections": 0,
                "pool_usage": "--",
            }
        )


@require_role("admin")
def database_tables():
    """Get table statistics."""
    from sqlalchemy import text, inspect

    try:
        # Check if we're using PostgreSQL
        db_url = str(db.engine.url)
        is_postgres = db_url.startswith("postgresql")

        tables = []

        if is_postgres:
            # PostgreSQL-specific query - use pg_class which is more reliable
            query = text("""
                SELECT 
                    n.nspname as schemaname,
                    c.relname as tablename,
                    CASE 
                        WHEN c.reltuples < 0 THEN 0
                        ELSE c.reltuples::bigint 
                    END as row_count,
                    pg_size_pretty(pg_total_relation_size(c.oid)) as size,
                    s.last_vacuum,
                    s.last_autovacuum,
                    s.n_live_tup as live_tuples
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                LEFT JOIN pg_stat_user_tables s ON s.schemaname = n.nspname AND s.relid = c.oid
                WHERE n.nspname = 'public' 
                AND c.relkind = 'r'
                ORDER BY c.relname
            """)

            results = db.session.execute(query)

            for row in results:
                last_activity = row.last_autovacuum or row.last_vacuum
                if last_activity:
                    last_activity = last_activity.strftime("%Y-%m-%d %H:%M")

                # Use live_tuples if available and row_count is 0 or -1
                actual_count = row.row_count
                if row.live_tuples is not None and (row.row_count <= 0):
                    actual_count = row.live_tuples

                # For certain tables, get actual count since estimates can be wrong
                if (
                    row.tablename
                    in [
                        "genesys_groups",
                        "genesys_locations",
                        "genesys_skills",
                        "graph_photos",
                        "user_sessions",
                        "search_cache",
                    ]
                    or actual_count <= 0
                ):
                    try:
                        # Use parameterized query with proper identifier quoting
                        # Get quoted table name safely
                        quoted_name_result = db.session.execute(
                            text("SELECT quote_ident(:table_name)"),
                            {"table_name": row.tablename},
                        ).scalar()
                        quoted_name = quoted_name_result or row.tablename
                        count_result = db.session.execute(
                            text(f"SELECT COUNT(*) as count FROM {quoted_name}")
                        ).first()
                        actual_count = count_result.count if count_result else 0
                    except Exception:
                        # If count fails, keep the estimate
                        pass

                tables.append(
                    {
                        "name": row.tablename,
                        "row_count": actual_count,
                        "size": row.size,
                        "last_activity": last_activity,
                    }
                )
        else:
            # Fallback for SQLite or other databases
            inspector = inspect(db.engine)
            table_names = inspector.get_table_names()

            for table_name in table_names:
                # Get row count using safe table name escaping
                from sqlalchemy.sql import quoted_name

                safe_table = quoted_name(table_name, quote=True)
                count_result = db.session.execute(
                    text(f"SELECT COUNT(*) as count FROM {safe_table}")
                ).first()
                row_count = count_result.count if count_result else 0

                # For SQLite, we can't get accurate size, so use row count as estimate
                # Ensure row_count is an int for comparisons
                row_count_int = (
                    int(row_count) if isinstance(row_count, (int, float)) else 0
                )
                if row_count_int > 1000000:
                    size_est = f"{row_count_int / 1000000:.1f}M rows"
                elif row_count_int > 1000:
                    size_est = f"{row_count_int / 1000:.1f}K rows"
                else:
                    size_est = f"{row_count_int} rows"

                tables.append(
                    {
                        "name": table_name,
                        "row_count": row_count,
                        "size": size_est,
                        "last_activity": "N/A",
                    }
                )

            # Sort by row count descending
            tables.sort(key=lambda x: x["row_count"], reverse=True)

        # Check if this is an Htmx request
        if request.headers.get("HX-Request"):
            return _render_table_statistics(tables)

        return jsonify({"tables": tables})
    except Exception as e:
        # Log the full error for debugging
        import traceback
        from flask import current_app

        current_app.logger.error(f"Error getting table statistics: {str(e)}")
        current_app.logger.error(traceback.format_exc())

        # Try a simple fallback - just list table names
        try:
            inspector = inspect(db.engine)
            table_names = inspector.get_table_names()

            tables = []
            for table_name in table_names:
                tables.append(
                    {
                        "name": table_name,
                        "row_count": "Unknown",
                        "size": "Unknown",
                        "last_activity": "N/A",
                    }
                )

            return jsonify(
                {
                    "tables": tables,
                    "warning": "Limited statistics available - database may not be fully initialized",
                }
            )
        except Exception:
            return jsonify({"error": str(e), "tables": []})


@require_role("admin")
def error_stats():
    """Get error log statistics."""
    # Check if this is an Htmx request
    if request.headers.get("HX-Request"):
        return _render_error_stats()

    from app.models import ErrorLog

    try:
        # Recent errors (last hour)
        recent_errors = ErrorLog.query.filter(
            ErrorLog.timestamp > datetime.utcnow() - timedelta(hours=1)
        ).count()

        # Last 24 hours
        errors_24h = ErrorLog.query.filter(
            ErrorLog.timestamp > datetime.utcnow() - timedelta(days=1)
        ).count()

        return jsonify({"recent_errors": recent_errors, "errors_24h": errors_24h})
    except Exception as e:
        return jsonify({"recent_errors": 0, "errors_24h": 0, "error": str(e)})


@require_role("admin")
def session_stats():
    """Get active session statistics."""
    # Check if this is an Htmx request
    if request.headers.get("HX-Request"):
        return _render_session_stats()

    from app.models import UserSession

    try:
        # Active sessions (activity in last 30 minutes)
        now = datetime.now(timezone.utc)
        active_sessions = UserSession.query.filter(
            UserSession.last_activity > now - timedelta(minutes=30),
            UserSession.is_active.is_(True),
        ).count()

        return jsonify({"active_sessions": active_sessions})
    except Exception as e:
        return jsonify({"active_sessions": 0, "error": str(e)})


@require_role("admin")
def cache_status():
    """Get cache status for all caches."""
    # Check if this is an Htmx request
    if request.headers.get("HX-Request"):
        return _render_cache_status()

    # JSON response for non-Htmx requests
    from app.models import SearchCache, ApiToken
    from app.services.genesys_cache_db import genesys_cache_db

    try:
        search_cache_count = SearchCache.query.count()
        tokens = ApiToken.get_all_tokens_status()
        genesys_cache = genesys_cache_db.get_cache_status()

        return jsonify(
            {
                "search_cache_count": search_cache_count,
                "tokens": tokens,
                "genesys_cache": genesys_cache,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@require_role("admin")
def refresh_cache(cache_type):
    """Refresh a specific cache."""
    from app.services.genesys_cache_db import genesys_cache_db
    from app.services.audit_service_postgres import audit_service

    try:
        # Get common audit fields
        admin_email = request.headers.get(
            "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
        )
        admin_role = getattr(request, "user_role", None)
        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        if cache_type == "genesys":
            result = genesys_cache_db.refresh_all_caches()

            audit_service.log_admin_action(
                user_email=admin_email,
                action="refresh_cache",
                target=f"cache:{cache_type}",
                user_role=admin_role,
                ip_address=user_ip,
                user_agent=request.headers.get("User-Agent"),
                success=True,
                details=result,
            )

            # Check if this is an Htmx request
            if request.headers.get("HX-Request"):
                return f"""
                <div class="bg-green-50 border-l-4 border-green-400 p-4 rounded-lg">
                    <div class="flex">
                        <div class="flex-shrink-0">
                            <i class="fas fa-check-circle text-green-400"></i>
                        </div>
                        <div class="ml-3">
                            <p class="text-green-700">
                                Genesys cache refreshed successfully!
                                Cached {result.get("groups", 0)} groups,
                                {result.get("skills", 0)} skills,
                                {result.get("locations", 0)} locations.
                            </p>
                        </div>
                    </div>
                </div>
                """

            return jsonify(
                {
                    "success": True,
                    "message": "Cache refreshed successfully",
                    "results": result,
                }
            )

        elif cache_type == "data_warehouse":
            from app.services.refresh_employee_profiles import employee_profiles_service

            result = employee_profiles_service.refresh_all_profiles()

            audit_service.log_admin_action(
                user_email=admin_email,
                action="refresh_cache",
                target=f"cache:{cache_type}",
                user_role=admin_role,
                ip_address=user_ip,
                user_agent=request.headers.get("User-Agent"),
                success=True,
                details=result,
            )

            # Check if this is an Htmx request
            if request.headers.get("HX-Request"):
                total_records = result.get("total_records", 0)
                cached_records = result.get("cached_records", 0)
                return f"""
                <div class="bg-green-50 border-l-4 border-green-400 p-4 rounded-lg">
                    <div class="flex">
                        <div class="flex-shrink-0">
                            <i class="fas fa-check-circle text-green-400"></i>
                        </div>
                        <div class="ml-3">
                            <p class="text-green-700">
                                Data warehouse cache refreshed successfully!
                                Cached {cached_records} of {total_records} user records.
                            </p>
                        </div>
                    </div>
                </div>
                """

            return jsonify(
                {
                    "success": True,
                    "message": "Data warehouse cache refreshed successfully",
                    "results": result,
                }
            )

        elif cache_type == "search":
            # Search cache doesn't support refresh, only clear
            # Return a message indicating this
            if request.headers.get("HX-Request"):
                return """
                <div class="bg-yellow-50 border-l-4 border-yellow-400 p-2 rounded-lg text-sm">
                    <p class="text-yellow-700">Search cache refreshes automatically with each new search. Use 'Clear' to remove expired entries.</p>
                </div>
                """

            return jsonify(
                {
                    "success": True,
                    "message": "Search cache refreshes automatically with each new search",
                    "note": "Use clear to remove expired entries",
                }
            )

        else:
            return jsonify(
                {"success": False, "message": f"Unknown cache type: {cache_type}"}
            ), 400

    except Exception as e:
        if request.headers.get("HX-Request"):
            return f"""
            <div class="bg-red-50 border-l-4 border-red-400 p-4 rounded-lg">
                <div class="flex">
                    <div class="flex-shrink-0">
                        <i class="fas fa-times-circle text-red-400"></i>
                    </div>
                    <div class="ml-3">
                        <p class="text-red-700">Failed to refresh cache: {str(e)}</p>
                    </div>
                </div>
            </div>
            """
        return jsonify({"success": False, "message": str(e)}), 500


@require_role("admin")
def clear_all_caches():
    """Clear all caches."""
    from app.models import (
        SearchCache,
        GenesysGroup,
        GenesysLocation,
        GenesysSkill,
    )
    from app.services.audit_service_postgres import audit_service

    try:
        # Clear search cache
        search_deleted = SearchCache.query.delete()

        # Clear Genesys caches
        groups_deleted = GenesysGroup.query.delete()
        locations_deleted = GenesysLocation.query.delete()
        skills_deleted = GenesysSkill.query.delete()

        # Clear employee profiles (consolidated cache)
        from app.models.employee_profiles import EmployeeProfiles

        profiles_deleted = EmployeeProfiles.query.delete()

        # For backward compatibility with the audit logging

        db.session.commit()

        # Log action
        admin_email = request.headers.get(
            "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
        )
        admin_role = getattr(request, "user_role", None)
        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        audit_service.log_admin_action(
            user_email=admin_email,
            action="clear_caches",
            target="all_caches",
            user_role=admin_role,
            ip_address=user_ip,
            user_agent=request.headers.get("User-Agent"),
            success=True,
            details={
                "search_cache": search_deleted,
                "genesys_groups": groups_deleted,
                "genesys_locations": locations_deleted,
                "genesys_skills": skills_deleted,
                "employee_profiles": profiles_deleted,
            },
        )

        # Check if this is an Htmx request
        if request.headers.get("HX-Request"):
            return f"""
            <div class="bg-green-50 border-l-4 border-green-400 p-4 rounded-lg">
                <div class="flex">
                    <div class="flex-shrink-0">
                        <i class="fas fa-check-circle text-green-400"></i>
                    </div>
                    <div class="ml-3">
                        <p class="text-green-700">
                            All caches cleared successfully!
                            Deleted {search_deleted} search entries,
                            {groups_deleted + locations_deleted + skills_deleted} Genesys entries,
                            and {profiles_deleted} employee profiles (including photos and data warehouse data).
                        </p>
                    </div>
                </div>
            </div>
            """

        return jsonify(
            {
                "success": True,
                "message": "All caches cleared successfully",
                "deleted": {
                    "search_cache": search_deleted,
                    "genesys_groups": groups_deleted,
                    "genesys_locations": locations_deleted,
                    "genesys_skills": skills_deleted,
                    "employee_profiles": profiles_deleted,
                },
            }
        )

    except Exception as e:
        db.session.rollback()
        if request.headers.get("HX-Request"):
            return f"""
            <div class="bg-red-50 border-l-4 border-red-400 p-4 rounded-lg">
                <div class="flex">
                    <div class="flex-shrink-0">
                        <i class="fas fa-times-circle text-red-400"></i>
                    </div>
                    <div class="ml-3">
                        <p class="text-red-700">Failed to clear caches: {str(e)}</p>
                    </div>
                </div>
            </div>
            """
        return jsonify({"success": False, "message": str(e)}), 500


@require_role("admin")
def optimize_database():
    """Run database optimization (VACUUM ANALYZE)."""
    from sqlalchemy import text
    from app.services.audit_service_postgres import audit_service

    try:
        # Get list of tables
        tables_result = db.session.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )

        # Run ANALYZE on each table with proper identifier quoting
        for row in tables_result:
            # Use parameterized query with proper identifier quoting
            safe_table = (
                db.session.connection()
                .execute(
                    text("SELECT quote_ident(:table_name)"),
                    {"table_name": row.tablename},
                )
                .scalar()
            )
            db.session.execute(text(f"ANALYZE {safe_table}"))

        db.session.commit()

        # Log action
        admin_email = request.headers.get(
            "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
        )
        admin_role = getattr(request, "user_role", None)
        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        audit_service.log_admin_action(
            user_email=admin_email,
            action="optimize_database",
            target="database",
            user_role=admin_role,
            ip_address=user_ip,
            user_agent=request.headers.get("User-Agent"),
            success=True,
            details={"operation": "analyze_tables"},
        )

        # Check if this is an Htmx request
        if request.headers.get("HX-Request"):
            return """
            <div class="bg-green-50 border-l-4 border-green-400 p-4 rounded-lg">
                <div class="flex">
                    <div class="flex-shrink-0">
                        <i class="fas fa-check-circle text-green-400"></i>
                    </div>
                    <div class="ml-3">
                        <p class="text-green-700">Database optimization completed successfully! Tables have been analyzed for optimal query performance.</p>
                    </div>
                </div>
            </div>
            """

        return jsonify({"success": True, "message": "Database optimization completed"})
    except Exception as e:
        if request.headers.get("HX-Request"):
            return f"""
            <div class="bg-red-50 border-l-4 border-red-400 p-4 rounded-lg">
                <div class="flex">
                    <div class="flex-shrink-0">
                        <i class="fas fa-times-circle text-red-400"></i>
                    </div>
                    <div class="ml-3">
                        <p class="text-red-700">Failed to optimize database: {str(e)}</p>
                    </div>
                </div>
            </div>
            """
        return jsonify({"success": False, "message": str(e)})


@require_role("admin")
def export_audit_logs():
    """Export audit logs as CSV."""
    from app.models import AuditLog

    try:
        # Get last 30 days of audit logs
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        logs = (
            AuditLog.query.filter(AuditLog.timestamp > cutoff_date)
            .order_by(AuditLog.timestamp.desc())
            .all()
        )

        # Create CSV
        output = StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            [
                "Timestamp",
                "Event Type",
                "User Email",
                "IP Address",
                "Success",
                "Message",
                "Search Query",
                "Results Count",
                "Services Used",
                "User Agent",
            ]
        )

        # Data
        for log in logs:
            # Parse services from JSON if available
            services = ""
            if log.search_services:
                try:
                    services_list = json.loads(log.search_services)
                    services = ", ".join(services_list) if services_list else ""
                except (json.JSONDecodeError, TypeError):
                    services = str(log.search_services) if log.search_services else ""

            writer.writerow(
                [
                    format_timestamp_long(log.timestamp),
                    log.event_type,
                    log.user_email or "",
                    log.ip_address or "",
                    "Yes" if log.success else "No",
                    log.message or "",
                    log.search_query or "",
                    log.search_results_count
                    if log.search_results_count is not None
                    else "",
                    services,
                    log.user_agent or "",
                ]
            )

        # Create response
        output.seek(0)
        return Response(
            output,
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=audit_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            },
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@require_role("admin")
def error_logs():
    """Display error logs viewer."""
    return render_template("admin/error_logs.html")


@require_role("admin")
def api_error_logs():
    """API endpoint for querying error logs."""
    from app.models import ErrorLog
    from datetime import datetime, timedelta

    # Get query parameters
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    severity = request.args.get("severity")
    hours = int(request.args.get("hours", 24))
    search = request.args.get("search", "")

    query = ErrorLog.query

    # Apply filters
    if severity:
        query = query.filter_by(severity=severity)

    # Time filter
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    query = query.filter(ErrorLog.timestamp > cutoff_time)

    # Search filter
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            db.or_(
                ErrorLog.error_message.ilike(search_pattern),
                ErrorLog.error_type.ilike(search_pattern),
                ErrorLog.request_path.ilike(search_pattern),
            )
        )

    # Get total count
    total = query.count()

    # Get paginated results
    errors = query.order_by(ErrorLog.timestamp.desc()).offset(offset).limit(limit).all()

    # Check if this is an Htmx request
    if request.headers.get("HX-Request"):
        return _render_error_logs(errors, total)

    results = []
    for error in errors:
        results.append(
            {
                "id": error.id,
                "timestamp": error.timestamp.isoformat(),
                "error_type": error.error_type,
                "error_message": error.error_message,
                "stack_trace": error.stack_trace,
                "user_email": error.user_email,
                "request_path": error.request_path,
                "request_method": error.request_method,
                "severity": error.severity,
            }
        )

    return jsonify({"total": total, "errors": results})


@require_role("admin")
def api_error_detail(error_id):
    """Get error detail for modal display."""
    from app.models import ErrorLog

    error = ErrorLog.query.get(error_id)
    if not error:
        return '<div class="p-4 text-red-600">Error not found</div>', 404

    return _render_error_detail(error)


@require_role("admin")
def sessions():
    """Display active sessions."""
    return render_template("admin/sessions.html")


@require_role("admin")
def api_sessions():
    """Get active user sessions."""
    from app.models import UserSession

    # Get active sessions (more lenient query to catch all sessions)
    now = datetime.now(timezone.utc)

    # First try original query
    active_sessions = (
        UserSession.query.filter(
            UserSession.expires_at > now,
            UserSession.last_activity > now - timedelta(hours=24),
            UserSession.is_active.is_(True),
        )
        .order_by(UserSession.last_activity.desc())
        .all()
    )

    # If no active sessions found, check for any recent sessions (debugging)
    if not active_sessions:
        # Look for sessions in the last 24 hours regardless of expiry
        active_sessions = (
            UserSession.query.filter(
                UserSession.last_activity > now - timedelta(hours=24),
                UserSession.is_active.is_(True),
            )
            .order_by(UserSession.last_activity.desc())
            .all()
        )

    # Check if this is an Htmx request
    if request.headers.get("HX-Request"):
        return _render_sessions_table(active_sessions)

    sessions = []
    for session in active_sessions:
        sessions.append(
            {
                "id": session.id,
                "user_email": session.user_email,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "ip_address": session.ip_address,
                "user_agent": session.user_agent,
            }
        )

    return jsonify({"sessions": sessions})


@require_role("admin")
def terminate_session(session_id):
    """Terminate a user session."""
    from app.models import UserSession
    from app.services.audit_service_postgres import audit_service
    import urllib.parse

    # URL decode the session ID in case it was encoded
    session_id = urllib.parse.unquote(session_id)

    session = UserSession.query.get(session_id)
    if not session:
        return jsonify({"success": False, "message": "Session not found"}), 404

    session.is_active = False
    db.session.commit()

    # Log action
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="terminate_session",
        target=f"session:{session_id}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        details={"terminated_user": session.user_email},
    )

    # Check if this is an Htmx request
    if request.headers.get("HX-Request"):
        # Return updated sessions list
        return api_sessions()

    return jsonify({"success": True, "message": "Session terminated"})


@require_role("admin")
def tokens_status():
    """Get status of all API tokens."""
    from app.models import ApiToken

    try:
        tokens = ApiToken.get_all_tokens_status()
        return jsonify({"tokens": tokens})
    except Exception as e:
        return jsonify({"error": str(e), "tokens": []})


@require_role("admin")
def refresh_token(service_name):
    """Manually refresh a specific service token."""
    from app.services.genesys_service import genesys_service
    from app.services.graph_service import graph_service
    from app.services.audit_service_postgres import audit_service

    try:
        success = False

        if service_name == "genesys":
            success = genesys_service.refresh_token_if_needed()
        elif service_name == "microsoft_graph":
            success = graph_service.refresh_token_if_needed()
        else:
            return jsonify(
                {"success": False, "message": f"Unknown service: {service_name}"}
            ), 400

        if success:
            # Log action
            admin_email = request.headers.get(
                "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
            )
            admin_role = getattr(request, "user_role", None)
            user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

            audit_service.log_admin_action(
                user_email=admin_email,
                action="refresh_token",
                target=f"token:{service_name}",
                user_role=admin_role,
                ip_address=user_ip,
                user_agent=request.headers.get("User-Agent"),
                success=True,
                details={"service": service_name},
            )

            return jsonify(
                {
                    "success": True,
                    "message": f"Token for {service_name} refreshed successfully",
                }
            )
        else:
            return jsonify(
                {
                    "success": False,
                    "message": f"Failed to refresh token for {service_name}",
                }
            ), 500

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ===== Htmx Helper Functions =====


def _render_database_health(data):
    """Render database health stats as HTML for Htmx."""
    status_icon = "check-circle" if data["status"] == "healthy" else "times-circle"
    status_color = "green" if data["status"] == "healthy" else "red"

    return f"""
    <div class="grid md:grid-cols-4 gap-4">
        <div class="text-center">
            <div class="text-3xl text-{status_color}-600 mb-2">
                <i class="fas fa-{status_icon}"></i>
            </div>
            <h3 class="font-semibold text-gray-700">Status</h3>
            <p class="text-gray-900">{data["status"].capitalize()}</p>
            <p class="text-sm text-gray-500">{data.get("database_type", "Unknown")}</p>
        </div>
        
        <div class="text-center">
            <div class="text-3xl text-blue-600 mb-2">
                <i class="fas fa-hdd"></i>
            </div>
            <h3 class="font-semibold text-gray-700">Database Size</h3>
            <p class="text-gray-900">{data["database_size"]}</p>
        </div>
        
        <div class="text-center">
            <div class="text-3xl text-purple-600 mb-2">
                <i class="fas fa-link"></i>
            </div>
            <h3 class="font-semibold text-gray-700">Active Connections</h3>
            <p class="text-gray-900">{data["active_connections"]}</p>
        </div>
        
        <div class="text-center">
            <div class="text-3xl text-orange-600 mb-2">
                <i class="fas fa-chart-bar"></i>
            </div>
            <h3 class="font-semibold text-gray-700">Pool Usage</h3>
            <p class="text-gray-900">{data["pool_usage"]}</p>
        </div>
    </div>
    """


def _render_table_statistics(tables):
    """Render table statistics as HTML for Htmx."""
    if not tables:
        return """
        <div class="text-center py-8 text-gray-500">
            No tables found
        </div>
        """

    html = """
    <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
            <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Table Name</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Row Count</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Size</th>
                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Last Activity</th>
            </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
    """

    for table in tables:
        row_count = table["row_count"]
        if isinstance(row_count, int):
            row_count = f"{row_count:,}"

        html += f"""
        <tr class="hover:bg-gray-50">
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                <i class="fas fa-table mr-2 text-gray-400"></i>
                {table["name"]}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{row_count}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{table["size"]}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{table.get("last_activity", "N/A")}</td>
        </tr>
        """

    html += """
        </tbody>
    </table>
    """

    return html


def _render_cache_status():
    """Render cache status as HTML for Htmx with modern mobile-friendly design."""
    from app.models import SearchCache, ApiToken
    from app.services.genesys_cache_db import genesys_cache_db
    from app.services.refresh_employee_profiles import employee_profiles_service
    from datetime import datetime

    try:
        # Get all cache data
        search_cache_count = SearchCache.query.count()
        tokens = ApiToken.get_all_tokens_status()
        genesys_token = next((t for t in tokens if t["service"] == "genesys"), None)
        graph_token = next(
            (t for t in tokens if t["service"] == "microsoft_graph"), None
        )
        genesys_cache = genesys_cache_db.get_cache_status()
        dw_cache = employee_profiles_service.get_cache_stats()

        # Helper function to format expiration time for tooltip
        def format_expiration(token_data):
            if not token_data or token_data.get("is_expired"):
                return ""
            expires_at = token_data.get("expires_at", "")
            try:
                # Parse and format the datetime for display
                dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                return dt.strftime("%m/%d/%Y %I:%M %p UTC")
            except Exception:
                return expires_at

        html = """
        <div class="space-y-6">
            <!-- API Tokens Section -->
            <div class="bg-gray-50 rounded-lg p-4">
                <h4 class="font-medium text-gray-900 mb-3 flex items-center">
                    <i class="fas fa-key text-blue-500 mr-2"></i>
                    API Tokens
                </h4>
                <div class="space-y-2">
        """

        # Genesys token
        if genesys_token:
            status_color = "red" if genesys_token["is_expired"] else "green"
            status_text = "Expired" if genesys_token["is_expired"] else "Valid"
            tooltip = format_expiration(genesys_token)
            tooltip_attr = f'title="Expires: {tooltip}"' if tooltip else ""

            html += f"""
                    <div class="flex justify-between items-center">
                        <span class="text-sm text-gray-600">Genesys Cloud:</span>
                        <span class="px-2 py-1 text-xs rounded-full bg-{status_color}-100 text-{status_color}-800 cursor-help" {tooltip_attr}>
                            {status_text}
                        </span>
                    </div>
            """

        # Graph token
        if graph_token:
            status_color = "red" if graph_token["is_expired"] else "green"
            status_text = "Expired" if graph_token["is_expired"] else "Valid"
            tooltip = format_expiration(graph_token)
            tooltip_attr = f'title="Expires: {tooltip}"' if tooltip else ""

            html += f"""
                    <div class="flex justify-between items-center">
                        <span class="text-sm text-gray-600">Microsoft Graph:</span>
                        <span class="px-2 py-1 text-xs rounded-full bg-{status_color}-100 text-{status_color}-800 cursor-help" {tooltip_attr}>
                            {status_text}
                        </span>
                    </div>
            """

        html += """
                </div>
            </div>

            <!-- Cache Statistics Section -->
            <div class="bg-gray-50 rounded-lg p-4">
                <h4 class="font-medium text-gray-900 mb-3 flex items-center">
                    <i class="fas fa-database text-purple-500 mr-2"></i>
                    Cache Statistics
                </h4>
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        """

        # Search Cache Card
        html += f"""
                    <div class="bg-white rounded-md p-3 border border-gray-200">
                        <div class="flex items-center justify-between">
                            <div>
                                <div class="text-xs text-gray-500 uppercase tracking-wide">Search Cache</div>
                                <div class="text-lg font-semibold text-gray-900">{search_cache_count}</div>
                                <div class="text-xs text-gray-500">entries</div>
                            </div>
                            <div class="text-blue-500">
                                <i class="fas fa-search text-xl"></i>
                            </div>
                        </div>
                    </div>
        """

        # Genesys Cache Card
        if genesys_cache:
            groups_count = genesys_cache.get("groups_cached", 0)
            locations_count = genesys_cache.get("locations_cached", 0)
            total_count = groups_count + locations_count
            age = (
                _format_cache_age(genesys_cache.get("group_cache_age", ""))
                if genesys_cache.get("group_cache_age")
                else "Unknown"
            )
            needs_refresh = genesys_cache.get("needs_refresh", False)
            refresh_color = "yellow" if needs_refresh else "green"

            html += f"""
                    <div class="bg-white rounded-md p-3 border border-gray-200">
                        <div class="flex items-center justify-between mb-2">
                            <div>
                                <div class="text-xs text-gray-500 uppercase tracking-wide">Genesys Cloud</div>
                                <div class="text-lg font-semibold text-gray-900">{total_count}</div>
                                <div class="text-xs text-gray-500">{groups_count} groups, {locations_count} locations</div>
                            </div>
                            <div class="text-orange-500">
                                <i class="fas fa-cloud text-xl"></i>
                            </div>
                        </div>
                        <div class="flex items-center justify-between">
                            <span class="text-xs text-gray-500">{age}</span>
                            <span class="px-1.5 py-0.5 text-xs rounded bg-{refresh_color}-100 text-{refresh_color}-800">
                                {"Needs Refresh" if needs_refresh else "Fresh"}
                            </span>
                        </div>
                        <button onclick="refreshGenesysCache()" 
                                class="mt-2 w-full px-2 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors">
                            <i class="fas fa-sync mr-1"></i> Refresh
                        </button>
                    </div>
            """

        # Data Warehouse Cache Card
        dw_count = dw_cache.get("record_count", 0)
        dw_status = dw_cache.get("refresh_status", "unknown")
        dw_last_updated = dw_cache.get("last_updated")

        # Format last updated time
        if dw_last_updated:
            try:
                dt = datetime.fromisoformat(dw_last_updated.replace("Z", "+00:00"))
                dw_age = _format_time_ago(dt)
            except Exception:
                dw_age = "Unknown"
        else:
            dw_age = "Never"

        status_colors = {
            "ready": "green",
            "needs_refresh": "yellow",
            "error": "red",
            "unknown": "gray",
        }
        status_color = status_colors.get(dw_status, "gray")

        html += f"""
                    <div class="bg-white rounded-md p-3 border border-gray-200">
                        <div class="flex items-center justify-between mb-2">
                            <div>
                                <div class="text-xs text-gray-500 uppercase tracking-wide">Data Warehouse</div>
                                <div class="text-lg font-semibold text-gray-900">{dw_count}</div>
                                <div class="text-xs text-gray-500">user records</div>
                            </div>
                            <div class="text-green-500">
                                <i class="fas fa-warehouse text-xl"></i>
                            </div>
                        </div>
                        <div class="flex items-center justify-between">
                            <span class="text-xs text-gray-500">{dw_age}</span>
                            <span class="px-1.5 py-0.5 text-xs rounded bg-{status_color}-100 text-{status_color}-800">
                                {dw_status.replace("_", " ").title()}
                            </span>
                        </div>
                        <button onclick="refreshDataWarehouseCache()" 
                                class="mt-2 w-full px-2 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors">
                            <i class="fas fa-sync mr-1"></i> Refresh
                        </button>
                    </div>
        """

        html += """
                </div>
            </div>

            <!-- Cache Actions Section -->
            <div class="bg-gray-50 rounded-lg p-4">
                <h4 class="font-medium text-gray-900 mb-3 flex items-center">
                    <i class="fas fa-tools text-gray-500 mr-2"></i>
                    Cache Management
                </h4>
                <div class="flex flex-col sm:flex-row gap-2">
                    <button onclick="refreshAllCaches()" 
                            class="flex-1 px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors text-sm font-medium">
                        <i class="fas fa-sync-alt mr-2"></i>
                        Refresh All Caches
                    </button>
                    <button onclick="clearAllCaches()" 
                            class="flex-1 px-4 py-2 bg-red-500 text-white rounded-md hover:bg-red-600 transition-colors text-sm font-medium">
                        <i class="fas fa-trash mr-2"></i>
                        Clear All Caches
                    </button>
                </div>
            </div>
            
            <!-- Overall Performance Metrics (hidden by default, extracted by HTMX) -->
            <div id="overall-performance-metrics" class="grid grid-cols-2 gap-4 text-sm" style="display: none;">
        """

        # Calculate total cache entries
        total_cache_entries = search_cache_count + total_count + dw_count

        # Calculate token health percentage
        total_tokens = 2  # Genesys and Graph
        valid_tokens = 0
        if genesys_token and not genesys_token.get("is_expired"):
            valid_tokens += 1
        if graph_token and not graph_token.get("is_expired"):
            valid_tokens += 1
        token_health = (
            int((valid_tokens / total_tokens) * 100) if total_tokens > 0 else 0
        )

        # Get current time for "Last Updated"
        from datetime import datetime

        current_time = datetime.now().strftime("%I:%M %p")

        html += f"""
                <div>
                    <span class="text-gray-500">Total Cache Entries:</span>
                    <span class="font-medium text-gray-900 ml-2">{total_cache_entries:,}</span>
                </div>
                <div>
                    <span class="text-gray-500">Token Health:</span>
                    <span class="font-medium {"text-green-600" if token_health >= 100 else "text-yellow-600" if token_health >= 50 else "text-red-600"} ml-2">{token_health}%</span>
                </div>
                <div>
                    <span class="text-gray-500">Active Services:</span>
                    <span class="font-medium text-gray-900 ml-2">3 of 3</span>
                </div>
                <div>
                    <span class="text-gray-500">Last Updated:</span>
                    <span class="font-medium text-gray-900 ml-2">{current_time}</span>
                </div>
            </div>
        </div>

        <script>
        function refreshGenesysCache() {{
            htmx.ajax('POST', '/admin/refresh-cache/genesys', {{target: '#cache-status'}});
        }}
        
        function refreshDataWarehouseCache() {{
            htmx.ajax('POST', '/admin/refresh-cache/data_warehouse', {{target: '#cache-status'}});
        }}
        
        function refreshAllCaches() {{
            Promise.all([
                htmx.ajax('POST', '/admin/refresh-cache/genesys'),
                htmx.ajax('POST', '/admin/refresh-cache/data_warehouse')
            ]).then(() => {{
                htmx.ajax('GET', '/admin/api/cache/status', {{target: '#cache-status'}});
            }});
        }}
        
        function clearAllCaches() {{
            if (confirm('Are you sure you want to clear all caches? This will remove all cached data.')) {{
                htmx.ajax('POST', '/admin/clear-all-caches', {{target: '#cache-status'}});
            }}
        }}
        </script>
        """

        return html

    except Exception as e:
        return f'<div class="text-red-600 text-sm p-4 bg-red-50 rounded-lg">Error loading cache status: {str(e)}</div>'


def _format_cache_age(age_string):
    """Format cache age string."""
    import re

    match = re.match(r"(\d+):(\d+):(\d+)", age_string)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))

        if hours > 0:
            return f"{hours}h {minutes}m ago"
        elif minutes > 0:
            return f"{minutes}m ago"
        else:
            return "Just refreshed"
    return age_string


def _format_time_ago(dt):
    """Format datetime as time ago string."""
    from datetime import timezone

    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    diff = now - dt

    if diff.days > 0:
        if diff.days == 1:
            return "1 day ago"
        return f"{diff.days} days ago"

    hours = diff.seconds // 3600
    if hours > 0:
        if hours == 1:
            return "1 hour ago"
        return f"{hours} hours ago"

    minutes = diff.seconds // 60
    if minutes > 0:
        if minutes == 1:
            return "1 minute ago"
        return f"{minutes} minutes ago"

    return "Just now"


def _render_session_stats():
    """Render session statistics as HTML for Htmx."""
    from app.models import UserSession

    try:
        # Active sessions (activity in last 30 minutes)
        now = datetime.now(timezone.utc)
        active_sessions = UserSession.query.filter(
            UserSession.last_activity > now - timedelta(minutes=30),
            UserSession.is_active.is_(True),
        ).count()

        return f"""
        <div class="text-center">
            <div class="text-5xl font-bold text-green-600 mb-2">{active_sessions}</div>
            <p class="text-sm text-gray-600">Active Users</p>
        </div>
        """
    except Exception as e:
        return f'<div class="text-red-600 text-sm">Error: {str(e)}</div>'


def _render_error_stats():
    """Render error statistics as HTML for Htmx."""
    from app.models import ErrorLog

    try:
        # Recent errors (last hour)
        recent_errors = ErrorLog.query.filter(
            ErrorLog.timestamp > datetime.utcnow() - timedelta(hours=1)
        ).count()

        # Last 24 hours
        errors_24h = ErrorLog.query.filter(
            ErrorLog.timestamp > datetime.utcnow() - timedelta(days=1)
        ).count()

        recent_color = "red" if recent_errors > 0 else "green"
        daily_color = (
            "yellow" if errors_24h > 10 else "green" if errors_24h > 0 else "gray"
        )

        return f"""
        <div class="flex justify-between items-center">
            <div>
                <span class="text-sm text-gray-600">Recent Errors:</span>
                <span class="ml-2 px-2 py-1 text-xs rounded-full bg-{recent_color}-100 text-{recent_color}-800">{recent_errors}</span>
            </div>
            <div>
                <span class="text-sm text-gray-600">Last 24h:</span>
                <span class="ml-2 px-2 py-1 text-xs rounded-full bg-{daily_color}-100 text-{daily_color}-800">{errors_24h}</span>
            </div>
        </div>
        """
    except Exception as e:
        return f'<div class="text-red-600 text-sm">Error: {str(e)}</div>'


def _render_error_logs(errors, total):
    """Render error logs table as HTML for Htmx."""
    if not errors:
        return """
        <div class="text-center py-8 text-gray-500">
            <i class="fas fa-smile text-5xl mb-3"></i>
            <p class="text-lg">No errors found. Everything's running smoothly!</p>
        </div>
        """

    html = """
    <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Timestamp</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Severity</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Error Type</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Message</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
                    <th class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
    """

    for error in errors:
        # Format timestamp using configured timezone
        timestamp = format_timestamp(error.timestamp)

        # Severity colors
        severity_colors = {"critical": "red", "error": "orange", "warning": "yellow"}
        severity_color = severity_colors.get(error.severity, "gray")

        # Truncate message
        message = error.error_message or ""
        if len(message) > 80:
            message = message[:77] + "..."

        html += f"""
        <tr class="hover:bg-gray-50">
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{timestamp}</td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-{severity_color}-100 text-{severity_color}-800">
                    {error.severity or "error"}
                </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-900">{error.error_type or "Unknown"}</td>
            <td class="px-6 py-4 text-sm text-gray-900 max-w-md truncate" title="{error.error_message or ""}">{message}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{error.user_email or "System"}</td>
            <td class="px-6 py-4 whitespace-nowrap text-center text-sm font-medium">
                <button onclick="viewErrorDetails({error.id})" 
                        class="text-blue-600 hover:text-blue-900">
                    <i class="fas fa-eye"></i> View
                </button>
            </td>
        </tr>
        """

    html += f"""
            </tbody>
        </table>
    </div>
    <div class="px-6 py-3 bg-gray-50 border-t border-gray-200">
        <p class="text-sm text-gray-700">
            Showing <span class="font-medium">{len(errors)}</span> of <span class="font-medium">{total}</span> errors
        </p>
    </div>
    """

    return html


def _render_error_detail(error):
    """Render error detail modal content."""
    # Format timestamps using configured timezone
    from app.utils.timezone import format_timestamp_long

    timestamp = format_timestamp_long(error.timestamp)

    # Format request info
    request_info = f"{error.request_method or 'N/A'} {error.request_path or 'N/A'}"

    return f"""
    <div class="bg-white rounded-lg">
        <div class="flex justify-between items-center p-4 border-b">
            <h3 class="text-lg font-semibold text-gray-900">Error Details</h3>
            <button onclick="document.getElementById('errorDetailModal').classList.add('hidden')"
                    class="text-gray-400 hover:text-gray-500">
                <i class="fas fa-times"></i>
            </button>
        </div>
        <div class="p-4 space-y-4">
            <div>
                <label class="block text-sm font-medium text-gray-700">Timestamp</label>
                <p class="mt-1 text-sm text-gray-900">{timestamp}</p>
            </div>
            
            <div>
                <label class="block text-sm font-medium text-gray-700">Error Type</label>
                <p class="mt-1 text-sm font-mono text-gray-900">{error.error_type or "Unknown"}</p>
            </div>
            
            <div>
                <label class="block text-sm font-medium text-gray-700">User</label>
                <p class="mt-1 text-sm text-gray-900">{error.user_email or "System"}</p>
            </div>
            
            <div>
                <label class="block text-sm font-medium text-gray-700">Request</label>
                <p class="mt-1 text-sm font-mono text-gray-900">{request_info}</p>
            </div>
            
            <div>
                <label class="block text-sm font-medium text-gray-700">Message</label>
                <div class="mt-1 p-3 bg-red-50 border border-red-200 rounded-md">
                    <p class="text-sm text-red-800">{error.error_message or "No message provided"}</p>
                </div>
            </div>
            
            <div>
                <label class="block text-sm font-medium text-gray-700">Stack Trace</label>
                <pre class="mt-1 p-3 bg-gray-900 text-gray-100 rounded-md overflow-x-auto text-xs">{error.stack_trace or "No stack trace available"}</pre>
            </div>
        </div>
    </div>
    """


def _render_sessions_table(sessions):
    """Render sessions table as HTML for Htmx."""
    if not sessions:
        return """
        <div class="text-center py-8 text-gray-500">
            <i class="fas fa-user-x text-5xl mb-3"></i>
            <p class="text-lg">No active sessions found.</p>
        </div>
        """

    html = """
    <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">IP Address</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Started</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Last Activity</th>
                    <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
    """

    now = datetime.now(timezone.utc)

    for session in sessions:
        # Format timestamps using configured timezone
        created = format_timestamp(session.created_at, "%m/%d %H:%M")
        last_activity = format_timestamp(session.last_activity, "%m/%d %H:%M")

        # Calculate time since last activity
        # Handle timezone-naive last_activity timestamps
        last_activity_tz = session.last_activity
        if last_activity_tz.tzinfo is None:
            last_activity_tz = last_activity_tz.replace(tzinfo=timezone.utc)

        idle_time = now - last_activity_tz
        idle_minutes = int(idle_time.total_seconds() / 60)

        # Determine status
        if idle_minutes > 30:
            status_color = "yellow"
            status_text = f"Idle ({idle_minutes}m)"
        else:
            status_color = "green"
            status_text = "Active"

        # Parse user agent for browser info
        user_agent = session.user_agent or "Unknown"
        if "Chrome" in user_agent:
            browser = "Chrome"
        elif "Firefox" in user_agent:
            browser = "Firefox"
        elif "Safari" in user_agent:
            browser = "Safari"
        elif "Edge" in user_agent:
            browser = "Edge"
        else:
            browser = "Other"

        # Escape quotes for JavaScript safety
        escaped_session_id = session.id.replace("'", "\\'").replace('"', '\\"')
        escaped_user_email = session.user_email.replace("'", "\\'").replace('"', '\\"')

        html += f"""
        <tr class="hover:bg-gray-50" 
            data-session="true" 
            data-user-email="{session.user_email}"
            data-last-activity="{session.last_activity.isoformat()}">
            <td class="px-6 py-4 whitespace-nowrap">
                <div class="text-sm font-medium text-gray-900">{session.user_email}</div>
                <div class="text-sm text-gray-500">Browser: {browser}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{session.ip_address or "Unknown"}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{created}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{last_activity}</td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-{status_color}-100 text-{status_color}-800">
                    {status_text}
                </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-center text-sm font-medium">
                <button onclick="confirmTerminate('{escaped_session_id}', '{escaped_user_email}')" 
                        class="text-red-600 hover:text-red-900">
                    <i class="fas fa-times-circle"></i> Terminate
                </button>
            </td>
        </tr>
        """

    html += """
            </tbody>
        </table>
    </div>
    """

    return html


@require_role("admin")
def database_cache_section(section_type):
    """Render cache management tab content."""
    if section_type == "stats":
        return render_template("admin/_cache_stats.html")
    elif section_type == "tokens":
        return render_template("admin/_api_tokens.html")
    elif section_type == "actions":
        return render_template("admin/_cache_actions.html")
    else:
        return "<div class='text-red-600'>Invalid section type</div>", 400


@require_role("admin")
def api_token_status(api_type):
    """Get status of a specific API token."""
    from app.models import ApiToken
    from datetime import datetime, timezone, timedelta

    try:
        # Get token directly from database, even if expired
        token = ApiToken.query.filter_by(service_name=api_type).first()

        if token:
            # Get current time and expiration time
            now = datetime.now(timezone.utc)
            expires_at = token.expires_at

            # Apply the same timezone logic as is_expired() method
            if expires_at.tzinfo is None:
                # Try treating as Central time first
                try:
                    cdt = pytz.timezone("US/Central")
                    expires_at_cdt = cdt.localize(expires_at, is_dst=True).astimezone(
                        timezone.utc
                    )

                    # If treating as CDT makes it a future time, use that
                    if expires_at_cdt > now:
                        expires_at = expires_at_cdt
                    else:
                        # Otherwise treat as UTC
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                except Exception:
                    # Fallback to UTC
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
            else:
                # Convert to UTC if needed
                expires_at = expires_at.astimezone(timezone.utc)

            # Calculate time until expiry
            time_until_expiry = expires_at - now

            # Check if expired (with 30 second buffer)
            buffer = timedelta(seconds=30)
            is_expired = now > (expires_at - buffer)

            if not is_expired and time_until_expiry.total_seconds() > 0:
                hours = int(time_until_expiry.total_seconds() // 3600)
                minutes = int((time_until_expiry.total_seconds() % 3600) // 60)

                # Different thresholds for different services
                if api_type == "microsoft_graph":
                    # Graph tokens are short-lived (60-90 min), only yellow if < 15 min
                    status_color = "green" if minutes > 15 or hours > 0 else "yellow"
                else:
                    # Other tokens (like Genesys) are longer-lived, yellow if < 1 hour
                    status_color = "green" if hours > 1 else "yellow"

                return f"""
                <div>
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-{status_color}-100 text-{status_color}-800">
                        <i class="fas fa-check-circle mr-1"></i> Active
                    </span>
                    <p class="text-xs text-gray-500 mt-1">Expires in {hours}h {minutes}m</p>
                </div>
                """
            else:
                return """
                <div>
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                        <i class="fas fa-times-circle mr-1"></i> Expired
                    </span>
                    <p class="text-xs text-gray-500 mt-1">Token needs refresh</p>
                </div>
                """
        else:
            return """
            <div>
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                    <i class="fas fa-question-circle mr-1"></i> No Token
                </span>
            </div>
            """
    except Exception as e:
        return f"""
        <div>
            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                <i class="fas fa-question-circle mr-1"></i> Error
            </span>
            <p class="text-xs text-gray-500 mt-1">{str(e)[:50]}</p>
        </div>
        """


@require_role("admin")
def refresh_api_tokens():
    """Refresh all API tokens."""
    from app.services.genesys_service import genesys_service
    from app.services.graph_service import graph_service

    try:
        # Manually trigger token refresh using the same logic as the background service
        results = {}

        # Refresh Genesys token
        try:
            if genesys_service.refresh_token_if_needed():
                results["genesys"] = {"success": True}
            else:
                results["genesys"] = {"success": False, "error": "Refresh failed"}
        except Exception as e:
            results["genesys"] = {"success": False, "error": str(e)}

        # Refresh Graph token
        try:
            if graph_service.refresh_token_if_needed():
                results["microsoft_graph"] = {"success": True}
            else:
                results["microsoft_graph"] = {
                    "success": False,
                    "error": "Refresh failed",
                }
        except Exception as e:
            results["microsoft_graph"] = {"success": False, "error": str(e)}

        success_count = sum(1 for r in results.values() if r.get("success"))

        return f"""
        <div class="bg-green-50 border-l-4 border-green-400 p-4 rounded-lg">
            <div class="flex">
                <div class="flex-shrink-0">
                    <i class="fas fa-check-circle text-green-400"></i>
                </div>
                <div class="ml-3">
                    <p class="text-green-700">Refreshed {success_count} of {len(results)} OAuth tokens successfully</p>
                    <p class="text-sm text-green-600 mt-1">Note: Data Warehouse uses direct SQL authentication and doesn't require token refresh</p>
                </div>
            </div>
        </div>
        """
    except Exception as e:
        return f"""
        <div class="bg-red-50 border-l-4 border-red-400 p-4 rounded-lg">
            <div class="flex">
                <div class="flex-shrink-0">
                    <i class="fas fa-times-circle text-red-400"></i>
                </div>
                <div class="ml-3">
                    <p class="text-red-700">Failed to refresh tokens: {str(e)}</p>
                </div>
            </div>
        </div>
        """


@require_role("admin")
def token_refresh_service_status():
    """Get token refresh service status."""
    try:
        # Since the token refresh service is initialized at app startup,
        # if the app is running, the service should be running
        # We'll verify by checking token update timestamps

        from app.models import ApiToken

        # Get all tokens and check their status
        tokens = ApiToken.query.all()
        if not tokens:
            return """
            <div class="bg-yellow-50 border-l-4 border-yellow-400 p-3 rounded-lg">
                <div class="flex items-start">
                    <i class="fas fa-exclamation-triangle text-yellow-500 mt-0.5 mr-3"></i>
                    <div>
                        <p class="text-sm font-medium text-yellow-800">No Tokens Found</p>
                        <p class="text-xs text-yellow-700 mt-1">
                            No API tokens are configured yet. Configure services to enable automatic token refresh.
                        </p>
                    </div>
                </div>
            </div>
            """

        # Check token freshness
        tokens_needing_immediate_refresh = []
        graph_token_expiring_normally = False
        token_debug_info = []

        for token in tokens:
            if token.is_expired():
                tokens_needing_immediate_refresh.append(token.service_name)
                token_debug_info.append(f"{token.service_name}: EXPIRED")
            else:
                time_until_expiry = token.time_until_expiry
                time_seconds = time_until_expiry.total_seconds()
                time_minutes = int(time_seconds // 60)  # Use floor division
                token_debug_info.append(f"{token.service_name}: {time_minutes}min")

                # Different thresholds for different services
                if token.service_name == "microsoft_graph":
                    # Graph tokens expire quickly, only warn if < 15 minutes
                    if time_seconds < 900:  # 15 minutes
                        tokens_needing_immediate_refresh.append("microsoft_graph")
                    elif time_seconds < 3600:  # 60 minutes
                        graph_token_expiring_normally = True
                else:
                    # Other tokens are long-lived, only warn if < 10 minutes (same as refresh threshold)
                    if time_seconds < 600:  # 10 minutes
                        tokens_needing_immediate_refresh.append(token.service_name)

        # The service is considered running if we can access this endpoint
        # (because it's started during app initialization)
        interval_minutes = 5  # Default check interval

        # Since we can't directly access the service instance in the request context,
        # we'll infer the status from token states
        if tokens_needing_immediate_refresh:
            # Check if we have expired tokens vs just expiring soon
            expired_tokens = [t for t in tokens if t.is_expired()]
            if expired_tokens:
                return """
                <div class="bg-red-50 border-l-4 border-red-400 p-3 rounded-lg">
                    <div class="flex items-start">
                        <i class="fas fa-exclamation-circle text-red-500 mt-0.5 mr-3"></i>
                        <div>
                            <p class="text-sm font-medium text-red-800">Expired Tokens Detected</p>
                            <p class="text-xs text-red-700 mt-1">
                                One or more tokens have expired. This may indicate the refresh service encountered an issue.
                            </p>
                            <p class="text-xs text-red-600 mt-1">
                                <i class="fas fa-hand-pointer mr-1"></i>
                                Use the individual refresh buttons to manually refresh expired tokens.
                            </p>
                        </div>
                    </div>
                </div>
                """
            else:
                # Tokens expiring very soon (within refresh threshold)
                debug_str = ", ".join(token_debug_info)
                tokens_str = ", ".join(tokens_needing_immediate_refresh)
                return f"""
                <div class="bg-yellow-50 border-l-4 border-yellow-400 p-3 rounded-lg">
                    <div class="flex items-start">
                        <i class="fas fa-clock text-yellow-500 mt-0.5 mr-3"></i>
                        <div>
                            <p class="text-sm font-medium text-yellow-800">Token Refresh Imminent</p>
                            <p class="text-xs text-yellow-700 mt-1">
                                Tokens needing refresh: {tokens_str}
                            </p>
                            <p class="text-xs text-yellow-600 mt-1">
                                Debug: {debug_str}
                            </p>
                            <p class="text-xs text-yellow-600 mt-1">
                                <i class="fas fa-sync mr-1"></i>
                                The service should refresh them automatically within {interval_minutes} minutes.
                            </p>
                        </div>
                    </div>
                </div>
                """
        elif graph_token_expiring_normally:
            # Only Graph token expiring within hour - this is normal
            return f"""
            <div class="bg-green-50 border-l-4 border-green-400 p-3 rounded-lg">
                <div class="flex items-start">
                    <i class="fas fa-check-circle text-green-500 mt-0.5 mr-3"></i>
                    <div>
                        <p class="text-sm font-medium text-green-800">Token Refresh Service Active</p>
                        <p class="text-xs text-green-700 mt-1">
                            Background service is running and checking tokens every {interval_minutes} minutes.
                        </p>
                        <p class="text-xs text-green-600 mt-1">
                            <i class="fas fa-info-circle mr-1"></i>
                            Microsoft Graph token expires frequently - this is normal behavior.
                        </p>
                    </div>
                </div>
            </div>
            """
        else:
            # Default case - all tokens are healthy
            return f"""
            <div class="bg-green-50 border-l-4 border-green-400 p-3 rounded-lg">
                <div class="flex items-start">
                    <i class="fas fa-check-circle text-green-500 mt-0.5 mr-3"></i>
                    <div>
                        <p class="text-sm font-medium text-green-800">Token Refresh Service Active</p>
                        <p class="text-xs text-green-700 mt-1">
                            Background service is running and checking tokens every {interval_minutes} minutes.
                        </p>
                        <p class="text-xs text-green-600 mt-1">
                            <i class="fas fa-info-circle mr-1"></i>
                            Tokens are automatically refreshed 10 minutes before expiration.
                        </p>
                    </div>
                </div>
            </div>
            """
    except Exception as e:
        return f"""
        <div class="bg-red-50 border-l-4 border-red-400 p-3 rounded-lg">
            <div class="flex items-start">
                <i class="fas fa-times-circle text-red-500 mt-0.5 mr-3"></i>
                <div>
                    <p class="text-sm font-medium text-red-800">Error Checking Service Status</p>
                    <p class="text-xs text-red-700 mt-1">{str(e)}</p>
                </div>
            </div>
        </div>
        """


@require_role("admin")
def search_cache_stats_html():
    """Get search cache statistics as HTML for HTMX."""
    from app.models import SearchCache
    from datetime import datetime, timezone, timedelta

    try:
        total_entries = SearchCache.query.count()

        # Get entries from last 24 hours for hit rate calculation
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        recent_entries = SearchCache.query.filter(
            SearchCache.created_at > yesterday
        ).count()

        # Get expired entries count
        expired_entries = SearchCache.query.filter(SearchCache.expires_at < now).count()
        active_entries = total_entries - expired_entries

        return f"""
        <div class="space-y-2">
            <div class="flex justify-between items-center">
                <span class="text-xs text-gray-600">Total:</span>
                <span class="text-sm font-semibold text-gray-900">{total_entries}</span>
            </div>
            <div class="flex justify-between items-center">
                <span class="text-xs text-gray-600">Active:</span>
                <span class="text-sm font-semibold text-green-600">{active_entries}</span>
            </div>
            <div class="flex justify-between items-center">
                <span class="text-xs text-gray-600">24h:</span>
                <span class="text-sm font-semibold text-blue-600">{recent_entries}</span>
            </div>
        </div>
        """
    except Exception:
        return """
        <div class="text-center text-sm text-red-600">
            <i class="fas fa-exclamation-circle mr-1"></i>
            Error loading stats
        </div>
        """


@require_role("admin")
def genesys_cache_stats_html():
    """Get Genesys cache statistics as HTML for HTMX."""
    from app.services.genesys_cache_db import genesys_cache_db

    try:
        status = genesys_cache_db.get_cache_status()

        groups = status.get("groups_cached", 0)
        locations = status.get("locations_cached", 0)
        skills = status.get("skills_cached", 0)
        total = groups + locations + skills

        # Parse cache age
        cache_age = status.get("group_cache_age", "Unknown")
        needs_refresh = status.get("needs_refresh", False)

        # Format cache age nicely
        if cache_age != "Unknown" and ":" in cache_age:
            parts = cache_age.split(":")
            if len(parts) >= 2:
                hours = int(parts[0])
                minutes = int(parts[1])
                if hours > 24:
                    days = hours // 24
                    cache_age = f"{days}d {hours % 24}h"
                else:
                    cache_age = f"{hours}h {minutes}m"

        status_color = "yellow" if needs_refresh else "green"
        status_text = "Needs Refresh" if needs_refresh else "Fresh"

        return f"""
        <div class="space-y-2">
            <div class="flex justify-between items-center">
                <span class="text-xs text-gray-600">Total:</span>
                <span class="text-sm font-semibold text-gray-900">{total}</span>
            </div>
            <div class="flex justify-between items-center">
                <span class="text-xs text-gray-600">Groups:</span>
                <span class="text-sm font-semibold text-orange-600">{groups}</span>
            </div>
            <div class="flex justify-between items-center">
                <span class="text-xs text-gray-600">Age:</span>
                <span class="text-sm font-semibold text-gray-700">{cache_age}</span>
            </div>
            <div class="flex justify-between items-center">
                <span class="text-xs text-gray-600">Status:</span>
                <span class="px-2 py-0.5 text-xs rounded-full bg-{status_color}-100 text-{status_color}-800">
                    {status_text}
                </span>
            </div>
        </div>
        """
    except Exception:
        return """
        <div class="text-center text-sm text-red-600">
            <i class="fas fa-exclamation-circle mr-1"></i>
            Error loading stats
        </div>
        """


@require_role("admin")
def data_warehouse_cache_stats_html():
    """Get data warehouse cache statistics as HTML for HTMX."""
    from app.services.refresh_employee_profiles import employee_profiles_service
    from datetime import datetime

    try:
        status = employee_profiles_service.get_cache_stats()

        record_count = status.get("record_count", 0)
        refresh_status = status.get("refresh_status", "unknown")
        last_updated = status.get("last_updated")

        # Format last updated time
        if last_updated:
            try:
                dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                age = _format_time_ago(dt)
            except Exception:
                age = "Unknown"
        else:
            age = "Never"

        # Status colors
        status_colors = {
            "ready": "green",
            "needs_refresh": "yellow",
            "error": "red",
            "unknown": "gray",
        }
        status_color = status_colors.get(refresh_status, "gray")
        status_text = refresh_status.replace("_", " ").title()

        return f"""
        <div class="space-y-2">
            <div class="flex justify-between items-center">
                <span class="text-xs text-gray-600">Records:</span>
                <span class="text-sm font-semibold text-gray-900">{record_count}</span>
            </div>
            <div class="flex justify-between items-center">
                <span class="text-xs text-gray-600">Updated:</span>
                <span class="text-sm font-semibold text-purple-600">{age}</span>
            </div>
            <div class="flex justify-between items-center">
                <span class="text-xs text-gray-600">Status:</span>
                <span class="px-2 py-0.5 text-xs rounded-full bg-{status_color}-100 text-{status_color}-800">
                    {status_text}
                </span>
            </div>
        </div>
        """
    except Exception:
        return """
        <div class="text-center text-sm text-red-600">
            <i class="fas fa-exclamation-circle mr-1"></i>
            Error loading stats
        </div>
        """


@require_role("admin")
def data_warehouse_connection_status():
    """Get data warehouse connection status as HTML for HTMX."""
    from app.services.refresh_employee_profiles import employee_profiles_service
    from app.services.simple_config import config_get

    try:
        # Check if credentials are configured
        client_id = config_get("data_warehouse.client_id", "")
        client_secret = config_get("data_warehouse.client_secret", "")

        if not client_id or not client_secret:
            return """
            <div>
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                    <i class="fas fa-times-circle mr-1"></i> Not Configured
                </span>
                <p class="text-xs text-gray-500 mt-1">Missing credentials</p>
            </div>
            """

        # Get cache status to check if connection is working
        cache_status = employee_profiles_service.get_cache_stats()
        record_count = cache_status.get("record_count", 0)
        refresh_status = cache_status.get("refresh_status", "unknown")

        if refresh_status == "error":
            return """
            <div>
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                    <i class="fas fa-exclamation-circle mr-1"></i> Error
                </span>
                <p class="text-xs text-gray-500 mt-1">Connection failed</p>
            </div>
            """
        elif record_count > 0:
            return f"""
            <div>
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                    <i class="fas fa-check-circle mr-1"></i> Connected
                </span>
                <p class="text-xs text-gray-500 mt-1">{record_count:,} records cached</p>
            </div>
            """
        else:
            return """
            <div>
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                    <i class="fas fa-question-circle mr-1"></i> No Data
                </span>
                <p class="text-xs text-gray-500 mt-1">Cache empty</p>
            </div>
            """

    except Exception as e:
        return f"""
        <div>
            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                <i class="fas fa-exclamation-triangle mr-1"></i> Unknown
            </span>
            <p class="text-xs text-gray-500 mt-1">{str(e)[:30]}</p>
        </div>
        """


@require_role("admin")
def refresh_single_token(service):
    """Refresh a single API token."""
    from app.services.genesys_service import genesys_service
    from app.services.graph_service import graph_service

    try:
        if service == "genesys":
            # Force token refresh for Genesys
            try:
                genesys_service._refresh_token()
                return """
                <div class="bg-green-50 border-l-2 border-green-400 p-2 mt-2 rounded text-xs">
                    <i class="fas fa-check-circle text-green-600 mr-1"></i>
                    <span class="text-green-700">Token refreshed successfully</span>
                </div>
                """
            except Exception as e:
                return f"""
                <div class="bg-red-50 border-l-2 border-red-400 p-2 mt-2 rounded text-xs">
                    <i class="fas fa-times-circle text-red-600 mr-1"></i>
                    <span class="text-red-700">Failed: {str(e)[:50]}</span>
                </div>
                """

        elif service == "microsoft_graph":
            # Force token refresh for Microsoft Graph
            try:
                graph_service._get_access_token()
                return """
                <div class="bg-green-50 border-l-2 border-green-400 p-2 mt-2 rounded text-xs">
                    <i class="fas fa-check-circle text-green-600 mr-1"></i>
                    <span class="text-green-700">Token refreshed successfully</span>
                </div>
                """
            except Exception as e:
                return f"""
                <div class="bg-red-50 border-l-2 border-red-400 p-2 mt-2 rounded text-xs">
                    <i class="fas fa-times-circle text-red-600 mr-1"></i>
                    <span class="text-red-700">Failed: {str(e)[:50]}</span>
                </div>
                """
        else:
            return """
            <div class="bg-yellow-50 border-l-2 border-yellow-400 p-2 mt-2 rounded text-xs">
                <i class="fas fa-question-circle text-yellow-600 mr-1"></i>
                <span class="text-yellow-700">Unknown service</span>
            </div>
            """

    except Exception as e:
        return f"""
        <div class="bg-red-50 border-l-2 border-red-400 p-2 mt-2 rounded text-xs">
            <i class="fas fa-exclamation-triangle text-red-600 mr-1"></i>
            <span class="text-red-700">Error: {str(e)[:50]}</span>
        </div>
        """


@require_role("admin")
def cache_performance_metrics():
    """Get overall cache performance metrics as HTML."""
    from app.models import SearchCache, ApiToken
    from app.services.genesys_cache_db import genesys_cache_db
    from app.services.refresh_employee_profiles import employee_profiles_service
    from datetime import datetime

    try:
        # Get cache counts
        search_cache_count = SearchCache.query.count()

        # Get Genesys cache stats
        genesys_status = genesys_cache_db.get_cache_status()
        genesys_total = (
            genesys_status.get("groups_cached", 0)
            + genesys_status.get("locations_cached", 0)
            + genesys_status.get("skills_cached", 0)
        )

        # Get data warehouse stats
        dw_status = employee_profiles_service.get_cache_stats()
        dw_count = dw_status.get("record_count", 0)

        # Calculate total cache entries
        total_cache_entries = search_cache_count + genesys_total + dw_count

        # Check token status
        tokens = ApiToken.get_all_tokens_status()
        valid_tokens = sum(1 for t in tokens if not t.get("is_expired"))

        # Check data warehouse status
        dw_connected = dw_count > 0 or dw_status.get("refresh_status") != "error"
        total_services = 3  # Genesys, Graph, Data Warehouse
        active_services = valid_tokens + (1 if dw_connected else 0)

        # Calculate overall health percentage
        service_health = (
            int((active_services / total_services) * 100) if total_services > 0 else 0
        )

        # Get current time
        current_time = datetime.now().strftime("%I:%M %p")

        return f"""
        <div class="grid grid-cols-2 gap-4 text-sm">
            <div>
                <span class="text-gray-500">Total Cache Entries:</span>
                <span class="font-medium text-gray-900 ml-2">{total_cache_entries:,}</span>
            </div>
            <div>
                <span class="text-gray-500">Service Health:</span>
                <span class="font-medium {"text-green-600" if service_health >= 100 else "text-yellow-600" if service_health >= 66 else "text-red-600"} ml-2">{service_health}%</span>
            </div>
            <div>
                <span class="text-gray-500">Active Services:</span>
                <span class="font-medium text-gray-900 ml-2">{active_services} of {total_services}</span>
            </div>
            <div>
                <span class="text-gray-500">Last Updated:</span>
                <span class="font-medium text-gray-900 ml-2">{current_time}</span>
            </div>
        </div>
        """
    except Exception:
        return """
        <div class="text-center text-sm text-gray-500">
            <i class="fas fa-exclamation-circle mr-1"></i>
            Unable to load metrics
        </div>
        """


@require_role("admin")
def api_cache_clear(cache_type):
    """Clear specific cache type."""
    from app.models import SearchCache
    from datetime import datetime, timezone

    try:
        if cache_type == "expired":
            # Clear only expired entries
            now = datetime.now(timezone.utc)
            search_deleted = SearchCache.query.filter(
                SearchCache.expires_at < now
            ).delete()

            # Note: Employee profiles don't have individual expiration
            # They are refreshed as a whole, so skip here

            db.session.commit()

            return f"""
            <div class="bg-green-50 border-l-4 border-green-400 p-4 rounded-lg">
                <div class="flex">
                    <div class="flex-shrink-0">
                        <i class="fas fa-check-circle text-green-400"></i>
                    </div>
                    <div class="ml-3">
                        <p class="text-green-700">Cleared {search_deleted} expired cache entries</p>
                    </div>
                </div>
            </div>
            """
        else:
            return jsonify(
                {"success": False, "message": f"Unknown cache type: {cache_type}"}
            ), 400

    except Exception as e:
        db.session.rollback()
        return f"""
        <div class="bg-red-50 border-l-4 border-red-400 p-4 rounded-lg">
            <div class="flex">
                <div class="flex-shrink-0">
                    <i class="fas fa-times-circle text-red-400"></i>
                </div>
                <div class="ml-3">
                    <p class="text-red-700">Failed to clear cache: {str(e)}</p>
                </div>
            </div>
        </div>
        """


@require_role("admin")
def clear_single_cache(cache_type):
    """Clear a specific cache type."""
    from app.models import SearchCache
    from app.models.genesys import GenesysGroup, GenesysLocation, GenesysSkill
    from app.models.employee_profiles import EmployeeProfiles
    from app.services.audit_service_postgres import audit_service

    try:
        deleted_count = 0
        cache_name = ""

        if cache_type == "search":
            deleted_count = SearchCache.query.delete()
            cache_name = "search cache"
        elif cache_type == "genesys":
            groups_deleted = GenesysGroup.query.delete()
            locations_deleted = GenesysLocation.query.delete()
            skills_deleted = GenesysSkill.query.delete()
            deleted_count = groups_deleted + locations_deleted + skills_deleted
            cache_name = "Genesys cache"
        elif cache_type == "photos":
            # Photos are now part of employee profiles
            deleted_count = EmployeeProfiles.query.delete()
            cache_name = "employee profiles (including photos)"
        else:
            return (
                f"""
            <div class="bg-red-50 border-l-4 border-red-400 p-2 rounded-lg text-sm">
                <p class="text-red-700">Unknown cache type: {cache_type}</p>
            </div>
            """,
                400,
            )

        db.session.commit()

        # Log action
        admin_email = request.headers.get(
            "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
        )
        admin_role = getattr(request, "user_role", None)
        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        audit_service.log_admin_action(
            user_email=admin_email,
            action="clear_cache",
            target=f"cache:{cache_type}",
            user_role=admin_role,
            ip_address=user_ip,
            user_agent=request.headers.get("User-Agent"),
            success=True,
            details={"deleted_count": deleted_count},
        )

        return f"""
        <div class="bg-green-50 border-l-4 border-green-400 p-2 rounded-lg text-sm">
            <p class="text-green-700">Cleared {deleted_count} entries from {cache_name}</p>
        </div>
        """

    except Exception as e:
        db.session.rollback()
        return (
            f"""
        <div class="bg-red-50 border-l-4 border-red-400 p-2 rounded-lg text-sm">
            <p class="text-red-700">Failed to clear cache: {str(e)}</p>
        </div>
        """,
            500,
        )
