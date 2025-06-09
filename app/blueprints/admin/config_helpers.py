"""
Helper functions for rendering configuration sections with Htmx.
"""


def is_sensitive_field(config_key):
    """Check if a configuration key should be treated as sensitive/encrypted based on naming."""
    try:
        category, key = config_key.split('.', 1)
        
        # Check if this should be encrypted based on naming (same logic as config.py)
        is_sensitive = any(
            suffix in key.lower() for suffix in ["secret", "password"]
        )
        
        # Special case: API keys ending with '_key' but not 'client_id' or 'tenant_id'
        if key.lower().endswith("_key") and not any(
            exclude in key.lower() for exclude in ["encryption_key"]
        ):
            is_sensitive = True
            
        return is_sensitive
    except:
        return False


def has_encrypted_value(config_key):
    """Check if a configuration key has an encrypted value in the database."""
    from app.services.configuration_service import config_get
    
    try:
        # First check if this is a sensitive field type
        if not is_sensitive_field(config_key):
            return False
            
        # Get the actual value - if it exists and looks encrypted, consider it encrypted
        value = config_get(config_key, None)
        
        # If we get None or empty string, but it's a sensitive field, 
        # it likely means there IS an encrypted value but it's being masked/hidden
        # In this case, we should check the database directly
        if not value:
            from app.database import db
            from sqlalchemy import text
            
            category, key = config_key.split('.', 1)
            with db.engine.begin() as conn:
                # Try both the exact key and common variations
                keys_to_try = [key]
                if key.islower():
                    keys_to_try.append(key.upper())
                elif key.isupper():
                    keys_to_try.append(key.lower())
                    
                for test_key in keys_to_try:
                    result = conn.execute(
                        text("SELECT encrypted_value FROM configuration WHERE category = :category AND setting_key = :key"),
                        {"category": category, "key": test_key}
                    )
                    row = result.fetchone()
                    if row and row[0]:
                        return True
        
        # If value looks encrypted
        if isinstance(value, str) and value.startswith("gAAAAAB") and len(value) > 50:
            return True
            
    except Exception as e:
        # Log the error for debugging
        try:
            from flask import current_app
            current_app.logger.error(f"Error checking encrypted value for {config_key}: {e}")
        except:
            pass
    
    return False


