/**
 * Admin Audit Logs JavaScript
 * Handles audit log viewing, filtering, and pagination
 */

let currentPage = 1;
let pageSize = 50;

document.addEventListener('DOMContentLoaded', function() {
    // Initialize audit logs management
    initializeAuditLogs();
    
    // Set up event listeners
    setupEventListeners();
    
    // Load initial data
    loadFilters();
    loadLogs(1);
});

function initializeAuditLogs() {
    // Set default date range (last 7 days)
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - 7);
    
    // Set datetime-local input values
    const startInput = document.getElementById('startDate');
    const endInput = document.getElementById('endDate');
    
    if (startInput) {
        startInput.value = formatDateForInput(startDate);
    }
    if (endInput) {
        endInput.value = formatDateForInput(endDate);
    }
}

function setupEventListeners() {
    // Filter form
    const filterForm = document.getElementById('filterForm');
    if (filterForm) {
        filterForm.addEventListener('submit', handleFilterSubmit);
    }
    
    // Reset filters button
    const resetButton = document.getElementById('resetFilters');
    if (resetButton) {
        resetButton.addEventListener('click', handleResetFilters);
    }
    
    // Pagination (delegated)
    attachEventListener('[data-action="load-page"]', 'click', handlePageClick);
    
    // Details view (delegated)
    attachEventListener('[data-action="view-details"]', 'click', handleViewDetails);
}

// ===== Data Loading =====

async function loadFilters() {
    try {
        const response = await authenticatedFetch('/admin/api/audit-logs/filters');
        const data = await handleApiResponse(response);
        
        populateFilterOptions(data);
        
    } catch (error) {
        console.error('Failed to load filter options:', error);
    }
}

function populateFilterOptions(data) {
    // Populate event types
    const eventTypeSelect = document.getElementById('eventType');
    if (eventTypeSelect && data.event_types) {
        data.event_types.forEach(type => {
            const option = createElement('option', { value: type }, formatEventType(type));
            eventTypeSelect.appendChild(option);
        });
    }
    
    // Populate users
    const userSelect = document.getElementById('userEmail');
    if (userSelect && data.users) {
        data.users.forEach(user => {
            const option = createElement('option', { value: user }, user);
            userSelect.appendChild(option);
        });
    }
}

async function loadLogs(page = 1) {
    currentPage = page;
    const tbody = document.getElementById('logsTableBody');
    
    // Show loading state
    if (tbody) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">Loading...</td></tr>';
    }
    
    try {
        const filters = gatherFilters();
        const params = {
            ...filters,
            page: page,
            per_page: pageSize
        };
        
        const response = await authenticatedFetch('/admin/api/audit-logs?' + new URLSearchParams(params));
        const data = await handleApiResponse(response);
        
        displayLogs(data.logs);
        updatePagination(data.total, page);
        updateResultInfo(data.total, data.offset, data.logs.length);
        
    } catch (error) {
        displayError(error, 'Failed to load audit logs');
        displayLogsError('Failed to load audit logs');
    }
}

function gatherFilters() {
    const form = document.getElementById('filterForm');
    if (!form) return {};
    
    const formData = new FormData(form);
    const filters = {};
    
    for (const [key, value] of formData.entries()) {
        if (value.trim()) {
            filters[key] = value.trim();
        }
    }
    
    return filters;
}

// ===== Display Functions =====

function displayLogs(logs) {
    const tbody = document.getElementById('logsTableBody');
    if (!tbody) return;
    
    if (logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">No audit logs found</td></tr>';
        return;
    }
    
    // Clear existing content
    tbody.innerHTML = '';
    
    logs.forEach(log => {
        const row = createLogRow(log);
        tbody.appendChild(row);
    });
}

