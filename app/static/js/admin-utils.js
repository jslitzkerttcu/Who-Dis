/**
 * Admin Panel Utility Functions
 * Consolidates common functionality used across admin templates
 */

// ===== Event Handler Management =====

/**
 * Attach event listeners to dynamically created elements
 * @param {string} selector - CSS selector for elements
 * @param {string} event - Event type (e.g., 'click')
 * @param {function} handler - Event handler function
 * @param {Element} container - Container element (defaults to document)
 */
function attachEventListener(selector, event, handler, container = document) {
    container.addEventListener(event, function(e) {
        const target = e.target.closest(selector);
        if (target) {
            handler.call(target, e);
        }
    });
}

/**
 * Safe element creation with text content
 * @param {string} tag - HTML tag name
 * @param {object} attrs - Attributes to set
 * @param {string} text - Text content (will be escaped)
 * @returns {HTMLElement} - Created element
 */
function createElement(tag, attrs = {}, text = '') {
    const element = document.createElement(tag);
    
    // Set attributes
    Object.entries(attrs).forEach(([key, value]) => {
        if (key === 'className') {
            element.className = value;
        } else if (key === 'dataset') {
            Object.entries(value).forEach(([dataKey, dataValue]) => {
                element.dataset[dataKey] = dataValue;
            });
        } else if (key.startsWith('aria') || key === 'role') {
            element.setAttribute(key, value);
        } else {
            element[key] = value;
        }
    });
    
    // Set text content (automatically escaped)
    if (text) {
        element.textContent = text;
    }
    
    return element;
}

/**
 * Safely update element content
 * @param {string|Element} element - Element or selector
 * @param {string} content - Content to set (will be escaped)
 * @param {boolean} isHtml - Whether to treat content as HTML (use with caution)
 */
function updateContent(element, content, isHtml = false) {
    const el = typeof element === 'string' ? document.querySelector(element) : element;
    if (!el) return;
    
    if (isHtml) {
        // Only use for trusted content
        el.innerHTML = content;
    } else {
        el.textContent = content;
    }
}

/**
 * Create a safe HTML template
 * @param {string} template - Template string with placeholders
 * @param {object} data - Data to interpolate (will be escaped)
 * @returns {string} - Safe HTML string
 */
function createTemplate(template, data) {
    return template.replace(/\{\{(\w+)\}\}/g, (match, key) => {
        return escapeHtml(data[key] || '');
    });
}

// ===== Table Creation Utilities =====

/**
 * Create a table row with proper escaping
 * @param {array} cells - Array of cell data
 * @param {object} options - Options for row creation
 * @returns {HTMLElement} - Table row element
 */
function createTableRow(cells, options = {}) {
    const tr = createElement('tr', { className: options.className || '' });
    
    cells.forEach((cell, index) => {
        const td = createElement('td');
        
        if (typeof cell === 'object' && cell.html) {
            // For trusted HTML content only
            td.innerHTML = cell.html;
        } else if (typeof cell === 'object' && cell.element) {
            // For DOM elements
            td.appendChild(cell.element);
        } else {
            // Default: escape text content
            td.textContent = String(cell);
        }
        
        tr.appendChild(td);
    });
    
    return tr;
}

/**
 * Create action buttons for table rows
 * @param {array} actions - Array of action definitions
 * @returns {HTMLElement} - Container with buttons
 */
function createActionButtons(actions) {
    const container = createElement('div', { className: 'btn-group btn-group-sm' });
    
    actions.forEach(action => {
        const btn = createElement('button', {
            className: `btn ${action.className || 'btn-outline-primary'}`,
            type: 'button',
            'aria-label': action.label,
            dataset: action.data || {}
        }, action.text);
        
        // Add icon if provided
        if (action.icon) {
            const icon = createElement('i', { className: action.icon });
            btn.prepend(icon);
            btn.prepend(' ');
        }
        
        container.appendChild(btn);
    });
    
    return container;
}

