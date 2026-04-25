"""Boundary tests for SearchEnhancer (Plan 02-06 gap closure round 2).

Targets the public ``enhance_search_results`` entry point + the two
helpers ``_extract_upn_from_azure_result`` and ``_format_employee_profile_for_search``.
The module imports a singleton ``employee_profiles_service`` from
``app.services.refresh_employee_profiles``; tests patch it at that
boundary so no DB / warehouse traffic is required.
"""
import pytest

from app.services.search_enhancer import SearchEnhancer

pytestmark = pytest.mark.unit


# ----------------------------- helpers --------------------------------------


def _basic_azure_ad():
    return {
        "userPrincipalName": "jdoe@x.com",
        "displayName": "J Doe",
        "mail": "jdoe@x.com",
    }


# ----------------------------- enhance_search_results ----------------------


def test_enhance_search_results_no_azure_ad_returns_keystone_none():
    """When azureAD is missing the enhancer marks keystone unavailable and bails."""
    enhancer = SearchEnhancer()
    result = enhancer.enhance_search_results({"azureAD": None, "genesys": {}})

    assert result["keystone"] is None
    assert "No Azure AD data" in result["keystone_error"]
    # Original data preserved (copy not mutate)
    assert result["genesys"] == {}


def test_enhance_search_results_multiple_azure_ad_short_circuits():
    """azureAD_multiple flag forces a 'select specific user' message."""
    enhancer = SearchEnhancer()
    result = enhancer.enhance_search_results(
        {"azureAD": _basic_azure_ad(), "azureAD_multiple": True}
    )
    assert result["keystone"] is None
    assert result["keystone_multiple"] is False
    assert "Multiple Azure AD users found" in result["keystone_error"]


def test_enhance_search_results_no_upn_in_azure_data():
    """An azureAD record without any UPN-shaped field flags the missing UPN."""
    enhancer = SearchEnhancer()
    result = enhancer.enhance_search_results(
        {"azureAD": {"displayName": "no upn here"}}
    )
    assert result["keystone"] is None
    assert result["keystone_error"] == "No UPN found in Azure AD data"
    assert result["keystone_multiple"] is False


def test_enhance_search_results_happy_path_returns_keystone_dict(mocker):
    """enhance_search_results pulls profile + formats it into the keystone shape."""
    enhancer = SearchEnhancer()
    fake_profile = {
        "upn": "jdoe@x.com",
        "user_serial": "12345",
        "is_locked": False,
        "lock_status": "Unlocked",
        "live_role": "Teller",
        "expected_role": "Teller",
        "test_role": None,
        "job_code": "T01",
        "last_login": None,
        "last_updated": "2026-04-25",
    }
    mocker.patch(
        "app.services.search_enhancer.employee_profiles_service.get_employee_profile",
        return_value=fake_profile,
    )
    result = enhancer.enhance_search_results({"azureAD": _basic_azure_ad()})
    assert result["keystone"]["service"] == "keystone"
    assert result["keystone"]["upn"] == "jdoe@x.com"
    assert result["keystone"]["live_role"] == "Teller"
    assert result["keystone"]["role_mismatch"] is False
    assert result["keystone"]["role_warning_level"] == "success"
    assert result["keystone_error"] is None
    assert result["keystone_multiple"] is False


def test_enhance_search_results_profile_not_found(mocker):
    """When employee_profiles_service returns None, keystone is None with explanatory error."""
    enhancer = SearchEnhancer()
    mocker.patch(
        "app.services.search_enhancer.employee_profiles_service.get_employee_profile",
        return_value=None,
    )
    result = enhancer.enhance_search_results({"azureAD": _basic_azure_ad()})
    assert result["keystone"] is None
    assert "No employee profile found" in result["keystone_error"]
    assert result["keystone_multiple"] is False


def test_enhance_search_results_profile_lookup_raises(mocker):
    """Exceptions in employee_profiles_service are caught; keystone marked unavailable."""
    enhancer = SearchEnhancer()
    mocker.patch(
        "app.services.search_enhancer.employee_profiles_service.get_employee_profile",
        side_effect=RuntimeError("DB exploded"),
    )
    result = enhancer.enhance_search_results({"azureAD": _basic_azure_ad()})
    assert result["keystone"] is None
    assert result["keystone_error"] == "Error retrieving employee profile data"
    assert result["keystone_multiple"] is False


# ----------------------------- _extract_upn_from_azure_result --------------


def test_extract_upn_returns_none_for_empty_input():
    enhancer = SearchEnhancer()
    assert enhancer._extract_upn_from_azure_result({}) is None
    assert enhancer._extract_upn_from_azure_result(None) is None


def test_extract_upn_prefers_userPrincipalName_lowercased():
    enhancer = SearchEnhancer()
    upn = enhancer._extract_upn_from_azure_result(
        {"userPrincipalName": "Jdoe@X.COM", "mail": "other@x.com"}
    )
    assert upn == "jdoe@x.com"


def test_extract_upn_falls_back_to_mail_when_no_upn_field():
    enhancer = SearchEnhancer()
    upn = enhancer._extract_upn_from_azure_result({"mail": "Foo@X.com"})
    assert upn == "foo@x.com"


def test_extract_upn_skips_value_without_at_sign():
    enhancer = SearchEnhancer()
    # 'upn' field present but invalid (no @) — falls through to mail
    upn = enhancer._extract_upn_from_azure_result(
        {"upn": "no-at-sign", "mail": "real@x.com"}
    )
    assert upn == "real@x.com"


# ----------------------------- _format_employee_profile_for_search ---------


def test_format_profile_role_mismatch_marks_high_warning():
    enhancer = SearchEnhancer()
    out = enhancer._format_employee_profile_for_search(
        {
            "upn": "jdoe@x.com",
            "live_role": "Manager",
            "expected_role": "Teller",
            "is_locked": True,
            "lock_status": "Locked",
            "last_login": None,
        }
    )
    assert out["role_mismatch"] is True
    assert out["role_warning_level"] == "high"
    assert "Role mismatch" in out["role_warning_message"]
    assert out["login_locked"] is True


def test_format_profile_no_expected_role_marks_medium_warning():
    enhancer = SearchEnhancer()
    out = enhancer._format_employee_profile_for_search(
        {
            "upn": "jdoe@x.com",
            "live_role": "Teller",
            "expected_role": None,
            "last_login": None,
        }
    )
    assert out["role_mismatch"] is True
    assert out["role_warning_level"] == "medium"
    assert "no expected role is mapped" in out["role_warning_message"]


def test_format_profile_parses_iso_last_login_string():
    enhancer = SearchEnhancer()
    out = enhancer._format_employee_profile_for_search(
        {
            "upn": "jdoe@x.com",
            "last_login": "2026-04-25T08:30:00Z",
        }
    )
    assert out["last_login_formatted"] is not None
    # Format string is %m/%d/%Y %I:%M %p
    assert "/" in out["last_login_formatted"]
    assert "AM" in out["last_login_formatted"] or "PM" in out["last_login_formatted"]


def test_format_profile_handles_unparseable_last_login_gracefully():
    enhancer = SearchEnhancer()
    out = enhancer._format_employee_profile_for_search(
        {"upn": "jdoe@x.com", "last_login": "not-a-date"}
    )
    # Falls back to str() representation, no exception
    assert out["last_login_formatted"] == "not-a-date"
