"""Boundary tests for JobRoleMappingService (Plan 02-05 gap closure).

Drives the real service against the testcontainers Postgres via factories.
Targets ~50% coverage on app/services/job_role_mapping_service.py (was 13.3%).

Pre-existing bug surfaced by these tests (xfail-strict per Plan 02-PATTERNS.md):
  ``create_mapping`` / ``delete_mapping`` rely on ORM relationship attributes
  that are not populated until SQLAlchemy auto-flushes; under
  ``commit=False`` the relationship-access path raises ``AttributeError`` or
  trips the FK constraint on the unrelated history table. Same pattern
  documented in deferred-items.md for ApiToken.is_expired and
  simple_config.config_set/get.
"""
import pytest

from app.database import db
from app.services.job_role_mapping_service import JobRoleMappingService
from app.models.job_role_compliance import (
    JobRoleMapping,
    JobRoleMappingHistory,
)
from tests.factories.job_code import JobCodeFactory
from tests.factories.system_role import SystemRoleFactory
from tests.factories.job_role_mapping import JobRoleMappingFactory

pytestmark = pytest.mark.unit


@pytest.fixture
def svc(app, db_session):
    return JobRoleMappingService()


@pytest.mark.xfail(
    strict=True,
    reason="Pre-existing bug: create_mapping accesses mapping.job_code (relationship) "
    "after save(commit=False) before flush, returns None. See plan 02-05 deferred items.",
)
def test_create_mapping_happy_path(svc, db_session):
    JobCodeFactory(job_code="ENG-1", job_title="Engineer")
    db.session.commit()

    mapping = svc.create_mapping(
        job_code="ENG-1",
        role_name="Admin",
        system_name="ad_groups",
        created_by="alice@test.local",
    )

    assert mapping.id is not None
    assert mapping.mapping_type == "required"
    assert mapping.job_code.job_code == "ENG-1"


@pytest.mark.xfail(
    strict=True,
    reason="Pre-existing bug: create_mapping relationship-access bug (see happy-path).",
)
def test_create_mapping_with_explicit_overrides(svc, db_session):
    JobCodeFactory(job_code="ENG-2")
    db.session.commit()

    mapping = svc.create_mapping(
        job_code="ENG-2",
        role_name="Reader",
        system_name="ad_groups",
        mapping_type="prohibited",
        priority=5,
        notes="Special case",
    )
    assert mapping.mapping_type == "prohibited"
    assert mapping.priority == 5


@pytest.mark.xfail(
    strict=True,
    reason="Pre-existing bug: create_mapping relationship-access bug (see happy-path).",
)
def test_create_mapping_duplicate_raises(svc, db_session):
    JobCodeFactory(job_code="ENG-3")
    db.session.commit()

    svc.create_mapping(
        job_code="ENG-3", role_name="Admin", system_name="ad_groups",
    )
    with pytest.raises(ValueError, match="already exists"):
        svc.create_mapping(
            job_code="ENG-3", role_name="Admin", system_name="ad_groups",
        )


def test_update_mapping_changes_fields_and_writes_history(svc, db_session):
    """Update path works because the mapping was previously committed by the factory,
    so the relationship is fully loaded before log_change accesses it."""
    mapping = JobRoleMappingFactory(mapping_type="required", priority=1)
    db.session.commit()
    mid = mapping.id

    updated = svc.update_mapping(
        mid,
        mapping_type="optional",
        priority=7,
        updated_by="carol@test.local",
        change_reason="Promotion review",
    )

    assert updated.mapping_type == "optional"
    assert updated.priority == 7

    history = JobRoleMappingHistory.query.filter_by(mapping_id=mid).all()
    assert any(h.change_type == "updated" for h in history)
    upd = next(h for h in history if h.change_type == "updated")
    assert upd.old_mapping_type == "required"
    assert upd.new_mapping_type == "optional"
    assert upd.old_priority == 1
    assert upd.new_priority == 7
    assert upd.changed_by == "carol@test.local"


def test_update_mapping_unknown_id_raises(svc, db_session):
    with pytest.raises(ValueError, match="not found"):
        svc.update_mapping(999_999, mapping_type="optional")


@pytest.mark.xfail(
    strict=True,
    reason="Pre-existing bug: JobRoleMappingHistory.mapping_id has FK to "
    "job_role_mappings.id without ON DELETE CASCADE; delete_mapping creates a "
    "history row pointing at the to-be-deleted mapping then commits both at once, "
    "raising IntegrityError on the FK violation.",
)
def test_delete_mapping_writes_history(svc, db_session):
    mapping = JobRoleMappingFactory()
    db.session.commit()
    mid = mapping.id

    assert svc.delete_mapping(mid, deleted_by="dave@test.local") is True
    assert JobRoleMapping.query.filter_by(id=mid).first() is None


