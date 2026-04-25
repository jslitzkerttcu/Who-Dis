"""Targeted unit tests for GenesysCloudService (D-12).

Mocks app.services.base.requests.request at the BaseAPIService HTTP boundary
so no real Genesys traffic is generated. Covers service_name/token_service_name
properties, search_user happy/empty paths, token refresh paths, and
ApiToken-row round-trip on token fetch.
"""
import pytest

from app.services.genesys_service import GenesysCloudService

pytestmark = pytest.mark.unit


def _make_genesys_service():
    svc = GenesysCloudService()
    svc._config_cache.update({
        "genesys.client_id": "fake-client-id",
        "genesys.client_secret": "fake-client-secret",
        "genesys.region": "mypurecloud.com",
        "genesys.api_timeout": 15,
    })
    return svc


def test_service_name_property():
    assert _make_genesys_service().service_name == "genesys"


def test_token_service_name_property():
    assert _make_genesys_service().token_service_name == "genesys"


def _mock_response(mocker, json_data, status_code=200):
    response = mocker.MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    response.raise_for_status = mocker.MagicMock()
    return response


def test_search_user_happy_path(mocker, db_session, app):
    """search_user returns processed dict for a single Genesys hit."""
    svc = _make_genesys_service()

    # Stub the cached-token path so _make_request only fires once for the search.
    mocker.patch.object(svc, "get_access_token", return_value="cached-token")

    search_response = _mock_response(mocker, {
        "results": [
            {
                "id": "gn-1",
                "name": "J Doe",
                "email": "jdoe@x.com",
                "username": "jdoe",
                "skills": [],
                "groups": [],
                "locations": [],
            }
        ]
    })

    mocker.patch("app.services.base.requests.request", return_value=search_response)

    result = svc.search_user("jdoe")
    assert result is not None
    assert result.get("id") == "gn-1"
    assert result.get("email") == "jdoe@x.com"


def test_search_user_no_results(mocker, db_session, app):
    svc = _make_genesys_service()
    mocker.patch.object(svc, "get_access_token", return_value="cached-token")
    mocker.patch(
        "app.services.base.requests.request",
        return_value=_mock_response(mocker, {"results": []}),
    )

    assert svc.search_user("ghost") is None


def test_refresh_token_when_expired_writes_apitoken_row(mocker, db_session, app):
    """When no cached token exists, _fetch_new_token() hits the OAuth endpoint
    and persists an ApiToken row via _store_token()."""
    from app.models.api_token import ApiToken

    svc = _make_genesys_service()

    # Pre-condition: no genesys token in DB
    assert ApiToken.query.filter_by(service_name="genesys").first() is None

    token_response = _mock_response(mocker, {"access_token": "new-token", "expires_in": 3600})
    mocker.patch("app.services.base.requests.request", return_value=token_response)

    ok = svc.refresh_token_if_needed()
    assert ok is True

    token = ApiToken.query.filter_by(service_name="genesys").first()
    assert token is not None
    assert token.access_token == "new-token"


def test_refresh_token_when_valid_uses_cached_path(mocker, db_session, app):
    """When _get_cached_token returns a token, refresh_token_if_needed succeeds
    without calling out to the OAuth endpoint. Patches ApiToken.get_token to
    return a usable token (sidesteps the pre-existing is_expired-as-method bug
    in app/models/api_token.py:117 — see SUMMARY.md Deviations)."""
    from app.models.api_token import ApiToken

    fake_token = mocker.MagicMock()
    fake_token.access_token = "existing-token"
    mocker.patch.object(ApiToken, "get_token", return_value=fake_token)

    svc = _make_genesys_service()

    http_mock = mocker.patch("app.services.base.requests.request")
    ok = svc.refresh_token_if_needed()
    assert ok is True
    assert http_mock.call_count == 0


def test_token_storage_round_trip(mocker, db_session, app):
    """Force the _fetch_new_token() path; assert ApiToken row written."""
    from app.models.api_token import ApiToken

    svc = _make_genesys_service()

    token_response = _mock_response(mocker, {"access_token": "fresh-tok", "expires_in": 1800})
    mocker.patch("app.services.base.requests.request", return_value=token_response)

    fetched = svc._fetch_new_token()
    assert fetched == "fresh-tok"

    row = ApiToken.query.filter_by(service_name="genesys").first()
    assert row is not None
    assert row.access_token == "fresh-tok"


def test_test_connection_failure_when_credentials_missing(mocker):
    """test_connection returns False when client_id/secret are not configured."""
    svc = GenesysCloudService()
    svc._config_cache.update({
        "genesys.client_id": None,
        "genesys.client_secret": None,
    })

    assert svc.test_connection() is False
