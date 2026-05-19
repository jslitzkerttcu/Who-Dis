"""Write operations coordinator service.

Couples every write action (LDAP unlock/reset/enable, Graph license assign/remove/swap)
with audit logging. Does not enforce auth -- callers (route handlers) must use
@require_role("admin") per T-09-02.
"""

import logging
from typing import Dict, Any

from flask import current_app, g, request

from app.utils.password_generator import generate_temp_password

logger = logging.getLogger(__name__)


class WriteOperationsService:
    """Coordinator for LDAP and Graph write operations with audit trail.

    Resolves dependencies from the DI container on each access to avoid
    stale references across configuration reloads.
    """

    @property
    def ldap_service(self) -> Any:
        return current_app.container.get("ldap_service")  # type: ignore[attr-defined]

    @property
    def graph_service(self) -> Any:
        return current_app.container.get("graph_service")  # type: ignore[attr-defined]

    @property
    def audit_logger(self) -> Any:
        return current_app.container.get("audit_logger")  # type: ignore[attr-defined]

    def _get_request_context(self) -> Dict[str, str]:
        """Extract IP and user-agent from current request for audit."""
        ip_address = request.headers.get(
            "X-Forwarded-For", request.remote_addr or "unknown"
        )
        user_agent = request.headers.get("User-Agent", "unknown")
        return {"ip_address": ip_address, "user_agent": user_agent}

    def unlock_account(
        self, user_dn: str, display_name: str, reason: str
    ) -> Dict[str, Any]:
        """Unlock an AD account and audit the action.

        Args:
            user_dn: Distinguished name of the user account.
            display_name: Human-readable name for audit trail.
            reason: Justification for the action.

        Returns:
            Dict with "success" bool and optional "message"/"error" keys.
        """
        ctx = self._get_request_context()
        try:
            result = self.ldap_service.unlock_account(user_dn)

            self.audit_logger.log_admin_action(
                user_email=g.user,
                action="unlock_account",
                target=user_dn,
                details={
                    "reason": reason,
                    "target_name": display_name,
                    "success": result,
                },
                ip_address=ctx["ip_address"],
                user_agent=ctx["user_agent"],
            )

            if result:
                return {"success": True, "message": f"Account unlocked: {display_name}"}
            return {"success": False, "error": "Unlock operation failed"}

        except Exception as e:
            logger.error(f"Error unlocking account {user_dn}: {str(e)}", exc_info=True)
            self.audit_logger.log_admin_action(
                user_email=g.user,
                action="unlock_account",
                target=user_dn,
                details={
                    "reason": reason,
                    "target_name": display_name,
                    "success": False,
                    "error": str(e),
                },
                ip_address=ctx["ip_address"],
                user_agent=ctx["user_agent"],
            )
            return {"success": False, "error": str(e)}

    def reset_password(
        self, user_dn: str, display_name: str, reason: str
    ) -> Dict[str, Any]:
        """Reset an AD user's password and audit the action.

        Generates a temporary password. The password is NEVER included in audit logs.

        Args:
            user_dn: Distinguished name of the user account.
            display_name: Human-readable name for audit trail.
            reason: Justification for the action.

        Returns:
            Dict with "success" bool, "data.password" on success, "error" on failure.
        """
        ctx = self._get_request_context()
        password = generate_temp_password()

        try:
            result = self.ldap_service.reset_password(user_dn, password)

            # T-09-01: Never log the password in audit details
            self.audit_logger.log_admin_action(
                user_email=g.user,
                action="reset_password",
                target=user_dn,
                details={
                    "reason": reason,
                    "target_name": display_name,
                    "success": result,
                },
                ip_address=ctx["ip_address"],
                user_agent=ctx["user_agent"],
            )

            if result:
                return {"success": True, "data": {"password": password}}
            return {"success": False, "error": "Password reset failed"}

        except Exception as e:
            logger.error(
                f"Error resetting password for {user_dn}: {str(e)}", exc_info=True
            )
            self.audit_logger.log_admin_action(
                user_email=g.user,
                action="reset_password",
                target=user_dn,
                details={
                    "reason": reason,
                    "target_name": display_name,
                    "success": False,
                    "error": str(e),
                },
                ip_address=ctx["ip_address"],
                user_agent=ctx["user_agent"],
            )
            return {"success": False, "error": str(e)}

    def set_account_enabled(
        self, user_dn: str, display_name: str, enabled: bool, reason: str
    ) -> Dict[str, Any]:
        """Enable or disable an AD account and audit the action.

        Args:
            user_dn: Distinguished name of the user account.
            display_name: Human-readable name for audit trail.
            enabled: True to enable, False to disable.
            reason: Justification for the action.

        Returns:
            Dict with "success" bool and optional "message"/"error" keys.
        """
        ctx = self._get_request_context()
        action = "enable_account" if enabled else "disable_account"

        try:
            result = self.ldap_service.set_account_enabled(user_dn, enabled)

            self.audit_logger.log_admin_action(
                user_email=g.user,
                action=action,
                target=user_dn,
                details={
                    "reason": reason,
                    "target_name": display_name,
                    "enabled": enabled,
                    "success": result,
                },
                ip_address=ctx["ip_address"],
                user_agent=ctx["user_agent"],
            )

            if result:
                verb = "enabled" if enabled else "disabled"
                return {"success": True, "message": f"Account {verb}: {display_name}"}
            return {"success": False, "error": f"Failed to {action.replace('_', ' ')}"}

        except Exception as e:
            logger.error(
                f"Error setting account enabled={enabled} for {user_dn}: {str(e)}",
                exc_info=True,
            )
            self.audit_logger.log_admin_action(
                user_email=g.user,
                action=action,
                target=user_dn,
                details={
                    "reason": reason,
                    "target_name": display_name,
                    "enabled": enabled,
                    "success": False,
                    "error": str(e),
                },
                ip_address=ctx["ip_address"],
                user_agent=ctx["user_agent"],
            )
            return {"success": False, "error": str(e)}

    def assign_license(
        self,
        user_id: str,
        user_email: str,
        sku_id: str,
        sku_name: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Assign an M365 license and audit the action.

        Args:
            user_id: Graph user ID.
            user_email: User email for audit target.
            sku_id: SKU GUID to assign.
            sku_name: Friendly SKU name for audit readability.
            reason: Justification for the action.

        Returns:
            Dict with "success" bool and optional "error" key.
        """
        ctx = self._get_request_context()

        try:
            result = self.graph_service.assign_license(user_id, sku_id)

            self.audit_logger.log_admin_action(
                user_email=g.user,
                action="assign_license",
                target=user_email,
                details={
                    "reason": reason,
                    "sku_id": sku_id,
                    "sku_name": sku_name,
                    "success": result.get("success", False),
                },
                ip_address=ctx["ip_address"],
                user_agent=ctx["user_agent"],
            )

            return result  # type: ignore[no-any-return]

        except Exception as e:
            logger.error(
                f"Error assigning license {sku_id} to {user_email}: {str(e)}",
                exc_info=True,
            )
            self.audit_logger.log_admin_action(
                user_email=g.user,
                action="assign_license",
                target=user_email,
                details={
                    "reason": reason,
                    "sku_id": sku_id,
                    "sku_name": sku_name,
                    "success": False,
                    "error": str(e),
                },
                ip_address=ctx["ip_address"],
                user_agent=ctx["user_agent"],
            )
            return {"success": False, "error": str(e)}

    def remove_license(
        self,
        user_id: str,
        user_email: str,
        sku_id: str,
        sku_name: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Remove an M365 license and audit the action.

        Args:
            user_id: Graph user ID.
            user_email: User email for audit target.
            sku_id: SKU GUID to remove.
            sku_name: Friendly SKU name for audit readability.
            reason: Justification for the action.

        Returns:
            Dict with "success" bool and optional "error" key.
        """
        ctx = self._get_request_context()

        try:
            result = self.graph_service.remove_license(user_id, sku_id)

            self.audit_logger.log_admin_action(
                user_email=g.user,
                action="remove_license",
                target=user_email,
                details={
                    "reason": reason,
                    "sku_id": sku_id,
                    "sku_name": sku_name,
                    "success": result.get("success", False),
                },
                ip_address=ctx["ip_address"],
                user_agent=ctx["user_agent"],
            )

            return result  # type: ignore[no-any-return]

        except Exception as e:
            logger.error(
                f"Error removing license {sku_id} from {user_email}: {str(e)}",
                exc_info=True,
            )
            self.audit_logger.log_admin_action(
                user_email=g.user,
                action="remove_license",
                target=user_email,
                details={
                    "reason": reason,
                    "sku_id": sku_id,
                    "sku_name": sku_name,
                    "success": False,
                    "error": str(e),
                },
                ip_address=ctx["ip_address"],
                user_agent=ctx["user_agent"],
            )
            return {"success": False, "error": str(e)}

    def swap_license(
        self,
        user_id: str,
        user_email: str,
        old_sku_id: str,
        old_sku_name: str,
        new_sku_id: str,
        new_sku_name: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Swap one M365 license for another and audit the action.

        On double failure (remove succeeds, assign fails, rollback fails),
        logs at ERROR level with MANUAL_INTERVENTION_REQUIRED marker.

        Args:
            user_id: Graph user ID.
            user_email: User email for audit target.
            old_sku_id: SKU GUID to remove.
            old_sku_name: Friendly name of old SKU.
            new_sku_id: SKU GUID to assign.
            new_sku_name: Friendly name of new SKU.
            reason: Justification for the action.

        Returns:
            Dict with "success" bool and swap state details.
        """
        ctx = self._get_request_context()

        try:
            result = self.graph_service.swap_license(user_id, old_sku_id, new_sku_id)

            # D-09: Log full state for manual recovery on double failure
            if result.get("rollback_needed") and not result.get("rollback_success"):
                logger.error(
                    f"MANUAL_INTERVENTION_REQUIRED: License swap double failure "
                    f"for {user_email} (user_id={user_id}). "
                    f"Old SKU: {old_sku_id} ({old_sku_name}), "
                    f"New SKU: {new_sku_id} ({new_sku_name})"
                )

            self.audit_logger.log_admin_action(
                user_email=g.user,
                action="swap_license",
                target=user_email,
                details={
                    "reason": reason,
                    "old_sku_id": old_sku_id,
                    "old_sku_name": old_sku_name,
                    "new_sku_id": new_sku_id,
                    "new_sku_name": new_sku_name,
                    "success": result.get("success", False),
                    "rollback_needed": result.get("rollback_needed", False),
                    "rollback_success": result.get("rollback_success"),
                },
                ip_address=ctx["ip_address"],
                user_agent=ctx["user_agent"],
            )

            return result  # type: ignore[no-any-return]

        except Exception as e:
            logger.error(
                f"Error swapping license for {user_email}: {str(e)}",
                exc_info=True,
            )
            self.audit_logger.log_admin_action(
                user_email=g.user,
                action="swap_license",
                target=user_email,
                details={
                    "reason": reason,
                    "old_sku_id": old_sku_id,
                    "old_sku_name": old_sku_name,
                    "new_sku_id": new_sku_id,
                    "new_sku_name": new_sku_name,
                    "success": False,
                    "error": str(e),
                },
                ip_address=ctx["ip_address"],
                user_agent=ctx["user_agent"],
            )
            return {"success": False, "error": str(e)}
