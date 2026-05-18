/**
 * Write Actions - Modal control, reason validation, HTMX event bridge.
 * Phase 9: AD write operations UI controller.
 */

/* global htmx, showToast */

// State
let _currentActionConfig = null;
let _passwordVisible = true; // D-05: visible by default

/**
 * Open the write confirmation modal.
 * @param {Object} config - Modal configuration.
 * @param {string} config.actionUrl - POST endpoint URL.
 * @param {string} config.actionTitle - Modal title text.
 * @param {string} config.targetName - Target user display name.
 * @param {string} config.targetEmail - Target user email.
 * @param {string} config.targetDn - Target user distinguished name.
 * @param {boolean} config.isDestructive - Whether action is high-risk.
 * @param {string} config.confirmLabel - Confirm button label.
 */
function openWriteModal(config) {
    _currentActionConfig = config;
    var modal = document.getElementById("write-confirm-modal");
    var title = document.getElementById("write-modal-title");
    var target = document.getElementById("write-modal-target");
    var warning = document.getElementById("write-modal-warning");
    var confirmBtn = document.getElementById("write-modal-confirm");
    var form = document.getElementById("write-modal-form");
    var reason = document.getElementById("write-modal-reason");

    // Populate fields
    title.textContent = config.actionTitle;
    target.textContent = "Target: " + config.targetName + " (" + config.targetEmail + ")";

    // Hidden form values
    document.getElementById("write-form-user-dn").value = config.targetDn;
    document.getElementById("write-form-display-name").value = config.targetName;
    document.getElementById("write-form-user-email").value = config.targetEmail;

    // Set HTMX attributes on form
    form.setAttribute("hx-post", config.actionUrl);
    if (config.actionUrl.indexOf("reset-password") !== -1) {
        form.setAttribute("hx-target", "#password-banner-container");
        form.setAttribute("hx-swap", "innerHTML");
    } else {
        form.setAttribute("hx-swap", "none");
        form.removeAttribute("hx-target");
    }
    // Re-process HTMX on the form since attributes changed
    htmx.process(form);

    // Warning + destructive styling
    if (config.isDestructive) {
        warning.classList.remove("hidden");
        confirmBtn.classList.remove("bg-ttcu-green");
        confirmBtn.classList.add("bg-red-600");
    } else {
        warning.classList.add("hidden");
        confirmBtn.classList.remove("bg-red-600");
        confirmBtn.classList.add("bg-ttcu-green");
    }

    // Confirm button label
    confirmBtn.textContent = config.confirmLabel || "Confirm";

    // Reset state
    reason.value = "";
    confirmBtn.disabled = true;
    confirmBtn.classList.add("opacity-50", "cursor-not-allowed");

    // Show modal
    modal.classList.remove("hidden");

    // Focus reason textarea
    setTimeout(function() { reason.focus(); }, 100);
}

/**
 * Close the write confirmation modal and reset state.
 */
function closeWriteModal() {
    var modal = document.getElementById("write-confirm-modal");
    modal.classList.add("hidden");
    document.getElementById("write-modal-reason").value = "";
    var confirmBtn = document.getElementById("write-modal-confirm");
    confirmBtn.disabled = true;
    confirmBtn.classList.add("opacity-50", "cursor-not-allowed");
    _currentActionConfig = null;
}

/**
 * Submit the write action form via HTMX.
 */
function submitWriteAction() {
    var reason = document.getElementById("write-modal-reason").value.trim();
    document.getElementById("write-form-reason").value = reason;
    var form = document.getElementById("write-modal-form");
    htmx.trigger(form, "submit");
}

// Reason validation: enable confirm when >= 3 chars
document.addEventListener("DOMContentLoaded", function() {
    var reason = document.getElementById("write-modal-reason");
    if (reason) {
        reason.addEventListener("input", function() {
            var confirmBtn = document.getElementById("write-modal-confirm");
            if (reason.value.trim().length >= 3) {
                confirmBtn.disabled = false;
                confirmBtn.classList.remove("opacity-50", "cursor-not-allowed");
            } else {
                confirmBtn.disabled = true;
                confirmBtn.classList.add("opacity-50", "cursor-not-allowed");
            }
        });
    }
});

// Escape key closes modal
document.addEventListener("keydown", function(e) {
    if (e.key === "Escape") {
        var modal = document.getElementById("write-confirm-modal");
        if (modal && !modal.classList.contains("hidden")) {
            closeWriteModal();
        }
    }
});

// HTMX event bridge: close modal on successful write action
document.addEventListener("DOMContentLoaded", function() {
    document.body.addEventListener("htmx:afterRequest", function(evt) {
        // Only handle responses from our write form
        if (evt.detail.elt && evt.detail.elt.id === "write-modal-form") {
            if (evt.detail.successful) {
                closeWriteModal();
            }
        }
    });

    // Bridge for showToast HX-Trigger event (HTMX dispatches custom events from HX-Trigger)
    document.body.addEventListener("showToast", function(evt) {
        if (typeof showToast === "function" && evt.detail) {
            showToast(evt.detail.message, evt.detail.type, evt.detail.duration || 5000);
        }
    });
});

/**
 * Toggle password visibility in the password banner.
 */
function togglePasswordVisibility() {
    var display = document.getElementById("password-display");
    var icon = document.getElementById("password-toggle-icon");
    if (!display) return;

    if (_passwordVisible) {
        // Mask it
        display.setAttribute("data-password", display.textContent);
        display.textContent = "•".repeat(display.textContent.length);
        icon.classList.remove("fa-eye-slash");
        icon.classList.add("fa-eye");
        _passwordVisible = false;
    } else {
        // Show it
        display.textContent = display.getAttribute("data-password") || "";
        icon.classList.remove("fa-eye");
        icon.classList.add("fa-eye-slash");
        _passwordVisible = true;
    }
}

/**
 * Copy password to clipboard.
 */
function copyPassword() {
    var display = document.getElementById("password-display");
    if (!display) return;
    var password = display.getAttribute("data-password") || display.textContent;
    navigator.clipboard.writeText(password).then(function() {
        if (typeof showToast === "function") {
            showToast("Password copied to clipboard", "success", 3000);
        }
    });
}
