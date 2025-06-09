"""
Cache management functionality for admin blueprint.
Handles search cache, Genesys cache operations, and cache status monitoring.
"""

from flask import jsonify, request, current_app
from app.middleware.auth import require_role
from app.database import db
from app.services.genesys_cache_db import genesys_cache_db as genesys_cache


@require_role("admin")
def cache_status():
    """Get Genesys cache status."""
    status = genesys_cache.get_cache_status()

    # Add token expiry info for backward compatibility
    from app.models import ApiToken

    token = ApiToken.get_token("genesys")
    if token:
        status["token_expires_at"] = token.expires_at.isoformat()

    return jsonify(status)


@require_role("admin")
def search_cache_status():
    """Get search cache statistics."""
    from app.models import SearchCache

    try:
        entry_count = SearchCache.query.count()
        return jsonify({"entry_count": entry_count, "status": "active"})
    except Exception as e:
        return jsonify({"entry_count": 0, "status": "error", "error": str(e)})


@require_role("admin")
def clear_caches():
    """Clear all caches."""
    from app.models import SearchCache
    from app.services.audit_service_postgres import audit_service

    try:
        # Clear search cache
        SearchCache.query.delete()
        db.session.commit()

        # Clear Genesys cache
        genesys_cache.clear()

        # Log action
        admin_email = request.headers.get(
            "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
        )
        admin_role = getattr(request, "user_role", None)
        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        audit_service.log_admin_action(
            user_email=admin_email,
            action="clear_caches",
            target="all_caches",
            user_role=admin_role,
            ip_address=user_ip,
            user_agent=request.headers.get("User-Agent"),
            success=True,
            details={"caches_cleared": ["search", "genesys"]},
        )

        return jsonify({"success": True, "message": "All caches cleared successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@require_role("admin")
def genesys_cache_status():
    """Get detailed Genesys cache status."""
    return jsonify(genesys_cache.get_cache_status())


@require_role("admin")
def genesys_cache_config():
    """Get or update Genesys cache configuration."""
    from app.services.configuration_service import config_get
    from app.services.audit_service_postgres import audit_service

    if request.method == "GET":
        # Get current configuration
        refresh_period = int(config_get("genesys.cache_refresh_period", 21600))
        return jsonify(
            {
                "refresh_period_seconds": refresh_period,
                "refresh_period_hours": refresh_period / 3600,
            }
        )

    else:  # POST
        try:
            # Get new refresh period in hours
            hours = float(request.json.get("refresh_period_hours", 6))
            seconds = int(hours * 3600)

            # Update configuration
            config_service = current_app.config.get("CONFIG_SERVICE")
            if config_service:
                # Get admin email for updated_by
                admin_email = request.headers.get(
                    "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
                )
                config_service.set(
                    "genesys", "cache_refresh_period", seconds, updated_by=admin_email
                )

                # Log action
                admin_email = request.headers.get(
                    "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
                )
                admin_role = getattr(request, "user_role", None)
                user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

                audit_service.log_admin_action(
                    user_email=admin_email,
                    action="update_genesys_cache_config",
                    target="configuration",
                    user_role=admin_role,
                    ip_address=user_ip,
                    user_agent=request.headers.get("User-Agent"),
                    success=True,
                    details={
                        "setting": "cache_refresh_period",
                        "old_value": config_get(
                            "genesys", "cache_refresh_period", 21600
                        ),
                        "new_value": seconds,
                        "hours": hours,
                    },
                )

                return jsonify(
                    {
                        "success": True,
                        "message": f"Cache refresh period updated to {hours} hours",
                    }
                )
            else:
                return jsonify(
                    {"success": False, "message": "Configuration service not available"}
                ), 500

        except Exception as e:
            return jsonify(
                {
                    "success": False,
                    "message": f"Failed to update configuration: {str(e)}",
                }
            ), 500


@require_role("admin")
def get_genesys_cache_status():
    """Get Genesys cache status."""
    try:
        status = genesys_cache.get_cache_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@require_role("admin")
def refresh_genesys_cache():
    """Manually refresh Genesys cache."""
    try:
        cache_type = request.json.get("type", "all")

        if cache_type == "all":
            results = genesys_cache.refresh_all()
        elif cache_type == "locations":
            results = {"locations": genesys_cache.refresh_locations()}
        elif cache_type == "groups":
            results = {"groups": genesys_cache.refresh_groups()}
        elif cache_type == "skills":
            results = {"skills": genesys_cache.refresh_skills()}
        else:
            return jsonify({"error": "Invalid cache type"}), 400

        return jsonify({"success": True, "results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@require_role("admin")
def data_warehouse_cache_status():
    """Get data warehouse cache status."""
    try:
        # Get data warehouse service from container
        data_warehouse_service = current_app.container.get("data_warehouse_service")
        
        status = data_warehouse_service.get_cache_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@require_role("admin")
def refresh_data_warehouse_cache():
    """Manually refresh data warehouse cache."""
    from app.services.audit_service_postgres import audit_service
    
    try:
        # Get data warehouse service from container
        data_warehouse_service = current_app.container.get("data_warehouse_service")
        
        # Execute cache refresh
        results = data_warehouse_service.refresh_cache()
        
        # Log action
        admin_email = request.headers.get(
            "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
        )
        admin_role = getattr(request, "user_role", None)
        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        audit_service.log_admin_action(
            user_email=admin_email,
            action="refresh_data_warehouse_cache",
            target="data_warehouse_cache",
            user_role=admin_role,
            ip_address=user_ip,
            user_agent=request.headers.get("User-Agent"),
            success=True,
            details=results,
        )
        
        return jsonify({"success": True, "results": results})
    except Exception as e:
        # Log failed action
        try:
            admin_email = request.headers.get(
                "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
            )
            admin_role = getattr(request, "user_role", None)
            user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

            audit_service.log_admin_action(
                user_email=admin_email,
                action="refresh_data_warehouse_cache",
                target="data_warehouse_cache",
                user_role=admin_role,
                ip_address=user_ip,
                user_agent=request.headers.get("User-Agent"),
                success=False,
                error_message=str(e),
            )
        except Exception:
            pass  # Don't fail if audit logging fails
            
        return jsonify({"error": str(e)}), 500


@require_role("admin")
def clear_data_warehouse_cache():
    """Clear data warehouse cache."""
    from app.services.audit_service_postgres import audit_service
    
    try:
        from app.models.data_warehouse import DataWarehouseCache
        
        # Clear cache
        cleared_count = DataWarehouseCache.clear_cache()
        
        # Log action
        admin_email = request.headers.get(
            "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
        )
        admin_role = getattr(request, "user_role", None)
        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        audit_service.log_admin_action(
            user_email=admin_email,
            action="clear_data_warehouse_cache",
            target="data_warehouse_cache",
            user_role=admin_role,
            ip_address=user_ip,
            user_agent=request.headers.get("User-Agent"),
            success=True,
            details={"records_cleared": cleared_count},
        )
        
        return jsonify({
            "success": True, 
            "message": f"Cleared {cleared_count} data warehouse cache records"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
