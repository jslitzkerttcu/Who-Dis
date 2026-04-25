"""In-memory ISearchService implementation for tests (D-04, D-05).

Implements ISearchService directly without inheriting from any production base service
class — keeps real HTTP/timeout logic out of the test path (per code_context).
"""
from typing import Any, Dict, List, Optional
from app.interfaces.search_service import ISearchService


class FakeLDAPService(ISearchService):
    def __init__(self, users: Optional[List[Dict[str, Any]]] = None) -> None:
        self._users: List[Dict[str, Any]] = list(users or [])

    @property
    def service_name(self) -> str:
        return "ldap"

    def test_connection(self) -> bool:
        return True

    def search_user(self, search_term: str) -> Optional[Dict[str, Any]]:
        term = (search_term or "").lower()
        matches = [
            u for u in self._users
            if term in u.get("sAMAccountName", "").lower()
            or term in u.get("mail", "").lower()
            or term in u.get("displayName", "").lower()
        ]
        if not matches:
            return None
        if len(matches) == 1:
            return matches[0]
        # Multiple-results wrapper per app/services/base.py:377-394
        return {"multiple_results": True, "results": matches, "total": len(matches)}

    def get_user_by_dn(self, dn: str) -> Optional[Dict[str, Any]]:
        """Orchestrator second-pass lookup (search_orchestrator.py:141-143)."""
        for u in self._users:
            if u.get("distinguishedName") == dn or u.get("dn") == dn:
                return u
        return None

    # --- Test helpers ---
    def add_user(self, user: Dict[str, Any]) -> None:
        self._users.append(user)
