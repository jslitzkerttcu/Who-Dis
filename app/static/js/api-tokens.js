/* Phase 10 API-01: External API token management UI interactions.
 * Handles create/reveal/revoke modal lifecycle, clipboard copy,
 * and HTMX event listeners for token CRUD operations.
 */
(function () {
    'use strict';

    // ===== Create Modal =====

    window.openCreateModal = function () {
        var modal = document.getElementById('create-token-modal');
        var input = document.getElementById('token-name-input');
        var errorEl = document.getElementById('create-token-error');
        if (input) { input.value = ''; }
        if (errorEl) { errorEl.classList.add('hidden'); errorEl.textContent = ''; }
        updateCreateButton('');
        if (modal) { modal.classList.remove('hidden'); }
        if (input) { setTimeout(function () { input.focus(); }, 100); }
    };

    window.closeCreateModal = function () {
        var modal = document.getElementById('create-token-modal');
        if (modal) { modal.classList.add('hidden'); }
    };

    // Input validation: enable/disable confirm button based on 2+ char requirement
    function updateCreateButton(value) {
        var btn = document.getElementById('create-token-confirm');
        if (!btn) return;
        var trimmed = (value || '').trim();
        if (trimmed.length >= 2) {
            btn.disabled = false;
            btn.classList.remove('opacity-50', 'cursor-not-allowed');
            // Re-process HTMX attributes after enabling
            if (typeof htmx !== 'undefined') { htmx.process(btn); }
        } else {
            btn.disabled = true;
            btn.classList.add('opacity-50', 'cursor-not-allowed');
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        var input = document.getElementById('token-name-input');
        if (input) {
            input.addEventListener('input', function () {
                updateCreateButton(this.value);
            });
        }
    });

    // ===== Reveal Modal =====

    function showRevealModal(token, name) {
        var modal = document.getElementById('reveal-token-modal');
        var tokenDisplay = document.getElementById('reveal-token-value');
        if (tokenDisplay) { tokenDisplay.textContent = token; }
        // Reset copy button state
        var icon = document.getElementById('copy-token-icon');
        var text = document.getElementById('copy-token-text');
        if (icon) { icon.className = 'fas fa-copy mr-2'; }
        if (text) { text.textContent = 'Copy'; }
        if (modal) { modal.classList.remove('hidden'); }
    }

    window.closeRevealModal = function () {
        var modal = document.getElementById('reveal-token-modal');
        var tokenDisplay = document.getElementById('reveal-token-value');
        // Security: clear token from DOM
        if (tokenDisplay) { tokenDisplay.textContent = ''; }
        if (modal) { modal.classList.add('hidden'); }
    };

    // ===== Copy Token =====

    window.copyToken = function () {
        var tokenDisplay = document.getElementById('reveal-token-value');
        if (!tokenDisplay || !tokenDisplay.textContent) return;

        if (!navigator.clipboard || !navigator.clipboard.writeText) {
            if (typeof showToast === 'function') {
                showToast("Couldn't copy. Select the text and copy manually.", 'error');
            }
            return;
        }

        navigator.clipboard.writeText(tokenDisplay.textContent).then(function () {
            if (typeof showToast === 'function') {
                showToast('Token copied to clipboard', 'success', 3000);
            }
            // Swap icon to check for 2 seconds
            var icon = document.getElementById('copy-token-icon');
            var text = document.getElementById('copy-token-text');
            if (icon) { icon.className = 'fas fa-check mr-2 text-green-600'; }
            if (text) { text.textContent = 'Copied'; }
            setTimeout(function () {
                if (icon) { icon.className = 'fas fa-copy mr-2'; }
                if (text) { text.textContent = 'Copy'; }
            }, 2000);
        }, function () {
            if (typeof showToast === 'function') {
                showToast("Couldn't copy. Select the text and copy manually.", 'error');
            }
        });
    };

    // ===== Revoke Modal =====

    window.openRevokeModal = function (tokenId, tokenName) {
        var modal = document.getElementById('revoke-token-modal');
        var nameSpan = document.getElementById('revoke-token-name');
        var confirmBtn = document.getElementById('revoke-token-confirm');
        if (nameSpan) { nameSpan.textContent = tokenName; }
        if (confirmBtn) {
            confirmBtn.setAttribute('hx-post', '/admin/api-tokens/' + tokenId + '/revoke');
            // Re-process HTMX attributes on the button
            if (typeof htmx !== 'undefined') { htmx.process(confirmBtn); }
        }
        if (modal) { modal.classList.remove('hidden'); }
    };

    window.closeRevokeModal = function () {
        var modal = document.getElementById('revoke-token-modal');
        if (modal) { modal.classList.add('hidden'); }
    };

    // ===== HTMX Event Listeners =====

    // Listen for successful token creation via HTMX afterRequest
    document.addEventListener('htmx:afterRequest', function (e) {
        var target = e.detail.elt;
        if (target && target.id === 'create-token-confirm' && e.detail.successful) {
            try {
                var data = JSON.parse(e.detail.xhr.responseText);
                if (data.success && data.token && data.name) {
                    closeCreateModal();
                    showRevealModal(data.token, data.name);
                }
            } catch (err) { /* ignore parse errors */ }
        }
    });

    // Listen for tokenRevoked event
    document.addEventListener('tokenRevoked', function () {
        closeRevokeModal();
    });

    // Handle HTMX errors on create/revoke
    document.addEventListener('htmx:responseError', function (e) {
        var target = e.detail.elt;
        if (target && target.id === 'create-token-confirm') {
            var errorEl = document.getElementById('create-token-error');
            if (errorEl) {
                errorEl.textContent = 'Token creation failed. Please try again.';
                errorEl.classList.remove('hidden');
            }
        }
    });

    // ===== Escape Key Handler =====

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            var createModal = document.getElementById('create-token-modal');
            var revealModal = document.getElementById('reveal-token-modal');
            var revokeModal = document.getElementById('revoke-token-modal');
            if (createModal && !createModal.classList.contains('hidden')) { closeCreateModal(); }
            else if (revealModal && !revealModal.classList.contains('hidden')) { closeRevealModal(); }
            else if (revokeModal && !revokeModal.classList.contains('hidden')) { closeRevokeModal(); }
        }
    });
})();
