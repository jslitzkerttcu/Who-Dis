/**
 * Admin Session Management JavaScript
 * Handles session monitoring and termination
 */

let sessions = [];
let sessionToTerminate = null;

document.addEventListener('DOMContentLoaded', function() {
    // Initialize session management
    initializeSessionManagement();
    
    // Set up event listeners
    setupEventListeners();
    
    // Load sessions on page load
    loadSessions();
    
    // Auto-refresh every 30 seconds
    setInterval(loadSessions, 30000);
});

function initializeSessionManagement() {
    // Initialize any required setup
    console.log('Session management initialized');
}

function setupEventListeners() {
    // Refresh button
    attachEventListener('[data-action="refresh-sessions"]', 'click', handleRefreshSessions);
    
    // Terminate session buttons (delegated)
    attachEventListener('[data-action="terminate-session"]', 'click', handleTerminateSession);
    
    // Confirm terminate button
    const confirmButton = document.getElementById('confirm-terminate');
    if (confirmButton) {
        confirmButton.addEventListener('click', handleConfirmTerminate);
    }
}

// ===== Session Loading =====

async function loadSessions() {
    const loadingEl = document.getElementById('sessions-loading');
    const contentEl = document.getElementById('sessions-content');
    
    // Show loading state
    if (loadingEl) loadingEl.style.display = 'block';
    if (contentEl) contentEl.style.display = 'none';
    
    try {
        const response = await authenticatedFetch('/admin/api/sessions');
        const data = await handleApiResponse(response);
        
        sessions = data.sessions || [];
        displaySessions(sessions);
        updateSessionStats(sessions);
        
    } catch (error) {
        displayError(error, 'Failed to load sessions');
        displaySessionError('Failed to load sessions. The session goblins are on strike.');
    } finally {
        // Hide loading state
        if (loadingEl) loadingEl.style.display = 'none';
        if (contentEl) contentEl.style.display = 'block';
    }
}

function displaySessions(sessions) {
    const tbody = document.getElementById('sessions-tbody');
    const noSessionsEl = document.getElementById('no-sessions');
    const tableContainer = tbody?.parentElement?.parentElement;
    
    if (!tbody) return;
    
    // Clear existing content
    tbody.innerHTML = '';
    
    if (sessions.length === 0) {
        if (noSessionsEl) noSessionsEl.style.display = 'block';
        if (tableContainer) tableContainer.style.display = 'none';
        return;
    }
    
    // Show table, hide no sessions message
    if (noSessionsEl) noSessionsEl.style.display = 'none';
    if (tableContainer) tableContainer.style.display = 'block';
    
    sessions.forEach(session => {
        const row = createSessionRow(session);
        tbody.appendChild(row);
    });
}

function createSessionRow(session) {
    const now = new Date();
    const created = new Date(session.created_at);
    const lastActivity = new Date(session.last_activity);
    const idleMinutes = Math.floor((now - lastActivity) / (1000 * 60));
    
    // Determine session status
    const status = getSessionStatus(idleMinutes);
    
    // Extract browser info
    const browserInfo = extractBrowserInfo(session.user_agent);
    
    // Create row elements
    const row = createElement('tr', { dataset: { sessionId: session.id } });
    
    // User cell
    const userCell = createElement('td');
    const userDiv = createElement('div', {}, session.user_email);
    const browserSmall = createElement('small', { className: 'text-muted' }, browserInfo);
    userCell.appendChild(userDiv);
    userCell.appendChild(browserSmall);
    
    // IP Address cell
    const ipCell = createElement('td', {}, session.ip_address || 'Unknown');
    
    // Created cell
    const createdCell = createElement('td', {}, created.toLocaleString());
    
    // Last Activity cell
    const lastActivityCell = createElement('td', {}, lastActivity.toLocaleString());
    
    // Status cell
    const statusCell = createElement('td');
    const statusBadge = createElement('span', {
        className: `badge ${status.badgeClass}`
    }, status.text);
    statusCell.appendChild(statusBadge);
    
    // Actions cell
    const actionsCell = createElement('td');
    const terminateButton = createElement('button', {
        className: 'btn btn-sm btn-outline-danger',
        type: 'button',
        dataset: { 
            action: 'terminate-session',
            sessionId: session.id,
            userEmail: session.user_email
        },
        'aria-label': `Terminate session for ${session.user_email}`
    });
    
    const icon = createElement('i', { className: 'bi bi-x-circle' });
    const text = document.createTextNode(' Terminate');
    terminateButton.appendChild(icon);
    terminateButton.appendChild(text);
    actionsCell.appendChild(terminateButton);
    
    // Append all cells
    row.appendChild(userCell);
    row.appendChild(ipCell);
    row.appendChild(createdCell);
    row.appendChild(lastActivityCell);
    row.appendChild(statusCell);
    row.appendChild(actionsCell);
    
    return row;
}

