/**
 * Shared Utility Functions
 * Consolidates common functionality used across the application
 */

// ===== SECURITY UTILITIES =====

/**
 * Escape HTML to prevent XSS attacks
 * @param {any} text - Text to escape
 * @returns {string} - Escaped HTML string
 */
function escapeHtml(text) {
    if (text === null || text === undefined) {
        return '';
    }
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

/**
 * Get CSRF token from cookie for double-submit pattern
 * @returns {string} - CSRF token value
 */
function getCSRFToken() {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'whodis-csrf-token') {
            return decodeURIComponent(value);
        }
    }
    return '';
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

// ===== FORMATTING UTILITIES =====

/**
 * Format phone numbers consistently
 * @param {string} phone - Phone number to format
 * @returns {string} - Formatted phone number
 */
function formatPhoneNumber(phone) {
    if (!phone) return phone;

    // Remove all non-digits
    const cleaned = phone.replace(/\D/g, '');

    // If it's a 4-digit extension, leave it as is
    if (cleaned.length === 4) {
        return cleaned;
    }

    // Handle 10-digit numbers (add US country code)
    if (cleaned.length === 10) {
        return `+1 ${cleaned.substr(0, 3)}-${cleaned.substr(3, 3)}-${cleaned.substr(6, 4)}`;
    }

    // Handle 11-digit numbers starting with 1
    if (cleaned.length === 11 && cleaned.startsWith('1')) {
        return `+1 ${cleaned.substr(1, 3)}-${cleaned.substr(4, 3)}-${cleaned.substr(7, 4)}`;
    }

    // Handle numbers that already have country code
    if (cleaned.length === 11) {
        return `+${cleaned.substr(0, 1)} ${cleaned.substr(1, 3)}-${cleaned.substr(4, 3)}-${cleaned.substr(7, 4)}`;
    }

    // For any other format, try to parse what we can
    if (cleaned.length > 10) {
        const countryCode = cleaned.substr(0, cleaned.length - 10);
        const areaCode = cleaned.substr(-10, 3);
        const prefix = cleaned.substr(-7, 3);
        const lineNumber = cleaned.substr(-4, 4);
        return `+${countryCode} ${areaCode}-${prefix}-${lineNumber}`;
    }

    // Return original if we can't format it
    return phone;
}

/**
 * Format date with smart relative time display
 * @param {string|Date} dateValue - Date to format
 * @param {string} label - Label for the date field
 * @param {boolean} showDaysInfo - Whether to show relative days
 * @returns {object} - Formatted date components
 */
function formatDateInfo(dateValue, label, showDaysInfo = true) {
    if (!dateValue) return null;

    const date = new Date(dateValue);
    const now = new Date();

    // Format date as M/D/YYYY
    const dateStr = `${date.getMonth() + 1}/${date.getDate()}/${date.getFullYear()}`;

    // Format time in 24-hour format without seconds
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    const timeStr = `${hours}:${minutes}`;

    // Calculate smart date difference
    let daysInfo = '';
    let daysClass = '';
    if (showDaysInfo) {
        // Calculate time difference in milliseconds
        const timeDiff = date - now;
        const msPerDay = 1000 * 60 * 60 * 24;

        // Check if dates are on the same day
        const dateDay = date.toDateString();
        const nowDay = now.toDateString();
        const isToday = dateDay === nowDay;

        // Calculate difference in days
        const daysDiff = timeDiff < 0 ? Math.ceil(timeDiff / msPerDay) : Math.floor(timeDiff / msPerDay);
        const absDays = Math.abs(daysDiff);

        // For very recent dates, show hours
        const absHours = Math.abs(timeDiff) / (1000 * 60 * 60);

        // Calculate years, months, and remaining days
        const years = Math.floor(absDays / 365);
        const months = Math.floor((absDays % 365) / 30);
        const days = absDays % 30;

        // Build the string based on what's significant
        let parts = [];
        if (isToday) {
            if (absHours < 1) {
                const minutes = Math.floor(Math.abs(timeDiff) / (1000 * 60));
                parts.push(`${minutes}m`);
            } else if (absHours < 24) {
                parts.push(`${Math.floor(absHours)}h`);
            }
        } else if (years > 0) {
            parts.push(`${years}Yr`);
            if (months > 0) {
                parts.push(`${months}Mo`);
            }
        } else if (months > 0) {
            parts.push(`${months}Mo`);
            if (days > 0 && months < 3) {
                parts.push(`${days}d`);
            }
        } else if (absDays > 0) {
            parts.push(`${absDays}d`);
        }

        // Format based on past or future
        if (timeDiff < 0) {
            daysInfo = isToday ? (parts.length > 0 ? parts.join(' ') + ' ago' : 'Today') : parts.join(' ') + ' ago';
        } else if (isToday) {
            daysInfo = parts.length > 0 ? 'in ' + parts.join(' ') : 'Today';
        } else {
            daysInfo = 'in ' + parts.join(' ');
            // Add color classes for expiration warnings
            if (label.includes('Expires')) {
                if (daysDiff < 7) daysClass = 'text-danger';
                else if (daysDiff < 30) daysClass = 'text-warning';
            }
        }
    }

    return { label, dateStr, timeStr, daysInfo, daysClass };
}

