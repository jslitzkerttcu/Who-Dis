"""Unit tests for app.services.keycloak_admin.KeycloakAdminClient.

Mocks requests at the Session level so no network IO occurs. Verifies:
- token caching across calls
- 401 retry refreshes the token once and replays the request
- find_user_id_by_email parses Keycloak's list response
- assign_client_role is idempotent (skips POST if mapping exists)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock

import pytest

from app.services.keycloak_admin import KeycloakAdminClient, KeycloakAdminError


def _resp(status: int = 200, body: Optional[Any] = None, text: str = "") -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    r.text = text
    return r


@pytest.fixture
def session():
    return MagicMock()


@pytest.fixture
def client(session):
    return KeycloakAdminClient(
        issuer="https://kc.example/realms/sandcastle",
        client_id="who-dis",
        client_secret="shh",
        session=session,
    )


def _stub_token_response(value: str = "tok-1", ttl: int = 300) -> MagicMock:
    return _resp(200, {"access_token": value, "expires_in": ttl})


def test_admin_base_derived_from_issuer(client):
    assert client._admin_base == "https://kc.example/admin/realms/sandcastle"
    assert client._realm == "sandcastle"


def test_token_cached_across_admin_calls(session, client):
    session.post.return_value = _stub_token_response("tok-1")
    session.request.side_effect = [_resp(200, []), _resp(200, [])]

    client.find_user_id_by_email("a@b.test")
    client.find_user_id_by_email("c@d.test")

    # token endpoint hit once; admin endpoint hit twice
    assert session.post.call_count == 1
    assert session.request.call_count == 2


def test_401_triggers_one_refresh_and_retry(session, client):
    session.post.side_effect = [
        _stub_token_response("tok-1"),
        _stub_token_response("tok-2"),
    ]
    # First admin call: 401 → second admin call: 200
    session.request.side_effect = [_resp(401), _resp(200, [])]

    result = client.find_user_id_by_email("a@b.test")

    assert result is None
    assert session.post.call_count == 2  # initial + refresh after 401
    assert session.request.call_count == 2


def test_persistent_401_surfaces_after_one_retry(session, client):
    session.post.side_effect = [
        _stub_token_response("tok-1"),
        _stub_token_response("tok-2"),
    ]
    session.request.side_effect = [_resp(401), _resp(401, text="still nope")]

    with pytest.raises(KeycloakAdminError, match="GET /users failed"):
        client.find_user_id_by_email("a@b.test")


def test_find_user_returns_none_when_empty(session, client):
    session.post.return_value = _stub_token_response()
    session.request.return_value = _resp(200, [])
    assert client.find_user_id_by_email("ghost@x.test") is None


def test_find_user_returns_first_id(session, client):
    session.post.return_value = _stub_token_response()
    session.request.return_value = _resp(200, [{"id": "uid-1", "email": "a@b.test"}])
    assert client.find_user_id_by_email("a@b.test") == "uid-1"


def test_find_user_uses_exact_query_param(session, client):
    session.post.return_value = _stub_token_response()
    session.request.return_value = _resp(200, [])
    client.find_user_id_by_email("a@b.test")
    _, kwargs = session.request.call_args
    assert kwargs["params"] == {"email": "a@b.test", "exact": "true"}


def _setup_role_assignment(
    session, *, existing_mappings: List[Dict[str, str]]
) -> Tuple[List[Any], List[Tuple[Any, ...]]]:
    """Wire session.request to walk the assign_client_role call sequence."""
    calls: List[Tuple[Any, ...]] = []
    queue: List[Any] = [
        # GET /clients?clientId=who-dis
        _resp(200, [{"id": "client-uuid", "clientId": "who-dis"}]),
        # GET /users/<uid>/role-mappings/clients/<cuuid>
        _resp(200, existing_mappings),
        # GET /clients/<cuuid>/roles/<role>
        _resp(200, {"id": "role-uuid", "name": "viewer"}),
        # POST /users/<uid>/role-mappings/clients/<cuuid>
        _resp(204),
    ]

    def fake_request(method, url, **kwargs):
        calls.append((method, url))
        return queue.pop(0)

    session.request.side_effect = fake_request
    return queue, calls


def test_assign_client_role_creates_when_missing(session, client):
    session.post.return_value = _stub_token_response()
    _, calls = _setup_role_assignment(session, existing_mappings=[])

    created = client.assign_client_role(
        user_id="uid-1", client_id="who-dis", role_name="viewer"
    )

    assert created is True
    methods = [m for m, _ in calls]
    assert methods == ["GET", "GET", "GET", "POST"]


def test_assign_client_role_skips_post_when_present(session, client):
    session.post.return_value = _stub_token_response()
    _, calls = _setup_role_assignment(session, existing_mappings=[{"name": "viewer"}])

    created = client.assign_client_role(
        user_id="uid-1", client_id="who-dis", role_name="viewer"
    )

    assert created is False
    # 1 GET clients, 1 GET role-mappings — no further calls
    assert len(calls) == 2


def test_client_uuid_cached(session, client):
    session.post.return_value = _stub_token_response()
    # First call: full sequence including GET /clients
    _setup_role_assignment(session, existing_mappings=[{"name": "viewer"}])
    client.assign_client_role(user_id="u1", client_id="who-dis", role_name="viewer")

    # Second call should NOT hit GET /clients again — only role-mappings + (cached) skip POST
    session.request.side_effect = [
        _resp(200, [{"name": "viewer"}]),  # role-mappings shows existing → no POST
    ]
    client.assign_client_role(user_id="u2", client_id="who-dis", role_name="viewer")

    # Verify the second-call request didn't include /clients
    last_call = session.request.call_args_list[-1]
    assert "/clients?clientId=" not in last_call.args[1]


def test_assign_client_role_raises_on_post_failure(session, client):
    session.post.return_value = _stub_token_response()
    session.request.side_effect = [
        _resp(200, [{"id": "client-uuid", "clientId": "who-dis"}]),
        _resp(200, []),
        _resp(200, {"id": "role-uuid", "name": "viewer"}),
        _resp(500, text="boom"),
    ]
    with pytest.raises(KeycloakAdminError, match="POST role-mappings failed"):
        client.assign_client_role(user_id="u1", client_id="who-dis", role_name="viewer")
