"""Fake Graph service implementing ISearchService + ITokenService."""
from typing import Any, Dict, List, Optional
from app.interfaces.search_service import ISearchService
from app.interfaces.token_service import ITokenService


class FakeGraphService(ISearchService, ITokenService):
    def __init__(self, users: Optional[List[Dict[str, Any]]] = None) -> None:
        self._users: List[Dict[str, Any]] = list(users or [])

    @property
    def service_name(self) -> str:
        return "graph"

    @property
    def token_service_name(self) -> str:
        return "graph"

    def test_connection(self) -> bool:
        return True

    def get_access_token(self) -> Optional[str]:
        return "fake-graph-token"

    def refresh_token_if_needed(self) -> bool:
        return True

    def search_user(self, search_term: str, include_photo: bool = False) -> Optional[Dict[str, Any]]:
        term = (search_term or "").lower()
        matches = [
            u for u in self._users
            if term in u.get("userPrincipalName", "").lower()
            or term in u.get("displayName", "").lower()
            or term in u.get("mail", "").lower()
        ]
        if not matches:
            return None
        if len(matches) == 1:
            return matches[0]
        return {"multiple_results": True, "results": matches, "total": len(matches)}

    def get_user_by_id(self, user_id: str, include_photo: bool = False) -> Optional[Dict[str, Any]]:
        for u in self._users:
            if u.get("id") == user_id or u.get("userPrincipalName") == user_id:
                return u
        return None

    def add_user(self, user: Dict[str, Any]) -> None:
        self._users.append(user)
