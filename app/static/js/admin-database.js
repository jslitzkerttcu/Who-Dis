/**
 * Admin Database Management JavaScript
 * Handles database health monitoring, cache management, and maintenance operations
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize database management
    initializeDatabaseManagement();
    
    // Set up event listeners
    setupEventListeners();
    
    // Load initial data
    loadAllDashboardData();
    
    // Set up auto-refresh
    setInterval(function() {
        loadDatabaseHealth();
        loadCacheStatus();
        loadSessionStats();
    }, 30000);
});

function initializeDatabaseManagement() {
    // Set up table stats accordion listener
    const tableStatsAccordion = document.getElementById('tableStatsCollapse');
    if (tableStatsAccordion) {
        tableStatsAccordion.addEventListener('show.bs.collapse', function () {
            loadTableStats();
        });
    }
}

function setupEventListeners() {
    // Cache management buttons
    attachEventListener('[data-action="refresh-genesys-cache"]', 'click', handleRefreshGenesysCache);
    attachEventListener('[data-action="clear-caches"]', 'click', handleClearCaches);
    
    // Maintenance buttons
    attachEventListener('[data-action="export-audit-logs"]', 'click', handleExportAuditLogs);
    attachEventListener('[data-action="optimize-database"]', 'click', handleOptimizeDatabase);
}

function loadAllDashboardData() {
    loadDatabaseHealth();
    loadCacheStatus();
    loadErrorStats();
    loadSessionStats();
}

// ===== Database Health =====

async function loadDatabaseHealth() {
    const loadingEl = document.getElementById('db-health-loading');
    const contentEl = document.getElementById('db-health-content');
    
    try {
        const response = await authenticatedFetch('/admin/api/database/health');
        const data = await handleApiResponse(response);
        
        // Hide loading, show content
        if (loadingEl) loadingEl.style.display = 'none';
        if (contentEl) contentEl.style.display = 'block';
        
        // Update status
        updateDatabaseStatus(data);
        updateDatabaseMetrics(data);
        
    } catch (error) {
        displayError(error, 'Failed to load database health');
        displayDatabaseError('Failed to load database health');
    }
}

function updateDatabaseStatus(data) {
    const statusIcon = document.getElementById('db-status-icon');
    const statusText = document.getElementById('db-status');
    
    if (!statusIcon || !statusText) return;
    
    if (data.status === 'healthy') {
        statusIcon.innerHTML = '<i class="bi bi-check-circle-fill text-success"></i>';
        statusText.innerHTML = `Healthy<br><small class="text-muted">${escapeHtml(data.database_type || 'Unknown')}</small>`;
        statusText.className = 'mb-0 text-success';
    } else {
        statusIcon.innerHTML = '<i class="bi bi-x-circle-fill text-danger"></i>';
        statusText.textContent = 'Issues Detected';
        statusText.className = 'mb-0 text-danger';
    }
}

function updateDatabaseMetrics(data) {
    updateContent('#db-size', data.database_size || '--');
    updateContent('#active-connections', data.active_connections?.toString() || '0');
    updateContent('#pool-usage', data.pool_usage || '--');
}

function displayDatabaseError(message) {
    const loadingEl = document.getElementById('db-health-loading');
    const contentEl = document.getElementById('db-health-content');
    
    if (loadingEl) loadingEl.style.display = 'none';
    if (contentEl) {
        contentEl.innerHTML = `
            <div class="alert alert-danger" role="alert">
                <i class="bi bi-exclamation-triangle"></i> ${escapeHtml(message)}
            </div>
        `;
    }
}

// ===== Table Statistics =====

async function loadTableStats() {
    const loadingEl = document.getElementById('table-stats-loading');
    const contentEl = document.getElementById('table-stats-content');
    const tbody = document.getElementById('table-stats-body');
    
    if (loadingEl) loadingEl.style.display = 'block';
    if (contentEl) contentEl.style.display = 'none';
    
    try {
        const response = await authenticatedFetch('/admin/api/database/tables');
        const data = await handleApiResponse(response);
        
        if (loadingEl) loadingEl.style.display = 'none';
        if (contentEl) contentEl.style.display = 'block';
        
        if (tbody) tbody.innerHTML = '';
        
        // Show warnings if present
        displayTableWarnings(data);
        
        // Handle errors
        if (data.error) {
            displayTableError('Failed to load table statistics');
            console.error('Database error:', data.error);
            return;
        }
        
        // Display tables
        displayTableStats(data.tables);
        
    } catch (error) {
        displayError(error, 'Failed to load table statistics');
        displayTableError('Failed to connect to database');
    }
}

function displayTableWarnings(data) {
    if (data.warning) {
        const contentEl = document.getElementById('table-stats-content');
        if (contentEl && !contentEl.querySelector('.alert-warning')) {
            const warningDiv = createElement('div', {
                className: 'alert alert-warning mb-3'
            });
            warningDiv.innerHTML = `<i class="bi bi-exclamation-triangle"></i> ${escapeHtml(data.warning)}`;
            contentEl.insertBefore(warningDiv, contentEl.firstChild);
        }
    }
}

function displayTableStats(tables) {
    const tbody = document.getElementById('table-stats-body');
    if (!tbody) return;
    
    if (tables && tables.length > 0) {
        tables.forEach(table => {
            const row = createTableStatsRow(table);
            tbody.appendChild(row);
        });
    } else {
        const row = createElement('tr');
        const cell = createElement('td', {
            className: 'text-center text-muted',
            colspan: '4'
        }, 'No tables found');
        row.appendChild(cell);
        tbody.appendChild(row);
    }
}

function createTableStatsRow(table) {
    const row = createElement('tr');
    
    // Table name cell
    const nameCell = createElement('td');
    const icon = createElement('i', { className: 'bi bi-table' });
    nameCell.appendChild(icon);
    nameCell.appendChild(document.createTextNode(` ${table.name}`));
    
    // Row count cell
    const rowCount = typeof table.row_count === 'number' 
        ? table.row_count.toLocaleString() 
        : table.row_count;
    const countCell = createElement('td', {}, rowCount);
    
    // Size cell
    const sizeCell = createElement('td', {}, table.size);
    
    // Activity cell
    const activityCell = createElement('td', {}, table.last_activity || 'N/A');
    
    row.appendChild(nameCell);
    row.appendChild(countCell);
    row.appendChild(sizeCell);
    row.appendChild(activityCell);
    
    return row;
}

function displayTableError(message) {
    const tbody = document.getElementById('table-stats-body');
    const loadingEl = document.getElementById('table-stats-loading');
    const contentEl = document.getElementById('table-stats-content');
    
    if (loadingEl) loadingEl.style.display = 'none';
    if (contentEl) contentEl.style.display = 'block';
    
    if (tbody) {
        const row = createElement('tr');
        const cell = createElement('td', {
            className: 'text-center text-danger',
            colspan: '4'
        });
        cell.innerHTML = `<i class="bi bi-exclamation-circle"></i> ${escapeHtml(message)}`;
        row.appendChild(cell);
        tbody.innerHTML = '';
        tbody.appendChild(row);
    }
}

// ===== Cache Management =====

async function loadCacheStatus() {
    // Load search cache status
    try {
        const searchResponse = await authenticatedFetch('/admin/api/cache/search/status');
        const searchData = await handleApiResponse(searchResponse);
        updateContent('#search-cache-size', `${searchData.entry_count || 0} entries`);
    } catch (error) {
        console.error('Error loading search cache status:', error);
    }
    
    // Load API tokens status
    try {
        const tokensResponse = await authenticatedFetch('/admin/api/tokens/status');
        const tokensData = await handleApiResponse(tokensResponse);
        updateTokenStatuses(tokensData.tokens);
    } catch (error) {
        console.error('Error loading token status:', error);
    }
    
    // Load Genesys cache details
    try {
        const genesysResponse = await authenticatedFetch('/admin/api/genesys/cache/status');
        const genesysData = await handleApiResponse(genesysResponse);
        updateGenesysCacheStatus(genesysData);
    } catch (error) {
        console.error('Error loading Genesys cache status:', error);
    }
}

function updateTokenStatuses(tokens) {
    // Update Graph API token status
    const graphToken = tokens.find(t => t.service === 'microsoft_graph');
    if (graphToken) {
        const badge = document.getElementById('graph-cache-status');
        if (badge) {
            if (graphToken.is_expired) {
                badge.textContent = 'Expired';
                badge.className = 'badge bg-danger';
            } else {
                badge.textContent = 'Valid';
                badge.className = 'badge bg-success';
            }
        }
    }
    
    // Update Genesys token status
    const genesysToken = tokens.find(t => t.service === 'genesys');
    if (genesysToken) {
        const badge = document.getElementById('genesys-cache-status');
        if (badge) {
            if (genesysToken.is_expired) {
                badge.textContent = 'Expired';
                badge.className = 'badge bg-danger';
            } else {
                badge.textContent = 'Valid';
                badge.className = 'badge bg-success';
            }
        }
    }
}

function updateGenesysCacheStatus(data) {
    updateContent('#genesys-groups-count', (data.groups_cached || 0).toString());
    updateContent('#genesys-locations-count', (data.locations_cached || 0).toString());
    
    // Format and update cache age
    if (data.group_cache_age) {
        const ageText = formatCacheAge(data.group_cache_age);
        const ageElement = document.getElementById('genesys-cache-age');
        if (ageElement) {
            ageElement.textContent = ageText;
            
            // Add refresh needed badge
            if (data.needs_refresh) {
                const badge = createElement('span', {
                    className: 'badge bg-warning ms-1'
                }, 'Refresh Needed');
                ageElement.appendChild(document.createTextNode(' '));
                ageElement.appendChild(badge);
            }
        }
    }
}

function formatCacheAge(ageString) {
    // Parse age string (e.g., "2:30:45.123456")
    const match = ageString.match(/(\d+):(\d+):(\d+)/);
    if (match) {
        const hours = parseInt(match[1]);
        const minutes = parseInt(match[2]);
        
        if (hours > 0) {
            return `${hours}h ${minutes}m ago`;
        } else if (minutes > 0) {
            return `${minutes}m ago`;
        } else {
            return 'Just refreshed';
        }
    }
    return ageString;
}

// ===== Error and Session Stats =====

async function loadErrorStats() {
    try {
        const response = await authenticatedFetch('/admin/api/database/errors/stats');
        const data = await handleApiResponse(response);
        
        updateContent('#error-count', (data.recent_errors || 0).toString());
        updateContent('#error-24h', (data.errors_24h || 0).toString());
    } catch (error) {
        console.error('Error loading error stats:', error);
    }
}

async function loadSessionStats() {
    try {
        const response = await authenticatedFetch('/admin/api/sessions/stats');
        const data = await handleApiResponse(response);
        
        updateContent('#active-sessions', (data.active_sessions || 0).toString());
    } catch (error) {
        console.error('Error loading session stats:', error);
    }
}

// ===== Event Handlers =====

async function handleRefreshGenesysCache(e) {
    e.preventDefault();
    
    const confirmed = await showConfirmModal({
        title: 'Refresh Genesys Cache',
        message: 'This will refresh the Genesys cache (groups, skills, locations). Continue?',
        confirmText: 'Refresh Cache'
    });
    
    if (!confirmed) return;
    
    const button = this;
    const originalContent = button.innerHTML;
    
    showLoading(button, 'Refreshing...');
    
    try {
        const response = await authenticatedFetch('/admin/api/genesys/refresh-cache', {
            method: 'POST',
            body: { type: 'all' }
        });
        
        const data = await handleApiResponse(response);
        
        if (data.success) {
            showToast('Genesys cache refreshed successfully!');
            loadCacheStatus();
            
            // Show detailed results if available
            if (data.results) {
                const messages = [];
                if (data.results.groups) messages.push(`${data.results.groups.cached || 0} groups`);
                if (data.results.skills) messages.push(`${data.results.skills.cached || 0} skills`);
                if (data.results.locations) messages.push(`${data.results.locations.cached || 0} locations`);
                if (messages.length > 0) {
                    showToast(`Cached: ${messages.join(', ')}`);
                }
            }
        } else {
            showToast(data.message || 'Failed to refresh cache', true);
        }
        
    } catch (error) {
        displayError(error, 'Failed to refresh cache');
    } finally {
        hideLoading(button);
    }
}

async function handleClearCaches(e) {
    e.preventDefault();
    
    const confirmed = await showConfirmModal({
        title: 'Clear All Caches',
        message: 'Are you sure you want to clear all caches? This may temporarily impact performance.',
        confirmText: 'Clear Caches',
        confirmClass: 'btn-warning'
    });
    
    if (!confirmed) return;
    
    try {
        const response = await authenticatedFetch('/admin/api/cache/clear', {
            method: 'POST'
        });
        
        const data = await handleApiResponse(response);
        
        if (data.success) {
            showToast('Caches cleared successfully!');
            loadCacheStatus();
        } else {
            showToast(data.message || 'Failed to clear caches', true);
        }
        
    } catch (error) {
        displayError(error, 'Failed to clear caches');
    }
}

function handleExportAuditLogs(e) {
    e.preventDefault();
    window.location.href = '/admin/api/database/export/audit-logs';
}

async function handleOptimizeDatabase(e) {
    e.preventDefault();
    
    const confirmed = await showConfirmModal({
        title: 'Optimize Database',
        message: 'This will optimize database tables. The operation may take a few moments. Continue?',
        confirmText: 'Optimize Tables'
    });
    
    if (!confirmed) return;
    
    try {
        const response = await authenticatedFetch('/admin/api/database/optimize', {
            method: 'POST'
        });
        
        const data = await handleApiResponse(response);
        
        if (data.success) {
            showToast('Database optimization completed!');
            loadTableStats();
        } else {
            showToast(data.message || 'Optimization failed', true);
        }
        
    } catch (error) {
        displayError(error, 'Failed to optimize database');
    }
}