from functools import wraps
from flask import jsonify, render_template, request
from sqlalchemy.exc import SQLAlchemyError
import traceback
from typing import Callable, Any, Optional, Dict
import logging


logger = logging.getLogger(__name__)


def handle_errors(
    func: Optional[Callable] = None,
    *,
    json_response: bool = False,
    log_errors: bool = True,
    audit_errors: bool = True,
    error_template: str = "nope.html",
    default_error_message: str = "An unexpected error occurred",
) -> Callable:
    """
    Decorator for standardized error handling across routes and services.

    Args:
        func: The function to decorate (automatically passed when used without parentheses)
        json_response: Return JSON error responses instead of HTML
        log_errors: Whether to log errors to the database
        audit_errors: Whether to create audit log entries for errors
        error_template: Template to render for HTML error responses
        default_error_message: Default message for unexpected errors

    Usage:
        @handle_errors  # Uses defaults
        @handle_errors(json_response=True)  # For API endpoints
        @handle_errors(error_template="admin/error.html")  # Custom error page
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return f(*args, **kwargs)
            except Exception as e:
                error_id = None
                user_email = None

                # Extract user information if available
                try:
                    if hasattr(request, "user_email"):
                        user_email = request.user_email
                    elif "X-MS-CLIENT-PRINCIPAL-NAME" in request.headers:
                        user_email = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
                except Exception:
                    pass

                # Log to application logger
                logger.error(f"Error in {f.__name__}: {str(e)}", exc_info=True)

                # Log to database if enabled
                if log_errors:
                    try:
                        from app.models import ErrorLog
                        from app.utils.ip_utils import format_ip_info

                        error_entry = ErrorLog.log_error(
                            user_email=user_email or "system",
                            error_type=type(e).__name__,
                            error_message=str(e),
                            stack_trace=traceback.format_exc(),
                            request_path=request.endpoint or f.__name__,
                            request_method=request.method
                            if hasattr(request, "method")
                            else "N/A",
                            request_data=_safe_request_data(),
                            ip_address=format_ip_info(),
                            user_agent=request.headers.get("User-Agent"),
                        )
                        error_id = error_entry.id
                    except Exception as log_error:
                        logger.error(f"Failed to log error to database: {log_error}")

                # Create audit log entry if enabled
                if audit_errors and user_email:
                    try:
                        from app.services.audit_service_postgres import (
                            PostgresAuditService,
                        )
                        from app.utils.ip_utils import format_ip_info

                        audit_service = PostgresAuditService()
                        audit_service.log_error(
                            user_email=user_email,
                            error_type=type(e).__name__,
                            error_message=str(e),
                            request_path=request.endpoint or f.__name__,
                            stack_trace=traceback.format_exc()[:1000],  # Limit length
                            ip_address=format_ip_info(),
                            user_agent=request.headers.get("User-Agent"),
                        )
                    except Exception as audit_error:
                        logger.error(f"Failed to create audit log: {audit_error}")

                # Determine error message and status code
                status_code = 500
                error_message = default_error_message

                if isinstance(e, ValueError):
                    status_code = 400
                    error_message = str(e) or "Invalid request data"
                elif isinstance(e, PermissionError):
                    status_code = 403
                    error_message = str(e) or "Access denied"
                elif isinstance(e, FileNotFoundError):
                    status_code = 404
                    error_message = str(e) or "Resource not found"
                elif isinstance(e, SQLAlchemyError):
                    error_message = "Database error occurred"
                elif hasattr(e, "message"):
                    error_message = e.message
                elif str(e):
                    error_message = str(e)

                # Return appropriate response
                if json_response:
                    return jsonify(
                        {
                            "error": error_message,
                            "error_type": type(e).__name__,
                            "error_id": error_id,
                            "status": "error",
                        }
                    ), status_code
                else:
                    # For HTML responses, check if request expects JSON
                    if request.headers.get("Accept", "").startswith("application/json"):
                        return jsonify(
                            {
                                "error": error_message,
                                "error_type": type(e).__name__,
                                "error_id": error_id,
                                "status": "error",
                            }
                        ), status_code

                    return render_template(
                        error_template,
                        error_message=error_message,
                        error_id=error_id,
                        status_code=status_code,
                    ), status_code

        return wrapper

    # Handle both @handle_errors and @handle_errors() syntax
    if func is None:
        return decorator
    else:
        return decorator(func)


def handle_service_errors(
    func: Optional[Callable] = None,
    *,
    service_name: Optional[str] = None,
    raise_errors: bool = True,
    default_return: Any = None,
) -> Callable:
    """
    Decorator for error handling in service methods.

    Args:
        func: The function to decorate
        service_name: Name of the service for logging
        raise_errors: Whether to re-raise errors after logging
        default_return: Value to return on error if not raising

    Usage:
        @handle_service_errors  # Re-raises errors after logging
        @handle_service_errors(raise_errors=False, default_return={})  # Returns {} on error
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return f(*args, **kwargs)
            except Exception as e:
                service = service_name or (
                    args[0].__class__.__name__ if args else "UnknownService"
                )
                logger.error(
                    f"Error in {service}.{f.__name__}: {str(e)}", exc_info=True
                )

                # Log to database
                try:
                    from app.models import ErrorLog

                    ErrorLog.log_error(
                        user_email="system",
                        error_type=type(e).__name__,
                        error_message=str(e),
                        stack_trace=traceback.format_exc(),
                        request_path=f"{service}.{f.__name__}",
                        request_method="SERVICE",
                    )
                except Exception as log_error:
                    logger.error(f"Failed to log service error: {log_error}")

                if raise_errors:
                    raise
                return default_return

        return wrapper

    if func is None:
        return decorator
    else:
        return decorator(func)


def _safe_request_data() -> Optional[Dict[str, Any]]:
    """Safely extract request data for error logging."""
    try:
        from app.utils.ip_utils import get_all_ips

        # Get comprehensive IP information
        ip_info = get_all_ips()

        data = {
            "url": request.url,
            "method": request.method,
            "headers": dict(request.headers),
            "remote_addr": request.remote_addr,
            "ip_info": ip_info,  # Add detailed IP information
        }

        # Remove sensitive headers
        sensitive_headers = ["Authorization", "Cookie", "X-MS-CLIENT-PRINCIPAL-NAME"]
        headers_dict = data["headers"]
        if isinstance(headers_dict, dict):
            for header in sensitive_headers:
                if header in headers_dict:
                    headers_dict[header] = "[REDACTED]"

        # Add form/json data if present
        if request.form:
            form_data = dict(request.form)
            data["form"] = form_data
            # Redact password fields
            for key in list(form_data.keys()):
                if "password" in key.lower() or "secret" in key.lower():
                    form_data[key] = "[REDACTED]"

        if request.is_json:
            try:
                json_data = request.get_json()
                if json_data and isinstance(json_data, dict):
                    data["json"] = json_data
                    # Redact sensitive fields
                    for key in list(json_data.keys()):
                        if "password" in key.lower() or "secret" in key.lower():
                            json_data[key] = "[REDACTED]"
            except Exception:
                pass

        return data
    except Exception:
        return None
