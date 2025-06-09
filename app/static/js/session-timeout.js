// Session timeout management
(function() {
    let timeoutMinutes = 15;
    let warningMinutes = 2;
    let checkIntervalSeconds = 30;
    
    let lastActivity = Date.now();
    let warningShown = false;
    let sessionCheckInterval = null;
    let warningModal = null;
    let countdownInterval = null;
    
    // Track user activity
    const activityEvents = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];
    
    function resetActivity() {
        lastActivity = Date.now();
        if (warningShown) {
            hideWarning();
        }
    }
    
    // Add activity listeners
    activityEvents.forEach(event => {
        document.addEventListener(event, resetActivity, true);
    });
    
    // Create warning modal
    function createWarningModal() {
        const modal = document.createElement('div');
        modal.id = 'session-warning-modal';
        modal.className = 'session-modal';
        modal.innerHTML = `
            <div class="session-modal-content">
                <h2>Session Timeout Warning</h2>
                <p>Your session will expire in <span id="countdown-timer">2:00</span> due to inactivity.</p>
                <p>Click "Continue Session" to remain logged in.</p>
                <div class="session-modal-buttons">
                    <button id="continue-session" class="btn-primary">Continue Session</button>
                    <button id="logout-now" class="btn-secondary">Logout Now</button>
                </div>
            </div>
        `;
        
        // Add styles
        const style = document.createElement('style');
        style.textContent = `
            .session-modal {
                display: none;
                position: fixed;
                z-index: 10000;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0, 0, 0, 0.5);
                animation: fadeIn 0.3s ease-in;
            }
            
            .session-modal.show {
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .session-modal-content {
                background-color: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
                max-width: 400px;
                width: 90%;
                text-align: center;
                animation: slideIn 0.3s ease-out;
            }
            
            .session-modal-content h2 {
                color: #333;
                margin-bottom: 20px;
            }
            
            .session-modal-content p {
                color: #666;
                margin-bottom: 15px;
                line-height: 1.5;
            }
            
            #countdown-timer {
                font-weight: bold;
                color: #FF4F1F;
                font-size: 1.2em;
            }
            
            .session-modal-buttons {
                display: flex;
                gap: 10px;
                justify-content: center;
                margin-top: 25px;
            }
            
            .session-modal-buttons button {
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
                transition: all 0.3s ease;
            }
            
            .btn-primary {
                background-color: #007c59;
                color: white;
            }
            
            .btn-primary:hover {
                background-color: #005940;
            }
            
            .btn-secondary {
                background-color: #6c757d;
                color: white;
            }
            
            .btn-secondary:hover {
                background-color: #545b62;
            }
            
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            
            @keyframes slideIn {
                from {
                    transform: translateY(-20px);
                    opacity: 0;
                }
                to {
                    transform: translateY(0);
                    opacity: 1;
                }
            }
        `;
        
        document.head.appendChild(style);
        document.body.appendChild(modal);
        
        // Add event listeners
        document.getElementById('continue-session').addEventListener('click', extendSession);
        document.getElementById('logout-now').addEventListener('click', logout);
        
        return modal;
    }
    
    // Show warning modal
    function showWarning() {
        if (!warningModal) {
            warningModal = createWarningModal();
        }
        
        warningShown = true;
        warningModal.classList.add('show');
        
        // Start countdown
        let remainingSeconds = warningMinutes * 60;
        updateCountdown(remainingSeconds);
        
        countdownInterval = setInterval(() => {
            remainingSeconds--;
            updateCountdown(remainingSeconds);
            
            if (remainingSeconds <= 0) {
                clearInterval(countdownInterval);
                logout();
            }
        }, 1000);
    }
    
    // Hide warning modal
    function hideWarning() {
        if (warningModal) {
            warningModal.classList.remove('show');
        }
        warningShown = false;
        
        if (countdownInterval) {
            clearInterval(countdownInterval);
            countdownInterval = null;
        }
    }
    
    // Update countdown timer
    function updateCountdown(seconds) {
        const minutes = Math.floor(seconds / 60);
        const secs = seconds % 60;
        const display = `${minutes}:${secs.toString().padStart(2, '0')}`;
        
        const timer = document.getElementById('countdown-timer');
        if (timer) {
            timer.textContent = display;
        }
    }
    
    // Check session status
    async function checkSession() {
        try {
            const response = await fetch('/api/session/check', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCSRFToken()
                },
                body: JSON.stringify({
                    last_activity: Math.floor(lastActivity / 1000)
                })
            });
            
            if (!response.ok) {
                if (response.status === 401) {
                    // Don't redirect if we're already on the login page to avoid loops
                    if (!window.location.pathname.includes('/login')) {
                        window.location.href = '/login?reason=session_expired';
                    }
                }
                return;
            }
            
            const data = await response.json();
            
            // Update configuration if changed
            if (data.timeout_minutes) {
                timeoutMinutes = data.timeout_minutes;
            }
            if (data.warning_minutes) {
                warningMinutes = data.warning_minutes;
            }
            
            // Check if we should show warning
            const inactiveMinutes = (Date.now() - lastActivity) / 1000 / 60;
            const shouldShowWarning = inactiveMinutes >= (timeoutMinutes - warningMinutes);
            
            if (shouldShowWarning && !warningShown) {
                showWarning();
            } else if (!shouldShowWarning && warningShown) {
                hideWarning();
            }
            
        } catch (error) {
            console.error('Session check failed:', error);
        }
    }
    
    // Extend session
    async function extendSession() {
        try {
            const response = await fetch('/api/session/extend', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCSRFToken()
                }
            });
            
            if (response.ok) {
                resetActivity();
                hideWarning();
            }
        } catch (error) {
            console.error('Failed to extend session:', error);
        }
    }
    
    // Logout
    async function logout() {
        try {
            await fetch('/api/session/logout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCSRFToken()
                }
            });
        } catch (error) {
            console.error('Logout failed:', error);
        } finally {
            window.location.href = '/login?reason=session_timeout';
        }
    }
    
    // Initialize session configuration
    async function initializeSessionConfig() {
        // Don't start session management on login page
        if (window.location.pathname.includes('/login')) {
            console.debug('On login page, skipping session management');
            return;
        }
        
        try {
            const response = await fetch('/api/session/config');
            if (response.ok) {
                const config = await response.json();
                timeoutMinutes = config.timeout_minutes || 15;
                warningMinutes = config.warning_minutes || 2;
                checkIntervalSeconds = config.check_interval_seconds || 30;
                
                // Test if session check works before starting interval
                const testCheck = await fetch('/api/session/check', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': getCSRFToken()
                    },
                    body: JSON.stringify({
                        last_activity: Math.floor(Date.now() / 1000)
                    })
                });
                
                if (testCheck.ok) {
                    // Session management works, start the interval
                    sessionCheckInterval = setInterval(checkSession, checkIntervalSeconds * 1000);
                    console.debug('Session management initialized successfully');
                } else {
                    console.debug('Session check failed, not starting session management');
                    return;
                }
            } else if (response.status === 401) {
                // User not authenticated, don't start session management
                console.debug('User not authenticated, skipping session management');
                return;
            }
        } catch (error) {
            console.error('Failed to load session config:', error);
        }
    }
    
    // Initialize on page load
    initializeSessionConfig();
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        if (sessionCheckInterval) {
            clearInterval(sessionCheckInterval);
        }
        if (countdownInterval) {
            clearInterval(countdownInterval);
        }
    });
})();