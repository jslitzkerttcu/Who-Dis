/**
 * Search Profile Display
 * Functions for displaying user profiles
 */

// Merge user data from Azure AD and Genesys sources
function mergeUserData(azureAD, genesys) {
    const merged = {
        // Core Identity - prefer Azure AD
        displayName: azureAD?.displayName || genesys?.name || null,
        givenName: azureAD?.givenName || null,
        surname: azureAD?.surname || null,
        email: azureAD?.mail || genesys?.email || null,
        title: azureAD?.title || genesys?.title || null,
        department: azureAD?.department || genesys?.department || null,

        // Account Details
        username: azureAD?.sAMAccountName || genesys?.username || null,
        userPrincipalName: azureAD?.userPrincipalName || null,
        employeeID: azureAD?.employeeID || null,
        employeeType: azureAD?.employeeType || null,
        genesysUsername: genesys?.username || null,

        // Manager & Office
        manager: azureAD?.manager || null,
        managerEmail: azureAD?.managerEmail || null,
        officeLocation: azureAD?.officeLocation || null,
        companyName: azureAD?.companyName || null,

        // Contact Information
        phoneNumbers: {},
        extension: azureAD?.extension || null,

        // Address
        address: azureAD?.address || null,

        // Groups & Roles
        adGroups: azureAD?.groupMembership || [],
        genesysGroups: genesys?.groups || [],
        genesysRoles: genesys?.roles || [],
        genesysSkills: genesys?.skills || [],
        genesysQueues: genesys?.queues || [],
        genesysLocations: genesys?.locations || [],
        genesysPresence: genesys?.presence || null,

        // Status
        enabled: azureAD?.enabled,
        locked: azureAD?.locked,
        userType: azureAD?.userType || null,
        genesysState: genesys?.state || null,

        // Dates
        createdDateTime: azureAD?.createdDateTime || null,
        employeeHireDate: azureAD?.employeeHireDate || null,
        pwdLastSet: azureAD?.pwdLastSet || null,
        pwdExpires: azureAD?.pwdExpires || null,
        lastPasswordChangeDateTime: azureAD?.lastPasswordChangeDateTime || null,
        refreshTokensValidFromDateTime: azureAD?.refreshTokensValidFromDateTime || null,
        signInSessionsValidFromDateTime: azureAD?.signInSessionsValidFromDateTime || null,
        onPremisesLastSyncDateTime: azureAD?.onPremisesLastSyncDateTime || null,
        dateOfBirth: azureAD?.dateOfBirth || null,
        lastLoginDate: genesys?.lastLoginDate || null,

        // Photo
        thumbnailPhoto: azureAD?.thumbnailPhoto || null,
        hasPhotoCached: azureAD?.hasPhotoCached || false,
        graphId: azureAD?.graphId || null,

        // Password policies
        passwordPolicies: azureAD?.passwordPolicies || null,

        // Data source flags
        hasAzureAD: !!azureAD,
        hasGenesys: !!genesys,
        hasGraphData: azureAD?.hasGraphData || false
    };

    // Merge phone numbers from both sources
    if (azureAD?.phoneNumbers) {
        Object.assign(merged.phoneNumbers, azureAD.phoneNumbers);
    }
    if (genesys?.phoneNumbers) {
        for (const [type, number] of Object.entries(genesys.phoneNumbers)) {
            if (!merged.phoneNumbers[type]) {
                merged.phoneNumbers[type] = number;
            }
        }
    }

    return merged;
}

// Format unified profile display
function formatUnifiedProfile(user) {
    if (!user || (!user.hasAzureAD && !user.hasGenesys)) {
        return '<p class="text-muted">No user found</p>';
    }

    let html = createCard(createProfileContent(user));
    
    // Load admin notes if user has admin role
    const userRole = document.getElementById('app-data')?.getAttribute('data-user-role');
    if (userRole === 'admin' && user.email) {
        setTimeout(() => loadAdminNotes(user.email), 100);
    }
    
    return html;
}

// Create the main profile content
function createProfileContent(user) {
    let content = '';
    
    // Profile header with photo and status badges
    content += createProfileHeader(user);
    
    // Main content sections
    content += '<div class="row mt-4">';
    content += '<div class="col-md-6">';
    
    // Contact Information
    content += createContactSection(user);
    
    // Account Details
    content += createAccountDetailsSection(user);
    
    content += '</div>';
    content += '<div class="col-md-6">';
    
    // Date Information
    content += createDateSection(user);
    
    // Group Memberships
    content += createGroupsSection(user);
    
    // Genesys Information
    if (user.hasGenesys) {
        content += createGenesysSection(user);
    }
    
    content += '</div>';
    content += '</div>';
    
    // Admin Notes Section
    const userRole = document.getElementById('app-data')?.getAttribute('data-user-role');
    if (userRole === 'admin') {
        content += createAdminNotesSection();
    }
    
    return content;
}