function getSessionStatus(idleMinutes) {
    if (idleMinutes > 120) {
        return { badgeClass: 'bg-secondary', text: 'Inactive' };
    } else if (idleMinutes > 30) {
        return { badgeClass: 'bg-warning', text: `Idle (${idleMinutes}m)` };
    } else {
        return { badgeClass: 'bg-success', text: 'Active' };
    }
}

function extractBrowserInfo(userAgent) {
    if (!userAgent) return 'Unknown';
    
    const match = userAgent.match(/(Chrome|Firefox|Safari|Edge)\/[\d.]+/);
    return match ? match[0] : 'Unknown';
}

function updateSessionStats(sessions) {
    const now = new Date();
    const uniqueUsers = new Set(sessions.map(s => s.user_email)).size;
    let idleCount = 0;
    
    sessions.forEach(session => {
        const lastActivity = new Date(session.last_activity);
        const idleMinutes = Math.floor((now - lastActivity) / (1000 * 60));
        if (idleMinutes > 30) idleCount++;
    });
    
    // Update stats display
    updateContent('#active-count', sessions.length.toString());
    updateContent('#unique-users', uniqueUsers.toString());
    updateContent('#idle-count', idleCount.toString());
}

function displaySessionError(message) {
    const contentEl = document.getElementById('sessions-content');
    if (contentEl) {
        contentEl.innerHTML = `
            <div class="alert alert-danger" role="alert">
                <i class="bi bi-exclamation-triangle"></i> ${escapeHtml(message)}
            </div>
        `;
    }
}

// ===== Event Handlers =====

function handleRefreshSessions(e) {
    e.preventDefault();
    loadSessions();
}

function handleTerminateSession(e) {
    e.preventDefault();
    
    const sessionId = this.dataset.sessionId;
    const userEmail = this.dataset.userEmail;
    
    if (sessionId && userEmail) {
        showTerminateConfirmation(sessionId, userEmail);
    }
}

function handleConfirmTerminate(e) {
    e.preventDefault();
    
    if (sessionToTerminate) {
        terminateSession(sessionToTerminate);
    }
}

// ===== Session Termination =====

function showTerminateConfirmation(sessionId, userEmail) {
    sessionToTerminate = sessionId;
    
    // Update modal content
    const userSpan = document.getElementById('terminate-user');
    if (userSpan) {
        userSpan.textContent = userEmail;
    }
    
    // Show modal
    const modalEl = document.getElementById('terminateModal');
    if (modalEl) {
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
    }
}

async function terminateSession(sessionId) {
    try {
        const response = await authenticatedFetch(`/admin/api/sessions/${sessionId}/terminate`, {
            method: 'POST'
        });
        
        const data = await handleApiResponse(response);
        
        if (data.success) {
            showToast('Session terminated successfully');
            
            // Hide modal
            const modalEl = document.getElementById('terminateModal');
            if (modalEl) {
                const modal = bootstrap.Modal.getInstance(modalEl);
                if (modal) modal.hide();
            }
            
            // Reload sessions
            await loadSessions();
            
            // Reset termination state
            sessionToTerminate = null;
            
        } else {
            showToast(data.message || 'Failed to terminate session', true);
        }
        
    } catch (error) {
        displayError(error, 'Failed to terminate session');
    }
}

// ===== Utility Functions =====

// Make loadSessions available globally for the refresh button
window.loadSessions = loadSessions;