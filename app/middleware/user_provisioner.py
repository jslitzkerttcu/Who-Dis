from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User


class UserProvisioner:
    """Handles user creation and management"""

    def get_or_create_user(self, email: str, role: str) -> "User":
        """
        Get existing user or create new one

        Args:
            email: User's email address
            role: User's role

        Returns:
            User object
        """
        from app.models.user import User

        # Try to get existing user
        user = User.get_by_email(email)
        if user:
            return user

        # Create new user
        return self.create_user(email, role)

    def create_user(
        self, email: str, role: str, created_by: str = "auth_system"
    ) -> "User":
        """
        Create new user record

        Args:
            email: User's email address
            role: User's role
            created_by: Who created the user

        Returns:
            New User object
        """
        from app.models.user import User

        return User.create_user(email=email, role=role, created_by=created_by)

    def update_user_login(self, user: "User") -> None:
        """Update user's last login timestamp"""
        user.update_last_login()

    def get_user_by_email(self, email: str) -> Optional["User"]:
        """Get user by email address"""
        from app.models.user import User

        return User.get_by_email(email)