def render_app_config():
    """Render application configuration section."""
    from app.services.configuration_service import config_get

    # Get current values
    flask_host = config_get("flask.host", "0.0.0.0")
    flask_port = config_get("flask.port", "5000")
    flask_debug = config_get("flask.debug", "False")
    secret_key = config_get("flask.secret_key", "")
    search_timeout = config_get("search.overall_timeout", "20")
    cache_expiration = config_get("search.cache_expiration_hours", "24")
    lazy_photos = config_get("search.lazy_load_photos", "true")
    audit_retention = config_get("audit.log_retention_days", "90")
    session_timeout = config_get("auth.session_timeout_minutes", "15")
    
    # Check for encrypted values
    secret_key_encrypted = is_sensitive_field("flask.secret_key")

    return f'''
    <form hx-post="/admin/api/configuration?section=app" 
          hx-target="this"
          hx-swap="outerHTML">
        
        <div class="bg-blue-50 border-l-4 border-blue-400 p-4 rounded-lg mb-6">
            <div class="flex">
                <div class="flex-shrink-0">
                    <i class="fas fa-info-circle text-blue-400"></i>
                </div>
                <div class="ml-3">
                    <p class="text-sm text-blue-700">
                        Encryption key (WHODIS_ENCRYPTION_KEY) must stay in .env file. 
                        The master encryption key cannot be stored in the database for security.
                    </p>
                </div>
            </div>
        </div>
        
        <!-- Flask Settings -->
        <h6 class="text-lg font-semibold text-gray-900 border-b border-gray-200 pb-2 mb-4">Flask Configuration</h6>
        <div class="grid md:grid-cols-2 gap-4 mb-6">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Flask Host</label>
                <input type="text" name="flask_host" value="{flask_host}" 
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">Host address for Flask server</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Flask Port</label>
                <input type="number" name="flask_port" value="{flask_port}" 
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">Port number for Flask server</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Debug Mode</label>
                <select name="flask_debug" 
                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                    <option value="True" {"selected" if flask_debug == "True" else ""}>Enabled</option>
                    <option value="False" {"selected" if flask_debug != "True" else ""}>Disabled</option>
                </select>
                <p class="text-xs text-gray-500 mt-1">Enable debug mode (not for production)</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                    Secret Key
                    {'<span class="ml-2 px-2 py-1 text-xs bg-green-100 text-green-800 rounded"><i class="fas fa-shield-alt mr-1"></i>Encrypted</span>' if secret_key_encrypted else ""}
                    <i class="fas fa-exclamation-triangle text-yellow-500 ml-2" title="Changing this will log out all users"></i>
                    {'''<i class="fas fa-info-circle text-blue-500 ml-2 cursor-help" title="This field is encrypted. To update: enter a new value. To keep current value: leave the field empty and save. The placeholder dots are for display only."></i>''' if secret_key_encrypted else ""}
                </label>
                <div class="relative">
                    <input type="password" name="flask_secret_key" 
                           placeholder="{"••••••••" if secret_key_encrypted else "Enter new secret key"}"
                           class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green pr-10">
                    {'<button type="button" onclick="togglePassword(this)" class="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700"><i class="fas fa-eye"></i></button>' if not secret_key_encrypted else ''}
                </div>
                <p class="text-xs text-gray-500 mt-1">Application secret key (keep secure!)</p>
            </div>
        </div>
        
        <!-- Search Settings -->
        <h6 class="text-lg font-semibold text-gray-900 border-b border-gray-200 pb-2 mb-4 mt-6">Search Configuration</h6>
        <div class="grid md:grid-cols-2 gap-4 mb-6">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Overall Search Timeout (seconds)</label>
                <input type="number" name="search_overall_timeout" value="{search_timeout}" 
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">Maximum time for all searches to complete</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Cache Expiration (hours)</label>
                <input type="number" name="search_cache_expiration_hours" value="{cache_expiration}" 
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">How long to cache search results</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Lazy Load Photos</label>
                <select name="search_lazy_load_photos" 
                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                    <option value="true" {"selected" if lazy_photos == "true" else ""}>Enabled (Recommended)</option>
                    <option value="false" {"selected" if lazy_photos != "true" else ""}>Disabled</option>
                </select>
                <p class="text-xs text-gray-500 mt-1">Load user photos after search results</p>
            </div>
        </div>
        
        <!-- Audit Settings -->
        <h6 class="text-lg font-semibold text-gray-900 border-b border-gray-200 pb-2 mb-4 mt-6">Audit Configuration</h6>
        <div class="grid md:grid-cols-2 gap-4 mb-6">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Audit Log Retention (days)</label>
                <input type="number" name="audit_log_retention_days" value="{audit_retention}" 
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">Days to keep audit logs</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Session Timeout (minutes)</label>
                <input type="number" name="auth_session_timeout_minutes" value="{session_timeout}" 
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">User session timeout period</p>
            </div>
        </div>
        
        <div class="flex justify-end items-center pt-4 border-t">
            <button type="button" onclick="resetForm(this.form)" 
                    class="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-md mr-2">
                <i class="fas fa-undo mr-2"></i>Reset
            </button>
            <button type="submit" 
                    class="px-4 py-2 bg-ttcu-green hover:bg-green-700 text-white rounded-md">
                <i class="fas fa-save mr-2"></i>Save Application Settings
            </button>
        </div>
    </form>
    
    <script>
        function togglePassword(btn) {{
            const input = btn.parentElement.querySelector('input');
            const icon = btn.querySelector('i');
            
            if (input.type === 'password') {{
                input.type = 'text';
                icon.classList.remove('fa-eye');
                icon.classList.add('fa-eye-slash');
            }} else {{
                input.type = 'password';
                icon.classList.remove('fa-eye-slash');
                icon.classList.add('fa-eye');
            }}
        }}
        
        function resetForm(form) {{
            form.reset();
            // Re-check all password fields after reset
            setTimeout(() => {{
                document.querySelectorAll('input[type="password"], input[type="text"][name*="password"], input[type="text"][name*="secret"]').forEach(input => {{
                    updatePasswordToggle(input);
                }});
            }}, 100);
        }}
        
        // Handle dynamic show/hide of toggle button
        document.addEventListener('DOMContentLoaded', function() {{
            setupPasswordToggles();
        }});
        
        // Also setup toggles when HTMX loads new content
        document.body.addEventListener('htmx:afterSwap', function(evt) {{
            setupPasswordToggles();
        }});
        
        function setupPasswordToggles() {{
            console.log('setupPasswordToggles called');
            // Monitor all password fields
            const passwordFields = document.querySelectorAll('input[type="password"]');
            console.log('Found password fields:', passwordFields.length);
            
            passwordFields.forEach((input, index) => {{
                console.log('Setting up password field', index, ':', input.name, input.placeholder);
                
                // Remove existing listeners to avoid duplicates
                input.removeEventListener('input', handlePasswordInput);
                
                // Add new listener
                input.addEventListener('input', handlePasswordInput);
                
                // Initial state
                updatePasswordToggle(input);
            }});
        }}
        
        function handlePasswordInput(event) {{
            updatePasswordToggle(event.target);
        }}
        
        function updatePasswordToggle(input) {{
            console.log('updatePasswordToggle called for:', input.name, 'value length:', input.value.length, 'placeholder:', input.placeholder);
            
            const container = input.parentElement;
            const existingBtn = container.querySelector('button[onclick*="togglePassword"]');
            const hasPlaceholder = input.placeholder && input.placeholder.includes('••••');
            const hasValue = input.value && input.value.length > 0;
            
            console.log('hasPlaceholder:', hasPlaceholder, 'hasValue:', hasValue, 'existingBtn:', !!existingBtn);
            
            // Only show button if user has typed something AND it's not a placeholder field
            if (hasValue && !hasPlaceholder) {{
                // Show button if it doesn't exist
                if (!existingBtn) {{
                    console.log('Creating new toggle button');
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.onclick = function() {{ togglePassword(this); }};
                    btn.className = 'absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700';
                    btn.innerHTML = '<i class="fas fa-eye"></i>';
                    container.appendChild(btn);
                }}
            }} else {{
                // Remove button if it exists
                if (existingBtn) {{
                    console.log('Removing existing toggle button');
                    existingBtn.remove();
                }}
            }}
        }}
    </script>
    '''


