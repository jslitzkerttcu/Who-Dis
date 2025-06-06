import sqlite3
import json
import threading
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from flask import g

logger = logging.getLogger(__name__)


class AuditService:
    """Flask-aware audit service with proper SQLite integration"""

    def __init__(self, app=None, db_path: str = "logs/audit.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_lock = threading.Lock()
        self._initialized = False

        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize with Flask app following Flask extension pattern"""
        app.config.setdefault("AUDIT_DATABASE", str(self.db_path))
        app.teardown_appcontext(self.close_connection)
        # Don't initialize database here - do it lazily on first use

    def get_db(self):
        """Get database connection for current request context"""
        db = getattr(g, "_audit_db", None)
        if db is None:
            db = g._audit_db = sqlite3.connect(
                str(self.db_path), timeout=30.0, check_same_thread=False
            )
            db.row_factory = sqlite3.Row
            # Set pragmas for each connection
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=NORMAL")
            db.execute("PRAGMA busy_timeout=30000")
            db.execute("PRAGMA temp_store=MEMORY")
            db.execute("PRAGMA mmap_size=30000000000")
        return db

    def close_connection(self, exception):
        """Close database connection at end of request"""
        db = getattr(g, "_audit_db", None)
        if db is not None:
            db.close()

    def _init_database(self):
        """Initialize database schema"""
        with self._init_lock:
            if self._initialized:
                return

            try:
                db = self.get_db()

                # Create table
                db.execute("""
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        event_type TEXT NOT NULL,
                        user_email TEXT NOT NULL,
                        user_role TEXT,
                        ip_address TEXT,
                        action TEXT NOT NULL,
                        target_resource TEXT,
                        search_query TEXT,
                        search_results_count INTEGER,
                        search_services TEXT,
                        success BOOLEAN DEFAULT 1,
                        error_message TEXT,
                        additional_data TEXT,
                        session_id TEXT,
                        user_agent TEXT
                    )
                """)

                # Create indexes
                db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC)"
                )
                db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_audit_user_email ON audit_log(user_email)"
                )
                db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_log(event_type)"
                )
                db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_audit_search ON audit_log(search_query)"
                )

                db.commit()
                self._initialized = True
                logger.info("Audit database initialized successfully")

            except Exception as e:
                logger.error(f"Failed to initialize audit database: {e}")
                # Don't block app startup
                self._initialized = True

    def _safe_execute(self, query, params=None):
        """Safely execute a query with automatic retry"""
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                db = self.get_db()
                cursor = db.execute(query, params or ())
                db.commit()
                return cursor
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    logger.warning(
                        f"Database locked, retry {attempt + 1}/{max_retries}"
                    )
                    import time

                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    logger.error(f"Database operation failed: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected database error: {e}")
                raise

    # Public logging methods

    def log_search(
        self,
        user_email: str,
        search_query: str,
        results_count: int,
        services: List[str],
        **kwargs,
    ):
        try:
            self._safe_execute(
                """
                INSERT INTO audit_log (
                    event_type, user_email, user_role, ip_address,
                    action, search_query, search_results_count,
                    search_services, success, error_message,
                    additional_data, session_id, user_agent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "search",
                    user_email,
                    kwargs.get("user_role"),
                    kwargs.get("ip_address"),
                    "identity_search",
                    search_query,
                    results_count,
                    json.dumps(services),
                    kwargs.get("success", True),
                    kwargs.get("error_message"),
                    json.dumps(kwargs.get("additional_data"))
                    if kwargs.get("additional_data")
                    else None,
                    kwargs.get("session_id"),
                    kwargs.get("user_agent"),
                ),
            )
        except Exception as e:
            logger.error(f"Failed to log search: {e}")

    def log_access(self, user_email: str, action: str, target_resource: str, **kwargs):
        try:
            self._safe_execute(
                """
                INSERT INTO audit_log (
                    event_type, user_email, user_role, ip_address,
                    action, target_resource, success, error_message,
                    additional_data, session_id, user_agent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "access",
                    user_email,
                    kwargs.get("user_role"),
                    kwargs.get("ip_address"),
                    action,
                    target_resource,
                    kwargs.get("success", True),
                    kwargs.get("error_message"),
                    json.dumps(kwargs.get("additional_data"))
                    if kwargs.get("additional_data")
                    else None,
                    kwargs.get("session_id"),
                    kwargs.get("user_agent"),
                ),
            )
        except Exception as e:
            logger.error(f"Failed to log access: {e}")

    def log_admin_action(
        self, user_email: str, action: str, target_resource: str, **kwargs
    ):
        try:
            self._safe_execute(
                """
                INSERT INTO audit_log (
                    event_type, user_email, user_role, ip_address,
                    action, target_resource, success, error_message,
                    additional_data, session_id, user_agent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "admin",
                    user_email,
                    kwargs.get("user_role"),
                    kwargs.get("ip_address"),
                    action,
                    target_resource,
                    kwargs.get("success", True),
                    kwargs.get("error_message"),
                    json.dumps(kwargs.get("additional_data"))
                    if kwargs.get("additional_data")
                    else None,
                    kwargs.get("session_id"),
                    kwargs.get("user_agent"),
                ),
            )
        except Exception as e:
            logger.error(f"Failed to log admin action: {e}")

    def log_config_change(
        self, user_email: str, action: str, config_key: str, **kwargs
    ):
        try:
            additional_data = kwargs.get("additional_data", {})
            additional_data.update(
                {
                    "old_value": kwargs.get("old_value"),
                    "new_value": kwargs.get("new_value"),
                }
            )

            self._safe_execute(
                """
                INSERT INTO audit_log (
                    event_type, user_email, user_role, ip_address,
                    action, target_resource, success, error_message,
                    additional_data, session_id, user_agent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "config",
                    user_email,
                    kwargs.get("user_role"),
                    kwargs.get("ip_address"),
                    action,
                    config_key,
                    kwargs.get("success", True),
                    kwargs.get("error_message"),
                    json.dumps(additional_data),
                    kwargs.get("session_id"),
                    kwargs.get("user_agent"),
                ),
            )
        except Exception as e:
            logger.error(f"Failed to log config change: {e}")

    def log_error(self, error_type: str, error_message: str, **kwargs):
        try:
            additional_data = kwargs.get("additional_data", {})
            additional_data.update(
                {
                    "stack_trace": kwargs.get("stack_trace"),
                    "request_method": kwargs.get("request_method"),
                }
            )

            self._safe_execute(
                """
                INSERT INTO audit_log (
                    event_type, user_email, user_role, ip_address,
                    action, target_resource, success, error_message,
                    additional_data, session_id, user_agent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "error",
                    kwargs.get("user_email", "system"),
                    kwargs.get("user_role"),
                    kwargs.get("ip_address"),
                    error_type,
                    kwargs.get("request_path"),
                    False,
                    error_message,
                    json.dumps(additional_data),
                    kwargs.get("session_id"),
                    kwargs.get("user_agent"),
                ),
            )
        except Exception as e:
            logger.error(f"Failed to log error: {e}")

    # Query methods

    def query_logs(
        self,
        event_type: Optional[str] = None,
        user_email: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search_query: Optional[str] = None,
        ip_address: Optional[str] = None,
        success: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        try:
            db = self.get_db()
            where_clauses = []
            params: List[Union[str, int]] = []

            if event_type:
                where_clauses.append("event_type = ?")
                params.append(event_type)
            if user_email:
                where_clauses.append("user_email LIKE ?")
                params.append(f"%{user_email}%")
            if start_date:
                where_clauses.append("timestamp >= ?")
                params.append(start_date)
            if end_date:
                where_clauses.append("timestamp <= ?")
                params.append(end_date)
            if search_query:
                where_clauses.append(
                    "(search_query LIKE ? OR action LIKE ? OR target_resource LIKE ?)"
                )
                params.extend([f"%{search_query}%"] * 3)
            if ip_address:
                where_clauses.append("ip_address LIKE ?")
                params.append(f"%{ip_address}%")
            if success is not None:
                where_clauses.append("success = ?")
                params.append(1 if success else 0)

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            # Get total count
            count_sql = f"SELECT COUNT(*) as total FROM audit_log WHERE {where_sql}"
            total_count = db.execute(count_sql, params).fetchone()["total"]

            # Get results
            query_sql = f"""
                SELECT * FROM audit_log 
                WHERE {where_sql}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])

            results = [dict(row) for row in db.execute(query_sql, params)]

            return {
                "results": results,
                "total": total_count,
                "limit": limit,
                "offset": offset,
            }
        except Exception as e:
            logger.error(f"Failed to query logs: {e}")
            return {
                "results": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
            }

    def get_recent_searches(self, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT * FROM audit_log
                WHERE event_type = 'search'
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (limit,),
            )
            return [dict(row) for row in cursor]
        except Exception as e:
            logger.error(f"Failed to get recent searches: {e}")
            return []

    def get_event_types(self) -> List[str]:
        try:
            db = self.get_db()
            cursor = db.execute("""
                SELECT DISTINCT event_type 
                FROM audit_log 
                ORDER BY event_type
            """)
            return [row["event_type"] for row in cursor]
        except Exception as e:
            logger.error(f"Failed to get event types: {e}")
            return []

    def get_users_with_activity(self) -> List[str]:
        try:
            db = self.get_db()
            cursor = db.execute("""
                SELECT DISTINCT user_email 
                FROM audit_log 
                WHERE user_email != 'system'
                ORDER BY user_email
            """)
            return [row["user_email"] for row in cursor]
        except Exception as e:
            logger.error(f"Failed to get users: {e}")
            return []

    def get_user_activity(
        self, user_email: str, days: int = 30
    ) -> List[Dict[str, Any]]:
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT * FROM audit_log
                WHERE user_email = ?
                AND timestamp >= datetime('now', ? || ' days')
                ORDER BY timestamp DESC
            """,
                (user_email, -days),
            )
            return [dict(row) for row in cursor]
        except Exception as e:
            logger.error(f"Failed to get user activity: {e}")
            return []

    def get_search_statistics(self, days: int = 30) -> Dict[str, Any]:
        try:
            db = self.get_db()
            stats = dict(
                db.execute(
                    """
                SELECT 
                    COUNT(*) as total_searches,
                    COUNT(DISTINCT user_email) as unique_users,
                    COUNT(DISTINCT search_query) as unique_queries,
                    AVG(search_results_count) as avg_results,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_searches
                FROM audit_log
                WHERE event_type = 'search'
                AND timestamp >= datetime('now', ? || ' days')
            """,
                    (-days,),
                ).fetchone()
            )

            cursor = db.execute(
                """
                SELECT search_query, COUNT(*) as count
                FROM audit_log
                WHERE event_type = 'search'
                AND timestamp >= datetime('now', ? || ' days')
                GROUP BY search_query
                ORDER BY count DESC
                LIMIT 10
            """,
                (-days,),
            )

            stats["top_searches"] = [dict(row) for row in cursor]
            return stats
        except Exception as e:
            logger.error(f"Failed to get search statistics: {e}")
            return {
                "total_searches": 0,
                "unique_users": 0,
                "unique_queries": 0,
                "avg_results": 0,
                "failed_searches": 0,
                "top_searches": [],
            }

    def get_config_changes(self, days: int = 30) -> List[Dict[str, Any]]:
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT * FROM audit_log
                WHERE event_type = 'config'
                AND timestamp >= datetime('now', ? || ' days')
                ORDER BY timestamp DESC
            """,
                (-days,),
            )
            return [dict(row) for row in cursor]
        except Exception as e:
            logger.error(f"Failed to get config changes: {e}")
            return []

    def get_errors(self, days: int = 7) -> List[Dict[str, Any]]:
        try:
            db = self.get_db()
            cursor = db.execute(
                """
                SELECT * FROM audit_log
                WHERE event_type = 'error'
                AND timestamp >= datetime('now', ? || ' days')
                ORDER BY timestamp DESC
            """,
                (-days,),
            )
            return [dict(row) for row in cursor]
        except Exception as e:
            logger.error(f"Failed to get errors: {e}")
            return []

    def get_error_statistics(self, days: int = 7) -> Dict[str, Any]:
        try:
            db = self.get_db()
            stats = dict(
                db.execute(
                    """
                SELECT 
                    COUNT(*) as total_errors,
                    COUNT(DISTINCT action) as unique_error_types,
                    COUNT(DISTINCT user_email) as affected_users,
                    COUNT(DISTINCT target_resource) as affected_paths
                FROM audit_log
                WHERE event_type = 'error'
                AND timestamp >= datetime('now', ? || ' days')
            """,
                    (-days,),
                ).fetchone()
            )

            cursor = db.execute(
                """
                SELECT action as error_type, COUNT(*) as count
                FROM audit_log
                WHERE event_type = 'error'
                AND timestamp >= datetime('now', ? || ' days')
                GROUP BY action
                ORDER BY count DESC
                LIMIT 10
            """,
                (-days,),
            )

            stats["top_errors"] = [dict(row) for row in cursor]
            return stats
        except Exception as e:
            logger.error(f"Failed to get error statistics: {e}")
            return {
                "total_errors": 0,
                "unique_error_types": 0,
                "affected_users": 0,
                "affected_paths": 0,
                "top_errors": [],
            }

    def stop(self):
        """Compatibility method - no longer needed with proper Flask integration"""
        pass


# Create a module-level instance
audit_service = AuditService()


# For backward compatibility
def get_audit_service():
    """Get singleton instance of AuditService"""
    return audit_service
