/**
 * Configuration Editor
 * Core functionality for loading, saving, and managing configuration
 */

// Configuration state management
const configState = {
    currentData: {},
    modifiedFields: new Set(),
    encryptedFields: []
};

// Load configuration for a specific category
async function loadConfiguration(category) {
    const categories = ['app', 'ldap', 'azure', 'genesys', 'data-warehouse'];
    
    // Map API categories to UI categories for tab handling
    const categoryMapping = {
        'app': 'app',
        'ldap': 'ldap', 
        'graph': 'azure',
        'genesys': 'genesys',
        'data_warehouse': 'data-warehouse'
    };
    
    const uiCategory = categoryMapping[category] || category;
    
    // Update active tab
    categories.forEach(cat => {
        const tabButton = document.querySelector(`[data-bs-target="#${cat}"]`);
        if (tabButton) {
            tabButton.classList.toggle('active', cat === uiCategory);
        }
    });
    
    // Show loading spinner with safety checks
    const loadingDiv = document.getElementById(`${uiCategory}-config-loading`);
    const contentDiv = document.getElementById(`${uiCategory}-config-content`);
    
    if (loadingDiv) {
        loadingDiv.style.display = 'block';
    } else {
        console.warn(`Loading div not found: ${uiCategory}-config-loading`);
    }
    
    if (contentDiv) {
        contentDiv.style.display = 'none';
    } else {
        console.warn(`Content div not found: ${uiCategory}-config-content`);
    }
    
    try {
        const response = await fetch('/admin/api/configuration');
        const data = await response.json();
        
        if (response.ok) {
            // Flatten the nested config structure to dot notation
            const flatConfig = {};
            for (const [categoryKey, categoryData] of Object.entries(data)) {
                if (typeof categoryData === 'object' && categoryData !== null) {
                    for (const [key, value] of Object.entries(categoryData)) {
                        // Map API keys to UI keys based on actual HTML data-key attributes
                        let uiKey = key.toLowerCase();
                        
                        // Specific mappings to match HTML data-key attributes
                        const keyMappings = {
                            'flask': {
                                'flask_host': 'host',
                                'flask_port': 'port', 
                                'flask_debug': 'debug',
                                'secret_key': 'secret_key'
                            },
                            'search': {
                                'search_overall_timeout': 'overall_timeout',
                                'cache_expiration_hours': 'cache_expiration_hours',
                                'search_lazy_load_photos': 'lazy_load_photos'
                            },
                            'audit': {
                                'audit_log_retention_days': 'log_retention_days'
                            },
                            'auth': {
                                'session_timeout_minutes': 'session_timeout_minutes'
                            },
                            'ldap': {
                                'ldap_host': 'host',
                                'ldap_port': 'port',
                                'ldap_use_ssl': 'use_ssl',
                                'ldap_connect_timeout': 'connect_timeout',
                                'ldap_bind_dn': 'bind_dn',
                                'ldap_bind_password': 'bind_password',
                                'ldap_base_dn': 'base_dn',
                                'ldap_user_search_base': 'user_search_base',
                                'ldap_operation_timeout': 'operation_timeout'
                            },
                            'graph': {
                                'graph_tenant_id': 'tenant_id',
                                'graph_client_id': 'client_id',
                                'graph_client_secret': 'client_secret',
                                'graph_api_timeout': 'api_timeout'
                            },
                            'genesys': {
                                'genesys_client_id': 'client_id',
                                'genesys_client_secret': 'client_secret',
                                'genesys_region': 'region',
                                'genesys_api_timeout': 'api_timeout',
                                'genesys_cache_refresh_hours': 'cache_refresh_hours'
                            },
                            'data_warehouse': {
                                'data_warehouse_server': 'server',
                                'data_warehouse_database': 'database',
                                'data_warehouse_client_id': 'client_id',
                                'data_warehouse_client_secret': 'client_secret',
                                'data_warehouse_connection_timeout': 'connection_timeout',
                                'data_warehouse_query_timeout': 'query_timeout',
                                'data_warehouse_cache_refresh_hours': 'cache_refresh_hours'
                            }
                        };
                        
                        if (keyMappings[categoryKey] && keyMappings[categoryKey][uiKey]) {
                            uiKey = keyMappings[categoryKey][uiKey];
                        }
                        flatConfig[`${categoryKey}.${uiKey}`] = value;
                    }
                }
            }
            
            configState.currentData = flatConfig;
            
            // Convert encrypted_fields to flat keys that match HTML IDs
            configState.encryptedFields = [];
            if (data.encrypted_fields) {
                configState.encryptedFields = data.encrypted_fields.map(field => {
                    const [category, key] = field.split('.');
                    let uiKey = key.toLowerCase();
                    
                    // Remove category prefixes and convert to match HTML data-key attributes
                    if (category === 'flask' && key === 'SECRET_KEY') {
                        uiKey = 'secret_key';
                    } else if (category === 'ldap') {
                        uiKey = uiKey.replace('ldap_', '');
                    } else if (category === 'genesys') {
                        uiKey = uiKey.replace('genesys_', '');
                    } else if (category === 'graph') {
                        uiKey = uiKey.replace('graph_', '');
                    } else if (category === 'data_warehouse') {
                        uiKey = uiKey.replace('data_warehouse_', '');
                    }
                    
                    return `${category}.${uiKey}`;
                });
            }
            
            
            // Populate form fields
            populateFormFields(uiCategory, flatConfig);
            
            // Update encrypted field indicators
            updateEncryptedFieldIndicators();
            
            // Special handling for Genesys cache status
            if (category === 'genesys') {
                loadGenesysCacheStatus();
            }
            
            // Special handling for Data Warehouse cache status
            if (category === 'data_warehouse') {
                loadDataWarehouseCacheStatus();
            }
        } else {
            showToast('Failed to load configuration', 'danger');
        }
    } catch (error) {
        console.error('Error loading configuration:', error);
        showToast('Error loading configuration', 'danger');
    } finally {
        if (loadingDiv) loadingDiv.style.display = 'none';
        if (contentDiv) contentDiv.style.display = 'block';
    }
}