function createLogRow(log) {
    const row = createElement('tr', { dataset: { logId: log.id } });
    
    // Timestamp cell
    const timestampCell = createElement('td', {}, new Date(log.timestamp).toLocaleString());
    
    // Event type cell
    const eventTypeCell = createElement('td');
    const eventBadge = createElement('span', {
        className: `badge ${getBadgeClass(log.event_type)}`
    }, formatEventType(log.event_type));
    eventTypeCell.appendChild(eventBadge);
    
    // User cell
    const userCell = createElement('td', {}, log.user_email || '-');
    
    // Action cell
    const actionCell = createElement('td', {}, getActionText(log));
    
    // Details cell
    const detailsCell = createElement('td');
    const detailsLink = createElement('a', {
        href: '#',
        className: 'text-decoration-none',
        dataset: { action: 'view-details', logData: JSON.stringify(log) },
        'aria-label': 'View log details'
    }, 'View Details');
    detailsCell.appendChild(detailsLink);
    
    // IP address cell
    const ipCell = createElement('td', {}, log.ip_address || '-');
    
    // Status cell
    const statusCell = createElement('td');
    const statusBadge = createElement('span', {
        className: log.success ? 'badge bg-success' : 'badge bg-danger'
    }, log.success ? 'Success' : 'Failed');
    statusCell.appendChild(statusBadge);
    
    // Append all cells
    row.appendChild(timestampCell);
    row.appendChild(eventTypeCell);
    row.appendChild(userCell);
    row.appendChild(actionCell);
    row.appendChild(detailsCell);
    row.appendChild(ipCell);
    row.appendChild(statusCell);
    
    return row;
}

function displayLogsError(message) {
    const tbody = document.getElementById('logsTableBody');
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center text-danger">
                    <i class="bi bi-exclamation-triangle"></i> ${escapeHtml(message)}
                </td>
            </tr>
        `;
    }
}

// ===== Helper Functions =====

function getBadgeClass(eventType) {
    const badges = {
        'search': 'bg-primary',
        'access': 'bg-warning',
        'admin': 'bg-info',
        'config': 'bg-secondary',
        'error': 'bg-danger'
    };
    return badges[eventType] || 'bg-secondary';
}

function formatEventType(eventType) {
    const types = {
        'search': 'Search',
        'access': 'Access',
        'admin': 'Admin',
        'config': 'Config',
        'error': 'Error'
    };
    return types[eventType] || eventType;
}

function getActionText(log) {
    switch(log.event_type) {
        case 'search':
            return log.search_query || '-';
        case 'access':
            return log.target_resource || '-';
        case 'admin':
            return `${escapeHtml(log.action || '')} - ${log.target_resource || '-'}`;
        case 'config':
            return `${escapeHtml(log.action || '')} - ${log.target_resource || '-'}`;
        case 'error':
            return log.error_message || log.action || '-';
        default:
            return log.action || '-';
    }
}

function formatDateForInput(date) {
    // Format date for datetime-local input (YYYY-MM-DDTHH:MM)
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

// ===== Pagination =====

function updatePagination(total, currentPage) {
    const totalPages = Math.ceil(total / pageSize);
    const paginationContainer = document.getElementById('pagination');
    
    if (!paginationContainer) return;
    
    if (totalPages <= 1) {
        paginationContainer.innerHTML = '';
        return;
    }
    
    const pagination = createPagination({
        currentPage: currentPage,
        totalPages: totalPages,
        onPageChange: (page) => loadLogs(page)
    });
    
    paginationContainer.innerHTML = '';
    paginationContainer.appendChild(pagination);
}

function updateResultInfo(total, offset, count) {
    const resultInfo = document.getElementById('resultInfo');
    if (resultInfo) {
        const start = total > 0 ? offset + 1 : 0;
        const end = offset + count;
        resultInfo.textContent = `Showing ${start}-${end} of ${total}`;
    }
}

// ===== Event Handlers =====

function handleFilterSubmit(e) {
    e.preventDefault();
    loadLogs(1); // Reset to first page when applying filters
}

function handleResetFilters(e) {
    e.preventDefault();
    
    const form = document.getElementById('filterForm');
    if (form) {
        form.reset();
        
        // Reset date range to default
        initializeAuditLogs();
        
        // Reload logs
        loadLogs(1);
    }
}

function handlePageClick(e) {
    e.preventDefault();
    
    const page = parseInt(this.dataset.page);
    if (page && page !== currentPage) {
        loadLogs(page);
    }
}

function handleViewDetails(e) {
    e.preventDefault();
    
    try {
        const logData = JSON.parse(this.dataset.logData);
        showDetailsModal(logData);
    } catch (error) {
        console.error('Failed to parse log data:', error);
        showToast('Failed to load log details', true);
    }
}

// ===== Details Modal =====

function showDetailsModal(log) {
    // Create or get modal
    let modal = document.getElementById('detailsModal');
    if (!modal) {
        modal = createDetailsModal();
        document.body.appendChild(modal);
    }
    
    // Populate modal content
    populateDetailsModal(log);
    
    // Show modal
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

function createDetailsModal() {
    const modal = createElement('div', {
        className: 'modal fade',
        id: 'detailsModal',
        tabindex: '-1',
        'aria-labelledby': 'detailsModalLabel',
        'aria-hidden': 'true'
    });
    
    modal.innerHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="detailsModalLabel">Audit Log Details</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body" id="detailsModalBody">
                    <!-- Content will be populated here -->
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                </div>
            </div>
        </div>
    `;
    
    return modal;
}

