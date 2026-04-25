"""Boundary tests for ResultMerger (Plan 02-06 gap closure round 2).

The merger has two top-level entry points the search blueprint uses:
  - merge_ldap_graph_data(ldap, graph, include_photo) -> Optional[Dict]
  - merge_azure_ad_results(ldap_result, genesys_result, graph_result)
        -> Tuple[azure_ad_result, azure_ad_error, azure_ad_multiple]
  - smart_match_services(azure_ad_result, azure_ad_multiple,
                         genesys_result, genesys_multiple)
        -> Tuple[updated_genesys_result, updated_genesys_multiple]

Plus several pure helpers (_combine_errors, _combine_multiple_results,
_merge_basic_info, _find_matching_genesys_user). These are exercised
without DB / HTTP — pure dict-in / dict-out tests.
"""
import pytest

from app.services.result_merger import ResultMerger

pytestmark = pytest.mark.unit


@pytest.fixture
def merger(app):
    """ResultMerger reads ``search.lazy_load_photos`` config; tests prime the
    cache with a default so no real config_get / DB hit is required."""
    m = ResultMerger()
    m._config_cache.update({"search.lazy_load_photos": "false"})
    return m


# --------------------------- merge_ldap_graph_data -------------------------


def test_merge_ldap_graph_data_returns_none_when_both_inputs_empty(merger):
    assert merger.merge_ldap_graph_data(None, None) is None


def test_merge_ldap_graph_data_only_ldap_returns_marked_dict(merger):
    out = merger.merge_ldap_graph_data(
        {"sAMAccountName": "jdoe", "mail": "jdoe@x.com"}, None
    )
    assert out is not None
    assert out["dataSource"] == "azureAD"
    assert out["sAMAccountName"] == "jdoe"
    # No Graph data merged -> no hasGraphData flag
    assert "hasGraphData" not in out


def test_merge_ldap_graph_data_only_graph_returns_marked_dict(merger):
    out = merger.merge_ldap_graph_data(
        None, {"userPrincipalName": "jdoe@x.com", "displayName": "J Doe", "id": "g1"}
    )
    assert out is not None
    assert out["dataSource"] == "azureAD"
    assert out["hasGraphData"] is True
    assert out["userPrincipalName"] == "jdoe@x.com"
    # Graph ID propagated for photo lookups even when LDAP absent
    assert out["graphId"] == "g1"


def test_merge_ldap_graph_data_graph_overrides_ldap_basic_fields(merger):
    out = merger.merge_ldap_graph_data(
        {"sAMAccountName": "jdoe", "displayName": "Old Name", "mail": "old@x.com"},
        {"displayName": "New Name", "mail": "new@x.com", "id": "g1"},
    )
    assert out["displayName"] == "New Name"
    assert out["mail"] == "new@x.com"
    # LDAP-only field retained
    assert out["sAMAccountName"] == "jdoe"


def test_merge_ldap_graph_data_strips_ldap_thumbnail_photo(merger):
    out = merger.merge_ldap_graph_data(
        {"sAMAccountName": "jdoe", "thumbnailPhoto": b"ldap-photo"}, None
    )
    assert "thumbnailPhoto" not in out


def test_merge_ldap_graph_data_account_enabled_propagates(merger):
    out = merger.merge_ldap_graph_data(
        {"sAMAccountName": "jdoe"},
        {"accountEnabled": False, "id": "g1"},
    )
    assert out["enabled"] is False


def test_merge_ldap_graph_data_phone_numbers_merged(merger):
    out = merger.merge_ldap_graph_data(
        {"sAMAccountName": "jdoe", "phoneNumbers": {"office": "111"}},
        {
            "id": "g1",
            "phoneNumbers": {"mobile": "222", "businessPhones": "333"},
        },
    )
    assert out["phoneNumbers"]["office"] == "111"
    assert out["phoneNumbers"]["mobile"] == "222"
    assert out["phoneNumbers"]["business"] == "333"


# --------------------------- merge_azure_ad_results ------------------------


def _wrap(result=None, error=None, multiple=False):
    return {"result": result, "error": error, "multiple": multiple}


def test_merge_azure_ad_results_both_single_returns_merged(merger):
    azure_ad, error, multiple = merger.merge_azure_ad_results(
        _wrap(result={"sAMAccountName": "jdoe", "mail": "jdoe@x.com"}),
        _wrap(),
        _wrap(result={"userPrincipalName": "jdoe@x.com", "displayName": "J Doe", "id": "g1"}),
    )
    assert error is None
    assert multiple is False
    assert azure_ad["dataSource"] == "azureAD"
    assert azure_ad["hasGraphData"] is True
    assert azure_ad["displayName"] == "J Doe"


def test_merge_azure_ad_results_only_ldap_returns_ldap_only(merger):
    azure_ad, error, multiple = merger.merge_azure_ad_results(
        _wrap(result={"sAMAccountName": "jdoe", "mail": "jdoe@x.com"}),
        _wrap(),
        _wrap(),
    )
    assert error is None
    assert multiple is False
    assert azure_ad["sAMAccountName"] == "jdoe"
    assert "hasGraphData" not in azure_ad


def test_merge_azure_ad_results_only_graph_returns_graph_only(merger):
    azure_ad, error, multiple = merger.merge_azure_ad_results(
        _wrap(),
        _wrap(),
        _wrap(result={"userPrincipalName": "jdoe@x.com", "id": "g1"}),
    )
    assert error is None
    assert azure_ad["hasGraphData"] is True
    assert azure_ad["userPrincipalName"] == "jdoe@x.com"