// Populate form fields with configuration data
function populateFormFields(category, configData) {
    const fields = document.querySelectorAll(`#${category} input, #${category} select, #${category} textarea`);
    
    fields.forEach(field => {
        const key = field.getAttribute('data-key');
        
        if (key && configData[key] !== undefined) {
            const value = configData[key];
            
            if (field.type === 'checkbox') {
                field.checked = value === true || value === 'true' || value === 'True';
            } else if (field.tagName === 'SELECT') {
                // Handle select dropdowns - convert boolean to string
                if (typeof value === 'boolean') {
                    field.value = value ? 'True' : 'False';
                } else {
                    field.value = String(value);
                }
            } else if (field.getAttribute('data-sensitive') === 'true') {
                // For encrypted fields, show placeholder even if value is null/empty
                // (since null might mean decryption failed or field exists but is encrypted)
                field.value = '••••••••';
                field.setAttribute('data-original-value', '••••••••');
            } else if (value === null) {
                // Handle null values
                field.value = '';
            } else {
                // Convert to string for text inputs
                field.value = String(value);
            }
        }
    });
}

// Save configuration for a specific section
async function saveConfiguration(section) {
    console.log('=== Starting saveConfiguration ===');
    console.log('Section:', section);
    
    const sectionMap = {
        'app': ['flask', 'search', 'session', 'audit', 'auth'],
        'ldap': ['ldap'],
        'azure': ['graph'],
        'graph': ['graph'],
        'genesys': ['genesys'],
        'data-warehouse': ['data_warehouse']
    };
    
    const prefixes = sectionMap[section] || [];
    console.log('Prefixes for section:', prefixes);
    
    // Structure updates in the format the backend expects: { category: { key: value } }
    const updates = {};
    
    // Collect all fields for this section
    const fields = document.querySelectorAll(`#${section} input, #${section} select, #${section} textarea`);
    console.log('Found fields:', fields.length);
    
    fields.forEach(field => {
        const key = field.getAttribute('data-key');
        if (!key) return;
        
        // Parse the key into category and setting
        const [category, ...settingParts] = key.split('.');
        const setting = settingParts.join('.');
        
        // Check if this field belongs to the current section
        if (!prefixes.includes(category)) {
            console.log('Skipping field - wrong category:', key, 'category:', category);
            return;
        }
        
        let value = field.value;
        
        // Handle different field types
        if (field.type === 'checkbox') {
            value = field.checked;
        } else if (field.type === 'number') {
            value = value ? parseInt(value) : null;
        }
        
        // Handle encrypted fields
        const isSensitive = field.getAttribute('data-sensitive') === 'true';
        if (isSensitive && value === '••••••••') {
            console.log('Skipping encrypted field (unchanged):', key);
            return;
        }
        
        // Map the field key to the backend expected key format
        const backendKeyMap = {
            'flask.host': 'FLASK_HOST',
            'flask.port': 'FLASK_PORT',
            'flask.debug': 'FLASK_DEBUG',
            'flask.secret_key': 'SECRET_KEY',
            'search.overall_timeout': 'SEARCH_OVERALL_TIMEOUT',
            'search.cache_expiration_hours': 'CACHE_EXPIRATION_HOURS',
            'search.lazy_load_photos': 'SEARCH_LAZY_LOAD_PHOTOS',
            'audit.log_retention_days': 'AUDIT_LOG_RETENTION_DAYS',
            'auth.session_timeout_minutes': 'SESSION_TIMEOUT_MINUTES',
            'ldap.host': 'LDAP_HOST',
            'ldap.port': 'LDAP_PORT',
            'ldap.use_ssl': 'LDAP_USE_SSL',
            'ldap.connect_timeout': 'LDAP_CONNECT_TIMEOUT',
            'ldap.bind_dn': 'LDAP_BIND_DN',
            'ldap.bind_password': 'LDAP_BIND_PASSWORD',
            'ldap.base_dn': 'LDAP_BASE_DN',
            'ldap.user_search_base': 'LDAP_USER_SEARCH_BASE',
            'ldap.operation_timeout': 'LDAP_OPERATION_TIMEOUT',
            'graph.tenant_id': 'GRAPH_TENANT_ID',
            'graph.client_id': 'GRAPH_CLIENT_ID',
            'graph.client_secret': 'GRAPH_CLIENT_SECRET',
            'graph.api_timeout': 'GRAPH_API_TIMEOUT',
            'genesys.client_id': 'GENESYS_CLIENT_ID',
            'genesys.client_secret': 'GENESYS_CLIENT_SECRET',
            'genesys.region': 'GENESYS_REGION',
            'genesys.api_timeout': 'GENESYS_API_TIMEOUT',
            'genesys.cache_refresh_hours': 'GENESYS_CACHE_REFRESH_HOURS',
            'data_warehouse.server': 'DATA_WAREHOUSE_SERVER',
            'data_warehouse.database': 'DATA_WAREHOUSE_DATABASE',
            'data_warehouse.client_id': 'DATA_WAREHOUSE_CLIENT_ID',
            'data_warehouse.client_secret': 'DATA_WAREHOUSE_CLIENT_SECRET',
            'data_warehouse.connection_timeout': 'DATA_WAREHOUSE_CONNECTION_TIMEOUT',
            'data_warehouse.query_timeout': 'DATA_WAREHOUSE_QUERY_TIMEOUT',
            'data_warehouse.cache_refresh_hours': 'DATA_WAREHOUSE_CACHE_REFRESH_HOURS'
        };
        
        const backendKey = backendKeyMap[key] || setting.toUpperCase();
        
        // Only include if value has changed
        const currentValue = configState.currentData[key];
        console.log(`Field ${key}: current="${currentValue}", new="${value}"`);
        
        if (currentValue !== value && currentValue !== String(value)) {
            if (!updates[category]) {
                updates[category] = {};
            }
            updates[category][backendKey] = value;
            console.log(`Adding update: ${category}.${backendKey} = ${value}`);
        }
    });
    
    if (Object.keys(updates).length === 0) {
        showToast('No changes to save', 'info');
        return;
    }
    
    console.log('Updates to send:', JSON.stringify(updates, null, 2));
    
    try {
        const response = await fetch('/admin/api/configuration', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCSRFToken()
            },
            body: JSON.stringify({ updates: updates })
        });
        
        console.log('Response status:', response.status);
        const responseData = await response.json();
        console.log('Response data:', responseData);
        
        if (!response.ok) {
            throw new Error(responseData.error || `Failed to save configuration (${response.status})`);
        }
        
        showToast('Configuration saved successfully', 'success');
        
        // Reload to get updated encrypted field indicators
        const reloadSection = section === 'app' ? 'app' : 
                            section === 'azure' ? 'graph' : 
                            section === 'data-warehouse' ? 'data_warehouse' : 
                            section;
        loadConfiguration(reloadSection);
        
    } catch (error) {
        console.error('Error saving configuration:', error);
        showToast(`Error saving configuration: ${error.message}`, 'danger');
    }
}

