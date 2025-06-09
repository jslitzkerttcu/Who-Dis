/**
 * Admin Error Logs JavaScript
 * Handles error log viewing and filtering
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize error logs management
    initializeErrorLogs();
    
    // Set up event listeners
    setupEventListeners();
    
    // Load initial data
    loadErrors();
});

function initializeErrorLogs() {
    // Set default filter values if needed
    console.log('Error logs management initialized');
}

function setupEventListeners() {
    // Filter button
    attachEventListener('[data-action="apply-filters"]', 'click', handleApplyFilters);
    
    // Error detail buttons (delegated)
    attachEventListener('[data-action="view-error-details"]', 'click', handleViewErrorDetails);
}

// ===== Error Loading =====

async function loadErrors() {
    const loadingEl = document.getElementById('errors-loading');
    const contentEl = document.getElementById('errors-content');
    
    // Show loading state
    if (loadingEl) loadingEl.style.display = 'block';
    if (contentEl) contentEl.style.display = 'none';
    
    try {
        const filters = gatherFilters();
        const params = new URLSearchParams(filters);
        
        const response = await authenticatedFetch('/admin/api/errors?' + params);
        const data = await handleApiResponse(response);
        
        displayErrors(data.errors || []);
        
    } catch (error) {
        displayError(error, 'Failed to load error logs');
        displayErrorsError('Failed to load error logs. The irony is not lost on us.');
    } finally {
        // Hide loading state
        if (loadingEl) loadingEl.style.display = 'none';
        if (contentEl) contentEl.style.display = 'block';
    }
}

function gatherFilters() {
    const severityFilter = document.getElementById('severity-filter');
    const dateFilter = document.getElementById('date-filter');
    
    const filters = {};
    
    if (severityFilter && severityFilter.value) {
        filters.severity = severityFilter.value;
    }
    
    if (dateFilter && dateFilter.value) {
        filters.hours = dateFilter.value;
    }
    
    return filters;
}

// ===== Display Functions =====

function displayErrors(errors) {
    const tbody = document.getElementById('errors-tbody');
    const noErrorsEl = document.getElementById('no-errors');
    const tableContainer = tbody?.parentElement?.parentElement;
    
    if (!tbody) return;
    
    // Clear existing content
    tbody.innerHTML = '';
    
    if (errors.length === 0) {
        if (noErrorsEl) noErrorsEl.style.display = 'block';
        if (tableContainer) tableContainer.style.display = 'none';
        return;
    }
    
    // Show table, hide no errors message
    if (noErrorsEl) noErrorsEl.style.display = 'none';
    if (tableContainer) tableContainer.style.display = 'block';
    
    errors.forEach(error => {
        const row = createErrorRow(error);
        tbody.appendChild(row);
    });
}

function createErrorRow(error) {
    const row = createElement('tr', { dataset: { errorId: error.id } });
    
    // Timestamp cell
    const timestampCell = createElement('td');
    const timestamp = new Date(error.timestamp);
    const timeStr = timestamp.toLocaleString();
    timestampCell.textContent = timeStr;
    
    // Error type cell
    const typeCell = createElement('td');
    const typeBadge = createElement('span', {
        className: `badge ${getSeverityBadgeClass(error.severity || 'error')}`
    }, error.error_type || 'Unknown');
    typeCell.appendChild(typeBadge);
    
    // Message cell
    const messageCell = createElement('td');
    const messageText = error.error_message || error.message || 'No message';
    // Truncate long messages
    const truncatedMessage = messageText.length > 100 
        ? messageText.substring(0, 100) + '...' 
        : messageText;
    messageCell.textContent = truncatedMessage;
    messageCell.title = messageText; // Full message on hover
    
    // User cell
    const userCell = createElement('td', {}, error.user_email || '-');
    
    // Actions cell
    const actionsCell = createElement('td');
    const detailsButton = createElement('button', {
        className: 'btn btn-sm btn-outline-primary',
        type: 'button',
        dataset: { 
            action: 'view-error-details',
            errorData: JSON.stringify(error)
        },
        'aria-label': 'View error details'
    });
    
    const icon = createElement('i', { className: 'bi bi-eye' });
    detailsButton.appendChild(icon);
    actionsCell.appendChild(detailsButton);
    
    // Append all cells
    row.appendChild(timestampCell);
    row.appendChild(typeCell);
    row.appendChild(messageCell);
    row.appendChild(userCell);
    row.appendChild(actionsCell);
    
    return row;
}

function displayErrorsError(message) {
    const tbody = document.getElementById('errors-tbody');
    const noErrorsEl = document.getElementById('no-errors');
    const tableContainer = tbody?.parentElement?.parentElement;
    
    if (noErrorsEl) noErrorsEl.style.display = 'none';
    if (tableContainer) tableContainer.style.display = 'block';
    
    if (tbody) {
        const row = createElement('tr');
        const cell = createElement('td', {
            className: 'text-center text-danger',
            colspan: '5'
        });
        cell.innerHTML = `<i class="bi bi-exclamation-triangle"></i> ${escapeHtml(message)}`;
        row.appendChild(cell);
        tbody.innerHTML = '';
        tbody.appendChild(row);
    }
}

// ===== Helper Functions =====

function getSeverityBadgeClass(severity) {
    const classes = {
        'critical': 'bg-danger',
        'error': 'bg-warning text-dark',
        'warning': 'bg-info',
        'info': 'bg-secondary'
    };
    return classes[severity?.toLowerCase()] || 'bg-secondary';
}

// ===== Event Handlers =====

function handleApplyFilters(e) {
    e.preventDefault();
    loadErrors();
}

function handleViewErrorDetails(e) {
    e.preventDefault();
    
    try {
        const errorData = JSON.parse(this.dataset.errorData);
        showErrorDetailsModal(errorData);
    } catch (error) {
        console.error('Failed to parse error data:', error);
        showToast('Failed to load error details', true);
    }
}

// ===== Error Details Modal =====

function showErrorDetailsModal(error) {
    // Update modal content
    populateErrorModal(error);
    
    // Show modal
    const modalEl = document.getElementById('errorModal');
    if (modalEl) {
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
    }
}

function populateErrorModal(error) {
    // Update timestamp
    const timestampEl = document.getElementById('modal-timestamp');
    if (timestampEl) {
        timestampEl.textContent = new Date(error.timestamp).toLocaleString();
    }
    
    // Update error type
    const typeEl = document.getElementById('modal-type');
    if (typeEl) {
        typeEl.textContent = error.error_type || 'Unknown';
    }
    
    // Update user
    const userEl = document.getElementById('modal-user');
    if (userEl) {
        userEl.textContent = error.user_email || 'Unknown';
    }
    
    // Update IP address
    const ipEl = document.getElementById('modal-ip');
    if (ipEl) {
        ipEl.textContent = error.ip_address || 'Unknown';
    }
    
    // Update user agent
    const agentEl = document.getElementById('modal-agent');
    if (agentEl) {
        agentEl.textContent = error.user_agent || 'Unknown';
    }
    
    // Update error message
    const messageEl = document.getElementById('modal-message');
    if (messageEl) {
        messageEl.textContent = error.error_message || error.message || 'No message';
    }
    
    // Update stack trace
    const stackEl = document.getElementById('modal-stack');
    if (stackEl) {
        if (error.stack_trace || error.stackTrace) {
            stackEl.textContent = error.stack_trace || error.stackTrace;
            stackEl.style.display = 'block';
            const stackContainer = stackEl.parentElement;
            if (stackContainer) stackContainer.style.display = 'block';
        } else {
            const stackContainer = stackEl.parentElement;
            if (stackContainer) stackContainer.style.display = 'none';
        }
    }
    
    // Update additional data
    const additionalEl = document.getElementById('modal-additional');
    if (additionalEl) {
        let additionalData = {};
        
        // Try to parse additional data
        if (error.additional_data) {
            try {
                additionalData = typeof error.additional_data === 'string' 
                    ? JSON.parse(error.additional_data)
                    : error.additional_data;
            } catch (e) {
                additionalData = { raw: error.additional_data };
            }
        }
        
        // Add other fields that might be useful
        ['url', 'method', 'params', 'headers'].forEach(field => {
            if (error[field]) {
                additionalData[field] = error[field];
            }
        });
        
        if (Object.keys(additionalData).length > 0) {
            additionalEl.textContent = JSON.stringify(additionalData, null, 2);
            additionalEl.style.display = 'block';
            const additionalContainer = additionalEl.parentElement;
            if (additionalContainer) additionalContainer.style.display = 'block';
        } else {
            const additionalContainer = additionalEl.parentElement;
            if (additionalContainer) additionalContainer.style.display = 'none';
        }
    }
}

// Make loadErrors available globally for the filter button
window.loadErrors = loadErrors;