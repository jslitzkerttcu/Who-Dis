"""Employee profiles consolidated model."""

from typing import Optional, Dict, Any, List
from app.database import db
from sqlalchemy import func, Index
from sqlalchemy.dialects.postgresql import JSONB


class EmployeeProfiles(db.Model):  # type: ignore
    """Consolidated employee profiles table."""

    __tablename__ = "employee_profiles"

    # Primary key
    upn = db.Column(db.String(255), primary_key=True)

    # Keystone fields
    ks_user_serial = db.Column(db.Integer)
    ks_last_login_time = db.Column(db.DateTime(timezone=True))
    ks_login_lock = db.Column(db.String(1))

    # Role fields
    live_role = db.Column(db.String(255))
    test_role = db.Column(db.String(255))
    keystone_expected_role = db.Column(db.String(255))

    # UKG field
    ukg_job_code = db.Column(db.String(50))

    # Photo fields
    photo_data = db.Column(db.LargeBinary)  # BYTEA for binary photo data
    photo_content_type = db.Column(db.String(50), default="image/jpeg")

    # Raw data storage
    raw_data = db.Column(JSONB)

    # Timestamp fields
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=func.now()
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
    )

    # Indexes
    __table_args__ = (
        Index("idx_employee_profiles_ks_login_lock", "ks_login_lock"),
        Index("idx_employee_profiles_live_role", "live_role"),
        Index("idx_employee_profiles_upn", "upn"),
        Index("idx_employee_profiles_keystone_expected_role", "keystone_expected_role"),
    )

    def __repr__(self):
        return f"<EmployeeProfiles {self.upn}>"

    @classmethod
    def get_by_upn(cls, upn: str) -> Optional["EmployeeProfiles"]:
        """Get employee profile by UPN."""
        return cls.query.filter_by(upn=upn).first()

    @classmethod
    def create_or_update_profile(
        cls, upn: str, profile_data: Dict[str, Any]
    ) -> "EmployeeProfiles":
        """
        Create or update employee profile.

        Args:
            upn: The UPN to create/update profile for
            profile_data: Dictionary containing profile data

        Returns:
            The created/updated profile record
        """
        try:
            profile = cls.query.filter_by(upn=upn).first()
            if not profile:
                profile = cls(upn=upn)
                db.session.add(profile)

            # Update fields from profile data
            profile.ks_user_serial = profile_data.get("ks_user_serial")
            profile.ks_last_login_time = profile_data.get("ks_last_login_time")
            profile.ks_login_lock = profile_data.get("ks_login_lock")
            profile.live_role = profile_data.get("live_role")
            profile.test_role = profile_data.get("test_role")
            profile.ukg_job_code = profile_data.get("ukg_job_code")
            profile.keystone_expected_role = profile_data.get("keystone_expected_role")
            profile.photo_data = profile_data.get("photo_data")
            profile.photo_content_type = profile_data.get(
                "photo_content_type", "image/jpeg"
            )
            profile.raw_data = profile_data.get("raw_data")

            db.session.commit()
            return profile
        except Exception as e:
            db.session.rollback()
            raise e

    @classmethod
    def get_profiles_by_role(cls, role: str) -> List["EmployeeProfiles"]:
        """Get all profiles with specified live role."""
        return cls.query.filter_by(live_role=role).all()

    @classmethod
    def get_locked_profiles(cls) -> List["EmployeeProfiles"]:
        """Get all locked employee profiles."""
        return cls.query.filter_by(ks_login_lock="L").all()

    def update_photo(self, photo_data: bytes, content_type: str = "image/jpeg"):
        """Update employee photo."""
        self.photo_data = photo_data
        self.photo_content_type = content_type
        db.session.commit()

    def clear_photo(self):
        """Clear employee photo."""
        self.photo_data = None
        self.photo_content_type = "image/jpeg"
        db.session.commit()

    def to_dict(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Convert to dictionary for API response.

        Args:
            exclude: List of fields to exclude

        Returns:
            Dictionary representation
        """
        exclude = exclude or []

        data = {
            "upn": self.upn,
            "ks_user_serial": self.ks_user_serial,
            "ks_last_login_time": self.ks_last_login_time.isoformat()
            if self.ks_last_login_time
            else None,
            "ks_login_lock": self.ks_login_lock,
            "live_role": self.live_role,
            "test_role": self.test_role,
            "ukg_job_code": self.ukg_job_code,
            "keystone_expected_role": self.keystone_expected_role,
            "photo_content_type": self.photo_content_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "raw_data": self.raw_data,
        }

        # Exclude photo_data by default (too large for typical API responses)
        if "photo_data" not in exclude:
            exclude.append("photo_data")

        return {k: v for k, v in data.items() if k not in exclude}

    def has_photo(self) -> bool:
        """Check if profile has photo data."""
        return self.photo_data is not None

    def is_account_locked(self) -> bool:
        """Check if account is locked."""
        return self.ks_login_lock == "L"

    def get_display_info(self) -> Dict[str, Any]:
        """Get formatted profile information for display."""
        return {
            "upn": self.upn,
            "user_serial": self.ks_user_serial,
            "last_login": self.ks_last_login_time.isoformat()
            if self.ks_last_login_time
            else None,
            "is_locked": self.is_account_locked(),
            "lock_status": "Locked" if self.is_account_locked() else "Unlocked",
            "live_role": self.live_role,
            "test_role": self.test_role,
            "job_code": self.ukg_job_code,
            "expected_role": self.keystone_expected_role,
            "has_photo": self.has_photo(),
            "last_updated": self.updated_at.isoformat() if self.updated_at else None,
        }
