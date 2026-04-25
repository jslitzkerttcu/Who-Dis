"""Boundary tests for EmployeeProfilesRefreshService (Plan 02-05 gap closure).

Patches ``pyodbc`` and ``httpx`` at the module-level boundary
``app.services.refresh_employee_profiles.<symbol>`` so no real Azure SQL or
Graph API traffic occurs. Stays away from the heavy async ``refresh_all_profiles``
orchestrator (asyncio.gather + httpx.AsyncClient + Semaphore — too much
fixture surface for a coverage gap-closure plan).
"""
import pytest

from app.database import db
from app.models.employee_profiles import EmployeeProfiles
from app.services import refresh_employee_profiles as ref_mod
from app.services.refresh_employee_profiles import EmployeeProfilesRefreshService

pytestmark = pytest.mark.unit


def _make_svc():
    svc = EmployeeProfilesRefreshService()
    svc._config_cache.update({
        "data_warehouse.server": "test-sql.example.com",
        "data_warehouse.database": "TestDB",
        "data_warehouse.client_id": "fake-client",
        "data_warehouse.client_secret": "fake-secret",
        "data_warehouse.connection_timeout": 30,
        "data_warehouse.query_timeout": 60,
        "data_warehouse.cache_refresh_hours": 6.0,
    })
    return svc


@pytest.fixture
def svc(app, db_session):
    return _make_svc()


# --- Pure helpers -------------------------------------------------------------


def test_mock_photo_bytes_returns_jpeg_like_bytes(svc):
    blob = svc._mock_photo_bytes()
    assert isinstance(blob, bytes)
    assert blob.startswith(b"\xff\xd8\xff\xe0")  # JFIF marker
    assert blob.endswith(b"\xff\xd9")  # JPEG EOI


def test_get_fallback_mock_data_returns_non_empty_list_of_dicts(svc):
    rows = svc._get_fallback_mock_data()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert "upn" in rows[0]
    assert "ukg_job_code" in rows[0]


def test_get_connection_string_includes_server_and_database(svc):
    cs = svc._get_connection_string()
    assert "test-sql.example.com" in cs
    assert "TestDB" in cs
    assert "ODBC Driver 18" in cs
    assert "Authentication=ActiveDirectoryServicePrincipal" in cs


# --- pyodbc-mocked paths ------------------------------------------------------


def test_test_connection_returns_false_when_pyodbc_none(svc, mocker):
    mocker.patch("app.services.refresh_employee_profiles.pyodbc", None)
    assert svc.test_connection() is False


def test_test_connection_returns_false_when_credentials_missing(svc, mocker):
    svc._config_cache["data_warehouse.client_id"] = None
    assert svc.test_connection() is False


def test_test_connection_happy_path_with_mocked_connect(svc, mocker):
    if ref_mod.pyodbc is None:
        pytest.skip("pyodbc unavailable in this env; happy path requires the module present")
    # test_connection() calls self._clear_config_cache() at the top, wiping our
    # pre-populated svc._config_cache. Patch it out so the mocked credentials survive.
    mocker.patch.object(svc, "_clear_config_cache")

    cursor = mocker.MagicMock()
    cursor.fetchone.return_value = (1,)
    conn = mocker.MagicMock()
    conn.cursor.return_value = cursor
    conn.__enter__ = mocker.MagicMock(return_value=conn)
    conn.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch(
        "app.services.refresh_employee_profiles.pyodbc.connect",
        return_value=conn,
    )

    assert svc.test_connection() is True


def test_load_keystone_employee_data_falls_back_on_query_error(svc, mocker):
    mocker.patch.object(svc, "execute_keystone_query", side_effect=Exception("boom"))
    rows = svc.load_keystone_employee_data()
    assert isinstance(rows, list)
    assert len(rows) >= 1  # mock fallback data


def test_load_keystone_employee_data_transforms_query_results(svc, mocker):
    raw = [
        {
            "UPN": "alice@test.local",
            "KS_User_Serial": 1,
            "KS_Last_Login_Time": None,
            "KS_Login_Lock": "N",
            "Live_Role": "Admin",
            "Test_Role": None,
            "UKG_Job_Code": "ENG",
            "Keystone_Expected_Role_For_Job_Title": "Admin",
        }
    ]
    mocker.patch.object(svc, "execute_keystone_query", return_value=raw)
    rows = svc.load_keystone_employee_data()
    assert len(rows) == 1
    assert rows[0]["upn"] == "alice@test.local"
    assert rows[0]["ukg_job_code"] == "ENG"


# --- DB-backed read paths -----------------------------------------------------


def test_get_employee_profile_returns_none_for_missing_upn(svc, db_session):
    assert svc.get_employee_profile("nobody@test.local") is None


def test_get_employee_profile_returns_dict_for_existing_upn(svc, db_session):
    db.session.add(
        EmployeeProfiles(
            upn="found@test.local",
            ukg_job_code="ENG",
            live_role="Admin",
            ks_login_lock="N",
        )
    )
    db.session.commit()

    result = svc.get_employee_profile("found@test.local")
    assert result is not None
    assert result["upn"] == "found@test.local"


@pytest.mark.xfail(
    strict=True,
    reason="Pre-existing bug: get_cache_stats compares tz-naive datetime.now() to "
    "tz-aware EmployeeProfiles.updated_at, raising TypeError; the except clause "
    "swallows it and returns a zero-count error dict.",
)
def test_get_cache_stats_returns_counts(svc, db_session):
    db.session.add(EmployeeProfiles(upn="a@test.local"))
    db.session.add(EmployeeProfiles(upn="b@test.local"))
    db.session.commit()

    stats = svc.get_cache_stats()
    assert stats["total_records"] == 2
    assert stats["record_count"] == 2
    assert "needs_refresh" in stats


def test_get_cache_stats_returns_dict_shape_when_empty(svc, db_session):
    """Even with the tz-comparison bug, the empty-table path returns a sane dict."""
    stats = svc.get_cache_stats()
    assert isinstance(stats, dict)
    assert "needs_refresh" in stats
    assert stats["total_records"] == 0


def test_get_cache_status_wrapper_returns_admin_ui_shape(svc, db_session):
    status = svc.get_cache_status()
    for key in ("total_records", "record_count", "last_updated", "refresh_status"):
        assert key in status


def test_test_data_warehouse_connection_wraps_test_connection(svc, mocker):
    mocker.patch.object(svc, "test_connection", return_value=False)
    result = svc.test_data_warehouse_connection()
    assert result["success"] is False
    assert result["connection_available"] is False
    assert "message" in result


def test_get_refresh_stats_returns_zero_when_empty(svc, db_session):
    stats = svc.get_refresh_stats()
    assert stats["total_profiles"] == 0
    assert stats["last_updated"] is None
