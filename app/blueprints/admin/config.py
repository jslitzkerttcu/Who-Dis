"""
Configuration management functionality for admin blueprint.
Handles configuration viewing, updating, and service connection testing.
"""

from flask import render_template, jsonify, request, current_app, make_response
from app.middleware.auth import require_role
import logging

logger = logging.getLogger(__name__)


@require_role("admin")
def configuration():
    """Display configuration management page."""
    return render_template("admin/configuration.html")


@require_role("admin")
def api_configuration():
    """Get or update configuration values."""
    from app.services.configuration_service import config_get, config_set
    from app.services.audit_service_postgres import audit_service

    if request.method == "GET":
        # Check if this is an Htmx request for a specific section
        section = request.args.get('section')
        if request.headers.get('HX-Request') and section:
            return _render_config_section(section)
        # Get all configuration values grouped by category
        config_data = {
            "flask": {
                "FLASK_HOST": config_get("flask.host", "0.0.0.0"),
                "FLASK_PORT": config_get("flask.port", "5000"),
                "FLASK_DEBUG": config_get("flask.debug", "False"),
                "SECRET_KEY": config_get("flask.secret_key", ""),
            },
            "auth": {
                "AUTH_REQUIRED": config_get("auth.required", "True"),
                "AUTH_BASIC_ENABLED": config_get("auth.basic_enabled", "False"),
                "AUTH_BASIC_USERNAME": config_get("auth.basic_username", ""),
                "AUTH_BASIC_PASSWORD": config_get("auth.basic_password", ""),
                "SESSION_TIMEOUT_MINUTES": config_get("auth.session_timeout_minutes", "15"),
            },
            "search": {
                "SEARCH_TIMEOUT": config_get("search.timeout", "20"),
                "SEARCH_OVERALL_TIMEOUT": config_get("search.overall_timeout", "20"),
                "CACHE_EXPIRATION_HOURS": config_get("search.cache_expiration_hours", "24"),
                "SEARCH_LAZY_LOAD_PHOTOS": config_get("search.lazy_load_photos", "true"),
            },
            "audit": {
                "AUDIT_RETENTION_DAYS": config_get("audit.retention_days", "90"),
                "AUDIT_LOG_RETENTION_DAYS": config_get("audit.log_retention_days", "90"),
            },
            "ldap": {
                "LDAP_HOST": config_get("ldap.host", ""),
                "LDAP_SERVER": config_get("ldap.server", ""),  # Alias for compatibility
                "LDAP_PORT": config_get("ldap.port", "389"),
                "LDAP_USE_SSL": config_get("ldap.use_ssl", "False"),
                "LDAP_BIND_DN": config_get("ldap.bind_dn", ""),
                "LDAP_BIND_PASSWORD": config_get("ldap.bind_password", ""),
                "LDAP_BASE_DN": config_get("ldap.base_dn", ""),
                "LDAP_USER_SEARCH_BASE": config_get("ldap.user_search_base", ""),
                "LDAP_CONNECT_TIMEOUT": config_get("ldap.connect_timeout", "5"),
                "LDAP_CONNECTION_TIMEOUT": config_get("ldap.connection_timeout", "5"),  # Alias
                "LDAP_OPERATION_TIMEOUT": config_get("ldap.operation_timeout", "10"),
            },
            "graph": {
                "GRAPH_CLIENT_ID": config_get("graph.client_id", ""),
                "GRAPH_CLIENT_SECRET": config_get("graph.client_secret", ""),
                "GRAPH_TENANT_ID": config_get("graph.tenant_id", ""),
                "GRAPH_API_TIMEOUT": config_get("graph.api_timeout", "15"),
            },
            "genesys": {
                "GENESYS_CLIENT_ID": config_get("genesys.client_id", ""),
                "GENESYS_CLIENT_SECRET": config_get("genesys.client_secret", ""),
                "GENESYS_REGION": config_get("genesys.region", "mypurecloud.com"),
                "GENESYS_API_TIMEOUT": config_get("genesys.api_timeout", "15"),
                "GENESYS_CACHE_REFRESH_HOURS": config_get("genesys.cache_refresh_hours", "6"),
            },
            "data_warehouse": {
                "DATA_WAREHOUSE_SERVER": config_get("data_warehouse.server", ""),
                "DATA_WAREHOUSE_DATABASE": config_get("data_warehouse.database", "CUFX"),
                "DATA_WAREHOUSE_CLIENT_ID": config_get("data_warehouse.client_id", ""),
                "DATA_WAREHOUSE_CLIENT_SECRET": config_get("data_warehouse.client_secret", ""),
                "DATA_WAREHOUSE_CONNECTION_TIMEOUT": config_get("data_warehouse.connection_timeout", "30"),
                "DATA_WAREHOUSE_QUERY_TIMEOUT": config_get("data_warehouse.query_timeout", "60"),
                "DATA_WAREHOUSE_CACHE_REFRESH_HOURS": config_get("data_warehouse.cache_refresh_hours", "6.0"),
            },
        }
        
        # Identify encrypted fields and mask their values
        encrypted_fields = []
        for category, settings in config_data.items():
            if category == "encrypted_fields":  # Skip this if it exists
                continue
            for key, value in settings.items():
                # Ensure value is a string, not bytes
                if isinstance(value, bytes):
                    try:
                        value = value.decode('utf-8')
                        config_data[category][key] = value
                    except UnicodeDecodeError:
                        config_data[category][key] = ""
                
                full_key = f"{category}.{key}"
                # Check if this should be encrypted based on naming
                is_sensitive_field = any(suffix in key.lower() for suffix in ['secret', 'password'])
                # Special case: API keys ending with '_key' but not 'client_id' or 'tenant_id'
                if key.lower().endswith('_key') and not any(exclude in key.lower() for exclude in ['encryption_key']):
                    is_sensitive_field = True
                
                # Only mask if it's actually a sensitive field
                # Don't mask just because it has encrypted content - that might be a mistake
                if is_sensitive_field:
                    encrypted_fields.append(full_key)
                    # Mask the value
                    config_data[category][key] = "••••••••"
                # If value looks encrypted but field isn't sensitive, it might be a mistake
                elif isinstance(value, str) and value.startswith('gAAAAAB') and len(value) > 50:
                    # This is likely an error - non-sensitive field with encrypted value
                    # Show empty string to indicate it needs to be re-entered
                    config_data[category][key] = ""
        
        response_data = config_data.copy()
        response_data["encrypted_fields"] = encrypted_fields
        return jsonify(response_data)

    else:  # POST
        try:
            current_app.logger.info("=== Configuration POST request ===")
            current_app.logger.info(f"Request JSON: {request.json}")
            
            updates = request.json.get("updates", {})
            current_app.logger.info(f"Updates extracted: {updates}")
            
            # Get config service from container
            try:
                config_service = current_app.container.get("config")
                current_app.logger.info(f"Config service available: {config_service is not None}")
            except Exception as e:
                current_app.logger.error(f"Failed to get config service from container: {e}")
                config_service = None

            if not config_service:
                current_app.logger.error("Configuration service not available")
                return jsonify(
                    {"success": False, "error": "Configuration service not available"}
                ), 500

            # Track changes for audit log
            changes = []

            # Apply updates
            for category, settings in updates.items():
                current_app.logger.info(f"Processing category: {category}")
                for key, value in settings.items():
                    current_app.logger.info(f"Processing key: {key} = {value}")
                    
                    # Map uppercase keys back to lowercase configuration keys
                    key_mapping = {
                        # Flask keys
                        "FLASK_HOST": "host",
                        "FLASK_PORT": "port",
                        "FLASK_DEBUG": "debug",
                        "SECRET_KEY": "secret_key",
                        # Auth keys
                        "AUTH_REQUIRED": "required",
                        "AUTH_BASIC_ENABLED": "basic_enabled",
                        "AUTH_BASIC_USERNAME": "basic_username",
                        "AUTH_BASIC_PASSWORD": "basic_password",
                        # Search keys
                        "SEARCH_TIMEOUT": "timeout",
                        "SEARCH_OVERALL_TIMEOUT": "overall_timeout",
                        "CACHE_EXPIRATION_HOURS": "cache_expiration_hours",
                        "SEARCH_LAZY_LOAD_PHOTOS": "lazy_load_photos",
                        # Audit keys
                        "AUDIT_RETENTION_DAYS": "retention_days",
                        "AUDIT_LOG_RETENTION_DAYS": "log_retention_days",
                        # Session keys
                        "SESSION_TIMEOUT_MINUTES": "session_timeout_minutes",
                        # LDAP keys
                        "LDAP_HOST": "host",
                        "LDAP_SERVER": "server",
                        "LDAP_PORT": "port",
                        "LDAP_USE_SSL": "use_ssl",
                        "LDAP_BASE_DN": "base_dn",
                        "LDAP_BIND_DN": "bind_dn",
                        "LDAP_BIND_PASSWORD": "bind_password",
                        "LDAP_USER_SEARCH_BASE": "user_search_base",
                        "LDAP_CONNECT_TIMEOUT": "connect_timeout",
                        "LDAP_CONNECTION_TIMEOUT": "connection_timeout",
                        "LDAP_OPERATION_TIMEOUT": "operation_timeout",
                        # Graph keys
                        "GRAPH_TENANT_ID": "tenant_id",
                        "GRAPH_CLIENT_ID": "client_id",
                        "GRAPH_CLIENT_SECRET": "client_secret",
                        "GRAPH_API_TIMEOUT": "api_timeout",
                        # Genesys keys
                        "GENESYS_CLIENT_ID": "client_id",
                        "GENESYS_CLIENT_SECRET": "client_secret",
                        "GENESYS_REGION": "region",
                        "GENESYS_API_TIMEOUT": "api_timeout",
                        "GENESYS_CACHE_REFRESH_HOURS": "cache_refresh_hours",
                        # Data warehouse keys
                        "DATA_WAREHOUSE_SERVER": "server",
                        "DATA_WAREHOUSE_DATABASE": "database",
                        "DATA_WAREHOUSE_CLIENT_ID": "client_id",
                        "DATA_WAREHOUSE_CLIENT_SECRET": "client_secret",
                        "DATA_WAREHOUSE_CONNECTION_TIMEOUT": "connection_timeout",
                        "DATA_WAREHOUSE_QUERY_TIMEOUT": "query_timeout",
                        "DATA_WAREHOUSE_CACHE_REFRESH_HOURS": "cache_refresh_hours",
                    }
                    
                    # Apply key mapping
                    key = key_mapping.get(key, key.lower())

                    config_key = f"{category}.{key}"
                    old_value = config_get(config_key, "")
                    current_app.logger.info(f"Old value for {config_key}: {old_value}")
                    
                    if str(old_value) != str(value):
                        # Get the admin email for updated_by
                        admin_email = request.headers.get(
                            "X-MS-CLIENT-PRINCIPAL-NAME",
                            request.remote_user or "unknown",
                        )
                        current_app.logger.info(f"Setting {config_key} = {value}")
                        result = config_set(config_key, value, admin_email)
                        current_app.logger.info(f"Set result for {config_key}: {result}")
                        changes.append(
                            {
                                "category": category,
                                "key": key,
                                "old_value": old_value,
                                "new_value": value,
                            }
                        )
                    else:
                        current_app.logger.info(f"No change for {config_key}, skipping")

            # Log configuration changes
            if changes:
                admin_email = request.headers.get(
                    "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
                )
                admin_role = getattr(request, "user_role", None)
                user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

                # Log each change individually
                for change in changes:
                    audit_service.log_config_change(
                        user_email=admin_email,
                        config_key=f"{change['category']}.{change['key']}",
                        old_value=str(change['old_value']),
                        new_value=str(change['new_value']),
                        user_role=admin_role,
                        ip_address=user_ip,
                        user_agent=request.headers.get("User-Agent"),
                    )

            return jsonify(
                {
                    "success": True,
                    "message": f"Configuration updated successfully ({len(changes)} changes)",
                    "changes": len(changes),
                }
            )

        except Exception as e:
            current_app.logger.error(f"Configuration update error: {e}", exc_info=True)
            return jsonify(
                {"success": False, "error": f"Failed to update configuration: {str(e)}"}
            ), 500


