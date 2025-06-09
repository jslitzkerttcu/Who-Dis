/**
 * Security utilities for XSS prevention
 */

// Enhanced escapeHtml function (if not already defined)
if (typeof escapeHtml === 'undefined') {
    function escapeHtml(text) {
        if (text === null || text === undefined) {
            return '';
        }
        const div = document.createElement('div');
        div.textContent = String(text);
        return div.innerHTML;
    }
}

/**
 * Safely render user data with HTML escaping
 * @param {any} value - The value to escape
 * @param {string} defaultValue - Default value if value is null/undefined
 * @returns {string} - Escaped HTML string
 */
function safeHtml(value, defaultValue = '') {
    if (value === null || value === undefined || value === '') {
        return defaultValue;
    }
    return escapeHtml(value);
}

/**
 * Render user field with optional default
 * @param {any} value - The value to render
 * @param {string} defaultHtml - Default HTML if value is empty (not escaped)
 * @returns {string} - Safe HTML string
 */
function renderField(value, defaultHtml = '<span class="text-muted">-</span>') {
    if (value === null || value === undefined || value === '') {
        return defaultHtml;
    }
    return escapeHtml(value);
}

/**
 * Safely join multiple values with a separator
 * @param {array} values - Array of values to join
 * @param {string} separator - Separator string
 * @returns {string} - Escaped joined string
 */
function safeJoin(values, separator = ', ') {
    return values
        .filter(v => v !== null && v !== undefined && v !== '')
        .map(v => escapeHtml(v))
        .join(separator);
}

/**
 * Create a safe template literal function
 * Usage: safeHtml`<div>${userInput}</div>`
 */
function safeTemplate(strings, ...values) {
    let result = strings[0];
    for (let i = 0; i < values.length; i++) {
        result += escapeHtml(values[i]) + strings[i + 1];
    }
    return result;
}

/**
 * Get CSRF token from cookie for double-submit pattern
 * This is the secure way to handle CSRF tokens - never expose them in DOM
 */
function getCSRFToken() {
    // Get token from cookie
    const cookies = document.cookie.split(';');
    console.log('getCSRFToken: Checking', cookies.length, 'cookies');
    
    for (let cookie of cookies) {
        const trimmedCookie = cookie.trim();
        console.log('getCSRFToken: Processing cookie:', trimmedCookie);
        
        const equalIndex = trimmedCookie.indexOf('=');
        if (equalIndex === -1) {
            console.log('getCSRFToken: No = found in cookie');
            continue;
        }
        
        const name = trimmedCookie.substring(0, equalIndex);
        const value = trimmedCookie.substring(equalIndex + 1);
        
        console.log('getCSRFToken: Cookie name:', name, 'matches _csrf_token?', name === '_csrf_token');
        
        if (name === '_csrf_token') {
            console.log('getCSRFToken: Found CSRF token, returning value');
            return value; // Don't decode - the token is not URL encoded
        }
    }
    console.log('getCSRFToken: No CSRF token found');
    return '';
}