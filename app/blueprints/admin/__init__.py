from flask import Blueprint, render_template, jsonify, request, Response, current_app
from app.middleware.auth import require_role
from app.services.genesys_cache_db import genesys_cache_db as genesys_cache
from app.database import db
from datetime import datetime, timedelta
import re

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/")
@require_role("admin")
def index():
    return render_template("admin/index.html")


@admin_bp.route("/cache-status")
@require_role("admin")
def cache_status():
    """Get Genesys cache status."""
    status = genesys_cache.get_cache_status()

    # Add token expiry info for backward compatibility
    from app.models import ApiToken

    token = ApiToken.get_token("genesys")
    if token:
        status["token_expires_at"] = token.expires_at.isoformat()

    return jsonify(status)


@admin_bp.route("/users")
@require_role("admin")
def manage_users():
    """Display user management page."""
    from app.models import User, UserNote

    # Get all users from database
    users = User.get_all_active()

    # Convert to list of dicts for template
    user_list = []
    for user in users:
        # Get all notes for this user
        notes = (
            UserNote.query.filter_by(user_id=user.id, is_active=True)
            .order_by(UserNote.created_at.desc())
            .all()
        )

        user_list.append(
            {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "last_login": user.last_login,
                "created_at": user.created_at,
                "notes": notes,
            }
        )

    return render_template("admin/users.html", users=user_list)


@admin_bp.route("/users/add", methods=["POST"])
@require_role("admin")
def add_user():
    """Add a new user with role."""
    from app.models import User

    email = request.form.get("email", "").strip().lower()
    role = request.form.get("role", "viewer")

    if not email or not re.match(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email
    ):
        return jsonify(
            {
                "success": False,
                "message": "Invalid email format. Even we have standards.",
            }
        ), 400

    # Check if user already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        if existing_user.is_active:
            return jsonify(
                {
                    "success": False,
                    "message": f"User {email} already exists.",
                }
            ), 400
        else:
            # Reactivate existing user
            admin_email = request.headers.get(
                "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
            )
            existing_user.is_active = True
            existing_user.role = role
            existing_user.updated_by = admin_email
            db.session.commit()

            message = f"User {email} reactivated as {role}."
    else:
        # Create new user
        admin_email = request.headers.get(
            "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
        )

        try:
            User.create_user(email=email, role=role, created_by=admin_email)
            message = f"User {email} added as {role}. May the Force be with them."
        except Exception as e:
            return jsonify(
                {
                    "success": False,
                    "message": f"Failed to add user: {str(e)}",
                }
            ), 500

    # Audit log
    from app.services.audit_service_postgres import audit_service

    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="add_user",
        target_resource=f"user:{email}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        additional_data={"new_user": email, "assigned_role": role},
    )

    return jsonify(
        {
            "success": True,
            "message": message,
        }
    )


@admin_bp.route("/users/update", methods=["POST"])
@require_role("admin")
def update_user():
    """Update user role."""
    from app.models import User

    email = request.form.get("email", "").strip().lower()
    new_role = request.form.get("role", "viewer")

    # Get admin info
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )

    # Update user in database
    user = User.update_user_role(email, new_role, admin_email)

    if not user:
        return jsonify(
            {"success": False, "message": "User not found. They must have ghosted us."}
        ), 404

    # Audit log
    from app.services.audit_service_postgres import audit_service

    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="update_user_role",
        target_resource=f"user:{email}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        additional_data={"user": email, "new_role": new_role},
    )

    return jsonify(
        {
            "success": True,
            "message": f"User {email} promoted/demoted to {new_role}. With great power...",
        }
    )


@admin_bp.route("/users/delete", methods=["POST"])
@require_role("admin")
def delete_user():
    """Remove user access."""
    from app.models import User

    email = request.form.get("email", "").strip().lower()

    # Get admin info
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )

    # Deactivate user in database (soft delete)
    user = User.deactivate_user(email, admin_email)

    if not user:
        return jsonify(
            {"success": False, "message": "User not found. Already yeeted?"}
        ), 404

    # Audit log
    from app.services.audit_service_postgres import audit_service

    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="delete_user",
        target_resource=f"user:{email}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        additional_data={"deleted_user": email},
    )

    return jsonify(
        {
            "success": True,
            "message": f"User {email} has been yeeted from the system. 👋",
        }
    )


