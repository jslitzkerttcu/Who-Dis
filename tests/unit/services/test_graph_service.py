"""Boundary tests for GraphService (real impl) — Plan 02-06 gap closure.

The integration tests use FakeGraphService via the `fake_graph` fixture.
These unit tests exercise the actual app.services.graph_service.GraphService
so that the 191 missed statements (msal flow, requests plumbing, error
handling) are covered.

GraphService inherits BaseAPIService whose _make_request() calls
requests.request via app/services/base.py. We patch
``app.services.base.requests.request`` for HTTP mocking — the same
boundary GenesysCloudService tests use. msal is imported at the
graph_service module top as ``ConfidentialClientApplication``; we
patch it at ``app.services.graph_service.ConfidentialClientApplication``.
"""
import base64

import pytest

from app.services.graph_service import GraphService

pytestmark = pytest.mark.unit


def _make_graph_service(mocker):
    """Build a GraphService whose ConfidentialClientApplication is mocked,
    config_cache is pre-populated, and self.app is initialized so msal-flow
    tests can stub `svc.app.acquire_token_*` directly."""
    mocker.patch(
        "app.services.graph_service.ConfidentialClientApplication",
        return_value=mocker.MagicMock(name="msal_app"),
    )
    svc = GraphService()
    svc._config_cache.update({
        "graph.client_id": "fake-id",
        "graph.client_secret": "fake-secret",
        "graph.tenant_id": "fake-tenant",
        "graph.api_timeout": 15,
    })
    # _fetch_new_token calls _load_config which pulls from _config_cache and
    # assigns the patched ConfidentialClientApplication to self.app. Trigger
    # it now so svc.app is the MagicMock for direct stubbing in tests.
    svc._load_config()
    return svc


def _mock_response(mocker, status_code=200, json_data=None, content=b""):
    resp = mocker.MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.content = content
    resp.raise_for_status = mocker.MagicMock()
    if status_code >= 400:
        from requests import HTTPError
        resp.raise_for_status.side_effect = HTTPError(response=resp)
    return resp


# ---------------------------- service_name ---------------------------------


def test_service_name_property(mocker):
    assert _make_graph_service(mocker).service_name == "graph"


def test_token_service_name_property(mocker):
    assert _make_graph_service(mocker).token_service_name == "microsoft_graph"


# ---------------------------- search_user ----------------------------------


def test_search_user_returns_none_when_no_msal_app(mocker):
    """When ConfidentialClientApplication can't initialize (missing creds),
    self.app stays None and search_user bails."""
    svc = GraphService()
    # Empty config -> _load_config sets self.app to None (no creds)
    assert svc.search_user("anyone") is None


def test_search_user_returns_none_when_no_token(mocker):
    svc = _make_graph_service(mocker)
    mocker.patch.object(svc, "get_access_token", return_value=None)
    assert svc.search_user("jdoe") is None


def test_search_user_happy_path_email_lookup(mocker, app):
    """Direct user lookup by UPN/email returns a single dict."""
    svc = _make_graph_service(mocker)
    mocker.patch.object(svc, "get_access_token", return_value="cached")
    user_payload = {
        "id": "g1",
        "userPrincipalName": "jdoe@x.com",
        "displayName": "J Doe",
        "mail": "jdoe@x.com",
        "businessPhones": [],
    }
    mocker.patch(
        "app.services.base.requests.request",
        return_value=_mock_response(mocker, 200, json_data=user_payload),
    )
    # Skip photo fetching to avoid extra HTTP cycles
    out = svc.search_user("jdoe@x.com", include_photo=False)
    assert out is not None
    assert out["id"] == "g1"
    assert out["userPrincipalName"] == "jdoe@x.com"


