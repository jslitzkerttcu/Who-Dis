/**
 * Search UI Components
 * Reusable UI builders for badges, sections, cards, etc.
 */

// Badge configurations
const BADGE_CONFIGS = {
    teams: { color: '#4f42b5', label: 'Teams' },
    genesys: { color: '#FF4F1F', label: 'Genesys' },
    ad: { color: '#007c59', label: 'AD' },
    enabled: { color: '#198754', label: 'AD Enabled', class: 'bg-success' },
    disabled: { color: '#dc3545', label: 'AD Disabled', class: 'bg-danger' },
    locked: { color: '#ffc107', label: 'Account Locked', class: 'bg-warning text-dark' },
    unlocked: { color: '#198754', label: 'Account Unlocked', class: 'bg-success' }
};

// Phone label priorities for deduplication
const PHONE_LABEL_PRIORITY = {
    'Phone': 1,
    'Office': 2,
    'Work': 3,
    'Business': 4,
    'Primary': 5,
    'Cell Phone': 6,
    'Mobile': 7,
    'Teams DID': 8,
    'Genesys DID': 9,
    'Extension': 10,
    'Genesys Ext': 11,
    'Work 3': 12
};

// Create a badge element
function createBadge(type, customText = null, customClass = null, size = '0.7rem') {
    const config = BADGE_CONFIGS[type];
    if (!config) {
        return `<span class="badge ${customClass || 'bg-secondary'}" style="font-size: ${size};">${escapeHtml(customText || type)}</span>`;
    }
    
    const badgeClass = config.class || 'badge';
    const style = config.class ? `font-size: ${size};` : `background-color: ${config.color}; font-size: ${size};`;
    const text = customText || config.label;
    
    return `<span class="${badgeClass}" style="${style}">${escapeHtml(text)}</span>`;
}

// Create a service badge (Teams, Genesys, AD)
function createServiceBadge(service) {
    return createBadge(service.toLowerCase());
}

// Create status badges for account status
function createStatusBadges(user) {
    let badges = [];
    
    // AD Status
    if (user.enabled !== undefined) {
        badges.push(user.enabled ? createBadge('enabled') : createBadge('disabled'));
    }
    
    // Lock Status
    if (user.locked !== undefined) {
        badges.push(user.locked ? createBadge('locked') : createBadge('unlocked'));
    }
    
    // Teams/Genesys badges
    if (user.userType) {
        const userType = user.userType;
        if (userType.is_genesys_extension_only || userType.is_genesys_with_did || userType.is_dual_user) {
            badges.push(createBadge('genesys', 'Genesys User'));
        }
        if (userType.is_teams_user || userType.is_dual_user) {
            badges.push(createBadge('teams', 'Teams User'));
        }
    }
    
    return badges;
}

// Create a definition list item
function createDefinitionItem(label, value, serviceBadge = null, fallback = '-', escapeValue = true) {
    const displayValue = escapeValue ? escapeHtml(value || fallback) : (value || fallback);
    const badge = serviceBadge ? ` ${createServiceBadge(serviceBadge)}` : '';
    return `<dt class="col-sm-4">${escapeHtml(label)}:</dt><dd class="col-sm-8">${displayValue}${badge}</dd>`;
}

// Create a collapsible section
function createCollapsibleSection(id, title, icon, items, expanded = false) {
    const collapseClass = expanded ? 'show' : '';
    const ariaExpanded = expanded ? 'true' : 'false';
    const itemCount = Array.isArray(items) ? items.length : 0;
    
    return `
        <h6>
            <i class="${icon}"></i> ${escapeHtml(title)}
            ${itemCount > 0 ? `<span class="badge bg-secondary ms-2">${itemCount}</span>` : ''}
            <a class="float-end text-decoration-none" data-bs-toggle="collapse" href="#${id}" 
               role="button" aria-expanded="${ariaExpanded}" aria-controls="${id}">
                <i class="bi bi-chevron-${expanded ? 'up' : 'down'}"></i>
            </a>
        </h6>
        <div class="collapse ${collapseClass}" id="${id}">
            <div class="mt-2">
                ${Array.isArray(items) ? items.join('') : items}
            </div>
        </div>
    `;
}

// Create a section with icon and content
function createSection(title, icon, content) {
    return `
        <h6><i class="${icon}"></i> ${escapeHtml(title)}</h6>
        ${content}
    `;
}

// Create a card structure
function createCard(content, headerContent = null, footerContent = null) {
    let html = '<div class="card">';
    
    if (headerContent) {
        html += `<div class="card-header">${headerContent}</div>`;
    }
    
    html += `<div class="card-body">${content}</div>`;
    
    if (footerContent) {
        html += `<div class="card-footer">${footerContent}</div>`;
    }
    
    html += '</div>';
    return html;
}