function populateDetailsModal(log) {
    const modalBody = document.getElementById('detailsModalBody');
    if (!modalBody) return;
    
    // Parse additional data
    let additionalData = {};
    if (log.additional_data) {
        try {
            additionalData = JSON.parse(log.additional_data);
        } catch (e) {
            additionalData = { raw: log.additional_data };
        }
    }
    
    // Create details table
    const table = createElement('table', { className: 'table table-sm' });
    
    const details = [
        { label: 'Timestamp', value: new Date(log.timestamp).toLocaleString() },
        { label: 'Event Type', value: `<span class="badge ${getBadgeClass(log.event_type)}">${formatEventType(log.event_type)}</span>`, isHtml: true },
        { label: 'User', value: log.user_email || '-' },
        { label: 'User Role', value: log.user_role || '-' },
        { label: 'IP Address', value: log.ip_address || '-' },
        { label: 'User Agent', value: log.user_agent || '-', wordBreak: true },
        { label: 'Action', value: log.action || '-' }
    ];
    
    // Add conditional fields
    if (log.search_query) {
        details.push({ label: 'Search Query', value: log.search_query });
    }
    if (log.search_results_count !== null && log.search_results_count !== undefined) {
        details.push({ label: 'Results Count', value: log.search_results_count.toString() });
    }
    if (log.search_services) {
        details.push({ label: 'Services Used', value: log.search_services });
    }
    if (log.target_resource) {
        details.push({ label: 'Target Resource', value: log.target_resource });
    }
    if (log.error_message) {
        details.push({ label: 'Error Message', value: log.error_message, className: 'text-danger' });
    }
    
    // Success status
    const successValue = log.success 
        ? '<span class="text-success">Yes</span>' 
        : '<span class="text-danger">No</span>';
    details.push({ label: 'Success', value: successValue, isHtml: true });
    
    // Create table rows
    details.forEach(detail => {
        const row = createElement('tr');
        
        const labelCell = createElement('th', { 
            style: 'width: 30%;' 
        }, detail.label);
        
        const valueCell = createElement('td');
        if (detail.wordBreak) {
            valueCell.style.wordBreak = 'break-all';
        }
        if (detail.className) {
            valueCell.className = detail.className;
        }
        
        if (detail.isHtml) {
            valueCell.innerHTML = detail.value;
        } else {
            valueCell.textContent = detail.value;
        }
        
        row.appendChild(labelCell);
        row.appendChild(valueCell);
        table.appendChild(row);
    });
    
    // Clear and populate modal body
    modalBody.innerHTML = '';
    modalBody.appendChild(table);
    
    // Add additional data section if present
    if (Object.keys(additionalData).length > 0) {
        const heading = createElement('h6', { className: 'mt-3' }, 'Additional Data:');
        const pre = createElement('pre', {
            className: 'bg-light p-2',
            style: 'max-height: 300px; overflow-y: auto;'
        }, JSON.stringify(additionalData, null, 2));
        
        modalBody.appendChild(heading);
        modalBody.appendChild(pre);
    }
}