// Create profile header with photo and badges
function createProfileHeader(user) {
    let html = '<div class="d-flex align-items-start mb-4">';
    
    // Profile photo
    html += '<div class="me-4">';
    if (user.thumbnailPhoto) {
        html += `<img src="${user.thumbnailPhoto}" class="rounded-circle" style="width: 120px; height: 120px; object-fit: cover;" alt="Profile">`;
    } else if (user.hasPhotoCached || user.graphId) {
        html += `<img src="/static/img/user-placeholder.svg" data-graph-id="${user.graphId || ''}" data-upn="${user.userPrincipalName || ''}" class="rounded-circle lazy-photo" style="width: 120px; height: 120px; object-fit: cover;" alt="Profile">`;
    } else {
        html += '<div class="rounded-circle bg-light d-flex align-items-center justify-content-center" style="width: 120px; height: 120px;">';
        html += '<i class="bi bi-person-fill text-secondary" style="font-size: 3rem;"></i>';
        html += '</div>';
    }
    html += '</div>';
    
    // User info
    html += '<div class="flex-grow-1">';
    html += '<div class="d-flex justify-content-between align-items-start mb-2">';
    
    // Name and title
    html += '<div>';
    html += `<h4 class="mb-1">${escapeHtml(user.displayName || 'Unknown User')}</h4>`;
    if (user.title) {
        html += `<p class="text-muted mb-0">${escapeHtml(user.title)}</p>`;
    }
    if (user.department) {
        html += `<p class="text-muted mb-0">${escapeHtml(user.department)}</p>`;
    }
    if (user.officeLocation) {
        html += `<p class="text-muted mb-0">${escapeHtml(user.officeLocation)}</p>`;
    }
    html += '</div>';
    
    // Status badges
    html += '<div class="text-end">';
    const badges = createStatusBadges(user);
    badges.forEach((badge, index) => {
        if (index > 0 && index % 2 === 0) html += '<br>';
        html += badge;
        if (index < badges.length - 1 && (index + 1) % 2 !== 0) html += ' ';
    });
    html += '</div>';
    
    html += '</div>';
    html += '</div>';
    html += '</div>';
    
    return html;
}

// Create contact information section
function createContactSection(user) {
    let items = [];
    
    // Email
    if (user.email) {
        items.push(createDefinitionItem('Email', 
            `<a href="mailto:${encodeURIComponent(user.email)}">${escapeHtml(user.email)}</a>`, null, '-', false));
    }
    
    // Phone numbers
    const phoneDisplay = createPhoneDisplay(user.phoneNumbers, user.extension);
    if (phoneDisplay !== '<span class="text-muted">No phone numbers</span>') {
        items.push(`<dt class="col-sm-4">Phone:</dt><dd class="col-sm-8">${phoneDisplay}</dd>`);
    }
    
    // Manager
    if (user.manager) {
        let managerDisplay = escapeHtml(user.manager);
        if (user.managerEmail) {
            managerDisplay = `<a href="mailto:${encodeURIComponent(user.managerEmail)}">${escapeHtml(user.manager)}</a>`;
        }
        items.push(createDefinitionItem('Manager', managerDisplay, null, '-', false));
    }
    
    // Address
    if (user.address) {
        items.push(createDefinitionItem('Address', user.address));
    }
    
    return createSection('Contact Information', 'bi bi-person-lines-fill', 
        `<dl class="row">${items.join('')}</dl>`);
}

// Create account details section
function createAccountDetailsSection(user) {
    let items = [];
    
    if (user.username) {
        items.push(createDefinitionItem('Username', user.username));
    }
    if (user.userPrincipalName && user.userPrincipalName !== user.email) {
        items.push(createDefinitionItem('UPN', user.userPrincipalName));
    }
    if (user.employeeID) {
        items.push(createDefinitionItem('Employee ID', user.employeeID));
    }
    if (user.employeeType) {
        items.push(createDefinitionItem('Employee Type', user.employeeType));
    }
    if (user.companyName) {
        items.push(createDefinitionItem('Company', user.companyName));
    }
    if (user.genesysUsername && user.genesysUsername !== user.username) {
        items.push(createDefinitionItem('Genesys Username', user.genesysUsername, 'genesys'));
    }
    if (user.genesysState) {
        items.push(createDefinitionItem('Genesys State', user.genesysState, 'genesys'));
    }
    
    if (items.length === 0) return '';
    
    return createSection('Account Details', 'bi bi-card-text', 
        `<dl class="row">${items.join('')}</dl>`);
}