def test_search_user_multiple_results_returned_via_filter(mocker, app):
    """Non-email term -> filter search; multiple matches return multiple_results wrapper."""
    svc = _make_graph_service(mocker)
    mocker.patch.object(svc, "get_access_token", return_value="cached")
    list_payload = {
        "value": [
            {"id": "g1", "userPrincipalName": "jdoe1@x.com", "displayName": "J1", "businessPhones": []},
            {"id": "g2", "userPrincipalName": "jdoe2@x.com", "displayName": "J2", "businessPhones": []},
        ]
    }
    mocker.patch(
        "app.services.base.requests.request",
        return_value=_mock_response(mocker, 200, json_data=list_payload),
    )
    out = svc.search_user("jdoe", include_photo=False)
    assert out is not None
    assert out["multiple_results"] is True
    assert out["total"] == 2
    assert len(out["results"]) == 2


def test_search_user_no_matches_returns_none(mocker, app):
    svc = _make_graph_service(mocker)
    mocker.patch.object(svc, "get_access_token", return_value="cached")
    mocker.patch(
        "app.services.base.requests.request",
        return_value=_mock_response(mocker, 200, json_data={"value": []}),
    )
    assert svc.search_user("ghost", include_photo=False) is None


def test_search_user_propagates_timeout_error(mocker, app):
    """TimeoutError from _make_request is re-raised, not swallowed.

    BaseAPIService._make_request catches requests.exceptions.Timeout
    specifically and wraps it as TimeoutError; raising the built-in
    TimeoutError directly would skip that branch and hit the generic
    Exception handler instead. Per Gemini PR #27 review.
    """
    import requests
    svc = _make_graph_service(mocker)
    mocker.patch.object(svc, "get_access_token", return_value="cached")
    mocker.patch(
        "app.services.base.requests.request",
        side_effect=requests.exceptions.Timeout("graph timeout"),
    )
    with pytest.raises(TimeoutError):
        svc.search_user("jdoe", include_photo=False)


# ---------------------------- _fetch_new_token -----------------------------


def test_fetch_new_token_returns_none_when_no_app(mocker):
    """If _load_config produces self.app = None, _fetch_new_token returns None."""
    svc = GraphService()  # No creds in cache
    assert svc._fetch_new_token() is None


def test_fetch_new_token_happy_path_stores_token(mocker, app, db_session):
    """Successful msal call -> _store_token writes ApiToken row, returns access token."""
    svc = _make_graph_service(mocker)
    svc.app.acquire_token_silent.return_value = None
    svc.app.acquire_token_for_client.return_value = {
        "access_token": "fresh-token",
        "expires_in": 3600,
    }
    token = svc._fetch_new_token()
    assert token == "fresh-token"

    from app.models.api_token import ApiToken
    row = ApiToken.query.filter_by(service_name="microsoft_graph").first()
    assert row is not None
    assert row.access_token == "fresh-token"


def test_fetch_new_token_msal_returns_error_dict(mocker, app):
    """When msal returns no access_token (error dict), method logs and returns None."""
    svc = _make_graph_service(mocker)
    svc.app.acquire_token_silent.return_value = None
    svc.app.acquire_token_for_client.return_value = {
        "error": "invalid_client",
        "error_description": "bad creds",
    }
    assert svc._fetch_new_token() is None


def test_fetch_new_token_msal_raises(mocker, app):
    """Exception in msal flow is caught and returns None."""
    svc = _make_graph_service(mocker)
    svc.app.acquire_token_silent.side_effect = RuntimeError("msal exploded")
    assert svc._fetch_new_token() is None


# ---------------------------- get_user_photo -------------------------------


def test_get_user_photo_returns_base64_data_url(mocker, app):
    svc = _make_graph_service(mocker)
    mocker.patch.object(svc, "get_access_token", return_value="cached")
    # JPEG magic bytes — keep test data consistent with the data:image/jpeg
    # MIME type the implementation hardcodes (per Gemini PR #27 review).
    raw = b"\xff\xd8\xff\xe0\x00\x10JFIF-fake-photo-bytes"
    mocker.patch(
        "app.services.base.requests.request",
        return_value=_mock_response(mocker, 200, content=raw),
    )
    out = svc.get_user_photo("g1")
    assert out is not None
    assert out.startswith("data:image/jpeg;base64,")
    encoded = out.split(",", 1)[1]
    assert base64.b64decode(encoded) == raw


