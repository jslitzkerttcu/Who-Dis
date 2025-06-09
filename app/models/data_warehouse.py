"""Data warehouse cache models."""

from typing import Optional, Dict, Any
from datetime import datetime, timezone
from app.database import db
from sqlalchemy.dialects.postgresql import JSONB
from .base import CacheableModel


class DataWarehouseCache(CacheableModel):
    """Cached data warehouse user records."""

    __tablename__ = "data_warehouse_cache"

    # UPN is unique but not primary key (id from BaseModel is primary key)
    upn = db.Column(db.String(100), unique=True, nullable=False, index=True)

    # Core Keystone data fields
    ks_user_serial = db.Column(db.String(50))
    ks_last_login_time = db.Column(db.DateTime(timezone=True))
    ks_login_lock = db.Column(db.String(1))  # Store as 'L' or 'N'
    live_role = db.Column(db.String(255))
    test_role = db.Column(db.String(255))
    ukg_job_code = db.Column(db.String(20))
    keystone_expected_role = db.Column(db.String(255))

    # Store complete raw data from query
    raw_data = db.Column(JSONB)

    def __repr__(self):
        return f"<DataWarehouseCache {self.upn}>"

    @classmethod
    def cache_user_data(
        cls, upn: str, user_data: Dict[str, Any]
    ) -> "DataWarehouseCache":
        """
        Cache user data from the data warehouse.

        Args:
            upn: The UPN to cache data for
            user_data: Dictionary containing user data from query

        Returns:
            The cached record
        """
        # Check if record exists
        record = cls.query.filter_by(upn=upn).first()
        if not record:
            record = cls(upn=upn)
            db.session.add(record)

        # Update fields
        record.ks_user_serial = user_data.get("KS_User_Serial")
        record.ks_last_login_time = user_data.get("KS_Last_Login_Time")
        record.ks_login_lock = user_data.get("KS_Login_Lock")
        record.live_role = user_data.get("Live_Role")
        record.test_role = user_data.get("Test_Role")
        record.ukg_job_code = user_data.get("UKG_Job_Code")
        record.keystone_expected_role = user_data.get(
            "Keystone_Expected_Role_For_Job_Title"
        )
        record.raw_data = user_data

        # Update cache timestamp
        record.updated_at = datetime.now(timezone.utc)
        record.expires_at = None  # No expiration for this cache

        db.session.commit()
        return record

    @classmethod
    def get_user_data(cls, upn: str) -> Optional["DataWarehouseCache"]:
        """
        Get cached user data by UPN.

        Args:
            upn: The UPN to look up

        Returns:
            Cached record or None if not found
        """
        return cls.query.filter_by(upn=upn).first()

    @classmethod
    def clear_cache(cls) -> int:
        """
        Clear all cached data.

        Returns:
            Number of records deleted
        """
        count = cls.query.count()
        cls.query.delete()
        db.session.commit()
        return count

    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_records = cls.query.count()

        # Get the most recent update time
        latest_record = cls.query.order_by(cls.updated_at.desc()).first()
        last_updated = latest_record.updated_at if latest_record else None

        return {"total_records": total_records, "last_updated": last_updated}

    def to_dict(self, exclude: Optional[list] = None) -> Dict[str, Any]:
        """
        Convert to dictionary for API response.

        Args:
            exclude: List of fields to exclude

        Returns:
            Dictionary representation
        """
        # Use base class to_dict and add custom formatting
        data = super().to_dict(exclude)

        # Add formatted fields for UI display
        formatted_data = {
            "upn": data.get("upn"),
            "ks_user_serial": data.get("ks_user_serial"),
            "ks_last_login_time": data.get("ks_last_login_time"),
            "ks_login_lock": data.get("ks_login_lock"),
            "live_role": data.get("live_role"),
            "test_role": data.get("test_role"),
            "ukg_job_code": data.get("ukg_job_code"),
            "keystone_expected_role": data.get("keystone_expected_role"),
            "last_cached": data.get("updated_at"),
            "raw_data": data.get("raw_data"),
        }

        return formatted_data

    def get_keystone_info(self) -> Dict[str, Any]:
        """
        Get formatted Keystone information for search results.

        Returns:
            Dictionary with Keystone info formatted for display
        """
        # Determine lock status
        is_locked = self.ks_login_lock == "L" if self.ks_login_lock else False
        lock_status = "Locked" if is_locked else "Unlocked"

        # Determine role mismatch status
        role_mismatch = None
        role_warning_level = None

        if self.live_role:  # User has a live role in Keystone
            if self.keystone_expected_role:
                # We have both live role and expected role - check if they match
                if self.live_role != self.keystone_expected_role:
                    role_mismatch = f"Live Role '{self.live_role}' does not match Expected Role '{self.keystone_expected_role}' based on job code mapping"
                    role_warning_level = "high"  # Security concern - wrong permissions
                else:
                    # Roles match - this is good!
                    role_mismatch = f"Live Role '{self.live_role}' correctly matches Expected Role based on job code mapping"
                    role_warning_level = "success"  # Positive indicator
            else:
                # User has live role but their job code has no expected role mapping
                job_code_text = f" ({self.ukg_job_code})" if self.ukg_job_code else ""
                role_mismatch = f"Job Code{job_code_text} has no expected role mapping - unable to verify if Live Role '{self.live_role}' assignment is correct"
                role_warning_level = "medium"  # Audit concern - need to add job code mapping
        elif self.keystone_expected_role:
            # User should have a role based on job code but doesn't have one assigned
            role_mismatch = f"User should have '{self.keystone_expected_role}' role based on job code but has no Live Role assigned"
            role_warning_level = "high"  # Security concern - missing required access

        return {
            "service": "keystone",
            "upn": self.upn,
            "user_serial": self.ks_user_serial,
            "last_login": self.ks_last_login_time.isoformat()
            if self.ks_last_login_time
            else None,
            "last_login_formatted": self._format_datetime(self.ks_last_login_time),
            "login_locked": is_locked,
            "lock_status": lock_status,
            "live_role": self.live_role,
            "test_role": self.test_role,
            "ukg_job_code": self.ukg_job_code,
            "expected_role": self.keystone_expected_role,
            "role_mismatch": role_mismatch,
            "role_warning_level": role_warning_level,
            "last_cached": self.updated_at.isoformat() if self.updated_at else None,
        }

    def _format_datetime(self, dt) -> Optional[str]:
        """Format datetime for display."""
        if not dt:
            return None

        # Format as M/D/YYYY H:MM AM/PM
        return dt.strftime("%m/%d/%Y %I:%M %p")