@require_role("admin")
def test_ldap_connection():
    """Test LDAP connection with current configuration."""
    from app.services.ldap_service import test_connection

    try:
        result = test_connection()
        return jsonify(
            {
                "success": result,
                "message": "Connection successful" if result else "Connection failed",
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@require_role("admin")
def test_graph_connection():
    """Test Microsoft Graph API connection."""
    from app.services.graph_service import graph_service

    try:
        # Try to get token
        if graph_service.refresh_token_if_needed():
            return jsonify({"success": True, "message": "Connection successful"})
        else:
            return jsonify({"success": False, "error": "Failed to obtain access token"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@require_role("admin")
def test_genesys_connection():
    """Test Genesys Cloud API connection."""
    from app.services.genesys_service import genesys_service

    try:
        # Try to get token
        if genesys_service.refresh_token_if_needed():
            return jsonify({"success": True, "message": "Connection successful"})
        else:
            return jsonify({"success": False, "error": "Failed to obtain access token"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@require_role("admin")
def test_data_warehouse_connection():
    """Test data warehouse connection."""
    from app.services.data_warehouse_service import data_warehouse_service

    try:
        result = data_warehouse_service.test_connection()
        return jsonify(
            {
                "success": result,
                "message": "Connection successful" if result else "Connection failed",
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