def render_test_result(success, message, test_type="info"):
    """Render a test result message."""
    if success:
        return f"""
        <div class="bg-green-50 border-l-4 border-green-400 p-4 rounded-lg">
            <div class="flex">
                <div class="flex-shrink-0">
                    <i class="fas fa-check-circle text-green-400"></i>
                </div>
                <div class="ml-3">
                    <p class="text-green-700">{message}</p>
                </div>
            </div>
        </div>
        """
    else:
        return f"""
        <div class="bg-red-50 border-l-4 border-red-400 p-4 rounded-lg">
            <div class="flex">
                <div class="flex-shrink-0">
                    <i class="fas fa-times-circle text-red-400"></i>
                </div>
                <div class="ml-3">
                    <p class="text-red-700">{message}</p>
                </div>
            </div>
        </div>
        """


def render_ldap_config():
    """Render LDAP configuration section."""
    from app.services.configuration_service import config_get
    
    # Get current values
    ldap_host = config_get("ldap.host", "")
    ldap_port = config_get("ldap.port", "389")
    ldap_use_ssl = config_get("ldap.use_ssl", "False")
    ldap_bind_dn = config_get("ldap.bind_dn", "")
    ldap_bind_password = config_get("ldap.bind_password", "")
    ldap_base_dn = config_get("ldap.base_dn", "")
    ldap_user_search_base = config_get("ldap.user_search_base", "")
    ldap_connect_timeout = config_get("ldap.connect_timeout", "5")
    ldap_operation_timeout = config_get("ldap.operation_timeout", "10")
    
    # Check for encrypted values
    ldap_password_encrypted = is_sensitive_field("ldap.bind_password")
    
    return f'''
    <form hx-post="/admin/api/configuration?section=ldap" 
          hx-target="this"
          hx-swap="outerHTML">
        
        <!-- LDAP Settings -->
        <h6 class="text-lg font-semibold text-gray-900 border-b border-gray-200 pb-2 mb-4">LDAP Configuration</h6>
        
        <div class="grid md:grid-cols-2 gap-4 mb-6">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">LDAP Host</label>
                <input type="text" name="ldap_host" value="{ldap_host}" 
                       placeholder="ldap.example.com"
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">LDAP server hostname or IP address</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">LDAP Port</label>
                <input type="number" name="ldap_port" value="{ldap_port}" 
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">LDAP server port (389 for LDAP, 636 for LDAPS)</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Use SSL/TLS</label>
                <select name="ldap_use_ssl" 
                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                    <option value="True" {"selected" if ldap_use_ssl == "True" else ""}>Yes (LDAPS)</option>
                    <option value="False" {"selected" if ldap_use_ssl != "True" else ""}>No</option>
                </select>
                <p class="text-xs text-gray-500 mt-1">Use secure connection (LDAPS)</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Base DN</label>
                <input type="text" name="ldap_base_dn" value="{ldap_base_dn}" 
                       placeholder="dc=example,dc=com"
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">Base distinguished name for searches</p>
            </div>
        </div>
        
        <div class="grid md:grid-cols-2 gap-4 mb-6">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                    Bind DN
                </label>
                <input type="text" name="ldap_bind_dn" value="{ldap_bind_dn}" 
                       placeholder="CN=BindUser,OU=Service Accounts,DC=example,DC=com"
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">Service account DN for binding</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                    Bind Password
                    {'<span class="ml-2 px-2 py-1 text-xs bg-green-100 text-green-800 rounded"><i class="fas fa-shield-alt mr-1"></i>Encrypted</span>' if ldap_password_encrypted else ""}
                    {'''<i class="fas fa-info-circle text-blue-500 ml-2 cursor-help" title="This field is encrypted. To update: enter a new value. To keep current value: leave the field empty and save. The placeholder dots are for display only."></i>''' if ldap_password_encrypted else ""}
                </label>
                <div class="relative">
                    <input type="password" name="ldap_bind_password" 
                           placeholder="{"••••••••" if ldap_password_encrypted else "Enter bind password"}"
                           class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green pr-10">
                    {'<button type="button" onclick="togglePassword(this)" class="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700"><i class="fas fa-eye"></i></button>' if not ldap_password_encrypted else ''}
                </div>
                <p class="text-xs text-gray-500 mt-1">Service account password</p>
            </div>
        </div>
        
        <div class="grid md:grid-cols-2 gap-4 mb-6">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">User Search Base</label>
                <input type="text" name="ldap_user_search_base" value="{ldap_user_search_base}" 
                       placeholder="OU=Users,DC=example,DC=com"
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">Optional: Specific OU for user searches</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Connect Timeout (seconds)</label>
                <input type="number" name="ldap_connect_timeout" value="{ldap_connect_timeout}" 
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">Connection timeout in seconds</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Operation Timeout (seconds)</label>
                <input type="number" name="ldap_operation_timeout" value="{ldap_operation_timeout}" 
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">Search operation timeout</p>
            </div>
        </div>
        
        
        <div class="flex justify-end items-center pt-4 border-t">
            <button type="button" onclick="resetForm(this.form)" 
                    class="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-md mr-2">
                <i class="fas fa-undo mr-2"></i>Reset
            </button>
            <button type="submit" 
                    class="px-4 py-2 bg-ttcu-green hover:bg-green-700 text-white rounded-md">
                <i class="fas fa-save mr-2"></i>Save LDAP Settings
            </button>
        </div>
    </form>
    '''


