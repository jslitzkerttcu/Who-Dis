"""Unit tests for Graph license write operations (assign, remove, swap).

Mocks requests at the base service boundary for HTTP mocking.
"""

import pytest
from requests import HTTPError

from app.services.graph_service import GraphService

pytestmark = pytest.mark.unit


def _make_graph_service(mocker):
    """Build a GraphService with mocked MSAL and pre-populated config."""
    mocker.patch(
        "app.services.graph_service.ConfidentialClientApplication",
        return_value=mocker.MagicMock(name="msal_app"),
    )
    svc = GraphService()
    svc._config_cache.update(
        {
            "graph.client_id": "fake-id",
            "graph.client_secret": "fake-secret",
            "graph.tenant_id": "fake-tenant",
            "graph.api_timeout": 15,
        }
    )
    svc._load_config()
    return svc


def _mock_response(mocker, status_code=200, json_data=None, content=b""):
    resp = mocker.MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.content = content
    resp.raise_for_status = mocker.MagicMock()
    if status_code >= 400:
        http_err = HTTPError(response=resp)
        resp.raise_for_status.side_effect = http_err
    return resp


class TestAssignLicense:
    def test_assign_license_success(self, mocker):
        svc = _make_graph_service(mocker)
        # Mock token acquisition
        svc.app.acquire_token_silent.return_value = {"access_token": "tok123", "expires_in": 3600}

        resp = _mock_response(mocker, status_code=200, json_data={})
        mocker.patch("app.services.base.requests.request", return_value=resp)

        result = svc.assign_license("user-id-123", "sku-abc-def")
        assert result["success"] is True

    def test_assign_license_permission_denied(self, mocker):
        svc = _make_graph_service(mocker)
        svc.app.acquire_token_silent.return_value = {"access_token": "tok123", "expires_in": 3600}

        resp = _mock_response(mocker, status_code=403)
        mocker.patch("app.services.base.requests.request", return_value=resp)

        result = svc.assign_license("user-id-123", "sku-abc-def")
        assert result["error"] == "permission_missing"
        assert result["permission"] == "LicenseAssignment.ReadWrite.All"


class TestRemoveLicense:
    def test_remove_license_success(self, mocker):
        svc = _make_graph_service(mocker)
        svc.app.acquire_token_silent.return_value = {"access_token": "tok123", "expires_in": 3600}

        resp = _mock_response(mocker, status_code=200, json_data={})
        mocker.patch("app.services.base.requests.request", return_value=resp)

        result = svc.remove_license("user-id-123", "sku-abc-def")
        assert result["success"] is True


class TestSwapLicense:
    def test_swap_license_atomic_success(self, mocker):
        """Single POST with both addLicenses and removeLicenses succeeds."""
        svc = _make_graph_service(mocker)
        svc.app.acquire_token_silent.return_value = {"access_token": "tok123", "expires_in": 3600}

        resp = _mock_response(mocker, status_code=200, json_data={})
        mocker.patch("app.services.base.requests.request", return_value=resp)

        result = svc.swap_license("user-id-123", "old-sku", "new-sku")
        assert result["success"] is True

    def test_swap_license_atomic_fails_fallback_succeeds(self, mocker):
        """Atomic call fails, two sequential calls succeed."""
        svc = _make_graph_service(mocker)
        svc.app.acquire_token_silent.return_value = {"access_token": "tok123", "expires_in": 3600}

        # First call (atomic) fails with 400, subsequent calls succeed
        resp_fail = _mock_response(mocker, status_code=400)
        resp_success = _mock_response(mocker, status_code=200, json_data={})

        mock_request = mocker.patch(
            "app.services.base.requests.request",
            side_effect=[resp_fail, resp_success, resp_success],
        )

        result = svc.swap_license("user-id-123", "old-sku", "new-sku")
        assert result["success"] is True

    def test_swap_license_partial_failure_rollback_success(self, mocker):
        """Remove succeeds, assign fails, rollback re-adds old SKU successfully."""
        svc = _make_graph_service(mocker)
        svc.app.acquire_token_silent.return_value = {"access_token": "tok123", "expires_in": 3600}

        # Atomic fails, remove succeeds, assign fails, rollback (assign old) succeeds
        resp_fail_atomic = _mock_response(mocker, status_code=400)
        resp_remove_ok = _mock_response(mocker, status_code=200, json_data={})
        resp_assign_fail = _mock_response(mocker, status_code=500)
        resp_rollback_ok = _mock_response(mocker, status_code=200, json_data={})

        mocker.patch(
            "app.services.base.requests.request",
            side_effect=[resp_fail_atomic, resp_remove_ok, resp_assign_fail, resp_rollback_ok],
        )

        result = svc.swap_license("user-id-123", "old-sku", "new-sku")
        assert result["success"] is False
        assert result["rollback_needed"] is True
        assert result["rollback_success"] is True

    def test_swap_license_double_failure(self, mocker):
        """Remove succeeds, assign fails, rollback also fails."""
        svc = _make_graph_service(mocker)
        svc.app.acquire_token_silent.return_value = {"access_token": "tok123", "expires_in": 3600}

        resp_fail_atomic = _mock_response(mocker, status_code=400)
        resp_remove_ok = _mock_response(mocker, status_code=200, json_data={})
        resp_assign_fail = _mock_response(mocker, status_code=500)
        resp_rollback_fail = _mock_response(mocker, status_code=500)

        mocker.patch(
            "app.services.base.requests.request",
            side_effect=[resp_fail_atomic, resp_remove_ok, resp_assign_fail, resp_rollback_fail],
        )

        result = svc.swap_license("user-id-123", "old-sku", "new-sku")
        assert result["success"] is False
        assert result["rollback_needed"] is True
        assert result["rollback_success"] is False
