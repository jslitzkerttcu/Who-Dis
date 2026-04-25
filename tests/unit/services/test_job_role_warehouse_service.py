"""Boundary tests for JobRoleWarehouseService (Plan 02-05 gap closure).

Mock pyodbc at ``app.services.job_role_warehouse_service.pyodbc`` (module-level
try/except import). Use ``svc._config_cache`` overrides for warehouse credentials
per Plan 02-PATTERNS.md (Configuration Access section).
"""
import pytest

from app.database import db
from app.models.job_role_compliance import JobCode, SystemRole
from app.services import job_role_warehouse_service as wh_mod
from app.services.job_role_warehouse_service import JobRoleWarehouseService

pytestmark = pytest.mark.unit


@pytest.fixture
def configured_svc(app, db_session):
    svc = JobRoleWarehouseService()
    svc._config_cache.update({
        "data_warehouse.server": "test-sql.example.com",
        "data_warehouse.database": "TestDB",
        "data_warehouse.client_id": "fake-client",
        "data_warehouse.client_secret": "fake-secret",
        "data_warehouse.connection_timeout": 30,
        "data_warehouse.query_timeout": 60,
    })
    return svc


def _mock_cursor(mocker, fetchall_return):
    cursor = mocker.MagicMock()
    cursor.fetchall.return_value = fetchall_return
    cursor.fetchone.return_value = (1,)
    conn = mocker.MagicMock()
    conn.cursor.return_value = cursor
    conn.__enter__ = mocker.MagicMock(return_value=conn)
    conn.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch(
        "app.services.job_role_warehouse_service.pyodbc.connect",
        return_value=conn,
    )
    return cursor, conn


# --- Pure helpers -------------------------------------------------------------


def test_get_connection_string_includes_server_and_database(configured_svc):
    cs = configured_svc._get_connection_string()
    assert "test-sql.example.com" in cs
    assert "TestDB" in cs
    assert "Authentication=ActiveDirectoryServicePrincipal" in cs
    assert "fake-client" in cs


# --- pyodbc-unavailable degradation ------------------------------------------


def test_test_connection_returns_false_when_pyodbc_none(configured_svc, mocker):
    mocker.patch("app.services.job_role_warehouse_service.pyodbc", None)
    assert configured_svc.test_connection() is False


def test_test_connection_returns_false_when_credentials_missing(configured_svc):
    configured_svc._config_cache["data_warehouse.client_id"] = None
    assert configured_svc.test_connection() is False


# --- pyodbc-mocked happy paths -----------------------------------------------


def test_test_connection_happy_path_returns_true(configured_svc, mocker):
    if wh_mod.pyodbc is None:
        pytest.skip("pyodbc unavailable in this env")
    _mock_cursor(mocker, fetchall_return=[])
    assert configured_svc.test_connection() is True


def test_sync_job_codes_creates_new_rows(configured_svc, mocker, db_session):
    if wh_mod.pyodbc is None:
        pytest.skip("pyodbc unavailable in this env")
    rows = [
        ("JC-NEW-1", "Engineer", "Eng Dept", "EMP1", "HQ", 1),
        ("JC-NEW-2", "Manager", "Eng Dept", "EMP2", "HQ", 1),
    ]
    _mock_cursor(mocker, fetchall_return=rows)

    result = configured_svc.sync_job_codes()
    assert result["created"] == 2
    assert result["updated"] == 0
    assert JobCode.query.filter_by(job_code="JC-NEW-1").first() is not None
    assert JobCode.query.filter_by(job_code="JC-NEW-2").first() is not None


def test_sync_job_codes_updates_existing_row(configured_svc, mocker, db_session):
    if wh_mod.pyodbc is None:
        pytest.skip("pyodbc unavailable in this env")
    # Pre-seed an existing JobCode
    JobCode(job_code="JC-UPD", job_title="Old Title").save()

    rows = [("JC-UPD", "New Title", "Eng Dept", "EMP1", "HQ", 1)]
    _mock_cursor(mocker, fetchall_return=rows)

    result = configured_svc.sync_job_codes()
    assert result["updated"] == 1
    assert result["created"] == 0
    refreshed = JobCode.query.filter_by(job_code="JC-UPD").first()
    assert refreshed.job_title == "New Title"


def test_sync_job_codes_skips_null_job_codes(configured_svc, mocker, db_session):
    if wh_mod.pyodbc is None:
        pytest.skip("pyodbc unavailable in this env")
    rows = [
        (None, "Title", "Dept", "EMP", "Loc", 1),
        ("JC-OK", "Title", "Dept", "EMP", "Loc", 1),
    ]
    _mock_cursor(mocker, fetchall_return=rows)

    result = configured_svc.sync_job_codes()
    assert result["created"] == 1


def test_sync_keystone_roles_creates_system_roles(configured_svc, mocker, db_session):
    if wh_mod.pyodbc is None:
        pytest.skip("pyodbc unavailable in this env")
    rows = [
        (1, "Keystone Admin"),
        (2, "Keystone Reader"),
    ]
    _mock_cursor(mocker, fetchall_return=rows)

    result = configured_svc.sync_keystone_roles()
    assert result["created"] == 2
    persisted = SystemRole.query.filter_by(system_name="keystone").all()
    assert len(persisted) == 2


def test_sync_keystone_roles_skips_null_role_names(configured_svc, mocker, db_session):
    if wh_mod.pyodbc is None:
        pytest.skip("pyodbc unavailable in this env")
    rows = [(1, None), (2, "Real Role")]
    _mock_cursor(mocker, fetchall_return=rows)

    result = configured_svc.sync_keystone_roles()
    assert result["created"] == 1


def test_sync_system_roles_aliases_keystone(configured_svc, mocker, db_session):
    if wh_mod.pyodbc is None:
        pytest.skip("pyodbc unavailable in this env")
    _mock_cursor(mocker, fetchall_return=[(1, "AliasedRole")])

    result = configured_svc.sync_system_roles()
    assert result["created"] == 1


# --- Orchestrator ------------------------------------------------------------


def test_sync_all_compliance_data_orchestrates_subcalls(configured_svc, mocker):
    m1 = mocker.patch.object(configured_svc, "sync_job_codes", return_value={"created": 0, "updated": 0})
    m2 = mocker.patch.object(configured_svc, "sync_keystone_roles", return_value={"created": 0, "updated": 0})
    m3 = mocker.patch.object(
        configured_svc,
        "sync_employee_keystone_assignments",
        return_value={"employees_processed": 0, "assignments_updated": 0},
    )

    result = configured_svc.sync_all_compliance_data()
    m1.assert_called_once()
    m2.assert_called_once()
    m3.assert_called_once()
    assert result["status"] == "success"
    assert "duration_seconds" in result


def test_sync_all_compliance_data_records_error_on_subcall_failure(configured_svc, mocker):
    mocker.patch.object(configured_svc, "sync_job_codes", side_effect=RuntimeError("boom"))
    result = configured_svc.sync_all_compliance_data()
    assert result["status"] == "error"
    assert "boom" in result["error"]