def test_get_user_photo_no_token_returns_none(mocker):
    svc = _make_graph_service(mocker)
    mocker.patch.object(svc, "get_access_token", return_value=None)
    assert svc.get_user_photo("g1") is None


# ---------------------------- get_user_by_id -------------------------------


def test_get_user_by_id_no_app_returns_none():
    svc = GraphService()
    assert svc.get_user_by_id("g1") is None


def test_get_user_by_id_no_token_returns_none(mocker):
    svc = _make_graph_service(mocker)
    mocker.patch.object(svc, "get_access_token", return_value=None)
    assert svc.get_user_by_id("g1") is None


# ---------------------------- test_connection -----------------------------


def test_test_connection_returns_false_when_creds_missing():
    """Empty config cache -> creds check fails first, returns False without HTTP."""
    svc = GraphService()
    assert svc.test_connection() is False


def test_test_connection_happy_path(mocker, app, db_session):
    """All creds present, msal returns token, test endpoint returns 200 -> True.

    test_connection() calls _clear_config_cache() before reading creds, so the
    pre-populated _config_cache from _make_graph_service is wiped — we patch
    _get_config to return the creds regardless of cache state.
    """
    svc = _make_graph_service(mocker)
    creds = {
        "client_id": "fake-id",
        "client_secret": "fake-secret",
        "tenant_id": "fake-tenant",
        "api_timeout": 15,
    }
    mocker.patch.object(svc, "_get_config", side_effect=lambda key, default=None: creds.get(key, default))
    svc.app.acquire_token_silent.return_value = None
    svc.app.acquire_token_for_client.return_value = {
        "access_token": "fresh",
        "expires_in": 3600,
    }
    mocker.patch(
        "app.services.base.requests.request",
        return_value=_mock_response(mocker, 200, json_data={"value": []}),
    )
    assert svc.test_connection() is True


# ---------------------------- get_sign_in_logs ---------------------------


def test_get_sign_in_logs_returns_none_without_token(mocker):
    svc = _make_graph_service(mocker)
    mocker.patch.object(svc, "get_access_token", return_value=None)
    assert svc.get_sign_in_logs("g1") is None


def test_get_sign_in_logs_happy_path(mocker, app):
    svc = _make_graph_service(mocker)
    mocker.patch.object(svc, "get_access_token", return_value="cached")
    payload = {
        "value": [
            {
                "createdDateTime": "2026-04-25T08:00:00Z",
                "appDisplayName": "Outlook",
                "ipAddress": "1.1.1.1",
                "clientAppUsed": "Browser",
                "status": {"errorCode": 0, "failureReason": ""},
                "location": {"city": "Tulsa", "state": "OK", "countryOrRegion": "US"},
                "deviceDetail": {"browser": "Chrome", "operatingSystem": "Win11"},
                "isInteractive": True,
            }
        ]
    }
    mocker.patch(
        "app.services.base.requests.request",
        return_value=_mock_response(mocker, 200, json_data=payload),
    )
    logs = svc.get_sign_in_logs("g1")
    assert logs is not None
    assert len(logs) == 1
    assert logs[0]["appDisplayName"] == "Outlook"
    assert logs[0]["city"] == "Tulsa"


def test_get_sign_in_logs_empty_response_returns_empty_list(mocker, app):
    svc = _make_graph_service(mocker)
    mocker.patch.object(svc, "get_access_token", return_value="cached")
    mocker.patch(
        "app.services.base.requests.request",
        return_value=_mock_response(mocker, 200, json_data={"value": []}),
    )
    assert svc.get_sign_in_logs("g1") == []


# Patch boundaries used in this file:
#   - app.services.graph_service.ConfidentialClientApplication (msal seam,
#     patched in _make_graph_service)
#   - app.services.base.requests.request (the HTTP boundary BaseAPIService
#     uses; graph_service does not import requests directly)
