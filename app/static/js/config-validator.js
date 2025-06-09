/**
 * Configuration Validator
 * Validation rules and functions for configuration fields
 */

// Validation rules for configuration fields
const validationRules = {
    // Flask settings
    'flask.debug': {
        type: 'boolean',
        required: true
    },
    'flask.port': {
        type: 'number',
        min: 1,
        max: 65535,
        required: false
    },
    
    // LDAP settings
    'ldap.host': {
        type: 'string',
        pattern: /^ldaps?:\/\/.+/,
        required: true,
        message: 'LDAP host must start with ldap:// or ldaps://'
    },
    'ldap.port': {
        type: 'number',
        min: 1,
        max: 65535,
        required: true
    },
    'ldap.bind_dn': {
        type: 'string',
        pattern: /^CN=.+/,
        required: true,
        message: 'Bind DN must be in format CN=...'
    },
    'ldap.base_dn': {
        type: 'string',
        pattern: /^DC=.+/,
        required: true,
        message: 'Base DN must be in format DC=...'
    },
    'ldap.user_search_base': {
        type: 'string',
        pattern: /^(OU|CN|DC)=.+/,
        required: false
    },
    'ldap.connection_timeout': {
        type: 'number',
        min: 1,
        max: 300,
        required: false
    },
    'ldap.operation_timeout': {
        type: 'number',
        min: 1,
        max: 300,
        required: false
    },
    
    // Graph API settings
    'graph.tenant_id': {
        type: 'string',
        pattern: /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/,
        required: true,
        message: 'Tenant ID must be a valid GUID'
    },
    'graph.client_id': {
        type: 'string',
        pattern: /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/,
        required: true,
        message: 'Client ID must be a valid GUID'
    },
    'graph.api_timeout': {
        type: 'number',
        min: 1,
        max: 300,
        required: false
    },
    
    // Genesys settings
    'genesys.region': {
        type: 'string',
        enum: ['mypurecloud.com', 'mypurecloud.ie', 'mypurecloud.de', 'mypurecloud.jp', 'mypurecloud.com.au', 'usw2.pure.cloud'],
        required: true
    },
    'genesys.api_timeout': {
        type: 'number',
        min: 1,
        max: 300,
        required: false
    },
    
    // Search settings
    'search.overall_timeout': {
        type: 'number',
        min: 1,
        max: 60,
        required: false
    },
    'search.lazy_load_photos': {
        type: 'boolean',
        required: false
    },
    
    // Session settings
    'session.timeout_minutes': {
        type: 'number',
        min: 1,
        max: 1440, // Max 24 hours
        required: false
    },
    'session.warning_minutes': {
        type: 'number',
        min: 1,
        max: 60,
        required: false
    },
    
    // Audit settings
    'audit.retention_days': {
        type: 'number',
        min: 1,
        max: 3650, // Max 10 years
        required: false
    }
};

// Validate a single field
function validateField(key, value) {
    const rule = validationRules[key];
    if (!rule) return { valid: true }; // No rule means valid
    
    // Check required fields
    if (rule.required && (value === null || value === undefined || value === '')) {
        return {
            valid: false,
            message: `${key} is required`
        };
    }
    
    // Empty optional fields are valid
    if (!rule.required && (value === null || value === undefined || value === '')) {
        return { valid: true };
    }
    
    // Type validation
    switch (rule.type) {
        case 'string':
            if (typeof value !== 'string') {
                return {
                    valid: false,
                    message: `${key} must be a string`
                };
            }
            break;
            
        case 'number':
            const num = Number(value);
            if (isNaN(num)) {
                return {
                    valid: false,
                    message: `${key} must be a number`
                };
            }
            if (rule.min !== undefined && num < rule.min) {
                return {
                    valid: false,
                    message: `${key} must be at least ${rule.min}`
                };
            }
            if (rule.max !== undefined && num > rule.max) {
                return {
                    valid: false,
                    message: `${key} must be at most ${rule.max}`
                };
            }
            break;
            
        case 'boolean':
            if (typeof value !== 'boolean' && value !== 'true' && value !== 'false') {
                return {
                    valid: false,
                    message: `${key} must be true or false`
                };
            }
            break;
    }
    
    // Pattern validation
    if (rule.pattern && !rule.pattern.test(value)) {
        return {
            valid: false,
            message: rule.message || `${key} has invalid format`
        };
    }
    
    // Enum validation
    if (rule.enum && !rule.enum.includes(value)) {
        return {
            valid: false,
            message: `${key} must be one of: ${rule.enum.join(', ')}`
        };
    }
    
    return { valid: true };
}

// Validate all fields in a section
function validateSection(section) {
    const errors = [];
    const fields = document.querySelectorAll(`#${section} input, #${section} select, #${section} textarea`);
    
    fields.forEach(field => {
        const key = field.getAttribute('data-key');
        if (!key) return;
        
        let value = field.value;
        
        // Handle different field types
        if (field.type === 'checkbox') {
            value = field.checked;
        } else if (field.type === 'number') {
            value = value ? parseInt(value) : null;
        }
        
        // Skip encrypted fields that haven't been changed
        const isSensitive = field.getAttribute('data-sensitive') === 'true';
        if (isSensitive && value === '••••••••') {
            return;
        }
        
        const validation = validateField(key, value);
        if (!validation.valid) {
            errors.push({
                field: field,
                key: key,
                message: validation.message
            });
            
            // Add visual feedback
            field.classList.add('is-invalid');
            
            // Add or update error message
            let feedback = field.parentElement.querySelector('.invalid-feedback');
            if (!feedback) {
                feedback = document.createElement('div');
                feedback.className = 'invalid-feedback';
                field.parentElement.appendChild(feedback);
            }
            feedback.textContent = validation.message;
        } else {
            // Remove visual feedback if valid
            field.classList.remove('is-invalid');
            const feedback = field.parentElement.querySelector('.invalid-feedback');
            if (feedback) {
                feedback.remove();
            }
        }
    });
    
    return errors;
}

// Clear all validation errors
function clearValidationErrors() {
    document.querySelectorAll('.is-invalid').forEach(field => {
        field.classList.remove('is-invalid');
    });
    document.querySelectorAll('.invalid-feedback').forEach(feedback => {
        feedback.remove();
    });
}

// Add real-time validation
function enableRealTimeValidation() {
    document.querySelectorAll('input[data-key], select[data-key], textarea[data-key]').forEach(field => {
        field.addEventListener('blur', function() {
            const key = this.getAttribute('data-key');
            let value = this.value;
            
            if (this.type === 'checkbox') {
                value = this.checked;
            } else if (this.type === 'number') {
                value = value ? parseInt(value) : null;
            }
            
            const validation = validateField(key, value);
            
            if (!validation.valid) {
                this.classList.add('is-invalid');
                
                let feedback = this.parentElement.querySelector('.invalid-feedback');
                if (!feedback) {
                    feedback = document.createElement('div');
                    feedback.className = 'invalid-feedback';
                    this.parentElement.appendChild(feedback);
                }
                feedback.textContent = validation.message;
            } else {
                this.classList.remove('is-invalid');
                const feedback = this.parentElement.querySelector('.invalid-feedback');
                if (feedback) {
                    feedback.remove();
                }
            }
        });
    });
}