/**
 * Configuration UI Components
 * UI rendering and component generation for configuration interface
 */

// Create loading spinner
function createLoadingSpinner(color = 'primary') {
    return `
        <div class="text-center py-4">
            <div class="spinner-border text-${color}" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
}

// Create form field
function createFormField(config) {
    const {
        id,
        key,
        label,
        type = 'text',
        value = '',
        placeholder = '',
        helpText = '',
        colWidth = 12,
        options = [],
        min = null,
        max = null,
        step = null,
        sensitive = false,
        readonly = false,
        required = false,
        icon = null,
        warningMessage = null
    } = config;
    
    let fieldHtml = '';
    const fieldId = id || key.replace(/\./g, '-');
    
    // Start column wrapper
    fieldHtml += `<div class="col-md-${colWidth}">`;
    
    // Label with badges and icons
    fieldHtml += '<label class="form-label">';
    fieldHtml += escapeHtml(label);
    
    // Add encrypted badge for sensitive fields
    if (sensitive) {
        fieldHtml += `
            <span class="badge bg-success ms-2 encrypted-badge d-none" id="${fieldId}-badge"
                  data-bs-toggle="tooltip"
                  data-bs-placement="top"
                  title="This value is securely encrypted in the database. The field shows dots for security. To update, type a new value. To keep existing, leave as-is or clear the field.">
                <i class="bi bi-shield-check"></i> Encrypted
            </span>
            <i class="bi bi-info-circle text-muted ms-1 encrypted-info d-none" id="${fieldId}-info"
               data-bs-toggle="tooltip"
               data-bs-placement="top"
               title="Current encrypted value will be preserved"></i>
        `;
    }
    
    // Add warning icon if provided
    if (warningMessage) {
        fieldHtml += `
            <i class="bi bi-exclamation-triangle text-warning ms-2" 
               data-bs-toggle="tooltip" 
               data-bs-placement="top" 
               title="${escapeHtml(warningMessage)}"></i>
        `;
    }
    
    fieldHtml += '</label>';
    
    // Field wrapper (input group for password fields)
    if (sensitive && type === 'password') {
        fieldHtml += '<div class="input-group">';
    }
    
    // Generate field based on type
    switch (type) {
        case 'select':
            fieldHtml += `<select class="form-select" id="${fieldId}" data-key="${key}"${readonly ? ' disabled' : ''}>`;
            options.forEach(opt => {
                const optValue = opt.value || opt;
                const optLabel = opt.label || opt;
                const selected = value == optValue ? ' selected' : '';
                fieldHtml += `<option value="${escapeHtml(optValue)}"${selected}>${escapeHtml(optLabel)}</option>`;
            });
            fieldHtml += '</select>';
            break;
            
        case 'textarea':
            fieldHtml += `<textarea class="form-control" id="${fieldId}" data-key="${key}"${readonly ? ' readonly' : ''}>${escapeHtml(value)}</textarea>`;
            break;
            
        case 'checkbox':
            fieldHtml += '<div class="form-check">';
            fieldHtml += `<input type="checkbox" class="form-check-input" id="${fieldId}" data-key="${key}"${value ? ' checked' : ''}${readonly ? ' disabled' : ''}>`;
            fieldHtml += '</div>';
            break;
            
        default:
            const inputType = sensitive ? 'password' : type;
            fieldHtml += `<input type="${inputType}" class="form-control" id="${fieldId}" data-key="${key}"`;
            if (value) fieldHtml += ` value="${escapeHtml(value)}"`;
            if (placeholder) fieldHtml += ` placeholder="${escapeHtml(placeholder)}"`;
            if (min !== null) fieldHtml += ` min="${min}"`;
            if (max !== null) fieldHtml += ` max="${max}"`;
            if (step !== null) fieldHtml += ` step="${step}"`;
            if (sensitive) fieldHtml += ' data-sensitive="true"';
            if (readonly) fieldHtml += ' readonly';
            if (required) fieldHtml += ' required';
            fieldHtml += '>';
    }
    
    // Eye button for password fields
    if (sensitive && type === 'password') {
        fieldHtml += `
            <button class="btn btn-outline-secondary encrypted-eye-btn d-none" type="button" 
                    onclick="togglePasswordVisibility('${fieldId}')" id="${fieldId}-eye">
                <i class="bi bi-eye"></i>
            </button>
        `;
        fieldHtml += '</div>'; // Close input-group
    }
    
    // Help text
    if (helpText) {
        fieldHtml += `<small class="text-muted">${escapeHtml(helpText)}</small>`;
    }
    
    fieldHtml += '</div>'; // Close column
    
    return fieldHtml;
}

// Create form section
function createFormSection(title, fields, icon = null) {
    let html = '';
    
    if (title) {
        html += `<h6 class="border-bottom pb-2 mb-3 mt-4">`;
        if (icon) {
            html += `<i class="${icon}"></i> `;
        }
        html += escapeHtml(title);
        html += '</h6>';
    }
    
    html += '<div class="row mb-3">';
    fields.forEach(field => {
        html += createFormField(field);
    });
    html += '</div>';
    
    return html;
}

// Create alert banner
function createAlertBanner(message, type = 'info', icon = 'bi-info-circle', tooltip = null) {
    let html = `<div class="alert alert-${type} py-2 px-3 mb-3 d-flex align-items-center" style="font-size: 0.875rem;">`;
    html += `<i class="bi ${icon} me-2"></i>`;
    html += `<span>${escapeHtml(message)}</span>`;
    
    if (tooltip) {
        html += `
            <i class="bi bi-question-circle ms-2 text-muted" 
               data-bs-toggle="tooltip" 
               data-bs-placement="top" 
               title="${escapeHtml(tooltip)}"></i>
        `;
    }
    
    html += '</div>';
    return html;
}

// Create action button
function createActionButton(config) {
    const {
        text,
        onclick,
        type = 'primary',
        icon = null,
        size = '',
        outline = false,
        customClass = '',
        customStyle = ''
    } = config;
    
    const btnClass = outline ? `btn-outline-${type}` : `btn-${type}`;
    const sizeClass = size ? `btn-${size}` : '';
    
    let html = `<button class="btn ${btnClass} ${sizeClass} ${customClass}"`;
    if (onclick) html += ` onclick="${onclick}"`;
    if (customStyle) html += ` style="${customStyle}"`;
    html += '>';
    
    if (icon) {
        html += `<i class="${icon}"></i> `;
    }
    
    html += escapeHtml(text);
    html += '</button>';
    
    return html;
}

// Create button group
function createButtonGroup(buttons, spacing = 'ms-2') {
    return buttons.map((button, index) => {
        const marginClass = index > 0 ? spacing : '';
        return `<span class="${marginClass}">${createActionButton(button)}</span>`;
    }).join('');
}

// Create tab panel
function createTabPanel(id, title, icon, content, isActive = false) {
    const activeClass = isActive ? ' show active' : '';
    
    return `
        <div class="tab-pane fade${activeClass}" id="${id}" role="tabpanel">
            <div class="card shadow-sm">
                <div class="card-header ${getHeaderStyle(id)}">
                    <h5 class="mb-0"><i class="${icon}"></i> ${escapeHtml(title)}</h5>
                </div>
                <div class="card-body">
                    <div id="${id}-config-loading" class="text-center py-4">
                        ${createLoadingSpinner(getSpinnerColor(id))}
                    </div>
                    <div id="${id}-config-content" style="display: none;">
                        ${content}
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Get header style based on section
function getHeaderStyle(section) {
    const styles = {
        'app': 'bg-primary text-white',
        'ldap': 'bg-success text-white',
        'azure': 'style="background-color: #007c59; color: white;"',
        'genesys': 'style="background-color: #FF4F1F; color: white;"'
    };
    
    return styles[section] || 'bg-primary text-white';
}

// Get spinner color based on section
function getSpinnerColor(section) {
    const colors = {
        'app': 'primary',
        'ldap': 'success',
        'azure': 'primary', // Custom color handled via style
        'genesys': 'primary' // Custom color handled via style
    };
    
    return colors[section] || 'primary';
}

// Create cache status field with refresh button
function createCacheStatusField(config) {
    const { id, label, helpText } = config;
    
    return `
        <div class="col-md-6">
            <label class="form-label">${escapeHtml(label)}</label>
            <div class="input-group">
                <input type="text" class="form-control" id="${id}" readonly>
                <button class="btn btn-outline-secondary" type="button" onclick="refreshGenesysCache()">
                    <i class="bi bi-arrow-clockwise"></i> Refresh Now
                </button>
            </div>
            ${helpText ? `<small class="text-muted">${escapeHtml(helpText)}</small>` : ''}
        </div>
    `;
}

// Render application settings form
function renderApplicationSettings() {
    let html = '';
    
    // Encryption key info
    html += createAlertBanner(
        'Encryption key (WHODIS_ENCRYPTION_KEY) must stay in .env file',
        'info',
        'bi-info-circle',
        'The master encryption key cannot be stored in the database for security. Changing it will make all encrypted configuration unreadable.'
    );
    
    // Flask settings
    const flaskFields = [
        {
            key: 'flask.host',
            label: 'Flask Host',
            placeholder: '0.0.0.0',
            helpText: 'Host address for Flask server',
            colWidth: 6
        },
        {
            key: 'flask.port',
            label: 'Flask Port',
            type: 'number',
            helpText: 'Port number for Flask server',
            colWidth: 6
        }
    ];
    
    html += createFormSection('Flask Configuration', flaskFields);
    
    // Debug mode and secret key
    const securityFields = [
        {
            key: 'flask.debug',
            label: 'Debug Mode',
            type: 'select',
            options: [
                { value: 'True', label: 'Enabled' },
                { value: 'False', label: 'Disabled' }
            ],
            helpText: 'Enable debug mode (not for production)',
            colWidth: 6
        },
        {
            key: 'flask.secret_key',
            label: 'Secret Key',
            type: 'password',
            sensitive: true,
            helpText: 'Application secret key (keep secure!)',
            warningMessage: '⚠️ CRITICAL: Changing this will log out all users and invalidate all sessions. Only change if absolutely necessary.',
            colWidth: 6
        }
    ];
    
    html += createFormSection(null, securityFields);
    
    // Search settings
    const searchFields = [
        {
            key: 'search.overall_timeout',
            label: 'Overall Search Timeout (seconds)',
            type: 'number',
            helpText: 'Maximum time for all searches to complete',
            colWidth: 6
        },
        {
            key: 'search.cache_expiration_hours',
            label: 'Cache Expiration (hours)',
            type: 'number',
            helpText: 'How long to cache search results',
            colWidth: 6
        },
        {
            key: 'search.lazy_load_photos',
            label: 'Lazy Load Photos',
            type: 'select',
            options: [
                { value: 'true', label: 'Enabled (Recommended)' },
                { value: 'false', label: 'Disabled' }
            ],
            helpText: 'Load user photos after search results for better performance',
            colWidth: 6
        }
    ];
    
    html += createFormSection('Search Configuration', searchFields);
    
    // Audit settings
    const auditFields = [
        {
            key: 'audit.log_retention_days',
            label: 'Audit Log Retention (days)',
            type: 'number',
            helpText: 'Days to keep audit logs',
            colWidth: 6
        },
        {
            key: 'auth.session_timeout_minutes',
            label: 'Session Timeout (minutes)',
            type: 'number',
            helpText: 'User session timeout period',
            colWidth: 6
        }
    ];
    
    html += createFormSection('Audit Configuration', auditFields);
    
    // Save button
    html += '<div class="mt-4">';
    html += createActionButton({
        text: 'Save Application Settings',
        onclick: "saveConfiguration('app')",
        icon: 'bi bi-save'
    });
    html += '</div>';
    
    return html;
}

// Initialize tooltips after content is loaded
function initializeTooltips(container) {
    const tooltipTriggerList = container.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggerList.forEach(tooltipTriggerEl => {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Remove the local showToast function - we'll use the one from shared-utils.js
// The showToast function is now provided by shared-utils.js which is loaded before this file

// Helper function to escape HTML
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Format cache age for display
function formatCacheAge(ageString) {
    const match = ageString.match(/(\d+):(\d+):(\d+)/);
    if (match) {
        const hours = parseInt(match[1]);
        const minutes = parseInt(match[2]);
        
        if (hours > 0) {
            return `${hours}h ${minutes}m ago`;
        } else if (minutes > 0) {
            return `${minutes}m ago`;
        } else {
            return 'just now';
        }
    }
    return ageString;
}

// Load Genesys cache status
async function loadGenesysCacheStatus() {
    try {
        const response = await fetch('/admin/api/genesys/cache/status');
        const data = await response.json();
        
        const statusInput = document.getElementById('genesys-cache-status');
        if (!statusInput) return;
        
        if (data.needs_refresh) {
            statusInput.value = 'Needs refresh';
            statusInput.classList.add('text-warning');
        } else {
            const ageText = formatCacheAge(data.group_cache_age || '0:00:00');
            statusInput.value = `Last updated ${ageText}`;
            statusInput.classList.remove('text-warning');
        }
    } catch (error) {
        console.error('Error loading cache status:', error);
    }
}

// Refresh Genesys cache
async function refreshGenesysCache() {
    const button = event.target.closest('button');
    const originalHTML = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Refreshing...';
    
    try {
        const response = await fetch('/admin/api/genesys/refresh-cache', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCSRFToken()
            },
            body: JSON.stringify({ type: 'all' })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Genesys cache refreshed successfully', 'success');
            await loadGenesysCacheStatus();
        } else {
            showToast(data.error || 'Error refreshing cache', 'danger');
        }
    } catch (error) {
        console.error('Error refreshing cache:', error);
        showToast('Error refreshing cache', 'danger');
    } finally {
        button.disabled = false;
        button.innerHTML = originalHTML;
    }
}

async function refreshDataWarehouseCache() {
    const button = event.target.closest('button');
    const originalHTML = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Refreshing...';
    
    try {
        const response = await fetch('/admin/api/data-warehouse/refresh-cache', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCSRFToken()
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Data warehouse cache refreshed successfully', 'success');
            await loadDataWarehouseCacheStatus();
        } else {
            showToast(data.error || 'Error refreshing cache', 'danger');
        }
    } catch (error) {
        console.error('Error refreshing data warehouse cache:', error);
        showToast('Error refreshing data warehouse cache', 'danger');
    } finally {
        button.disabled = false;
        button.innerHTML = originalHTML;
    }
}

async function loadDataWarehouseCacheStatus() {
    try {
        const response = await fetch('/admin/api/data-warehouse/cache-status');
        const data = await response.json();
        
        const statusInput = document.getElementById('data-warehouse-cache-status');
        if (!statusInput) return;
        
        if (data.refresh_status === 'needs_refresh' || data.record_count === 0) {
            statusInput.value = 'Needs refresh';
            statusInput.classList.add('text-warning');
        } else if (data.last_updated) {
            const lastUpdate = new Date(data.last_updated);
            const now = new Date();
            const diffMs = now - lastUpdate;
            const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
            const diffMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
            
            let ageText = '';
            if (diffHours > 0) {
                ageText = `${diffHours}h ${diffMinutes}m ago`;
            } else {
                ageText = `${diffMinutes}m ago`;
            }
            
            statusInput.value = `Last updated ${ageText} (${data.record_count} records)`;
            statusInput.classList.remove('text-warning');
        }
    } catch (error) {
        console.error('Error loading data warehouse cache status:', error);
    }
}