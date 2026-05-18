"""Unit tests for M365 license write operation endpoints (Phase 9, Plan 03).

Tests cover:
- Assign license success + reason validation
- Remove license success
- Swap license success + rollback success + double failure (showBanner)
- Available SKUs fragment endpoint
"""

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def client(app):
    """Flask test client with CSRF disabled."""
    app.config["WTF_CSRF_ENABLED"] = False
    return app.test_client()


@pytest.fixture
def mock_write_ops():
    """Mock WriteOperationsService injected into container."""
    mock = MagicMock()
    return mock


@pytest.fixture
def mock_graph_service():
    """Mock GraphService for available-skus endpoint."""
    mock = MagicMock()
    return mock


@pytest.fixture
def mock_sku_catalog():
    """Mock SkuCatalogCache."""
    mock = MagicMock()
    mock.get_sku_name.return_value = None  # Fallback to skuPartNumber
    return mock


@pytest.fixture(autouse=True)
def patch_auth_and_service(app, mock_write_ops, mock_graph_service, mock_sku_catalog):
    """Bypass auth decorators and inject mock services."""
    app.container.register("write_operations", lambda c: mock_write_ops)
    app.container.register("graph_service", lambda c: mock_graph_service)
    app.container.register("sku_catalog_cache", lambda c: mock_sku_catalog)

    with patch("app.blueprints.search.write_routes.require_role", lambda role: lambda f: f):
        with patch(
            "app.blueprints.search.write_routes.csrf_double_submit"
        ) as mock_csrf:
            mock_csrf.protect = lambda f: f
            yield


@pytest.fixture(autouse=True)
def fake_user(app):
    """Set g.user and g.role for all requests in this module."""

    @app.before_request
    def _set_fake_user():
        from flask import g

        g.user = "admin@test.com"
        g.role = "admin"

    yield

    app.before_request_funcs.setdefault(None, [])
    if _set_fake_user in app.before_request_funcs.get(None, []):
        app.before_request_funcs[None].remove(_set_fake_user)


class TestAssignLicense:
    def test_assign_license_success(self, client, mock_write_ops):
        mock_write_ops.assign_license.return_value = {"success": True}

        resp = client.post(
            "/search/api/write/assign-license",
            data={
                "user_id": "user-123",
                "user_email": "user@test.com",
                "sku_id": "sku-abc",
                "sku_name": "Office 365 E3",
                "reason": "New hire setup",
            },
        )

        assert resp.status_code == 200
        trigger = json.loads(resp.headers["HX-Trigger"])
        assert trigger["showToast"]["message"] == "License assigned successfully"
        assert trigger["showToast"]["type"] == "success"

    def test_assign_license_no_reason(self, client, mock_write_ops):
        resp = client.post(
            "/search/api/write/assign-license",
            data={
                "user_id": "user-123",
                "user_email": "user@test.com",
                "sku_id": "sku-abc",
                "sku_name": "Office 365 E3",
                "reason": "ab",
            },
        )

        assert resp.status_code == 400
        assert b"Reason must be at least 3 characters" in resp.data

    def test_assign_license_permission_missing(self, client, mock_write_ops):
        mock_write_ops.assign_license.return_value = {
            "error": "permission_missing",
            "permission": "LicenseAssignment.ReadWrite.All",
        }

        resp = client.post(
            "/search/api/write/assign-license",
            data={
                "user_id": "user-123",
                "user_email": "user@test.com",
                "sku_id": "sku-abc",
                "sku_name": "Office 365 E3",
                "reason": "New hire",
            },
        )

        assert resp.status_code == 403
        assert b"Graph API permission missing" in resp.data


class TestRemoveLicense:
    def test_remove_license_success(self, client, mock_write_ops):
        mock_write_ops.remove_license.return_value = {"success": True}

        resp = client.post(
            "/search/api/write/remove-license",
            data={
                "user_id": "user-123",
                "user_email": "user@test.com",
                "sku_id": "sku-abc",
                "sku_name": "Office 365 E3",
                "reason": "Termination",
            },
        )

        assert resp.status_code == 200
        trigger = json.loads(resp.headers["HX-Trigger"])
        assert trigger["showToast"]["message"] == "License removed successfully"

    def test_remove_license_no_reason(self, client, mock_write_ops):
        resp = client.post(
            "/search/api/write/remove-license",
            data={
                "user_id": "user-123",
                "user_email": "user@test.com",
                "sku_id": "sku-abc",
                "sku_name": "Office 365 E3",
                "reason": "x",
            },
        )

        assert resp.status_code == 400


