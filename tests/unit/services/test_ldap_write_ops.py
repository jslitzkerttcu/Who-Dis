"""Unit tests for LDAP write operations (unlock, reset password, enable/disable).

Mocks ldap3 Connection at the import boundary so no real LDAP traffic is generated.
"""

import pytest

from app.services.ldap_service import LDAPService

pytestmark = pytest.mark.unit


def _make_ldap_service(use_ssl: bool = True):
    """Return a LDAPService with config cache pre-populated."""
    svc = LDAPService()
    svc._config_cache.update(
        {
            "ldap.host": "ldap://fake",
            "ldap.port": 636,
            "ldap.use_ssl": use_ssl,
            "ldap.bind_dn": "CN=fake,DC=x",
            "ldap.bind_password": "secret",
            "ldap.base_dn": "DC=x",
            "ldap.user_search_base": "OU=Users,DC=x",
            "ldap.connect_timeout": 5,
            "ldap.operation_timeout": 10,
        }
    )
    return svc


class TestUnlockAccount:
    def test_unlock_account_success(self, mocker):
        svc = _make_ldap_service()
        mock_conn = mocker.MagicMock()
        mock_conn.__enter__ = mocker.MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = mocker.MagicMock(return_value=False)
        mock_conn.modify.return_value = True

        mocker.patch("app.services.ldap_service.Server", return_value=mocker.MagicMock())
        mocker.patch("app.services.ldap_service.Connection", return_value=mock_conn)

        result = svc.unlock_account("CN=User,OU=Users,DC=x")
        assert result is True
        mock_conn.modify.assert_called_once()
        call_args = mock_conn.modify.call_args
        assert call_args[0][0] == "CN=User,OU=Users,DC=x"
        # Check lockoutTime is being reset to '0'
        changes = call_args[0][1]
        assert "lockoutTime" in changes

    def test_unlock_account_ldap_failure(self, mocker):
        svc = _make_ldap_service()
        mock_conn = mocker.MagicMock()
        mock_conn.__enter__ = mocker.MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = mocker.MagicMock(return_value=False)
        mock_conn.modify.return_value = False

        mocker.patch("app.services.ldap_service.Server", return_value=mocker.MagicMock())
        mocker.patch("app.services.ldap_service.Connection", return_value=mock_conn)

        result = svc.unlock_account("CN=User,OU=Users,DC=x")
        assert result is False


class TestResetPassword:
    def test_reset_password_success(self, mocker):
        svc = _make_ldap_service(use_ssl=True)
        mock_conn = mocker.MagicMock()
        mock_conn.__enter__ = mocker.MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = mocker.MagicMock(return_value=False)
        mock_conn.extend.microsoft.modify_password.return_value = True

        mocker.patch("app.services.ldap_service.Server", return_value=mocker.MagicMock())
        mocker.patch("app.services.ldap_service.Connection", return_value=mock_conn)

        result = svc.reset_password("CN=User,OU=Users,DC=x", "NewPass123!")
        assert result is True
        mock_conn.extend.microsoft.modify_password.assert_called_once_with(
            "CN=User,OU=Users,DC=x", "NewPass123!"
        )

    def test_reset_password_no_ssl(self, mocker, caplog):
        import logging

        svc = _make_ldap_service(use_ssl=False)

        with caplog.at_level(logging.ERROR):
            result = svc.reset_password("CN=User,OU=Users,DC=x", "NewPass123!")

        assert result is False
        assert "SSL" in caplog.text or "ssl" in caplog.text.lower()


class TestSetAccountEnabled:
    def test_set_account_enabled_enable(self, mocker):
        """UAC 514 (512+2=disabled) -> clearing bit 1 -> 512."""
        svc = _make_ldap_service()
        mock_conn = mocker.MagicMock()
        mock_conn.__enter__ = mocker.MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = mocker.MagicMock(return_value=False)

        # Mock the search for current UAC
        mock_entry = mocker.MagicMock()
        mock_entry.userAccountControl.value = 514
        mock_conn.entries = [mock_entry]
        mock_conn.search.return_value = True
        mock_conn.modify.return_value = True

        mocker.patch("app.services.ldap_service.Server", return_value=mocker.MagicMock())
        mocker.patch("app.services.ldap_service.Connection", return_value=mock_conn)

        result = svc.set_account_enabled("CN=User,OU=Users,DC=x", enabled=True)
        assert result is True

        # Verify the UAC was set to 512 (cleared bit 1)
        modify_call = mock_conn.modify.call_args
        changes = modify_call[0][1]
        assert "userAccountControl" in changes
        # The new value should be 512 (514 & ~2)
        new_uac_values = changes["userAccountControl"]
        assert "512" in str(new_uac_values)

    def test_set_account_enabled_disable(self, mocker):
        """UAC 512 (normal) -> setting bit 1 -> 514."""
        svc = _make_ldap_service()
        mock_conn = mocker.MagicMock()
        mock_conn.__enter__ = mocker.MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = mocker.MagicMock(return_value=False)

        mock_entry = mocker.MagicMock()
        mock_entry.userAccountControl.value = 512
        mock_conn.entries = [mock_entry]
        mock_conn.search.return_value = True
        mock_conn.modify.return_value = True

        mocker.patch("app.services.ldap_service.Server", return_value=mocker.MagicMock())
        mocker.patch("app.services.ldap_service.Connection", return_value=mock_conn)

        result = svc.set_account_enabled("CN=User,OU=Users,DC=x", enabled=False)
        assert result is True

        modify_call = mock_conn.modify.call_args
        changes = modify_call[0][1]
        assert "userAccountControl" in changes
        # The new value should be 514 (512 | 2)
        new_uac_values = changes["userAccountControl"]
        assert "514" in str(new_uac_values)

    def test_set_account_enabled_preserves_other_flags(self, mocker):
        """UAC 66050 (normal+dont_expire_password+disabled) -> enable clears bit 1 -> 66048."""
        svc = _make_ldap_service()
        mock_conn = mocker.MagicMock()
        mock_conn.__enter__ = mocker.MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = mocker.MagicMock(return_value=False)

        # 66050 = 65536 (DONT_EXPIRE_PASSWORD) + 512 (NORMAL_ACCOUNT) + 2 (ACCOUNTDISABLE)
        mock_entry = mocker.MagicMock()
        mock_entry.userAccountControl.value = 66050
        mock_conn.entries = [mock_entry]
        mock_conn.search.return_value = True
        mock_conn.modify.return_value = True

        mocker.patch("app.services.ldap_service.Server", return_value=mocker.MagicMock())
        mocker.patch("app.services.ldap_service.Connection", return_value=mock_conn)

        # Enable: should clear bit 1 only -> 66048
        result = svc.set_account_enabled("CN=User,OU=Users,DC=x", enabled=True)
        assert result is True

        modify_call = mock_conn.modify.call_args
        changes = modify_call[0][1]
        new_uac_values = changes["userAccountControl"]
        assert "66048" in str(new_uac_values)
