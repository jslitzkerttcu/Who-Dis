"""Targeted unit tests for LDAPService (D-12).

Mocks ldap3.Connection at the import boundary in app/services/ldap_service.py
so no real LDAP traffic is generated. Covers service_name property,
test_connection success/failure, search_user happy/empty/multiple paths,
and config-cache behavior.
"""
import pytest

from app.services.ldap_service import LDAPService

pytestmark = pytest.mark.unit


def _make_ldap_service():
    """Return a real LDAPService with config cache pre-populated to avoid hitting
    the simple_config table (which is empty under TESTING)."""
    svc = LDAPService()
    svc._config_cache.update({
        "ldap.host": "ldap://fake",
        "ldap.port": 389,
        "ldap.use_ssl": False,
        "ldap.bind_dn": "CN=fake,DC=x",
        "ldap.bind_password": "secret",
        "ldap.base_dn": "DC=x",
        "ldap.user_search_base": "OU=Users,DC=x",
        "ldap.connect_timeout": 5,
        "ldap.operation_timeout": 10,
    })
    return svc


def test_service_name_property():
    svc = _make_ldap_service()
    assert svc.service_name == "ldap"


def test_test_connection_success(mocker):
    svc = _make_ldap_service()
    mock_conn = mocker.MagicMock()
    mock_conn.__enter__ = mocker.MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = mocker.MagicMock(return_value=False)
    mock_conn.search.return_value = True
    mocker.patch("app.services.ldap_service.Server", return_value=mocker.MagicMock())
    mocker.patch("app.services.ldap_service.Connection", return_value=mock_conn)

    assert svc.test_connection() is True


def test_test_connection_failure(mocker, caplog):
    import logging

    svc = _make_ldap_service()
    mocker.patch("app.services.ldap_service.Server", return_value=mocker.MagicMock())
    mocker.patch(
        "app.services.ldap_service.Connection",
        side_effect=Exception("boom"),
    )

    with caplog.at_level(logging.ERROR, logger="app.services.ldap_service"):
        result = svc.test_connection()

    assert result is False
    assert any("LDAP connection test failed" in r.getMessage() for r in caplog.records)


def _make_entry(mocker, **attrs):
    """Build a mock ldap3 entry whose attribute access mirrors ldap3 idioms."""
    entry = mocker.MagicMock()
    entry.entry_dn = attrs.get("dn", "CN=jdoe,DC=x")
    for k, v in attrs.items():
        attr_obj = mocker.MagicMock()
        attr_obj.value = v
        attr_obj.values = [v] if not isinstance(v, list) else v
        attr_obj.__str__ = lambda self, val=v: str(val)
        attr_obj.__bool__ = lambda self, val=v: bool(val)
        setattr(entry, k, attr_obj)
    # Default missing attrs to falsy
    for k in ("memberOf", "userAccountControl", "lockoutTime", "telephoneNumber",
              "extensionAttribute4", "pager", "manager", "thumbnailPhoto",
              "pwdLastSet", "accountExpires", "msDS-UserPasswordExpiryTimeComputed",
              "ExclaimerMobile", "department", "title", "employeeID", "ipPhone",
              "userPrincipalName"):
        if k not in attrs:
            blank = mocker.MagicMock()
            blank.value = None
            blank.values = []
            blank.__bool__ = lambda self: False
            setattr(entry, k, blank)
    return entry


def test_search_user_happy_path(mocker):
    svc = _make_ldap_service()

    entry = _make_entry(
        mocker,
        dn="CN=jdoe,DC=x",
        sAMAccountName="jdoe",
        mail="jdoe@x.com",
        displayName="J Doe",
    )

    mock_conn = mocker.MagicMock()
    mock_conn.__enter__ = mocker.MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = mocker.MagicMock(return_value=False)
    mock_conn.entries = [entry]
    mock_conn.search.return_value = True

    mocker.patch("app.services.ldap_service.Server", return_value=mocker.MagicMock())
    mocker.patch("app.services.ldap_service.Connection", return_value=mock_conn)

    result = svc.search_user("jdoe")
    assert result is not None
    assert result.get("sAMAccountName") == "jdoe"
    assert result.get("mail") == "jdoe@x.com"


def test_search_user_no_results(mocker):
    svc = _make_ldap_service()

    mock_conn = mocker.MagicMock()
    mock_conn.__enter__ = mocker.MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = mocker.MagicMock(return_value=False)
    mock_conn.entries = []
    mock_conn.search.return_value = True

    mocker.patch("app.services.ldap_service.Server", return_value=mocker.MagicMock())
    mocker.patch("app.services.ldap_service.Connection", return_value=mock_conn)

    result = svc.search_user("ghost")
    assert result is None


def test_search_user_multiple_results(mocker):
    svc = _make_ldap_service()

    entries = [
        _make_entry(mocker, dn="CN=jdoe1,DC=x", sAMAccountName="jdoe1", mail="a@x.com", displayName="J1"),
        _make_entry(mocker, dn="CN=jdoe2,DC=x", sAMAccountName="jdoe2", mail="b@x.com", displayName="J2"),
    ]

    mock_conn = mocker.MagicMock()
    mock_conn.__enter__ = mocker.MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = mocker.MagicMock(return_value=False)
    mock_conn.entries = entries
    mock_conn.search.return_value = True

    mocker.patch("app.services.ldap_service.Server", return_value=mocker.MagicMock())
    mocker.patch("app.services.ldap_service.Connection", return_value=mock_conn)

    result = svc.search_user("jdoe")
    assert result is not None
    assert result.get("multiple_results") is True
    assert result.get("total") == 2
    assert len(result.get("results", [])) == 2


def test_config_cache_round_trip():
    """Verify _get_config returns from internal cache (no DB needed when seeded)."""
    svc = LDAPService()
    svc._config_cache["ldap.host"] = "ldap://test-host"
    assert svc.host == "ldap://test-host"
    svc._clear_config_cache()
    # After clear, the cache is empty; next access goes to config_get → default
    assert svc.host == "ldap://localhost"  # the default in the host property


def test_search_user_swallows_unexpected_exception(mocker):
    """search_user catches generic Exception and returns None — verified by the
    except Exception block at app/services/ldap_service.py:284-289."""
    svc = _make_ldap_service()

    mocker.patch("app.services.ldap_service.Server", side_effect=RuntimeError("bad"))
    result = svc.search_user("anyone")
    assert result is None