def render_graph_config():
    """Render Microsoft Graph configuration section."""
    from app.services.configuration_service import config_get
    
    # Get current values
    graph_tenant_id = config_get("graph.tenant_id", "")
    graph_client_id = config_get("graph.client_id", "")
    graph_client_secret = config_get("graph.client_secret", "")
    graph_api_timeout = config_get("graph.api_timeout", "15")
    
    # Check for encrypted values
    graph_secret_encrypted = is_sensitive_field("graph.client_secret")
    
    return f'''
    <form hx-post="/admin/api/configuration?section=graph" 
          hx-target="this"
          hx-swap="outerHTML">
        
        <!-- Graph Settings -->
        <h6 class="text-lg font-semibold text-gray-900 border-b border-gray-200 pb-2 mb-4">Microsoft Graph Configuration</h6>
        
        <div class="bg-blue-50 border-l-4 border-blue-400 p-4 rounded-lg mb-6">
            <div class="flex">
                <div class="flex-shrink-0">
                    <i class="fas fa-info-circle text-blue-400"></i>
                </div>
                <div class="ml-3">
                    <p class="text-sm text-blue-700">
                        Microsoft Graph API is used to enhance Azure AD data with additional user properties and profile photos.
                        Configure an App Registration in Azure AD with <code>User.Read.All</code> application permissions.
                    </p>
                </div>
            </div>
        </div>
        
        <div class="grid md:grid-cols-2 gap-4 mb-6">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Tenant ID</label>
                <input type="text" name="graph_tenant_id" value="{graph_tenant_id}" 
                       placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">Azure AD tenant ID</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Client ID</label>
                <input type="text" name="graph_client_id" value="{graph_client_id}" 
                       placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">App registration client ID</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                    Client Secret
                    {'<span class="ml-2 px-2 py-1 text-xs bg-green-100 text-green-800 rounded"><i class="fas fa-shield-alt mr-1"></i>Encrypted</span>' if graph_secret_encrypted else ""}
                    {'''<i class="fas fa-info-circle text-blue-500 ml-2 cursor-help" title="This field is encrypted. To update: enter a new value. To keep current value: leave the field empty and save. The placeholder dots are for display only."></i>''' if graph_secret_encrypted else ""}
                </label>
                <div class="relative">
                    <input type="password" name="graph_client_secret" 
                           placeholder="{"••••••••" if graph_secret_encrypted else "Enter client secret"}"
                           class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green pr-10">
                    {'<button type="button" onclick="togglePassword(this)" class="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700"><i class="fas fa-eye"></i></button>' if not graph_secret_encrypted else ''}
                </div>
                <p class="text-xs text-gray-500 mt-1">App registration client secret</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">API Timeout (seconds)</label>
                <input type="number" name="graph_api_timeout" value="{graph_api_timeout}" 
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">API request timeout in seconds</p>
            </div>
        </div>
        
        
        <div class="flex justify-end items-center pt-4 border-t">
            <button type="button" onclick="resetForm(this.form)" 
                    class="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-md mr-2">
                <i class="fas fa-undo mr-2"></i>Reset
            </button>
            <button type="submit" 
                    class="px-4 py-2 bg-ttcu-green hover:bg-green-700 text-white rounded-md">
                <i class="fas fa-save mr-2"></i>Save Graph Settings
            </button>
        </div>
    </form>
    '''


