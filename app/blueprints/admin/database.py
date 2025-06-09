"""
Database management functionality for admin blueprint.
Handles database health checks, table statistics, optimization, and session management.
"""

from flask import render_template, jsonify, request, Response
from app.middleware.auth import require_role
from app.database import db
from datetime import datetime, timedelta
from io import StringIO
import csv
import os


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
        active_sessions = UserSession.query.filter(
            UserSession.last_activity > datetime.utcnow() - timedelta(minutes=30),
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
    from app.services.genesys_cache_db import get_cache_status

    try:
        search_cache_count = SearchCache.query.count()
        tokens = ApiToken.get_all_tokens_status()
        genesys_cache = get_cache_status()

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
    from app.services.genesys_cache_db import refresh_all_caches
    from app.services.audit_service_postgres import audit_service

    try:
        if cache_type == "genesys":
            result = refresh_all_caches()

            # Log action
            admin_email = request.headers.get(
                "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
            )
            admin_role = getattr(request, "user_role", None)
            user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

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
                                Cached {result.get("groups", {}).get("cached", 0)} groups,
                                {result.get("skills", {}).get("cached", 0)} skills,
                                {result.get("locations", {}).get("cached", 0)} locations.
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
        GraphPhoto,
    )
    from app.services.audit_service_postgres import audit_service

    try:
        # Clear search cache
        search_deleted = SearchCache.query.delete()

        # Clear Genesys caches
        groups_deleted = GenesysGroup.query.delete()
        locations_deleted = GenesysLocation.query.delete()
        skills_deleted = GenesysSkill.query.delete()

        # Clear Graph photos
        photos_deleted = GraphPhoto.query.delete()

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
                "graph_photos": photos_deleted,
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
                            and {photos_deleted} cached photos.
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
                    "graph_photos": photos_deleted,
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
            writer.writerow(
                [
                    log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    log.event_type,
                    log.user_email or "",
                    log.ip_address or "",
                    "Yes" if log.success else "No",
                    log.message or "",
                    log.search_query or "",
                    log.results_count if log.results_count is not None else "",
                    ", ".join(log.services_used) if log.services_used else "",
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

    # Get active sessions (not expired and active in last 24 hours)
    active_sessions = (
        UserSession.query.filter(
            UserSession.expires_at > datetime.utcnow(),
            UserSession.last_activity > datetime.utcnow() - timedelta(hours=24),
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
    """Render cache status as HTML for Htmx."""
    from app.models import SearchCache, ApiToken
    from app.services.genesys_cache_db import get_cache_status

    try:
        # Get search cache count
        search_cache_count = SearchCache.query.count()

        # Get API token statuses
        tokens = ApiToken.get_all_tokens_status()
        genesys_token = next((t for t in tokens if t["service"] == "genesys"), None)
        graph_token = next(
            (t for t in tokens if t["service"] == "microsoft_graph"), None
        )

        # Get Genesys cache status
        genesys_cache = get_cache_status()

        html = f"""
        <div class="space-y-2">
            <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Search Cache:</span>
                <span class="text-sm font-medium text-gray-900">{search_cache_count} entries</span>
            </div>
        """

        # Genesys token status
        if genesys_token:
            status_color = "red" if genesys_token["is_expired"] else "green"
            status_text = "Expired" if genesys_token["is_expired"] else "Valid"
            html += f"""
            <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Genesys Token:</span>
                <span class="px-2 py-1 text-xs rounded-full bg-{status_color}-100 text-{status_color}-800">{status_text}</span>
            </div>
            """

        # Graph token status
        if graph_token:
            status_color = "red" if graph_token["is_expired"] else "green"
            status_text = "Expired" if graph_token["is_expired"] else "Valid"
            html += f"""
            <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Graph API Token:</span>
                <span class="px-2 py-1 text-xs rounded-full bg-{status_color}-100 text-{status_color}-800">{status_text}</span>
            </div>
            """

        html += '<hr class="my-2 border-gray-200">'

        # Genesys cache details
        if genesys_cache:
            html += f"""
            <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Genesys Groups:</span>
                <span class="text-sm font-medium text-blue-600">{genesys_cache.get("groups_cached", 0)}</span>
            </div>
            <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Genesys Locations:</span>
                <span class="text-sm font-medium text-blue-600">{genesys_cache.get("locations_cached", 0)}</span>
            </div>
            """

            if genesys_cache.get("group_cache_age"):
                age = _format_cache_age(genesys_cache["group_cache_age"])
                refresh_badge = ""
                if genesys_cache.get("needs_refresh"):
                    refresh_badge = '<span class="ml-2 px-2 py-1 text-xs rounded-full bg-yellow-100 text-yellow-800">Refresh Needed</span>'
                html += f"""
                <div class="flex justify-between items-center">
                    <span class="text-sm text-gray-600">Cache Age:</span>
                    <span class="text-sm text-gray-500">{age}{refresh_badge}</span>
                </div>
                """

        html += "</div>"
        return html

    except Exception as e:
        return f'<div class="text-red-600 text-sm">Error loading cache status: {str(e)}</div>'


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


def _render_session_stats():
    """Render session statistics as HTML for Htmx."""
    from app.models import UserSession

    try:
        # Active sessions (activity in last 30 minutes)
        active_sessions = UserSession.query.filter(
            UserSession.last_activity > datetime.utcnow() - timedelta(minutes=30),
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
        # Format timestamp
        timestamp = error.timestamp.strftime("%m/%d %H:%M:%S")

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
    # Format timestamps
    timestamp = error.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")

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

    now = datetime.utcnow()

    for session in sessions:
        # Format timestamps
        created = session.created_at.strftime("%m/%d %H:%M")
        last_activity = session.last_activity.strftime("%m/%d %H:%M")

        # Calculate time since last activity
        idle_time = now - session.last_activity
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
                <button onclick="confirmTerminate({session.id}, '{session.user_email}')" 
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