@admin_bp.route("/audit-logs")
@require_role("admin")
def audit_logs():
    """Display audit logs viewer."""
    return render_template("admin/audit_logs.html")


@admin_bp.route("/api/audit-logs")
@require_role("admin")
def api_audit_logs():
    """API endpoint for querying audit logs."""
    from app.services.audit_service_postgres import audit_service

    # Get query parameters
    event_type = request.args.get("event_type")
    user_email = request.args.get("user_email")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    search_query = request.args.get("search_query")
    ip_address = request.args.get("ip_address")
    success = request.args.get("success")
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))

    # Convert success parameter
    if success is not None:
        success = success.lower() == "true"

    # Query logs
    results = audit_service.query_logs(
        event_type=event_type,
        user_email=user_email,
        start_date=start_date,
        end_date=end_date,
        search_query=search_query,
        ip_address=ip_address,
        success=success,
        limit=limit,
        offset=offset,
    )

    return jsonify(results)


@admin_bp.route("/api/audit-metadata")
@require_role("admin")
def api_audit_metadata():
    """Get metadata for audit log filtering."""
    from app.services.audit_service_postgres import audit_service

    return jsonify(
        {
            "event_types": audit_service.get_event_types(),
            "users": audit_service.get_users_with_activity(),
        }
    )


@admin_bp.route("/database")
@require_role("admin")
def database():
    """Display database management page."""
    return render_template("admin/database.html")


@admin_bp.route("/api/database/health")
@require_role("admin")
def database_health():
    """Get database health and connection stats."""
    from app.database import db
    from sqlalchemy import text
    import os

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
            db_size_bytes = result.size

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
            active_connections = pool.checkedout()
            pool_size = pool.size()
            pool_usage = f"{active_connections}/{pool_size}"
            max_connections = pool_size + pool.overflow()
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


