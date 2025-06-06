import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from app.models.configuration import Configuration, ConfigurationHistory
from app.services.encryption_service import get_encryption_service


class ConfigurationService:
    def __init__(self, db_connection):
        self.conn = db_connection
        self._cache = {}
        self._encryption_service = None
        try:
            self._encryption_service = get_encryption_service()
        except ValueError:
            # Encryption key not available yet
            pass
        self._load_cache()

    def _load_cache(self):
        """Load all configuration into memory cache"""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, category, setting_key, setting_value, data_type, 
                           description, is_sensitive, validation_regex, min_value, 
                           max_value, default_value, created_at, updated_at, updated_by,
                           encrypted_value
                    FROM configuration
                    """
                )
                for row in cursor.fetchall():
                    config = Configuration.from_row(row)
                    cache_key = f"{config.category}.{config.setting_key}"
                    self._cache[cache_key] = config
        except Exception as e:
            print(f"Error loading configuration cache: {e}")
            # Fall back to environment variables if database not available
            self._cache = {}

    def get(self, category: str, key: str, default: Any = None) -> Any:
        """Get configuration value with type conversion and decryption"""
        cache_key = f"{category}.{key}"

        # Check cache first
        if cache_key in self._cache:
            config = self._cache[cache_key]

            # Handle encrypted values
            if config.encrypted_value and self._encryption_service:
                try:
                    # Convert memoryview/buffer to bytes if needed
                    encrypted_bytes = config.encrypted_value
                    if hasattr(encrypted_bytes, "tobytes"):
                        encrypted_bytes = encrypted_bytes.tobytes()
                    elif not isinstance(encrypted_bytes, bytes):
                        encrypted_bytes = bytes(encrypted_bytes)

                    decrypted_value = self._encryption_service.decrypt(encrypted_bytes)
                    config.setting_value = decrypted_value
                except Exception as e:
                    print(f"Error decrypting {category}.{key}: {e}")
                    return default

            return config.get_typed_value()

        # Fall back to environment variable
        env_key = f"{category.upper()}_{key.upper()}"
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value

        return default

    def get_all_by_category(self, category: str) -> Dict[str, Any]:
        """Get all configuration values for a category"""
        result = {}
        for cache_key, config in self._cache.items():
            if config.category == category:
                # Handle encrypted values
                if config.encrypted_value and self._encryption_service:
                    try:
                        # Convert memoryview/buffer to bytes if needed
                        encrypted_bytes = config.encrypted_value
                        if hasattr(encrypted_bytes, "tobytes"):
                            encrypted_bytes = encrypted_bytes.tobytes()
                        elif not isinstance(encrypted_bytes, bytes):
                            encrypted_bytes = bytes(encrypted_bytes)

                        decrypted_value = self._encryption_service.decrypt(
                            encrypted_bytes
                        )
                        config.setting_value = decrypted_value
                    except Exception as e:
                        print(f"Error decrypting {category}.{config.setting_key}: {e}")

                result[config.setting_key] = config.get_typed_value()
        return result

    def get_all_settings(self) -> List[Configuration]:
        """Get all configuration settings"""
        return list(self._cache.values())

    def set(
        self,
        category: str,
        key: str,
        value: Any,
        updated_by: str,
        change_reason: Optional[str] = None,
        is_sensitive: Optional[bool] = None,
    ) -> bool:
        """Update configuration value with encryption support"""
        try:
            cache_key = f"{category}.{key}"

            # Convert value to string for storage
            str_value = str(value)

            # Check if configuration exists
            if cache_key in self._cache:
                config = self._cache[cache_key]

                # Determine if value should be encrypted
                encrypt_value = (
                    is_sensitive if is_sensitive is not None else config.is_sensitive
                )

                # Validate the value
                if not self._validate_value(config, str_value):
                    return False

                # Update in database
                with self.conn.cursor() as cursor:
                    if encrypt_value and self._encryption_service:
                        # Encrypt the value
                        encrypted_bytes = self._encryption_service.encrypt(str_value)
                        cursor.execute(
                            """
                            UPDATE configuration 
                            SET setting_value = NULL, encrypted_value = %s, 
                                updated_by = %s, is_sensitive = TRUE
                            WHERE category = %s AND setting_key = %s
                            """,
                            (encrypted_bytes, updated_by, category, key),
                        )
                    else:
                        cursor.execute(
                            """
                            UPDATE configuration 
                            SET setting_value = %s, encrypted_value = NULL, 
                                updated_by = %s
                            WHERE category = %s AND setting_key = %s
                            """,
                            (str_value, updated_by, category, key),
                        )

                    # Add change reason to history if provided
                    if change_reason and cursor.rowcount > 0:
                        cursor.execute(
                            """
                            UPDATE configuration_history 
                            SET change_reason = %s
                            WHERE id = (
                                SELECT id FROM configuration_history 
                                WHERE category = %s AND setting_key = %s 
                                ORDER BY changed_at DESC LIMIT 1
                            )
                            """,
                            (change_reason, category, key),
                        )

                    self.conn.commit()

                # Update cache
                config.setting_value = str_value
                config.updated_by = updated_by
                config.updated_at = datetime.now()

                return True
            else:
                # Create new configuration
                return self._create_config(category, key, str_value, updated_by)

        except Exception as e:
            print(f"Error updating configuration: {e}")
            self.conn.rollback()
            return False

    def _validate_value(self, config: Configuration, value: str) -> bool:
        """Validate a configuration value"""
        try:
            # Check regex validation
            if config.validation_regex:
                if not re.match(config.validation_regex, value):
                    return False

            # Check numeric constraints
            if config.data_type in ("integer", "float"):
                num_value = float(value)
                if config.min_value is not None and num_value < config.min_value:
                    return False
                if config.max_value is not None and num_value > config.max_value:
                    return False

            return True
        except (ValueError, re.error):
            return False

    def _create_config(
        self,
        category: str,
        key: str,
        value: str,
        created_by: str,
        data_type: str = "string",
    ) -> bool:
        """Create new configuration entry"""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO configuration 
                    (category, setting_key, setting_value, data_type, updated_by)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (category, key, value, data_type, created_by),
                )
                cursor.fetchone()[0]  # Get the ID but we don't need it
                self.conn.commit()

                # Reload cache
                self._load_cache()
                return True
        except Exception as e:
            print(f"Error creating configuration: {e}")
            self.conn.rollback()
            return False

    def get_history(
        self,
        category: Optional[str] = None,
        key: Optional[str] = None,
        limit: int = 100,
    ) -> List[ConfigurationHistory]:
        """Get configuration change history"""
        try:
            with self.conn.cursor() as cursor:
                query = """
                    SELECT id, config_id, category, setting_key, old_value, 
                           new_value, changed_at, changed_by, change_reason
                    FROM configuration_history
                """
                params: List[Any] = []

                conditions = []
                if category:
                    conditions.append("category = %s")
                    params.append(category)
                if key:
                    conditions.append("setting_key = %s")
                    params.append(key)

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                query += " ORDER BY changed_at DESC LIMIT %s"
                params.append(limit)

                cursor.execute(query, params)
                return [ConfigurationHistory.from_row(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting configuration history: {e}")
            return []

    def refresh_cache(self):
        """Refresh the configuration cache from database"""
        self._load_cache()

    def get_categories(self) -> List[str]:
        """Get all unique configuration categories"""
        categories = set()
        for config in self._cache.values():
            categories.add(config.category)
        return sorted(list(categories))

    def export_to_dict(
        self, include_sensitive: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """Export all configuration as nested dictionary"""
        result: Dict[str, Dict[str, Any]] = {}
        for config in self._cache.values():
            if not include_sensitive and config.is_sensitive:
                continue

            if config.category not in result:
                result[config.category] = {}

            result[config.category][config.setting_key] = {
                "value": config.get_typed_value(),
                "type": config.data_type,
                "description": config.description,
                "default": config.default_value,
            }
        return result


# Singleton instance
_config_service: Optional[ConfigurationService] = None


def get_config_service(db_connection=None) -> Optional[ConfigurationService]:
    """Get or create configuration service instance"""
    global _config_service
    if _config_service is None and db_connection is not None:
        _config_service = ConfigurationService(db_connection)
    return _config_service


def config_get(category: str, key: str, default: Any = None) -> Any:
    """Convenience function to get configuration value"""
    service = get_config_service()
    if service:
        return service.get(category, key, default)
    # Fall back to environment variable
    env_key = f"{category.upper()}_{key.upper()}"
    return os.getenv(env_key, default)