def test_delete_mapping_unknown_id_raises(svc, db_session):
    with pytest.raises(ValueError, match="not found"):
        svc.delete_mapping(999_999, deleted_by="x")


def test_get_mappings_for_job_code_returns_priority_sorted(svc, db_session):
    jc = JobCodeFactory(job_code="ENG-LIST")
    sr1 = SystemRoleFactory(role_name="r1", system_name="ad_groups")
    sr2 = SystemRoleFactory(role_name="r2", system_name="ad_groups")
    sr3 = SystemRoleFactory(role_name="r3", system_name="ad_groups")
    JobRoleMappingFactory(job_code=jc, system_role=sr1, priority=1)
    JobRoleMappingFactory(job_code=jc, system_role=sr2, priority=5)
    JobRoleMappingFactory(job_code=jc, system_role=sr3, priority=3)
    db.session.commit()

    mappings = svc.get_mappings_for_job_code("ENG-LIST")
    assert len(mappings) == 3
    priorities = [m.priority for m in mappings]
    assert priorities == sorted(priorities, reverse=True)


def test_get_mappings_for_role_filters_by_system(svc, db_session):
    sr_ad = SystemRoleFactory(role_name="shared-name", system_name="ad_groups")
    sr_ks = SystemRoleFactory(role_name="shared-name", system_name="keystone")
    JobRoleMappingFactory(system_role=sr_ad)
    JobRoleMappingFactory(system_role=sr_ks)
    db.session.commit()

    matches = svc.get_mappings_for_role("shared-name", "ad_groups")
    assert len(matches) == 1
    assert matches[0].system_role.system_name == "ad_groups"


def test_get_mapping_matrix_filters_by_system(svc, db_session):
    jc = JobCodeFactory(job_code="MIX-1")
    sr_ad = SystemRoleFactory(role_name="ad-role", system_name="ad_groups")
    sr_ks = SystemRoleFactory(role_name="ks-role", system_name="keystone")
    JobRoleMappingFactory(job_code=jc, system_role=sr_ad)
    JobRoleMappingFactory(job_code=jc, system_role=sr_ks)
    db.session.commit()

    matrix = svc.get_mapping_matrix(system_name="ad_groups")
    assert "ad_groups" in matrix["systems"]
    assert "keystone" not in matrix["systems"]
    assert len(matrix["mappings"]) == 1


def test_get_mapping_matrix_unfiltered_returns_all_systems(svc, db_session):
    jc = JobCodeFactory(job_code="MIX-2")
    sr_ad = SystemRoleFactory(role_name="role-x", system_name="ad_groups")
    sr_ks = SystemRoleFactory(role_name="role-y", system_name="keystone")
    JobRoleMappingFactory(job_code=jc, system_role=sr_ad)
    JobRoleMappingFactory(job_code=jc, system_role=sr_ks)
    db.session.commit()

    matrix = svc.get_mapping_matrix()
    assert set(matrix["systems"]) == {"ad_groups", "keystone"}
    assert len(matrix["mappings"]) == 2


def test_get_statistics_counts_by_mapping_type(svc, db_session):
    JobRoleMappingFactory(mapping_type="required")
    JobRoleMappingFactory(mapping_type="required")
    JobRoleMappingFactory(mapping_type="optional")
    JobRoleMappingFactory(mapping_type="prohibited")
    db.session.commit()

    stats = svc.get_statistics()
    assert stats["total_mappings"] == 4
    assert stats["mapping_types"]["required"] == 2
    assert stats["mapping_types"]["optional"] == 1
    assert stats["mapping_types"]["prohibited"] == 1
    assert stats["total_job_codes"] >= 4
    assert stats["total_roles"] >= 4


def test_export_mappings_csv_round_trip(svc, db_session):
    jc = JobCodeFactory(job_code="CSV-1", job_title="CSV Tester")
    sr = SystemRoleFactory(role_name="csv-role", system_name="ad_groups")
    JobRoleMappingFactory(job_code=jc, system_role=sr, mapping_type="optional", priority=2)
    db.session.commit()

    csv_text = svc.export_mappings_csv()
    assert "job_code" in csv_text  # header
    assert "CSV-1" in csv_text
    assert "csv-role" in csv_text
    assert "optional" in csv_text


def test_get_mapping_history_filters_by_job_code(svc, db_session):
    mapping = JobRoleMappingFactory()
    db.session.commit()
    # Use update_mapping (works) to write a history row, then query with filter
    svc.update_mapping(mapping.id, mapping_type="optional", updated_by="x")

    rows = svc.get_mapping_history(mapping_id=mapping.id)
    assert len(rows) >= 1
    assert all(r.mapping_id == mapping.id for r in rows)
