"""
Simplified configuration service for WhoDis.

This replaces the overengineered configuration system with a simple,
pragmatic approach that handles 99% of use cases with 10% of the complexity.
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from cryptography.fernet import Fernet
from sqlalchemy import text
from app.database import db
from app.utils.error_handler import handle_service_errors
from app.interfaces.configuration_service import IConfigurationService

logger = logging.getLogger(__name__)


class SimpleConfig(IConfigurationService):
    """Simple configuration with database persistence and optional encryption."""

    __tablename__ = "simple_config"

    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}
        self._fernet: Optional[Fernet] = None
        self._encryption_key = os.getenv("WHODIS_ENCRYPTION_KEY")

        if self._encryption_key:
            # Use Fernet directly - no need for complex key derivation
            try:
                if len(self._encryption_key) == 44:
                    self._fernet = Fernet(self._encryption_key.encode())
                    logger.debug("Encryption key initialized successfully")
                else:
                    logger.error(
                        f"Invalid encryption key length: {len(self._encryption_key)}, expected 44. "
                        "Configuration decryption will fail!"
                    )
                    self._fernet = None
            except Exception as e:
                logger.error(f"Failed to initialize Fernet: {e}")
                self._fernet = None
        else:
            logger.warning(
                "WHODIS_ENCRYPTION_KEY not found in environment - encrypted configuration values will not be decrypted"
            )

    def _should_encrypt(self, key: str) -> bool:
        """Determine if a key should be encrypted based on naming convention."""
        # Extract just the field name from full key like "category.field"
        field_name = key.split(".")[-1] if "." in key else key
        sensitive_suffixes = ("_password", "_secret", "_key", "_token", "_credential")
        return any(field_name.lower().endswith(suffix) for suffix in sensitive_suffixes)

    def _encrypt(self, value: str) -> str:
        """Encrypt a value if encryption is available."""
        if self._fernet and value:
            return self._fernet.encrypt(value.encode()).decode()
        return value

    def _decrypt(self, value: str) -> str:
        """Decrypt a value if it appears to be encrypted."""
        if not self._fernet:
            logger.warning(
                "No Fernet instance available for decryption - returning value as-is"
            )
            return value

        if not value:
            return value

        try:
            # Try to decrypt - if it fails, it's not encrypted
            decrypted = self._fernet.decrypt(value.encode()).decode()
            return decrypted
        except Exception as e:
            # Not encrypted or wrong key - return as is
            if "InvalidToken" in str(type(e)):
                logger.error(
                    "Encryption key mismatch detected - unable to decrypt configuration value. "
                    "This usually means the WHODIS_ENCRYPTION_KEY has changed."
                )
                # For InvalidToken errors (key mismatch), return empty string to force re-entry
                return ""
            else:
                # Not encrypted, return as-is
                return value

    @handle_service_errors(raise_errors=False, default_return=None)
    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Get a configuration value with optional environment variable fallback."""
        # Check cache first
        if key in self._cache:
            return self._cache[key]

        # Check database
        try:
            with db.engine.begin() as conn:
                result = conn.execute(
                    text("SELECT value FROM simple_config WHERE key = :key"),
                    {"key": key},
                ).first()

                if result:
                    value = result[0]  # Get the single value column

                    # Try to decrypt if it looks encrypted
                    if value and isinstance(value, str) and value.startswith("gAAAAAB"):
                        try:
                            value = self._decrypt(value)
                            # Debug logging for encrypted values
                            if self._should_encrypt(key):
                                logger.debug(f"Successfully decrypted {key}")
                        except Exception as e:
                            logger.warning(f"Failed to decrypt {key}: {e}")
                            # If decryption fails and this shouldn't be encrypted, keep original
                            if not self._should_encrypt(key):
                                pass  # Keep the original value
                            else:
                                value = default  # Use default for encrypted fields that fail

                    self._cache[key] = value
                    return value
        except Exception as e:
            logger.debug(f"Database lookup failed for {key}: {e}")

        # Environment variable fallback removed - database is the authoritative source
        # Return default
        self._cache[key] = default
        return default

    @handle_service_errors(raise_errors=False, default_return=False)
    def set_with_result(self, key: str, value: Any, user: str = "system") -> bool:
        """Set a configuration value."""
        str_value = str(value) if value is not None else ""

        try:
            with db.engine.begin() as conn:
                # Parse key into category and setting_key
                if "." in key:
                    category, setting_key = key.split(".", 1)
                else:
                    category, setting_key = "general", key

                # Determine if we should encrypt
                should_encrypt = self._should_encrypt(key)

                if should_encrypt:
                    encrypted_value = self._encrypt(str_value)
                    setting_value = None
                else:
                    encrypted_value = None
                    setting_value = str_value

                # Upsert using PostgreSQL's ON CONFLICT
                conn.execute(
                    text("""
                    INSERT INTO configuration (category, setting_key, setting_value, encrypted_value, updated_by, updated_at, is_sensitive)
                    VALUES (:category, :setting_key, :setting_value, :encrypted_value, :user, :updated_at, :is_sensitive)
                    ON CONFLICT (category, setting_key) DO UPDATE
                    SET setting_value = EXCLUDED.setting_value,
                        encrypted_value = EXCLUDED.encrypted_value,
                        updated_by = EXCLUDED.updated_by,
                        updated_at = EXCLUDED.updated_at,
                        is_sensitive = EXCLUDED.is_sensitive
                """),
                    {
                        "category": category,
                        "setting_key": setting_key,
                        "setting_value": setting_value,
                        "encrypted_value": encrypted_value,
                        "user": user,
                        "updated_at": datetime.utcnow(),
                        "is_sensitive": should_encrypt,
                    },
                )

            # Update cache
            self._cache[key] = str_value
            return True

        except Exception as e:
            logger.error(f"Failed to set config {key}: {e}")
            return False

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value (interface-compliant version)."""
        self.set_with_result(key, value, "system")

    def exists(self, key: str) -> bool:
        """Check if a configuration key exists."""
        try:
            result = self.get(key)
            return result is not None
        except Exception:
            return False

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values."""
        try:
            configs = {}
            with db.engine.begin() as conn:
                results = conn.execute(
                    text(
                        "SELECT category, setting_key, setting_value, encrypted_value FROM configuration ORDER BY category, setting_key"
                    )
                )
                for category, setting_key, setting_value, encrypted_value in results:
                    key = f"{category}.{setting_key}"

                    # Use encrypted_value if available, otherwise setting_value
                    if encrypted_value:
                        try:
                            # Handle memoryview objects from PostgreSQL BYTEA columns
                            if hasattr(encrypted_value, "tobytes"):
                                encrypted_str = encrypted_value.tobytes().decode(
                                    "utf-8"
                                )
                            else:
                                encrypted_str = str(encrypted_value)
                            value = self._decrypt(encrypted_str)

                            # If decryption returned empty string due to key mismatch
                            # and this field shouldn't be encrypted, use plain value
                            if (
                                value == ""
                                and not self._should_encrypt(key)
                                and setting_value
                            ):
                                logger.warning(
                                    f"Using plain value for {key} due to decryption failure"
                                )
                                value = setting_value
                        except Exception as e:
                            logger.warning(f"Failed to decrypt {key}: {e}")
                            value = setting_value
                    else:
                        value = setting_value

                    configs[key] = value
            return configs
        except Exception as e:
            logger.error(f"Failed to get all configs: {e}")
            return {}

    def delete(self, key: str) -> bool:
        """Delete a configuration value."""
        try:
            with db.engine.begin() as conn:
                # Parse key into category and setting_key
                if "." in key:
                    category, setting_key = key.split(".", 1)
                else:
                    category, setting_key = "general", key

                conn.execute(
                    text(
                        "DELETE FROM configuration WHERE category = :category AND setting_key = :setting_key"
                    ),
                    {"category": category, "setting_key": setting_key},
                )

            # Remove from cache
            self._cache.pop(key, None)
            return True

        except Exception as e:
            logger.error(f"Failed to delete config {key}: {e}")
            return False

    def clear_cache(self) -> None:
        """Clear the configuration cache."""
        self._cache.clear()


# Global instance
_config = SimpleConfig()


# Simple API functions
@handle_service_errors(raise_errors=False, default_return=None)
def config_get(key: str, default: Optional[Any] = None) -> Any:
    """Get a configuration value."""
    return _config.get(key, default)


def config_set(key: str, value: Any, user: str = "system") -> bool:
    """Set a configuration value."""
    try:
        result = _config.set_with_result(key, value, user)
        return bool(result)  # Ensure boolean return
    except Exception:
        return False


def config_delete(key: str) -> bool:
    """Delete a configuration value."""
    result = _config.delete(key)
    return bool(result)


def config_get_all() -> Dict[str, Any]:
    """Get all configuration values."""
    return _config.get_all()


def config_clear_cache() -> None:
    """Clear the configuration cache."""
    _config.clear_cache()


def config_exists(key: str) -> bool:
    """Check if a configuration key exists."""
    return _config.exists(key)
