"""Admin database management routes."""

import logging
from flask import render_template, request, jsonify, session
from sqlalchemy import text
from app.middleware.auth import require_role
from app.database import db
from app.utils.error_handler import handle_errors
from app.blueprints.admin import admin_bp
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@admin_bp.route("/database")
@require_role("admin")
@handle_errors()
def database():
    """Display database management page."""
    return render_template("admin/database.html")


@admin_bp.route("/api/database/health")
@require_role("admin")
@handle_errors(json_response=True)
def database_health():
    """Get database health and connection stats."""
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
            if db_size_bytes < 1024 * 1024:
                db_size = f"{db_size_bytes / 1024:.1f} KB"
            elif db_size_bytes < 1024 * 1024 * 1024:
                db_size = f"{db_size_bytes / (1024 * 1024):.1f} MB"
            else:
                db_size = f"{db_size_bytes / (1024 * 1024 * 1024):.1f} GB"

            # Get connection count
            result = db.session.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
                )
            ).first()
            connection_count = result[0] if result else 0

            # Get table statistics
            table_stats = []
            stats_query = text("""
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
                    n_live_tup AS row_count
                FROM pg_stat_user_tables
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                LIMIT 10
            """)

            for row in db.session.execute(stats_query):
                table_stats.append(
                    {
                        "name": f"{row.schemaname}.{row.tablename}",
                        "size": row.size,
                        "rows": row.row_count if row.row_count >= 0 else "Unknown",
                    }
                )
        else:
            # SQLite or other database
            db_size = "N/A"
            connection_count = 1
            table_stats = []

        return jsonify(
            {
                "status": db_status,
                "database_type": "PostgreSQL" if is_postgres else "Other",
                "database_size": db_size,
                "connection_count": connection_count,
                "table_stats": table_stats,
            }
        )

    except Exception as e:
        return jsonify(
            {
                "status": "unhealthy",
                "error": str(e),
                "database_type": "Unknown",
                "database_size": "N/A",
                "connection_count": 0,
                "table_stats": [],
            }
        )


@admin_bp.route("/api/database/tables")
@require_role("admin")
@handle_errors(json_response=True)
def database_tables():
    """Get detailed table information."""
    try:
        # Get all tables with their stats
        query = text("""
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
                n_live_tup AS row_count,
                n_dead_tup AS dead_rows,
                last_vacuum,
                last_autovacuum,
                last_analyze,
                last_autoanalyze
            FROM pg_stat_user_tables
            ORDER BY tablename
        """)

        tables = []
        for row in db.session.execute(query):
            tables.append(
                {
                    "schema": row.schemaname,
                    "name": row.tablename,
                    "size": row.size,
                    "rows": row.row_count if row.row_count >= 0 else -1,
                    "dead_rows": row.dead_rows,
                    "last_vacuum": row.last_vacuum.isoformat()
                    if row.last_vacuum
                    else None,
                    "last_autovacuum": row.last_autovacuum.isoformat()
                    if row.last_autovacuum
                    else None,
                    "last_analyze": row.last_analyze.isoformat()
                    if row.last_analyze
                    else None,
                    "last_autoanalyze": row.last_autoanalyze.isoformat()
                    if row.last_autoanalyze
                    else None,
                }
            )

        return jsonify({"tables": tables})

    except Exception as e:
        return jsonify({"error": str(e), "tables": []})


# Service Connection Tests
@admin_bp.route("/api/test/ldap", methods=["GET"])
@require_role("admin")
@handle_errors(json_response=True)
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
@handle_errors(json_response=True)
def test_graph_connection():
    """Test Microsoft Graph API connection."""
    from app.services.graph_service import graph_service

    try:
        # Test connection with fresh token (no cache)
        if graph_service.test_connection():
            return jsonify({"success": True, "message": "Connection successful"})
        else:
            return jsonify(
                {
                    "success": False,
                    "error": "Failed to obtain access token or API call failed",
                }
            )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@admin_bp.route("/api/test/genesys", methods=["GET"])