@admin_bp.route("/api/database/tables")
@require_role("admin")
def database_tables():
    """Get table statistics."""
    from app.database import db
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
                        count_result = db.session.execute(
                            text("SELECT COUNT(*) as count FROM " + db.session.connection().execute(
                                text("SELECT quote_ident(:table_name)"),
                                {"table_name": row.tablename}
                            ).scalar())
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
                if row_count > 1000000:
                    size_est = f"{row_count / 1000000:.1f}M rows"
                elif row_count > 1000:
                    size_est = f"{row_count / 1000:.1f}K rows"
                else:
                    size_est = f"{row_count} rows"

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


@admin_bp.route("/api/cache/search/status")
@require_role("admin")
def search_cache_status():
    """Get search cache statistics."""
    from app.models import SearchCache

    try:
        entry_count = SearchCache.query.count()
        return jsonify({"entry_count": entry_count, "status": "active"})
    except Exception as e:
        return jsonify({"entry_count": 0, "status": "error", "error": str(e)})


@admin_bp.route("/api/cache/clear", methods=["POST"])
@require_role("admin")
def clear_caches():
    """Clear all caches."""
    from app.models import SearchCache
    from app.services.genesys_cache_db import genesys_cache_db as genesys_cache
    from app.services.audit_service_postgres import audit_service

    try:
        # Clear search cache
        SearchCache.query.delete()
        db.session.commit()

        # Clear Genesys cache
        genesys_cache.clear()

        # Log action
        admin_email = request.headers.get(
            "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
        )
        admin_role = getattr(request, "user_role", None)
        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        audit_service.log_admin_action(
            user_email=admin_email,
            action="clear_caches",
            target_resource="all_caches",
            user_role=admin_role,
            ip_address=user_ip,
            user_agent=request.headers.get("User-Agent"),
            success=True,
            additional_data={"caches_cleared": ["search", "genesys"]},
        )

        return jsonify({"success": True, "message": "All caches cleared successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@admin_bp.route("/api/database/errors/stats")
@require_role("admin")
def error_stats():
    """Get error log statistics."""
    from app.models import ErrorLog
    from datetime import timedelta

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


@admin_bp.route("/api/sessions/stats")
@require_role("admin")
def session_stats():
    """Get active session statistics."""
    from app.models import UserSession
    from datetime import timedelta

    try:
        # Active sessions (activity in last 30 minutes)
        active_sessions = UserSession.query.filter(
            UserSession.last_activity > datetime.utcnow() - timedelta(minutes=30),
            UserSession.is_active.is_(True),
        ).count()

        return jsonify({"active_sessions": active_sessions})
    except Exception as e:
        return jsonify({"active_sessions": 0, "error": str(e)})


@admin_bp.route("/api/database/optimize", methods=["POST"])
@require_role("admin")
def optimize_database():
    """Run database optimization (VACUUM ANALYZE)."""
    from app.database import db
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
            safe_table = db.session.connection().execute(
                text("SELECT quote_ident(:table_name)"),
                {"table_name": row.tablename}
            ).scalar()
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
            target_resource="database",
            user_role=admin_role,
            ip_address=user_ip,
            user_agent=request.headers.get("User-Agent"),
            success=True,
            additional_data={"operation": "analyze_tables"},
        )

        return jsonify({"success": True, "message": "Database optimization completed"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@admin_bp.route("/api/database/export/audit-logs")
@require_role("admin")
def export_audit_logs():
    """Export audit logs as CSV."""
    from app.models import AuditLog
    from io import StringIO
    import csv
    from datetime import datetime

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


@admin_bp.route("/error-logs")
@require_role("admin")
def error_logs():
    """Display error logs viewer."""
    return render_template("admin/error_logs.html")


@admin_bp.route("/api/error-logs")
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


@admin_bp.route("/sessions")
@require_role("admin")
def sessions():
    """Display active sessions."""
    return render_template("admin/sessions.html")


@admin_bp.route("/api/sessions")
@require_role("admin")
def api_sessions():
    """Get active user sessions."""
    from app.models import UserSession
    from datetime import timedelta

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


@admin_bp.route("/api/sessions/<int:session_id>/terminate", methods=["POST"])
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
        target_resource=f"session:{session_id}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        additional_data={"terminated_user": session.user_email},
    )

    return jsonify({"success": True, "message": "Session terminated"})


@admin_bp.route("/api/tokens/status")
@require_role("admin")
def tokens_status():
    """Get status of all API tokens."""
    from app.models import ApiToken

    try:
        tokens = ApiToken.get_all_tokens_status()
        return jsonify({"tokens": tokens})
    except Exception as e:
        return jsonify({"error": str(e), "tokens": []})


@admin_bp.route("/api/tokens/refresh/<service_name>", methods=["POST"])
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
                target_resource=f"token:{service_name}",
                user_role=admin_role,
                ip_address=user_ip,
                user_agent=request.headers.get("User-Agent"),
                success=True,
                additional_data={"service": service_name},
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


@admin_bp.route("/api/genesys/cache/status")
@require_role("admin")
def genesys_cache_status():
    """Get detailed Genesys cache status."""
    from app.services.genesys_cache_db import genesys_cache_db

    return jsonify(genesys_cache_db.get_cache_status())


@admin_bp.route("/api/genesys/cache/config", methods=["GET", "POST"])
@require_role("admin")
def genesys_cache_config():
    """Get or update Genesys cache configuration."""
    from app.services.configuration_service import config_get
    from app.services.audit_service_postgres import audit_service

    if request.method == "GET":
        # Get current configuration
        refresh_period = int(config_get("genesys", "cache_refresh_period", 21600))
        return jsonify(
            {
                "refresh_period_seconds": refresh_period,
                "refresh_period_hours": refresh_period / 3600,
            }
        )

    else:  # POST
        try:
            # Get new refresh period in hours
            hours = float(request.json.get("refresh_period_hours", 6))
            seconds = int(hours * 3600)

            # Update configuration
            config_service = current_app.config.get("CONFIG_SERVICE")
            if config_service:
                # Get admin email for updated_by
                admin_email = request.headers.get(
                    "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
                )
                config_service.set(
                    "genesys", "cache_refresh_period", seconds, updated_by=admin_email
                )

                # Log action
                admin_email = request.headers.get(
                    "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
                )
                admin_role = getattr(request, "user_role", None)
                user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

                audit_service.log_admin_action(
                    user_email=admin_email,
                    action="update_genesys_cache_config",
                    target_resource="configuration",
                    user_role=admin_role,
                    ip_address=user_ip,
                    user_agent=request.headers.get("User-Agent"),
                    success=True,
                    additional_data={
                        "setting": "cache_refresh_period",
                        "old_value": config_get(
                            "genesys", "cache_refresh_period", 21600
                        ),
                        "new_value": seconds,
                        "hours": hours,
                    },
                )

                return jsonify(
                    {
                        "success": True,
                        "message": f"Cache refresh period updated to {hours} hours",
                    }
                )
            else:
                return jsonify(
                    {"success": False, "message": "Configuration service not available"}
                ), 500

        except Exception as e:
            return jsonify(
                {
                    "success": False,
                    "message": f"Failed to update configuration: {str(e)}",
                }
            ), 500


@admin_bp.route("/configuration")
@require_role("admin")
def configuration():
    """Display configuration management page."""
    return render_template("admin/configuration.html")


@admin_bp.route("/api/configuration", methods=["GET", "POST"])
@require_role("admin")
def api_configuration():
    """Get or update configuration values."""
    from app.services.configuration_service import config_get
    from app.services.audit_service_postgres import audit_service

    if request.method == "GET":
        # Get all configuration values grouped by category
        config_data = {
            "flask": {
                "FLASK_HOST": config_get("flask", "FLASK_HOST", "0.0.0.0"),
                "FLASK_PORT": config_get("flask", "FLASK_PORT", "5000"),
                "FLASK_DEBUG": config_get("flask", "FLASK_DEBUG", "False"),
                "SECRET_KEY": config_get("flask", "SECRET_KEY", ""),
            },
            "auth": {
                "SESSION_TIMEOUT_MINUTES": config_get(
                    "auth", "SESSION_TIMEOUT_MINUTES", "60"
                ),
            },
            "search": {
                "SEARCH_OVERALL_TIMEOUT": config_get(
                    "search", "SEARCH_OVERALL_TIMEOUT", "20"
                ),
                "CACHE_EXPIRATION_HOURS": config_get(
                    "search", "CACHE_EXPIRATION_HOURS", "24"
                ),
                "SEARCH_LAZY_LOAD_PHOTOS": config_get(
                    "search", "lazy_load_photos", "true"
                ),
            },
            "audit": {
                "AUDIT_LOG_RETENTION_DAYS": config_get(
                    "audit", "AUDIT_LOG_RETENTION_DAYS", "90"
                ),
            },
            "ldap": {
                "LDAP_HOST": config_get("ldap", "LDAP_HOST", ""),
                "LDAP_PORT": config_get("ldap", "LDAP_PORT", "389"),
                "LDAP_USE_SSL": config_get("ldap", "LDAP_USE_SSL", "False"),
                "LDAP_BIND_DN": config_get("ldap", "LDAP_BIND_DN", ""),
                "LDAP_BIND_PASSWORD": config_get("ldap", "LDAP_BIND_PASSWORD", ""),
                "LDAP_BASE_DN": config_get("ldap", "LDAP_BASE_DN", ""),
                "LDAP_USER_SEARCH_BASE": config_get(
                    "ldap", "LDAP_USER_SEARCH_BASE", ""
                ),
                "LDAP_CONNECT_TIMEOUT": config_get("ldap", "LDAP_CONNECT_TIMEOUT", "5"),
                "LDAP_OPERATION_TIMEOUT": config_get(
                    "ldap", "LDAP_OPERATION_TIMEOUT", "10"
                ),
            },
            "graph": {
                "GRAPH_CLIENT_ID": config_get("graph", "GRAPH_CLIENT_ID", ""),
                "GRAPH_CLIENT_SECRET": config_get("graph", "GRAPH_CLIENT_SECRET", ""),
                "GRAPH_TENANT_ID": config_get("graph", "GRAPH_TENANT_ID", ""),
                "GRAPH_API_TIMEOUT": config_get("graph", "GRAPH_API_TIMEOUT", "15"),
            },
            "genesys": {
                "GENESYS_CLIENT_ID": config_get("genesys", "GENESYS_CLIENT_ID", ""),
                "GENESYS_CLIENT_SECRET": config_get(
                    "genesys", "GENESYS_CLIENT_SECRET", ""
                ),
                "GENESYS_REGION": config_get(
                    "genesys", "GENESYS_REGION", "mypurecloud.com"
                ),
                "GENESYS_API_TIMEOUT": config_get(
                    "genesys", "GENESYS_API_TIMEOUT", "15"
                ),
                "GENESYS_CACHE_REFRESH_HOURS": str(
                    int(config_get("genesys", "cache_refresh_period", "21600")) / 3600
                ),
            },
        }
        return jsonify(config_data)

    else:  # POST
        try:
            updates = request.json.get("updates", {})
            config_service = current_app.config.get("CONFIG_SERVICE")

            if not config_service:
                return jsonify(
                    {"success": False, "error": "Configuration service not available"}
                ), 500

            # Track changes for audit log
            changes = []

            # Apply updates
            for category, settings in updates.items():
                for key, value in settings.items():
                    # Special handling for cache refresh hours
                    if key == "GENESYS_CACHE_REFRESH_HOURS":
                        key = "cache_refresh_period"
                        value = str(int(float(value) * 3600))
                    # Special handling for lazy load photos
                    elif key == "SEARCH_LAZY_LOAD_PHOTOS":
                        key = "lazy_load_photos"

                    old_value = config_get(category, key, "")
                    if str(old_value) != str(value):
                        # Get the admin email for updated_by
                        admin_email = request.headers.get(
                            "X-MS-CLIENT-PRINCIPAL-NAME",
                            request.remote_user or "unknown",
                        )
                        config_service.set(category, key, value, updated_by=admin_email)
                        changes.append(
                            {
                                "category": category,
                                "key": key,
                                "old_value": old_value,
                                "new_value": value,
                            }
                        )

            # Log configuration changes
            if changes:
                admin_email = request.headers.get(
                    "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
                )
                admin_role = getattr(request, "user_role", None)
                user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

                audit_service.log_config_change(
                    user_email=admin_email,
                    action="update_configuration",
                    config_key="multiple",
                    config_section="multiple",
                    old_value="various",
                    new_value="various",
                    user_role=admin_role,
                    ip_address=user_ip,
                    user_agent=request.headers.get("User-Agent"),
                    success=True,
                    additional_data={"changes": changes},
                )

            return jsonify(
                {
                    "success": True,
                    "message": f"Configuration updated successfully ({len(changes)} changes)",
                    "changes": len(changes),
                }
            )

        except Exception as e:
            return jsonify(
                {"success": False, "error": f"Failed to update configuration: {str(e)}"}
            ), 500


@admin_bp.route("/api/test/ldap", methods=["GET"])
@require_role("admin")
def test_ldap_connection():
    """Test LDAP connection with current configuration."""
    from app.services.ldap_service import test_connection

    try:
        result = test_connection()
        return jsonify(
            {
                "success": result,
                "message": "Connection successful" if result else "Connection failed",
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@admin_bp.route("/api/test/graph", methods=["GET"])
@require_role("admin")
def test_graph_connection():
    """Test Microsoft Graph API connection."""
    from app.services.graph_service import graph_service

    try:
        # Try to get token
        if graph_service.refresh_token_if_needed():
            return jsonify({"success": True, "message": "Connection successful"})
        else:
            return jsonify({"success": False, "error": "Failed to obtain access token"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@admin_bp.route("/api/test/genesys", methods=["GET"])
@require_role("admin")
def test_genesys_connection():
    """Test Genesys Cloud API connection."""
    from app.services.genesys_service import genesys_service

    try:
        # Try to get token
        if genesys_service.refresh_token_if_needed():
            return jsonify({"success": True, "message": "Connection successful"})
        else:
            return jsonify({"success": False, "error": "Failed to obtain access token"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@admin_bp.route("/api/genesys/cache-status", methods=["GET"])
@require_role("admin")
def get_genesys_cache_status():
    """Get Genesys cache status."""
    try:
        status = genesys_cache.get_cache_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/api/genesys/refresh-cache", methods=["POST"])
@require_role("admin")
def refresh_genesys_cache():
    """Manually refresh Genesys cache."""
    try:
        cache_type = request.json.get("type", "all")

        if cache_type == "all":
            results = genesys_cache.refresh_all()
        elif cache_type == "locations":
            results = {"locations": genesys_cache.refresh_locations()}
        elif cache_type == "groups":
            results = {"groups": genesys_cache.refresh_groups()}
        elif cache_type == "skills":
            results = {"skills": genesys_cache.refresh_skills()}
        else:
            return jsonify({"error": "Invalid cache type"}), 400

        return jsonify({"success": True, "results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/api/users/<int:user_id>/notes", methods=["GET"])
@require_role("admin")
def get_user_notes(user_id):
    """Get all notes for a specific user."""
    from app.models import UserNote

    notes = (
        UserNote.query.filter_by(user_id=user_id, is_active=True)
        .order_by(UserNote.created_at.desc())
        .all()
    )

    notes_list = []
    for note in notes:
        notes_list.append(
            {
                "id": note.id,
                "note": note.note,
                "created_by": note.created_by,
                "created_at": note.created_at.isoformat(),
                "updated_at": note.updated_at.isoformat(),
            }
        )

    return jsonify({"notes": notes_list})


@admin_bp.route("/api/users/<int:user_id>/notes", methods=["POST"])
@require_role("editor")  # Allow editors and admins
def add_user_note(user_id):
    """Add a note for a specific user."""
    from app.models import User, UserNote
    from app.services.audit_service_postgres import audit_service

    # Verify user exists
    user = User.query.get(user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    note_text = request.json.get("note", "").strip()
    if not note_text:
        return jsonify({"success": False, "message": "Note cannot be empty"}), 400

    # Get admin info
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )

    # Create note
    note = UserNote(user_id=user_id, note=note_text, created_by=admin_email)
    db.session.add(note)
    db.session.commit()

    # Audit log
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="add_user_note",
        target_resource=f"user:{user.email}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        additional_data={
            "user": user.email,
            "note_id": note.id,
            "note_preview": note_text[:50] + "..."
            if len(note_text) > 50
            else note_text,
        },
    )

    return jsonify(
        {
            "success": True,
            "message": "Note added successfully",
            "note": {
                "id": note.id,
                "note": note.note,
                "created_by": note.created_by,
                "created_at": note.created_at.isoformat(),
            },
        }
    )


@admin_bp.route("/api/users/notes/<int:note_id>", methods=["PUT"])
@require_role("editor")  # Allow editors and admins
def update_user_note(note_id):
    """Update an existing user note."""
    from app.models import UserNote
    from app.services.audit_service_postgres import audit_service

    note = UserNote.query.get(note_id)
    if not note or not note.is_active:
        return jsonify({"success": False, "message": "Note not found"}), 404

    note_text = request.json.get("note", "").strip()
    if not note_text:
        return jsonify({"success": False, "message": "Note cannot be empty"}), 400

    old_note_text = note.note
    note.note = note_text
    db.session.commit()

    # Audit log
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="update_user_note",
        target_resource=f"note:{note_id}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        additional_data={
            "note_id": note_id,
            "old_note": old_note_text[:50] + "..."
            if len(old_note_text) > 50
            else old_note_text,
            "new_note": note_text[:50] + "..." if len(note_text) > 50 else note_text,
        },
    )

    return jsonify({"success": True, "message": "Note updated successfully"})


@admin_bp.route("/api/users/notes/<int:note_id>", methods=["DELETE"])
@require_role("editor")  # Allow editors and admins
def delete_user_note(note_id):
    """Delete (soft delete) a user note."""
    from app.models import UserNote
    from app.services.audit_service_postgres import audit_service

    note = UserNote.query.get(note_id)
    if not note or not note.is_active:
        return jsonify({"success": False, "message": "Note not found"}), 404

    note.is_active = False
    db.session.commit()

    # Audit log
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="delete_user_note",
        target_resource=f"note:{note_id}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        additional_data={
            "note_id": note_id,
            "note_preview": note.note[:50] + "..."
            if len(note.note) > 50
            else note.note,
        },
    )

    return jsonify({"success": True, "message": "Note deleted successfully"})


@admin_bp.route("/api/users/by-email/<email>/notes", methods=["GET"])
@require_role("viewer")
def get_user_notes_by_email(email):
    """Get notes for a user by email (for search results)."""
    from app.models import User, UserNote

    # All authenticated users can see notes
    user_role = getattr(request, "user_role", "viewer")

    # Find user by email
    user = User.query.filter_by(email=email.lower()).first()
    if not user:
        return jsonify({"notes": []})

    # Get active notes
    notes = (
        UserNote.query.filter_by(user_id=user.id, is_active=True)
        .order_by(UserNote.created_at.desc())
        .all()
    )

    notes_list = []
    for note in notes:
        notes_list.append(
            {
                "id": note.id,
                "note": note.note,
                "created_by": note.created_by,
                "created_at": note.created_at.isoformat(),
                "updated_at": note.updated_at.isoformat(),
                "can_edit": user_role
                in ["admin", "editor"],  # Add edit permission flag
            }
        )

    return jsonify({"notes": notes_list, "can_edit": user_role in ["admin", "editor"]})


@admin_bp.route("/api/users/by-email/<email>/notes", methods=["POST"])
@require_role("editor")  # Allow editors and admins
def add_user_note_by_email(email):
    """Add a note for a user by email."""
    from app.models import User, UserNote
    from app.services.audit_service_postgres import audit_service

    # Find user by email, create if doesn't exist
    user = User.query.filter_by(email=email.lower()).first()

    if not user:
        # Create user if they don't exist
        admin_email = request.headers.get(
            "X-MS-CLIENT-PRINCIPAL_NAME", request.remote_user or "unknown"
        )
        user = User.create_user(
            email=email.lower(), role="viewer", created_by=admin_email
        )

    note_text = request.json.get("note", "").strip()
    if not note_text:
        return jsonify({"success": False, "message": "Note cannot be empty"}), 400

    # Get admin info
    admin_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )

    # Create note
    note = UserNote(user_id=user.id, note=note_text, created_by=admin_email)
    db.session.add(note)
    db.session.commit()

    # Audit log
    admin_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    audit_service.log_admin_action(
        user_email=admin_email,
        action="add_user_note",
        target_resource=f"user:{user.email}",
        user_role=admin_role,
        ip_address=user_ip,
        user_agent=request.headers.get("User-Agent"),
        success=True,
        additional_data={
            "user": user.email,
            "note_id": note.id,
            "note_preview": note_text[:50] + "..."
            if len(note_text) > 50
            else note_text,
        },
    )

    return jsonify(
        {
            "success": True,
            "message": "Note added successfully",
            "note": {
                "id": note.id,
                "note": note.note,
                "created_by": note.created_by,
                "created_at": note.created_at.isoformat(),
            },
        }
    )
