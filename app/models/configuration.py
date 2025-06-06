from datetime import datetime
from typing import Any, Dict, Optional, Union


class Configuration:
    def __init__(
        self,
        id: Optional[int] = None,
        category: str = None,
        setting_key: str = None,
        setting_value: str = None,
        data_type: str = "string",
        description: str = None,
        is_sensitive: bool = False,
        validation_regex: str = None,
        min_value: float = None,
        max_value: float = None,
        default_value: str = None,
        created_at: datetime = None,
        updated_at: datetime = None,
        updated_by: str = None,
        encrypted_value: bytes = None,
    ):
        self.id = id
        self.category = category
        self.setting_key = setting_key
        self.setting_value = setting_value
        self.data_type = data_type
        self.description = description
        self.is_sensitive = is_sensitive
        self.validation_regex = validation_regex
        self.min_value = min_value
        self.max_value = max_value
        self.default_value = default_value
        self.created_at = created_at
        self.updated_at = updated_at
        self.updated_by = updated_by
        self.encrypted_value = encrypted_value

    def get_typed_value(self) -> Union[str, int, float, bool, None]:
        """Convert setting_value to appropriate type based on data_type"""
        if self.setting_value is None:
            if self.default_value is None:
                return None
            return self.default_value

        value = self.setting_value

        try:
            if self.data_type == "integer":
                return int(value)
            elif self.data_type == "float":
                return float(value)
            elif self.data_type == "boolean":
                return value.lower() in ("true", "1", "yes", "on")
            else:
                return value
        except (ValueError, AttributeError):
            if self.default_value is None:
                return None
            return self.default_value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "category": self.category,
            "setting_key": self.setting_key,
            "setting_value": self.setting_value if not self.is_sensitive else "***",
            "data_type": self.data_type,
            "description": self.description,
            "is_sensitive": self.is_sensitive,
            "validation_regex": self.validation_regex,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "default_value": self.default_value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "updated_by": self.updated_by,
        }

    @classmethod
    def from_row(cls, row) -> "Configuration":
        """Create Configuration instance from database row"""
        return cls(
            id=row[0],
            category=row[1],
            setting_key=row[2],
            setting_value=row[3],
            data_type=row[4],
            description=row[5],
            is_sensitive=row[6],
            validation_regex=row[7],
            min_value=row[8],
            max_value=row[9],
            default_value=row[10],
            created_at=row[11],
            updated_at=row[12],
            updated_by=row[13],
            encrypted_value=row[14] if len(row) > 14 else None,
        )


class ConfigurationHistory:
    def __init__(
        self,
        id: Optional[int] = None,
        config_id: int = None,
        category: str = None,
        setting_key: str = None,
        old_value: str = None,
        new_value: str = None,
        changed_at: datetime = None,
        changed_by: str = None,
        change_reason: str = None,
    ):
        self.id = id
        self.config_id = config_id
        self.category = category
        self.setting_key = setting_key
        self.old_value = old_value
        self.new_value = new_value
        self.changed_at = changed_at
        self.changed_by = changed_by
        self.change_reason = change_reason

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "config_id": self.config_id,
            "category": self.category,
            "setting_key": self.setting_key,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "changed_at": self.changed_at.isoformat() if self.changed_at else None,
            "changed_by": self.changed_by,
            "change_reason": self.change_reason,
        }

    @classmethod
    def from_row(cls, row) -> "ConfigurationHistory":
        """Create ConfigurationHistory instance from database row"""
        return cls(
            id=row[0],
            config_id=row[1],
            category=row[2],
            setting_key=row[3],
            old_value=row[4],
            new_value=row[5],
            changed_at=row[6],
            changed_by=row[7],
            change_reason=row[8] if len(row) > 8 else None,
        )