@require_role("admin")
@handle_errors(json_response=True)
def test_genesys_connection():
    """Test Genesys Cloud API connection."""
    from app.services.genesys_service import genesys_service

    try:
        # Test connection with fresh token (no cache)
        if genesys_service.test_connection():
            return jsonify({"success": True, "message": "Connection successful"})
        else:
            return jsonify(
                {
                    "success": False,
                    "error": "Failed to obtain access token or API call failed",
                }
            )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# Genesys Cache Management
@admin_bp.route("/api/genesys/cache/status", methods=["GET"])
@require_role("admin")
@handle_errors(json_response=True)
def api_genesys_cache_status():
    """Get Genesys cache status."""
    from app.services.genesys_cache_db import genesys_cache_db

    try:
        # Get cache age information
        result = db.session.execute(
            text(
                "SELECT MAX(updated_at) FROM external_service_data WHERE service_name = 'genesys' AND data_type = 'group'"
            )
        ).scalar()

        if not result:
            return jsonify(
                {
                    "needs_refresh": True,
                    "group_cache_age": "0:00:00",
                    "last_updated": None,
                    "cache_counts": {"groups": 0, "skills": 0, "locations": 0},
                }
            )

        # Calculate age
        last_update = result

        # Ensure timezone consistency
        now = datetime.now(timezone.utc)
        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=timezone.utc)

        age_delta = now - last_update

        # Format age as H:MM:SS
        hours = int(age_delta.total_seconds() // 3600)
        minutes = int((age_delta.total_seconds() % 3600) // 60)
        seconds = int(age_delta.total_seconds() % 60)
        age_string = f"{hours}:{minutes:02d}:{seconds:02d}"

        # Get cache counts
        counts = {}
        for data_type in ["group", "skill", "location"]:
            count_result = db.session.execute(
                text(
                    "SELECT COUNT(*) FROM external_service_data WHERE service_name = 'genesys' AND data_type = :data_type"
                ),
                {"data_type": data_type},
            ).scalar()
            counts[f"{data_type}s"] = count_result or 0

        # Check if needs refresh
        needs_refresh = genesys_cache_db.needs_refresh()

        return jsonify(
            {
                "needs_refresh": needs_refresh,
                "group_cache_age": age_string,
                "last_updated": last_update.isoformat() if last_update else None,
                "cache_counts": counts,
            }
        )

    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        return jsonify(
            {
                "needs_refresh": True,
                "group_cache_age": "0:00:00",
                "last_updated": None,
                "cache_counts": {"groups": 0, "skills": 0, "locations": 0},
                "error": str(e),
            }
        )


@admin_bp.route("/api/genesys/refresh-cache", methods=["POST"])
@require_role("admin")
@handle_errors(json_response=True)
def api_genesys_refresh_cache():
    """Refresh Genesys cache."""
    from app.services.genesys_cache_db import genesys_cache_db
    from app.services.audit_service_postgres import audit_service

    try:
        # Get current user
        user_email = session.get("user_email", "system")

        # Refresh cache
        results = genesys_cache_db.refresh_all_caches()

        if any(results.values()):
            # Log the cache refresh
            audit_service.log_admin_action(
                user_email=user_email,
                action="refresh_genesys_cache",
                target="genesys_cache",
                user_role="admin",
                ip_address=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
                success=True,
                details={"results": results},
            )

            return jsonify(
                {
                    "success": True,
                    "message": "Cache refreshed successfully",
                    "results": results,
                }
            )
        else:
            return jsonify(
                {
                    "success": False,
                    "message": "Failed to refresh cache",
                    "results": results,
                }
            )

    except Exception as e:
        logger.error(f"Error refreshing cache: {str(e)}")
        return jsonify({"success": False, "error": str(e)})
