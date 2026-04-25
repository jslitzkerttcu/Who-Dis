"""Fake Genesys service. Supports the orchestrator's too_many_results degraded path."""
from typing import Any, Dict, List, Optional
from app.interfaces.search_service import ISearchService
from app.interfaces.token_service import ITokenService


class FakeGenesysService(ISearchService, ITokenService):
    def __init__(
        self,
        users: Optional[List[Dict[str, Any]]] = None,
        too_many: bool = False,
        too_many_total: int = 999,
    ) -> None:
        self._users: List[Dict[str, Any]] = list(users or [])
        self._too_many = too_many
        self._too_many_total = too_many_total

    @property
    def service_name(self) -> str:
        return "genesys"

    @property
    def token_service_name(self) -> str:
        return "genesys"

    def test_connection(self) -> bool:
        return True

    def get_access_token(self) -> Optional[str]:
        return "fake-genesys-token"

    def refresh_token_if_needed(self) -> bool:
        return True

    def search_user(self, search_term: str) -> Optional[Dict[str, Any]]:
        if self._too_many:
            # Exact shape from search_orchestrator.py:238-242
            return {
                "error": "too_many_results",
                "message": f"Search returned {self._too_many_total} results; refine the term.",
                "total": self._too_many_total,
            }
        term = (search_term or "").lower()
        matches = [
            u for u in self._users
            if term in u.get("email", "").lower() or term in u.get("name", "").lower()
        ]
        if not matches:
            return None
        if len(matches) == 1:
            return matches[0]
        return {"multiple_results": True, "results": matches, "total": len(matches)}

    def get_user_by_id(self, genesys_user_id: str) -> Optional[Dict[str, Any]]:
        for u in self._users:
            if u.get("id") == genesys_user_id:
                return u
        return None

    def add_user(self, user: Dict[str, Any]) -> None:
        self._users.append(user)