// ===== Modal Management =====

/**
 * Create and show a confirmation modal
 * @param {object} options - Modal options
 * @returns {Promise} - Resolves to true if confirmed, false otherwise
 */
function showConfirmModal(options) {
    return new Promise((resolve) => {
        const modalId = 'confirmModal-' + Date.now();
        
        // Create modal HTML
        const modalHtml = `
            <div class="modal fade" id="${modalId}" tabindex="-1" aria-labelledby="${modalId}Label" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="${modalId}Label">${escapeHtml(options.title || 'Confirm Action')}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            ${escapeHtml(options.message || 'Are you sure?')}
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                ${escapeHtml(options.cancelText || 'Cancel')}
                            </button>
                            <button type="button" class="btn ${options.confirmClass || 'btn-primary'}" id="${modalId}Confirm">
                                ${escapeHtml(options.confirmText || 'Confirm')}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Add to body
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        const modalElement = document.getElementById(modalId);
        const modal = new bootstrap.Modal(modalElement);
        
        // Handle confirm button
        document.getElementById(`${modalId}Confirm`).addEventListener('click', () => {
            modal.hide();
            resolve(true);
        });
        
        // Handle modal hidden event
        modalElement.addEventListener('hidden.bs.modal', () => {
            modalElement.remove();
            resolve(false);
        });
        
        // Show modal
        modal.show();
    });
}

// ===== Form Utilities =====

/**
 * Add ARIA labels to form elements
 * @param {HTMLElement} form - Form element
 */
function enhanceFormAccessibility(form) {
    // Add labels to inputs without them
    form.querySelectorAll('input, select, textarea').forEach(field => {
        if (!field.getAttribute('aria-label') && !field.getAttribute('aria-labelledby')) {
            // Try to find associated label
            const label = form.querySelector(`label[for="${field.id}"]`);
            if (label) {
                field.setAttribute('aria-labelledby', label.id);
            } else if (field.placeholder) {
                field.setAttribute('aria-label', field.placeholder);
            } else if (field.name) {
                field.setAttribute('aria-label', field.name.replace(/_/g, ' '));
            }
        }
    });
    
    // Add role to buttons without text
    form.querySelectorAll('button').forEach(button => {
        if (!button.textContent.trim() && !button.getAttribute('aria-label')) {
            const icon = button.querySelector('i');
            if (icon) {
                const iconClass = icon.className;
                if (iconClass.includes('search')) button.setAttribute('aria-label', 'Search');
                else if (iconClass.includes('plus')) button.setAttribute('aria-label', 'Add');
                else if (iconClass.includes('trash')) button.setAttribute('aria-label', 'Delete');
                else if (iconClass.includes('edit')) button.setAttribute('aria-label', 'Edit');
            }
        }
    });
}

/**
 * Serialize form data to object
 * @param {HTMLFormElement} form - Form element
 * @returns {object} - Form data as object
 */
function serializeForm(form) {
    const formData = new FormData(form);
    const data = {};
    
    for (const [key, value] of formData.entries()) {
        data[key] = value;
    }
    
    return data;
}

// ===== Loading State Management =====

/**
 * Show loading state for an element
 * @param {string|Element} element - Element or selector
 * @param {string} message - Loading message
 */
function showLoading(element, message = 'Loading...') {
    const el = typeof element === 'string' ? document.querySelector(element) : element;
    if (!el) return;
    
    el.dataset.originalContent = el.innerHTML;
    el.innerHTML = createLoadingSpinner(message).outerHTML;
    el.disabled = true;
}

/**
 * Hide loading state for an element
 * @param {string|Element} element - Element or selector
 */
function hideLoading(element) {
    const el = typeof element === 'string' ? document.querySelector(element) : element;
    if (!el || !el.dataset.originalContent) return;
    
    el.innerHTML = el.dataset.originalContent;
    delete el.dataset.originalContent;
    el.disabled = false;
}

// ===== Pagination Utilities =====

/**
 * Create pagination controls
 * @param {object} options - Pagination options
 * @returns {HTMLElement} - Pagination element
 */
function createPagination(options) {
    const { currentPage, totalPages, onPageChange } = options;
    
    const nav = createElement('nav', { 'aria-label': 'Page navigation' });
    const ul = createElement('ul', { className: 'pagination justify-content-center' });
    
    // Previous button
    const prevLi = createElement('li', { 
        className: `page-item ${currentPage === 1 ? 'disabled' : ''}` 
    });
    const prevLink = createElement('a', {
        className: 'page-link',
        href: '#',
        'aria-label': 'Previous page',
        tabindex: currentPage === 1 ? '-1' : '0'
    }, '← Previous');
    prevLi.appendChild(prevLink);
    ul.appendChild(prevLi);
    
    // Page numbers
    const maxVisible = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);
    
    if (endPage - startPage + 1 < maxVisible) {
        startPage = Math.max(1, endPage - maxVisible + 1);
    }
    
    for (let i = startPage; i <= endPage; i++) {
        const li = createElement('li', {
            className: `page-item ${i === currentPage ? 'active' : ''}`
        });
        const link = createElement('a', {
            className: 'page-link',
            href: '#',
            'aria-label': `Go to page ${i}`,
            'aria-current': i === currentPage ? 'page' : null
        }, String(i));
        li.appendChild(link);
        ul.appendChild(li);
    }
    
    // Next button
    const nextLi = createElement('li', {
        className: `page-item ${currentPage === totalPages ? 'disabled' : ''}`
    });
    const nextLink = createElement('a', {
        className: 'page-link',
        href: '#',
        'aria-label': 'Next page',
        tabindex: currentPage === totalPages ? '-1' : '0'
    }, 'Next →');
    nextLi.appendChild(nextLink);
    ul.appendChild(nextLi);
    
    nav.appendChild(ul);
    
    // Add event listeners using delegation
    nav.addEventListener('click', (e) => {
        e.preventDefault();
        const link = e.target.closest('.page-link');
        if (!link || link.closest('.disabled')) return;
        
        let newPage;
        if (link.textContent.includes('Previous')) {
            newPage = currentPage - 1;
        } else if (link.textContent.includes('Next')) {
            newPage = currentPage + 1;
        } else {
            newPage = parseInt(link.textContent);
        }
        
        if (newPage >= 1 && newPage <= totalPages && newPage !== currentPage) {
            onPageChange(newPage);
        }
    });
    
    return nav;
}

// ===== Loading State Management =====

/**
 * Show loading state in an element
 * @param {HTMLElement} element - Element to show loading in
 * @param {string} message - Loading message
 */
function showLoading(element, message = 'Loading...') {
    if (!element) return;
    
    const spinner = createLoadingSpinner(message);
    element.innerHTML = '';
    element.appendChild(spinner);
}

/**
 * Hide loading state and clear element
 * @param {HTMLElement} element - Element to hide loading from
 */
function hideLoading(element) {
    if (!element) return;
    
    // Only clear if it contains our loading spinner
    const spinner = element.querySelector('.spinner-border');
    if (spinner) {
        element.innerHTML = '';
    }
}

// ===== Error Handling =====

/**
 * Display API error message
 * @param {Error|string} error - Error object or message
 * @param {string} context - Context for the error
 */
function displayError(error, context = '') {
    console.error(`${context} error:`, error);
    
    let message = 'An error occurred';
    if (error.message) {
        message = error.message;
    } else if (typeof error === 'string') {
        message = error;
    }
    
    showToast(`${context}: ${message}`, true);
}

// ===== Export utilities from shared-utils.js =====
// Make sure shared utilities are available globally
if (typeof escapeHtml === 'undefined' && typeof window !== 'undefined') {
    console.warn('admin-utils.js: shared-utils.js should be loaded before admin-utils.js');
}