// Create date information section
function createDateSection(user) {
    const dateFields = [];
    
    // Collect all date fields
    if (user.employeeHireDate) {
        dateFields.push(formatDateInfo(user.employeeHireDate, 'Hire Date'));
    }
    if (user.createdDateTime) {
        dateFields.push(formatDateInfo(user.createdDateTime, 'Account Created'));
    }
    if (user.pwdLastSet) {
        dateFields.push(formatDateInfo(user.pwdLastSet, 'Password Last Set'));
    }
    if (user.pwdExpires) {
        dateFields.push(formatDateInfo(user.pwdExpires, 'Password Expires'));
    }
    if (user.lastLoginDate) {
        dateFields.push(formatDateInfo(user.lastLoginDate, 'Last Genesys Login'));
    }
    if (user.dateOfBirth) {
        dateFields.push(formatDateInfo(user.dateOfBirth, 'Date of Birth', false));
    }
    
    // Sort by date (most recent first for past dates, soonest first for future dates)
    dateFields.sort((a, b) => {
        if (!a || !b) return 0;
        const aDate = new Date(a.dateStr);
        const bDate = new Date(b.dateStr);
        const now = new Date();
        
        // Future dates (like expiration) should be sorted soonest first
        if (aDate > now && bDate > now) {
            return aDate - bDate;
        }
        // Past dates should be sorted most recent first
        return bDate - aDate;
    });
    
    const dateDisplay = createDateFieldsDisplay(dateFields);
    if (!dateDisplay) return '';
    
    return createSection('Important Dates', 'bi bi-calendar3', dateDisplay);
}

// Create groups section
function createGroupsSection(user) {
    let sections = [];
    
    // AD Groups
    if (user.adGroups && user.adGroups.length > 0) {
        const adGroupsHtml = formatGroupList(user.adGroups, 'secondary');
        sections.push(createCollapsibleSection('adGroups', 
            `AD Groups ${createServiceBadge('ad')}`, 
            'bi bi-people-fill', 
            adGroupsHtml, 
            false));
    }
    
    // Genesys Groups
    if (user.genesysGroups && user.genesysGroups.length > 0) {
        const genesysGroupsHtml = formatGroupList(user.genesysGroups, 'secondary');
        sections.push(createCollapsibleSection('genesysGroups', 
            `Genesys Groups ${createServiceBadge('genesys')}`, 
            'bi bi-people-fill', 
            genesysGroupsHtml, 
            false));
    }
    
    if (sections.length === 0) return '';
    
    return sections.join('');
}

// Create Genesys-specific section
function createGenesysSection(user) {
    let sections = [];
    
    // Skills
    if (user.genesysSkills && user.genesysSkills.length > 0) {
        const skillsHtml = user.genesysSkills.map(skill => {
            const name = escapeHtml(skill.name || skill);
            const proficiency = skill.proficiency ? ` (${escapeHtml(skill.proficiency)})` : '';
            return `<span class="badge bg-info me-1 mb-1">${name}${proficiency}</span>`;
        }).join('');
        
        sections.push(createCollapsibleSection('genesysSkills',
            `Skills ${createServiceBadge('genesys')}`,
            'bi bi-award',
            skillsHtml,
            false));
    }
    
    // Queues
    if (user.genesysQueues && user.genesysQueues.length > 0) {
        const queuesHtml = formatGroupList(user.genesysQueues, 'warning text-dark');
        sections.push(createCollapsibleSection('genesysQueues',
            `Queues ${createServiceBadge('genesys')}`,
            'bi bi-headset',
            queuesHtml,
            false));
    }
    
    // Locations
    if (user.genesysLocations && user.genesysLocations.length > 0) {
        const locationsHtml = user.genesysLocations.map(loc => 
            `<span class="badge bg-success me-1 mb-1">${escapeHtml(loc)}</span>`
        ).join('');
        
        sections.push(createCollapsibleSection('genesysLocations',
            `Locations ${createServiceBadge('genesys')}`,
            'bi bi-geo-alt',
            locationsHtml,
            false));
    }
    
    return sections.join('');
}

// Create admin notes section placeholder
function createAdminNotesSection() {
    return `
        <div class="mt-4">
            <h6><i class="bi bi-sticky-fill"></i> Internal Notes 
                <button class="btn btn-sm btn-outline-secondary float-end" onclick="addNewNote()">
                    <i class="bi bi-plus-circle"></i> Add Note
                </button>
            </h6>
            <div id="adminNotesContent">
                <div class="text-center text-muted">
                    <div class="spinner-border spinner-border-sm" role="status">
                        <span class="visually-hidden">Loading notes...</span>
                    </div>
                </div>
            </div>
        </div>
    `;
}