// Update encrypted field indicators
function updateEncryptedFieldIndicators() {
    // Reset all indicators first
    document.querySelectorAll('.encrypted-badge, .encrypted-info, .encrypted-eye-btn').forEach(el => {
        el.classList.add('d-none');
    });
    
    // Show indicators for encrypted fields
    configState.encryptedFields.forEach(fieldKey => {
        const fieldId = fieldKey.replace(/\./g, '-').replace(/_/g, '-');
        
        const badge = document.getElementById(`${fieldId}-badge`);
        const info = document.getElementById(`${fieldId}-info`);
        const eyeBtn = document.getElementById(`${fieldId}-eye`);
        
        if (badge) badge.classList.remove('d-none');
        // Don't show the info circle - the badge is sufficient
        // if (info) info.classList.remove('d-none');
        
        // Only show eye button if field doesn't have placeholder dots
        if (eyeBtn) {
            const field = document.getElementById(fieldId);
            if (field && field.value !== '••••••••') {
                eyeBtn.classList.remove('d-none');
            }
        }
    });
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Toggle password visibility
function togglePasswordVisibility(inputId) {
    const input = document.getElementById(inputId);
    const eyeBtn = document.getElementById(`${inputId}-eye`);
    const icon = eyeBtn ? eyeBtn.querySelector('i') : null;
    
    if (input && input.type === 'password') {
        input.type = 'text';
        if (icon) {
            icon.classList.remove('bi-eye');
            icon.classList.add('bi-eye-slash');
        }
    } else if (input) {
        input.type = 'password';
        if (icon) {
            icon.classList.remove('bi-eye-slash');
            icon.classList.add('bi-eye');
        }
    }
}

// Test service connections
async function testConnection(service, displayName) {
    // Save configuration first
    const sectionMap = {
        'ldap': 'ldap',
        'graph': 'azure',
        'genesys': 'genesys'
    };
    
    const section = sectionMap[service];
    if (section) {
        await saveConfiguration(section);
    }
    
    // Wait a moment for config to be applied
    setTimeout(async () => {
        try {
            const response = await fetch(`/admin/api/test/${service}`);
            const data = await response.json();
            
            if (data.success) {
                showToast(`${displayName} connection successful!`, 'success');
            } else {
                showToast(`${displayName} connection failed: ${data.error || 'Unknown error'}`, 'danger');
            }
        } catch (error) {
            console.error(`Error testing ${displayName} connection:`, error);
            showToast(`Error testing ${displayName} connection`, 'danger');
        }
    }, 1000);
}

// Specific test connection functions for backward compatibility
function testLDAPConnection() {
    testConnection('ldap', 'LDAP');
}

function testGraphConnection() {
    testConnection('graph', 'Microsoft Graph');
}

function testGenesysConnection() {
    testConnection('genesys', 'Genesys Cloud');
}

// Reset configuration to original values
function resetConfiguration(section) {
    // Map section names to categories
    const sectionToCategoryMap = {
        'app': 'app',
        'ldap': 'ldap',
        'azure': 'azure',
        'graph': 'azure', // Alternative name
        'genesys': 'genesys',
        'data-warehouse': 'data-warehouse'
    };
    
    const category = sectionToCategoryMap[section] || section;
    
    // Reload the configuration for this section
    loadConfiguration(category === 'azure' ? 'graph' : category === 'data-warehouse' ? 'data_warehouse' : category);
    
    // Show a toast notification
    showToast('Configuration reset to saved values', 'info');
}

// Note: getCSRFToken() is provided by security-utils.js