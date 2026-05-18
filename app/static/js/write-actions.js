/**
 * Write Actions - Modal control, reason validation, HTMX event bridge.
 * Phase 9: AD + License write operations UI controller.
 */

/* global htmx, showToast, showBanner */

// State
let _currentActionConfig = null;
let _passwordVisible = true; // D-05: visible by default

function _escapeHtml(str) {
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

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
 * @param {string} [config.modalType] - "assign-license", "swap-license", "remove-license", or undefined (AD).
 * @param {string} [config.userId] - Graph user ID (for license actions).
 * @param {string} [config.skuId] - SKU ID (for remove-license).
 * @param {string} [config.skuName] - SKU display name (for remove-license).
 * @param {Array} [config.currentLicenses] - User's current licenses (for swap-license).
 */
function openWriteModal(config) {
    _currentActionConfig = config;
    var modal = document.getElementById("write-confirm-modal");
    var modalBox = modal.querySelector(".modal-box");
    var title = document.getElementById("write-modal-title");
    var target = document.getElementById("write-modal-target");
    var warning = document.getElementById("write-modal-warning");
    var confirmBtn = document.getElementById("write-modal-confirm");
    var form = document.getElementById("write-modal-form");
    var reason = document.getElementById("write-modal-reason");
    var extraFields = document.getElementById("write-modal-extra-fields");

    // Populate fields
    title.textContent = config.actionTitle;
    target.textContent = "Target: " + config.targetName + " (" + config.targetEmail + ")";

    // Hidden form values
    document.getElementById("write-form-user-dn").value = config.targetDn || "";
    document.getElementById("write-form-display-name").value = config.targetName;
    document.getElementById("write-form-user-email").value = config.targetEmail;

    // Clear extra fields
    if (extraFields) {
        extraFields.innerHTML = "";
    }

    // Modal width adjustment for swap
    if (modalBox) {
        modalBox.classList.remove("max-w-lg");
        modalBox.classList.add("max-w-md");
    }

    // License-specific modal content
    if (config.modalType === "assign-license") {
        _buildAssignLicenseFields(config, extraFields);
    } else if (config.modalType === "swap-license") {
        _buildSwapLicenseFields(config, extraFields);
        if (modalBox) {
            modalBox.classList.remove("max-w-md");
            modalBox.classList.add("max-w-lg");
        }
    } else if (config.modalType === "remove-license") {
        _buildRemoveLicenseFields(config, extraFields);
    }

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
 * Build extra fields for assign-license modal.
 */
function _buildAssignLicenseFields(config, container) {
    if (!container) return;

    var html = '<div class="mb-3">' +
        '<label class="text-xs font-semibold text-gray-700">License to Assign</label>' +
        '<select id="write-license-select" class="w-full border border-gray-300 rounded p-2 text-sm mt-1" ' +
        'onchange="_onLicenseSelectChange()">' +
        '<option disabled selected value="">Loading...</option>' +
        '</select>' +
        '<input type="hidden" name="user_id" id="write-form-user-id">' +
        '<input type="hidden" name="sku_id" id="write-form-sku-id">' +
        '<input type="hidden" name="sku_name" id="write-form-sku-name">' +
        '</div>';
    container.innerHTML = html;

    // Set user_id
    document.getElementById("write-form-user-id").value = config.userId || "";

    // Load SKU options via fetch
    fetch("/search/api/write/available-skus")
        .then(function(resp) { return resp.text(); })
        .then(function(html) {
            var select = document.getElementById("write-license-select");
            if (select) select.innerHTML = html;
        });
}

/**
 * Build extra fields for swap-license modal.
 */
function _buildSwapLicenseFields(config, container) {
    if (!container) return;

    var licenses = config.currentLicenses || [];
    var removeOptions = '<option disabled selected value="">Select license to remove...</option>';
    for (var i = 0; i < licenses.length; i++) {
        var lic = licenses[i];
        var name = _escapeHtml(lic.displayName || lic.name || lic.skuId);
        removeOptions += '<option value="' + _escapeHtml(lic.skuId) + '" data-display-name="' + name + '">' + name + '</option>';
    }

    var html = '<div class="mb-3">' +
        '<label class="text-xs font-semibold text-gray-700">Remove License</label>' +
        '<select id="write-swap-remove-select" class="w-full border border-gray-300 rounded p-2 text-sm mt-1" ' +
        'onchange="_onSwapRemoveChange()">' +
        removeOptions +
        '</select>' +
        '</div>' +
        '<div class="mb-3">' +
        '<label class="text-xs font-semibold text-gray-700">Assign License</label>' +
        '<select id="write-swap-assign-select" class="w-full border border-gray-300 rounded p-2 text-sm mt-1" ' +
        'onchange="_onSwapAssignChange()">' +
        '<option disabled selected value="">Select remove license first...</option>' +
        '</select>' +
        '</div>' +
        '<input type="hidden" name="user_id" id="write-form-user-id">' +
        '<input type="hidden" name="old_sku_id" id="write-form-old-sku-id">' +
        '<input type="hidden" name="old_sku_name" id="write-form-old-sku-name">' +
        '<input type="hidden" name="new_sku_id" id="write-form-new-sku-id">' +
        '<input type="hidden" name="new_sku_name" id="write-form-new-sku-name">';
    container.innerHTML = html;

    // Set user_id
    document.getElementById("write-form-user-id").value = config.userId || "";
}

/**
 * Build extra fields for remove-license modal (pre-populated from chip).
 */
function _buildRemoveLicenseFields(config, container) {
    if (!container) return;

    var html = '<input type="hidden" name="user_id" id="write-form-user-id">' +
        '<input type="hidden" name="sku_id" id="write-form-sku-id">' +
        '<input type="hidden" name="sku_name" id="write-form-sku-name">' +
        '<p class="text-sm text-gray-700 mb-2">' +
        '<i class="fas fa-minus-circle text-red-600 mr-1"></i>' +
        'Remove: <strong>' + _escapeHtml(config.skuName || "Unknown") + '</strong></p>';
    container.innerHTML = html;

    document.getElementById("write-form-user-id").value = config.userId || "";
    document.getElementById("write-form-sku-id").value = config.skuId || "";
    document.getElementById("write-form-sku-name").value = config.skuName || "";
}

/**
 * Handle assign-license select change.
 */
function _onLicenseSelectChange() {
    var select = document.getElementById("write-license-select");
    if (!select) return;
    var option = select.options[select.selectedIndex];
    document.getElementById("write-form-sku-id").value = select.value;
    document.getElementById("write-form-sku-name").value = option.getAttribute("data-display-name") || option.textContent.split(" (")[0];
    _validateLicenseConfirm();
}

/**
 * Handle swap remove-license select change -- load assign options filtered.
 */
function _onSwapRemoveChange() {
    var select = document.getElementById("write-swap-remove-select");
    if (!select) return;
    var option = select.options[select.selectedIndex];
    document.getElementById("write-form-old-sku-id").value = select.value;
    document.getElementById("write-form-old-sku-name").value = option.getAttribute("data-display-name") || option.textContent;

    // Load available SKUs excluding the one being removed
    var assignSelect = document.getElementById("write-swap-assign-select");
    if (assignSelect) {
        assignSelect.innerHTML = '<option disabled selected value="">Loading...</option>';
    }

    fetch("/search/api/write/available-skus?exclude_sku_id=" + encodeURIComponent(select.value))
        .then(function(resp) { return resp.text(); })
        .then(function(html) {
            if (assignSelect) assignSelect.innerHTML = html;
        });

    _validateLicenseConfirm();
}

/**
 * Handle swap assign-license select change.
 */
function _onSwapAssignChange() {
    var select = document.getElementById("write-swap-assign-select");
    if (!select) return;
    var option = select.options[select.selectedIndex];
    document.getElementById("write-form-new-sku-id").value = select.value;
    document.getElementById("write-form-new-sku-name").value = option.getAttribute("data-display-name") || option.textContent.split(" (")[0];
    _validateLicenseConfirm();
}

/**
 * Validate license confirm button state based on dropdown selection + reason.
 */
function _validateLicenseConfirm() {
    var confirmBtn = document.getElementById("write-modal-confirm");
    var reason = document.getElementById("write-modal-reason");
    if (!confirmBtn || !reason) return;

    var reasonValid = reason.value.trim().length >= 3;
    var selectionValid = false;

    if (_currentActionConfig && _currentActionConfig.modalType === "assign-license") {
        var sel = document.getElementById("write-license-select");
        selectionValid = sel && sel.value && sel.value !== "";
    } else if (_currentActionConfig && _currentActionConfig.modalType === "swap-license") {
        var removeSel = document.getElementById("write-swap-remove-select");
        var assignSel = document.getElementById("write-swap-assign-select");
        selectionValid = removeSel && removeSel.value && removeSel.value !== "" &&
                         assignSel && assignSel.value && assignSel.value !== "";
    } else if (_currentActionConfig && _currentActionConfig.modalType === "remove-license") {
        // Pre-populated, always valid
        selectionValid = true;
    } else {
        // AD actions: no dropdown needed
        selectionValid = true;
    }

    if (reasonValid && selectionValid) {
        confirmBtn.disabled = false;
        confirmBtn.classList.remove("opacity-50", "cursor-not-allowed");
    } else {
        confirmBtn.disabled = true;
        confirmBtn.classList.add("opacity-50", "cursor-not-allowed");
    }
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
    var extraFields = document.getElementById("write-modal-extra-fields");
    if (extraFields) extraFields.innerHTML = "";
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

// Reason validation: enable confirm when >= 3 chars (+ license dropdown validation)
document.addEventListener("DOMContentLoaded", function() {
    var reason = document.getElementById("write-modal-reason");
    if (reason) {
        reason.addEventListener("input", function() {
            _validateLicenseConfirm();
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

    // Bridge for showBanner HX-Trigger event (D-09: persistent error banner for double failure)
    document.body.addEventListener("showBanner", function(evt) {
        if (typeof showBanner === "function" && evt.detail) {
            showBanner(evt.detail.message, evt.detail.type || "error", evt.detail.duration || 0);
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