// Create a user selection card for multiple results
function createUserSelectionCard(user, index, source, onClickFunction) {
    const name = escapeHtml(user.displayName || user.name || 'Unknown');
    const email = escapeHtml(user.mail || user.email || '');
    const title = escapeHtml(user.title || '');
    const dept = escapeHtml(user.department || '');
    
    let details = [];
    if (title) details.push(title);
    if (dept) details.push(dept);
    if (email) details.push(email);
    
    // Updated to use Tailwind classes and add preview button
    return `
        <div class="bg-white rounded-lg shadow-md border border-gray-200 hover:shadow-lg transition-shadow duration-200 p-4 cursor-pointer"
             onclick="${onClickFunction}">
            <div class="flex justify-between items-start">
                <div class="flex-1">
                    <h6 class="text-lg font-semibold text-gray-900">${name}</h6>
                    ${details.length > 0 ? `<p class="text-sm text-gray-600 mt-1">${details.join(' • ')}</p>` : ''}
                </div>
                ${email ? `
                <button class="ml-2 text-indigo-600 hover:text-indigo-900 text-sm"
                        onclick="event.stopPropagation(); loadUserPreview('${email}', this)"
                        hx-get="/search/api/user/${email}/preview"
                        hx-target="#preview-${source}-${index}"
                        hx-swap="innerHTML">
                    <i class="fas fa-eye"></i>
                </button>
                ` : ''}
            </div>
            <div id="preview-${source}-${index}" class="htmx-preview mt-3"></div>
        </div>
    `;
}

// Load user preview function
function loadUserPreview(email, button) {
    // Htmx will handle the actual loading
    // This function can be used for any additional JS logic if needed
    console.log(`Loading preview for ${email}`);
}

// Format a list of groups with badges
function formatGroupList(groups, badgeType = 'secondary') {
    if (!groups || groups.length === 0) return '<span class="text-muted">None</span>';
    
    return groups.map(group => {
        let groupName;
        
        // Handle different group formats
        if (typeof group === 'object' && group.name) {
            // Genesys format: {id: ..., name: ...}
            groupName = group.name;
        } else if (typeof group === 'string') {
            // LDAP format: CN=GroupName,OU=...
            groupName = group.includes('CN=') ? group.split(',')[0].substring(3) : group;
        } else {
            // Fallback
            groupName = String(group);
        }
        
        return `<span class="badge bg-${badgeType} me-1 mb-1">${escapeHtml(groupName)}</span>`;
    }).join('');
}

// Create phone display with deduplication
function createPhoneDisplay(phoneNumbers, extension = null) {
    if (!phoneNumbers || Object.keys(phoneNumbers).length === 0) {
        return '<span class="text-muted">No phone numbers</span>';
    }
    
    // Create a map to deduplicate phone numbers
    const phoneMap = new Map();
    
    // Process all phone numbers
    for (const [type, number] of Object.entries(phoneNumbers)) {
        // Skip the _user_type object and empty values
        if (!number || type === '_user_type' || type === 'userType') continue;
        
        const formatted = formatPhoneNumber(number);
        let label = '';
        let source = '';
        
        // Determine label and source based on type
        if (type === 'mobile') {
            label = 'Cell Phone';
            source = 'AD';
        } else if (type === 'teams_did') {
            label = 'Teams DID';
            source = 'Teams';
        } else if (type === 'genesys_did') {
            label = 'Genesys DID';
            source = 'Genesys';
        } else if (type === 'genesys_ext') {
            label = 'Extension';
            source = 'Genesys';
        } else {
            label = type.charAt(0).toUpperCase() + type.slice(1);
            source = 'Unknown';
        }
        
        // Check if this phone number already exists
        if (phoneMap.has(formatted)) {
            const existing = phoneMap.get(formatted);
            if (!existing.sources.includes(source) && source) {
                existing.sources.push(source);
            }
            // Update label if the new one has higher priority
            if (PHONE_LABEL_PRIORITY[label] < PHONE_LABEL_PRIORITY[existing.label]) {
                existing.label = label;
            }
        } else {
            phoneMap.set(formatted, {
                label: label,
                sources: source ? [source] : [],
                originalType: type
            });
        }
    }
    
    // Convert to HTML
    const phoneHtml = [];
    phoneMap.forEach((info, number) => {
        let badgeHtml = '';
        if (info.sources.includes('Teams')) {
            badgeHtml += ' ' + createBadge('teams');
        }
        if (info.sources.includes('Genesys')) {
            badgeHtml += ' ' + createBadge('genesys');
        }
        phoneHtml.push(`<strong>${escapeHtml(info.label)}:</strong> ${escapeHtml(number)}${badgeHtml}`);
    });
    
    // Add extension if not already included
    if (extension && !phoneMap.has(formatPhoneNumber(extension))) {
        phoneHtml.push(`<strong>Extension:</strong> ${escapeHtml(formatPhoneNumber(extension))}`);
    }
    
    return phoneHtml.join('<br>');
}

// Create date fields display
function createDateFieldsDisplay(dateFields) {
    if (!dateFields || dateFields.length === 0) return '';
    
    return dateFields.map(field => {
        if (!field) return '';
        
        let html = `<strong>${field.label}:</strong> ${field.dateStr}`;
        if (field.timeStr !== '00:00') {
            html += ` at ${field.timeStr}`;
        }
        if (field.daysInfo) {
            const daysClass = field.daysClass ? ` class="${field.daysClass}"` : '';
            html += ` <small${daysClass}>(${field.daysInfo})</small>`;
        }
        return html;
    }).filter(Boolean).join('<br>');
}