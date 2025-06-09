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

        return jsonify({"success": True, "message": "Database optimization completed"})
    except Exception as e:
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

    # Get query parameters
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    severity = request.args.get("severity")

    query = ErrorLog.query

    if severity:
        query = query.filter_by(severity=severity)

    # Get total count
    total = query.count()

    # Get paginated results
    errors = query.order_by(ErrorLog.timestamp.desc()).offset(offset).limit(limit).all()

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
