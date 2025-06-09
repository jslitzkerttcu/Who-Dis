"""Error handling middleware and decorators."""

from functools import wraps
from flask import jsonify, request, current_app
import traceback


def handle_errors(json_response=False):
    """
    Decorator to handle errors in route functions.

    Args:
        json_response (bool): If True, always return JSON responses on error.
                             If False, return HTML/text for regular requests.
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                # Log the error
                current_app.logger.error(
                    f"Error in {f.__name__}: {str(e)}", exc_info=True
                )

                # Log to audit service
                try:
                    from app.services.audit_service_postgres import audit_service

                    user_email = request.headers.get(
                        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user
                    )
                    user_role = getattr(request, "user_role", None)
                    user_ip = request.headers.get(
                        "X-Forwarded-For", request.remote_addr
                    )

                    audit_service.log_error(
                        error_type=type(e).__name__,
                        error_message=str(e),
                        stack_trace=traceback.format_exc(),
                        user_email=user_email,
                        user_role=user_role,
                        ip_address=user_ip,
                        request_path=request.path,
                        request_method=request.method,
                        user_agent=request.headers.get("User-Agent"),
                        additional_data={
                            "url": request.url,
                            "function": f.__name__,
                            "args": dict(request.args),
                            "form": dict(request.form) if request.form else None,
                        },
                    )
                except Exception as log_error:
                    current_app.logger.error(
                        f"Failed to log error to audit: {log_error}"
                    )

                # Return appropriate error response
                if json_response or request.is_json or request.path.startswith("/api/"):
                    return jsonify(
                        {
                            "success": False,
                            "error": "An internal error occurred",
                            "message": str(e)
                            if current_app.debug
                            else "An internal error occurred",
                        }
                    ), 500
                else:
                    error_msg = (
                        f"Error: {str(e)}"
                        if current_app.debug
                        else "An internal error occurred"
                    )
                    return error_msg, 500

        return decorated_function

    return decorator