class TestSwapLicense:
    def test_swap_license_success(self, client, mock_write_ops):
        mock_write_ops.swap_license.return_value = {"success": True}

        resp = client.post(
            "/search/api/write/swap-license",
            data={
                "user_id": "user-123",
                "user_email": "user@test.com",
                "old_sku_id": "sku-old",
                "old_sku_name": "E3",
                "new_sku_id": "sku-new",
                "new_sku_name": "E5",
                "reason": "License upgrade",
            },
        )

        assert resp.status_code == 200
        trigger = json.loads(resp.headers["HX-Trigger"])
        assert trigger["showToast"]["message"] == "License swapped successfully"

    def test_swap_license_rollback_success(self, client, mock_write_ops):
        mock_write_ops.swap_license.return_value = {
            "success": False,
            "rollback_needed": True,
            "rollback_success": True,
        }

        resp = client.post(
            "/search/api/write/swap-license",
            data={
                "user_id": "user-123",
                "user_email": "user@test.com",
                "old_sku_id": "sku-old",
                "old_sku_name": "E3",
                "new_sku_id": "sku-new",
                "new_sku_name": "E5",
                "reason": "License upgrade",
            },
        )

        assert resp.status_code == 200
        trigger = json.loads(resp.headers["HX-Trigger"])
        assert "rollback succeeded" in trigger["showToast"]["message"]
        assert trigger["showToast"]["type"] == "warning"

    def test_swap_license_double_failure(self, client, mock_write_ops):
        mock_write_ops.swap_license.return_value = {
            "success": False,
            "rollback_needed": True,
            "rollback_success": False,
        }

        resp = client.post(
            "/search/api/write/swap-license",
            data={
                "user_id": "user-123",
                "user_email": "user@test.com",
                "old_sku_id": "sku-old",
                "old_sku_name": "E3",
                "new_sku_id": "sku-new",
                "new_sku_name": "E5",
                "reason": "License upgrade",
            },
        )

        assert resp.status_code == 500
        trigger = json.loads(resp.headers["HX-Trigger"])
        assert "showBanner" in trigger
        assert "CRITICAL" in trigger["showBanner"]["message"]
        assert "Manual intervention" in trigger["showBanner"]["message"]
        assert trigger["showBanner"]["type"] == "error"
        assert trigger["showBanner"]["duration"] == 0

    def test_swap_license_standard_failure(self, client, mock_write_ops):
        mock_write_ops.swap_license.return_value = {
            "success": False,
            "rollback_needed": False,
            "error": "Remove failed: SKU not assigned",
        }

        resp = client.post(
            "/search/api/write/swap-license",
            data={
                "user_id": "user-123",
                "user_email": "user@test.com",
                "old_sku_id": "sku-old",
                "old_sku_name": "E3",
                "new_sku_id": "sku-new",
                "new_sku_name": "E5",
                "reason": "License upgrade",
            },
        )

        assert resp.status_code == 500
        assert b"Remove failed" in resp.data


class TestAvailableSkus:
    def test_available_skus(self, client, mock_graph_service, mock_sku_catalog):
        mock_graph_service.get_subscribed_skus.return_value = [
            {
                "skuId": "sku-001",
                "skuPartNumber": "ENTERPRISEPACK",
                "capabilityStatus": "Enabled",
                "prepaidUnits": {"enabled": 100},
                "consumedUnits": 80,
            },
            {
                "skuId": "sku-002",
                "skuPartNumber": "POWER_BI_STANDARD",
                "capabilityStatus": "Enabled",
                "prepaidUnits": {"enabled": 50},
                "consumedUnits": 50,
            },
        ]
        mock_sku_catalog.get_sku_name.side_effect = lambda sid: {
            "sku-001": "Office 365 E3",
            "sku-002": "Power BI (free)",
        }.get(sid)

        resp = client.get("/search/api/write/available-skus")

        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Office 365 E3" in html
        assert "20/100 available" in html
        assert "Power BI (free)" in html
        assert "none available" in html  # 0 available

    def test_available_skus_exclude(self, client, mock_graph_service, mock_sku_catalog):
        mock_graph_service.get_subscribed_skus.return_value = [
            {
                "skuId": "sku-001",
                "skuPartNumber": "ENTERPRISEPACK",
                "capabilityStatus": "Enabled",
                "prepaidUnits": {"enabled": 100},
                "consumedUnits": 80,
            },
            {
                "skuId": "sku-002",
                "skuPartNumber": "POWER_BI",
                "capabilityStatus": "Enabled",
                "prepaidUnits": {"enabled": 50},
                "consumedUnits": 10,
            },
        ]

        resp = client.get("/search/api/write/available-skus?exclude_sku_id=sku-001")

        assert resp.status_code == 200
        html = resp.data.decode()
        assert "sku-001" not in html
        assert "POWER_BI" in html

    def test_available_skus_permission_missing(self, client, mock_graph_service):
        mock_graph_service.get_subscribed_skus.return_value = {
            "error": "permission_missing",
            "permission": "Organization.Read.All",
        }

        resp = client.get("/search/api/write/available-skus")

        assert resp.status_code == 403
        assert b"permission missing" in resp.data