/**
 * Simple date formatter for tables and lists
 * @param {string|Date} dateValue - Date to format
 * @returns {string} - Formatted date string
 */
function formatDate(dateValue) {
    if (!dateValue) return '-';
    const date = new Date(dateValue);
    return `${date.getMonth() + 1}/${date.getDate()}/${date.getFullYear()} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
}

// ===== UI UTILITIES =====

/**
 * Show toast notification
 * @param {string} message - Message to display
 * @param {string|boolean} typeOrIsError - Bootstrap color type ('success', 'danger', 'warning', 'info') or boolean for backward compatibility
 */
function showToast(message, typeOrIsError = 'success') {
    // Handle backward compatibility - if boolean is passed, convert to type
    let type;
    if (typeof typeOrIsError === 'boolean') {
        type = typeOrIsError ? 'danger' : 'success';
    } else {
        type = typeOrIsError || 'success';
    }
    
    // Find or create toast container
    let toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toastContainer';
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        toastContainer.style.zIndex = '1050';
        document.body.appendChild(toastContainer);
    }

    // Determine background color and text color based on type
    let bgClass = 'bg-' + type;
    let textClass = 'text-white';
    
    // Warning toasts should have dark text
    if (type === 'warning') {
        textClass = 'text-dark';
    }

    // Create toast element
    const toastId = 'toast-' + Date.now();
    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center ${textClass} ${bgClass} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    ${escapeHtml(message)}
                </div>
                <button type="button" class="btn-close ${type === 'warning' ? '' : 'btn-close-white'} me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;

    // Add to container
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);

    // Show toast
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, { autohide: true, delay: 3000 });
    toast.show();

    // Remove from DOM after hidden
    toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
    });
}

/**
 * Create loading spinner
 * @param {string} message - Loading message
 * @returns {HTMLElement} - Spinner element
 */
function createLoadingSpinner(message = 'Loading...') {
    const spinner = document.createElement('div');
    spinner.className = 'text-center p-4';
    spinner.innerHTML = `
        <div class="spinner-border text-primary" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
        <p class="mt-2">${escapeHtml(message)}</p>
    `;
    return spinner;
}

// ===== AJAX UTILITIES =====

/**
 * Make an authenticated AJAX request
 * @param {string} url - Request URL
 * @param {object} options - Fetch options
 * @returns {Promise} - Fetch promise
 */
async function authenticatedFetch(url, options = {}) {
    // Add CSRF token to headers
    options.headers = options.headers || {};
    options.headers['X-CSRF-Token'] = getCSRFToken();
    
    // Add content type for JSON requests
    if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(options.body);
    }
    
    return fetch(url, options);
}

/**
 * Handle API response with error checking
 * @param {Response} response - Fetch response
 * @returns {Promise} - Parsed response data
 */
async function handleApiResponse(response) {
    const data = await response.json();
    
    if (!response.ok) {
        throw new Error(data.error || data.message || 'Request failed');
    }
    
    return data;
}

// ===== VALIDATION UTILITIES =====

/**
 * Validate email address
 * @param {string} email - Email to validate
 * @returns {boolean} - Whether email is valid
 */
function isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

/**
 * Validate phone number (basic check)
 * @param {string} phone - Phone to validate
 * @returns {boolean} - Whether phone is valid
 */
function isValidPhone(phone) {
    const cleaned = phone.replace(/\D/g, '');
    return cleaned.length >= 10;
}

// ===== EXPORT FOR MODULE SYSTEMS (if using) =====
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        escapeHtml,
        getCSRFToken,
        safeHtml,
        renderField,
        formatPhoneNumber,
        formatDateInfo,
        formatDate,
        showToast,
        createLoadingSpinner,
        authenticatedFetch,
        handleApiResponse,
        isValidEmail,
        isValidPhone
    };
}