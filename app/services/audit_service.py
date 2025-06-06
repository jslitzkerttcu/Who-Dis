import sqlite3
import json
import time
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, Dict, Any, List


class AuditService:
    def __init__(self, db_path: str = "logs/audit.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_database()

    def _init_database(self):
        with self._get_connection() as conn:
            conn.execute("""
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

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_user_email ON audit_log(user_email)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_log(event_type)
            """)

    @contextmanager
    def _get_connection(self):
        # Retry logic for database locks
        max_retries = 5
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                # Use timeout and isolation level to reduce locks
                conn = sqlite3.connect(
                    self.db_path, 
                    timeout=10.0,  # 10 second timeout
                    isolation_level=None  # Autocommit mode
                )
                conn.row_factory = sqlite3.Row
                # Enable WAL mode for better concurrency
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                
                try:
                    yield conn
                except Exception:
                    raise
                finally:
                    conn.close()
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    raise

    def log_search(
        self,
        user_email: str,
        search_query: str,
        results_count: int,
        services: List[str],
        user_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ):
        with self._get_connection() as conn:
            conn.execute(
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
                    user_role,
                    ip_address,
                    "identity_search",
                    search_query,
                    results_count,
                    json.dumps(services),
                    success,
                    error_message,
                    json.dumps(additional_data) if additional_data else None,
                    session_id,
                    user_agent,
                ),
            )

    def log_access(
        self,
        user_email: str,
        action: str,
        target_resource: str,
        user_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ):
        with self._get_connection() as conn:
            conn.execute(
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
                    user_role,
                    ip_address,
                    action,
                    target_resource,
                    success,
                    error_message,
                    json.dumps(additional_data) if additional_data else None,
                    session_id,
                    user_agent,
                ),
            )

    def log_admin_action(
        self,
        user_email: str,
        action: str,
        target_resource: str,
        user_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ):
        with self._get_connection() as conn:
            conn.execute(
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
                    user_role,
                    ip_address,
                    action,
                    target_resource,
                    success,
                    error_message,
                    json.dumps(additional_data) if additional_data else None,
                    session_id,
                    user_agent,
                ),
            )

    def get_recent_searches(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM audit_log
                WHERE event_type = 'search'
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (limit,),
            )
            return [dict(row) for row in cursor]

    def get_user_activity(
        self, user_email: str, days: int = 30
    ) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM audit_log
                WHERE user_email = ?
                AND timestamp >= datetime('now', ? || ' days')
                ORDER BY timestamp DESC
            """,
                (user_email, -days),
            )
            return [dict(row) for row in cursor]

    def get_search_statistics(self, days: int = 30) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.execute(
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
            )

            stats = dict(cursor.fetchone())

            cursor = conn.execute(
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

    def log_config_change(
        self,
        user_email: str,
        action: str,
        config_key: str,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        user_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ):
        with self._get_connection() as conn:
            conn.execute(
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
                    user_role,
                    ip_address,
                    action,
                    config_key,
                    success,
                    error_message,
                    json.dumps(
                        {
                            "old_value": old_value,
                            "new_value": new_value,
                            **(additional_data or {}),
                        }
                    ),
                    session_id,
                    user_agent,
                ),
            )

    def log_error(
        self,
        error_type: str,
        error_message: str,
        stack_trace: Optional[str] = None,
        user_email: Optional[str] = None,
        user_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_path: Optional[str] = None,
        request_method: Optional[str] = None,
        session_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ):
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_log (
                    event_type, user_email, user_role, ip_address,
                    action, target_resource, success, error_message,
                    additional_data, session_id, user_agent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "error",
                    user_email or "system",
                    user_role,
                    ip_address,
                    error_type,
                    request_path,
                    False,
                    error_message,
                    json.dumps(
                        {
                            "stack_trace": stack_trace,
                            "request_method": request_method,
                            **(additional_data or {}),
                        }
                    ),
                    session_id,
                    user_agent,
                ),
            )

    def get_config_changes(self, days: int = 30) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM audit_log
                WHERE event_type = 'config'
                AND timestamp >= datetime('now', ? || ' days')
                ORDER BY timestamp DESC
            """,
                (-days,),
            )
            return [dict(row) for row in cursor]

    def get_errors(self, days: int = 7) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM audit_log
                WHERE event_type = 'error'
                AND timestamp >= datetime('now', ? || ' days')
                ORDER BY timestamp DESC
            """,
                (-days,),
            )
            return [dict(row) for row in cursor]

    def get_error_statistics(self, days: int = 7) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.execute(
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
            )

            stats = dict(cursor.fetchone())

            cursor = conn.execute(
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


audit_service = AuditService()
