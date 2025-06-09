document.addEventListener('DOMContentLoaded', function() {
    console.log('Who Dis? app loaded');
    
    // Initialize global app data from data attributes
    const appData = document.getElementById('app-data');
    if (appData) {
        window.userRole = appData.dataset.userRole;
    }
});