def test_merge_azure_ad_results_no_sources_returns_none(merger):
    azure_ad, error, multiple = merger.merge_azure_ad_results(_wrap(), _wrap(), _wrap())
    assert azure_ad is None
    assert error is None
    assert multiple is False


def test_merge_azure_ad_results_combines_errors_when_both_fail(merger):
    _, error, _ = merger.merge_azure_ad_results(
        _wrap(error="ldap timeout"),
        _wrap(),
        _wrap(error="graph 503"),
    )
    assert "Active Directory" in error and "Microsoft Graph" in error


def test_merge_azure_ad_results_only_ldap_error_passes_through(merger):
    _, error, _ = merger.merge_azure_ad_results(
        _wrap(error="ldap timeout"), _wrap(), _wrap()
    )
    assert error == "ldap timeout"


def test_merge_azure_ad_results_ldap_multiple_returns_multiple(merger):
    """When LDAP returned multiple results and Graph empty, surface the LDAP wrapper."""
    azure_ad, _, multiple = merger.merge_azure_ad_results(
        _wrap(
            result={"multiple_results": True, "results": [{"sAMAccountName": "j1"}], "total": 5},
            multiple=True,
        ),
        _wrap(),
        _wrap(),
    )
    assert multiple is True
    assert azure_ad["multiple_results"] is True
    assert azure_ad["total"] == 5


def test_merge_azure_ad_results_both_multiple_combined(merger):
    azure_ad, _, multiple = merger.merge_azure_ad_results(
        _wrap(
            result={"multiple_results": True, "results": [{"sAMAccountName": "l"}], "total": 3},
            multiple=True,
        ),
        _wrap(),
        _wrap(
            result={"multiple_results": True, "results": [{"id": "g"}], "total": 4},
            multiple=True,
        ),
    )
    assert multiple is True
    assert azure_ad["multiple_results"] is True
    assert azure_ad["total"] == 7
    assert len(azure_ad["ldap_results"]) == 1
    assert len(azure_ad["graph_results"]) == 1


# --------------------------- smart_match_services -------------------------


def test_smart_match_services_passes_through_when_no_smart_case(merger):
    """Single AD + single Genesys -> no smart matching needed; pass through."""
    genesys = {"id": "gn-1", "email": "j@x.com"}
    out, multiple = merger.smart_match_services(
        azure_ad_result={"mail": "j@x.com"},
        azure_ad_multiple=False,
        genesys_result=genesys,
        genesys_multiple=False,
    )
    assert out is genesys
    assert multiple is False


def test_smart_match_services_no_email_in_azure_ad_returns_multi(merger):
    """No mail on AD -> can't match -> returns multiple flag intact."""
    out, multiple = merger.smart_match_services(
        azure_ad_result={"sAMAccountName": "jdoe"},  # no mail
        azure_ad_multiple=False,
        genesys_result={"results": [{"id": "g1", "email": "g@x.com"}]},
        genesys_multiple=True,
    )
    assert multiple is True


# --------------------------- pure helpers ---------------------------------


def test_combine_errors_only_ldap_passes_through(merger):
    assert merger._combine_errors("ldap-fail", None) == "ldap-fail"


def test_combine_errors_only_graph_passes_through(merger):
    assert merger._combine_errors(None, "graph-fail") == "graph-fail"


def test_combine_errors_both_returns_summary(merger):
    out = merger._combine_errors("ldap", "graph")
    assert "Active Directory" in out
    assert "Microsoft Graph" in out


def test_combine_errors_neither_returns_none(merger):
    assert merger._combine_errors(None, None) is None


def test_find_matching_genesys_user_matches_by_email(merger):
    users = [
        {"id": "1", "email": "no@x.com", "username": "no"},
        {"id": "2", "email": "Hit@X.com", "username": "hit"},
    ]
    match = merger._find_matching_genesys_user("hit@x.com", users)
    assert match["id"] == "2"


def test_find_matching_genesys_user_returns_none_when_no_match(merger):
    users = [{"id": "1", "email": "other@x.com", "username": "other"}]
    assert merger._find_matching_genesys_user("ghost@x.com", users) is None


def test_combine_multiple_results_sums_totals(merger):
    out = merger._combine_multiple_results(
        {"results": [{"a": 1}], "total": 3},
        {"results": [{"b": 2}, {"b": 3}], "total": 4},
    )
    assert out["multiple_results"] is True
    assert out["total"] == 7
    assert len(out["ldap_results"]) == 1
    assert len(out["graph_results"]) == 2


def test_combine_multiple_results_handles_none_inputs(merger):
    out = merger._combine_multiple_results(None, None)
    assert out["multiple_results"] is True
    assert out["total"] == 0
    assert out["ldap_results"] == []
    assert out["graph_results"] == []


def test_lazy_load_photos_property_reads_config(merger):
    merger._config_cache["search.lazy_load_photos"] = "true"
    assert merger.lazy_load_photos is True
    merger._config_cache["search.lazy_load_photos"] = "false"
    assert merger.lazy_load_photos is False


def test_lazy_load_photos_handles_bool_directly(merger):
    merger._config_cache["search.lazy_load_photos"] = True
    assert merger.lazy_load_photos is True