def render_genesys_config():
    """Render Genesys configuration section."""
    from app.services.configuration_service import config_get
    
    # Get current values
    genesys_client_id = config_get("genesys.client_id", "")
    genesys_client_secret = config_get("genesys.client_secret", "")
    genesys_region = config_get("genesys.region", "mypurecloud.com")
    genesys_api_timeout = config_get("genesys.api_timeout", "15")
    genesys_cache_refresh_hours = config_get("genesys.cache_refresh_hours", "6")
    
    # Check for encrypted values
    genesys_secret_encrypted = is_sensitive_field("genesys.client_secret")
    
    return f'''
    <form hx-post="/admin/api/configuration?section=genesys" 
          hx-target="this"
          hx-swap="outerHTML">
        
        <!-- Genesys Settings -->
        <h6 class="text-lg font-semibold text-gray-900 border-b border-gray-200 pb-2 mb-4">Genesys Cloud Configuration</h6>
        
        <div class="bg-blue-50 border-l-4 border-blue-400 p-4 rounded-lg mb-6">
            <div class="flex">
                <div class="flex-shrink-0">
                    <i class="fas fa-info-circle text-blue-400"></i>
                </div>
                <div class="ml-3">
                    <p class="text-sm text-blue-700">
                        Genesys Cloud integration provides contact center data including skills, queues, and locations.
                        Configure an OAuth client with the <code>users:readonly</code> scope.
                    </p>
                </div>
            </div>
        </div>
        
        <div class="grid md:grid-cols-2 gap-4 mb-6">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Client ID</label>
                <input type="text" name="genesys_client_id" value="{genesys_client_id}" 
                       placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">OAuth client ID</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                    Client Secret
                    {'<span class="ml-2 px-2 py-1 text-xs bg-green-100 text-green-800 rounded"><i class="fas fa-shield-alt mr-1"></i>Encrypted</span>' if genesys_secret_encrypted else ""}
                    {'''<i class="fas fa-info-circle text-blue-500 ml-2 cursor-help" title="This field is encrypted. To update: enter a new value. To keep current value: leave the field empty and save. The placeholder dots are for display only."></i>''' if genesys_secret_encrypted else ""}
                </label>
                <div class="relative">
                    <input type="password" name="genesys_client_secret" 
                           placeholder="{"••••••••" if genesys_secret_encrypted else "Enter client secret"}"
                           class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green pr-10">
                    {'<button type="button" onclick="togglePassword(this)" class="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700"><i class="fas fa-eye"></i></button>' if not genesys_secret_encrypted else ''}
                </div>
                <p class="text-xs text-gray-500 mt-1">OAuth client secret</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Region</label>
                <select name="genesys_region" 
                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                    <option value="mypurecloud.com" {"selected" if genesys_region == "mypurecloud.com" else ""}>Americas (mypurecloud.com)</option>
                    <option value="mypurecloud.ie" {"selected" if genesys_region == "mypurecloud.ie" else ""}>EMEA (mypurecloud.ie)</option>
                    <option value="mypurecloud.de" {"selected" if genesys_region == "mypurecloud.de" else ""}>EMEA (mypurecloud.de)</option>
                    <option value="mypurecloud.com.au" {"selected" if genesys_region == "mypurecloud.com.au" else ""}>APAC (mypurecloud.com.au)</option>
                    <option value="mypurecloud.jp" {"selected" if genesys_region == "mypurecloud.jp" else ""}>APAC (mypurecloud.jp)</option>
                    <option value="usw2.pure.cloud" {"selected" if genesys_region == "usw2.pure.cloud" else ""}>US West 2 (usw2.pure.cloud)</option>
                    <option value="cac1.pure.cloud" {"selected" if genesys_region == "cac1.pure.cloud" else ""}>Canada (cac1.pure.cloud)</option>
                    <option value="euw2.pure.cloud" {"selected" if genesys_region == "euw2.pure.cloud" else ""}>EU West 2 (euw2.pure.cloud)</option>
                    <option value="aps1.pure.cloud" {"selected" if genesys_region == "aps1.pure.cloud" else ""}>Asia Pacific (aps1.pure.cloud)</option>
                </select>
                <p class="text-xs text-gray-500 mt-1">Genesys Cloud region</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">API Timeout (seconds)</label>
                <input type="number" name="genesys_api_timeout" value="{genesys_api_timeout}" 
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">API request timeout in seconds</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Cache Refresh Hours</label>
                <input type="number" name="genesys_cache_refresh_hours" value="{genesys_cache_refresh_hours}" 
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">Hours between cache refreshes</p>
            </div>
        </div>
        
        
        <div class="flex justify-end items-center pt-4 border-t">
            <button type="button" onclick="resetForm(this.form)" 
                    class="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-md mr-2">
                <i class="fas fa-undo mr-2"></i>Reset
            </button>
            <button type="submit" 
                    class="px-4 py-2 bg-ttcu-green hover:bg-green-700 text-white rounded-md">
                <i class="fas fa-save mr-2"></i>Save Genesys Settings
            </button>
        </div>
    </form>
    '''


