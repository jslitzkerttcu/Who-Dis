import os
from typing import Optional, Tuple, List


class RoleResolver:
    """Handles role determination and validation"""

    ROLE_HIERARCHY = {"viewer": 1, "editor": 2, "admin": 3}

    def get_user_role(self, email: str) -> Optional[str]:
        """
        Determine user role based on email

        Args:
            email: User's email address

        Returns:
            str: User role (viewer, editor, admin) or None if no access
        """
        try:
            from app.models import User

            # Try database first
            user = User.get_by_email(email)
            if user:
                # Update last login
                user.update_last_login()
                return str(user.role)
        except Exception:
            # Database not available, fall back to env
            pass

        # Fallback to environment variables/configuration
        viewers, editors, admins = self._load_role_lists()

        if email in admins:
            return "admin"
        elif email in editors:
            return "editor"
        elif email in viewers:
            return "viewer"
        else:
            return None

    def has_minimum_role(self, user_role: str, minimum_role: str) -> bool:
        """
        Check if user has minimum required role

        Args:
            user_role: User's current role
            minimum_role: Minimum required role

        Returns:
            bool: True if user has sufficient role
        """
        if user_role not in self.ROLE_HIERARCHY:
            return False

        user_level = self.ROLE_HIERARCHY.get(user_role, 0)
        required_level = self.ROLE_HIERARCHY.get(minimum_role, 0)

        return user_level >= required_level

    def is_valid_role(self, role: str) -> bool:
        """Check if role is valid"""
        return role in self.ROLE_HIERARCHY

    def _load_role_lists(self) -> Tuple[List[str], List[str], List[str]]:
        """Load role lists from database (fallback to env for migration)"""
        try:
            from app.models import User

            # Use targeted queries to avoid loading all users into memory
            viewers = [
                email[0]
                for email in User.query.filter_by(is_active=True, role=User.ROLE_VIEWER)
                .with_entities(User.email)
                .all()
            ]
            editors = [
                email[0]
                for email in User.query.filter_by(is_active=True, role=User.ROLE_EDITOR)
                .with_entities(User.email)
                .all()
            ]
            admins = [
                email[0]
                for email in User.query.filter_by(is_active=True, role=User.ROLE_ADMIN)
                .with_entities(User.email)
                .all()
            ]

            if viewers or editors or admins:
                return viewers, editors, admins
        except Exception:
            # Database not available or table doesn't exist yet
            pass

        # Try configuration service (encrypted values)
        try:
            from app.services.configuration_service import config_get

            viewers_str = config_get("auth.viewers", "")
            editors_str = config_get("auth.editors", "")
            admins_str = config_get("auth.admins", "")

            if viewers_str or editors_str or admins_str:
                viewers = [
                    email.strip() for email in viewers_str.split(",") if email.strip()
                ]
                editors = [
                    email.strip() for email in editors_str.split(",") if email.strip()
                ]
                admins = [
                    email.strip() for email in admins_str.split(",") if email.strip()
                ]
                return viewers, editors, admins
        except Exception:
            pass

        # Fallback to environment variables
        viewers = os.getenv("VIEWERS", "").split(",")
        editors = os.getenv("EDITORS", "").split(",")
        admins = os.getenv("ADMINS", "").split(",")

        viewers = [email.strip() for email in viewers if email.strip()]
        editors = [email.strip() for email in editors if email.strip()]
        admins = [email.strip() for email in admins if email.strip()]

        return viewers, editors, admins