def render_data_warehouse_config():
    """Render Data Warehouse configuration section."""
    from app.services.configuration_service import config_get
    
    # Get current values
    dw_server = config_get("data_warehouse.server", "")
    dw_database = config_get("data_warehouse.database", "CUFX")
    dw_client_id = config_get("data_warehouse.client_id", "")
    dw_client_secret = config_get("data_warehouse.client_secret", "")
    dw_connection_timeout = config_get("data_warehouse.connection_timeout", "30")
    dw_query_timeout = config_get("data_warehouse.query_timeout", "60")
    dw_cache_refresh_hours = config_get("data_warehouse.cache_refresh_hours", "6.0")
    
    # Check for encrypted values
    dw_secret_encrypted = is_sensitive_field("data_warehouse.client_secret")
    
    return f'''
    <form hx-post="/admin/api/configuration?section=data_warehouse" 
          hx-target="this"
          hx-swap="outerHTML">
        
        <!-- Data Warehouse Settings -->
        <h6 class="text-lg font-semibold text-gray-900 border-b border-gray-200 pb-2 mb-4">Data Warehouse Configuration</h6>
        
        <div class="bg-blue-50 border-l-4 border-blue-400 p-4 rounded-lg mb-6">
            <div class="flex">
                <div class="flex-shrink-0">
                    <i class="fas fa-info-circle text-blue-400"></i>
                </div>
                <div class="ml-3">
                    <p class="text-sm text-blue-700">
                        Data Warehouse integration provides additional user information from SQL Server.
                        Configure Azure AD authentication with appropriate database permissions.
                    </p>
                </div>
            </div>
        </div>
        
        <div class="grid md:grid-cols-2 gap-4 mb-6">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Server</label>
                <input type="text" name="data_warehouse_server" value="{dw_server}" 
                       placeholder="server.database.windows.net"
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">SQL Server hostname</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Database</label>
                <input type="text" name="data_warehouse_database" value="{dw_database}" 
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">Database name</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Client ID</label>
                <input type="text" name="data_warehouse_client_id" value="{dw_client_id}" 
                       placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">Azure AD app client ID</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                    Client Secret
                    {'<span class="ml-2 px-2 py-1 text-xs bg-green-100 text-green-800 rounded"><i class="fas fa-shield-alt mr-1"></i>Encrypted</span>' if dw_secret_encrypted else ""}
                    {'''<i class="fas fa-info-circle text-blue-500 ml-2 cursor-help" title="This field is encrypted. To update: enter a new value. To keep current value: leave the field empty and save. The placeholder dots are for display only."></i>''' if dw_secret_encrypted else ""}
                </label>
                <div class="relative">
                    <input type="password" name="data_warehouse_client_secret" 
                           placeholder="{"••••••••" if dw_secret_encrypted else "Enter client secret"}"
                           class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green pr-10">
                    {'<button type="button" onclick="togglePassword(this)" class="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700"><i class="fas fa-eye"></i></button>' if not dw_secret_encrypted else ''}
                </div>
                <p class="text-xs text-gray-500 mt-1">Azure AD app client secret</p>
            </div>
        </div>
        
        <div class="grid md:grid-cols-3 gap-4 mb-6">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Connection Timeout (seconds)</label>
                <input type="number" name="data_warehouse_connection_timeout" value="{dw_connection_timeout}" 
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">Connection timeout</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Query Timeout (seconds)</label>
                <input type="number" name="data_warehouse_query_timeout" value="{dw_query_timeout}" 
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">Query execution timeout</p>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Cache Refresh Hours</label>
                <input type="number" step="0.5" name="data_warehouse_cache_refresh_hours" value="{dw_cache_refresh_hours}" 
                       class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-ttcu-green">
                <p class="text-xs text-gray-500 mt-1">Hours between cache refreshes</p>
            </div>
        </div>
        
        
        <div class="flex justify-end items-center pt-4 border-t">
            <button type="button" onclick="resetForm(this.form)" 
                    class="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-md mr-2">
                <i class="fas fa-undo mr-2"></i>Reset
            </button>
            <button type="submit" 
                    class="px-4 py-2 bg-ttcu-green hover:bg-green-700 text-white rounded-md">
                <i class="fas fa-save mr-2"></i>Save Data Warehouse Settings
            </button>
        </div>
    </form>
    '''
