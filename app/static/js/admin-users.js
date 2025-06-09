/**
 * Admin User Management JavaScript
 * Handles user CRUD operations and notes management
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize form accessibility
    const forms = document.querySelectorAll('form');
    forms.forEach(form => enhanceFormAccessibility(form));
    
    // Load users on page load
    loadUsers();
    
    // Add User Form Handler
    const addUserForm = document.getElementById('addUserForm');
    if (addUserForm) {
        addUserForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await handleAddUser();
        });
    }
    
    // Event delegation for dynamic buttons
    attachEventListener('[data-action="toggle-user"]', 'click', handleToggleUser);
    attachEventListener('[data-action="update-role"]', 'change', handleUpdateRole);
    attachEventListener('[data-action="view-notes"]', 'click', handleViewNotes);
    attachEventListener('[data-action="add-note"]', 'click', handleAddNote);
    attachEventListener('[data-action="edit-note"]', 'click', handleEditNote);
    attachEventListener('[data-action="delete-note"]', 'click', handleDeleteNote);
    attachEventListener('[data-action="save-note"]', 'click', handleSaveNote);
});

// ===== User Management Functions =====

async function loadUsers() {
    const userList = document.getElementById('userList');
    showLoading(userList, 'Loading the roster of the privileged few...');
    
    try {
        const response = await authenticatedFetch('/admin/api/users');
        const data = await handleApiResponse(response);
        
        if (data.users && data.users.length > 0) {
            displayUsers(data.users);
        } else {
            updateContent(userList, 'No users found. Are you sure this system exists?');
        }
    } catch (error) {
        displayError(error, 'Failed to load users');
        updateContent(userList, 'Failed to load users. The digital deities are displeased.');
    } finally {
        hideLoading(userList);
    }
}

function displayUsers(users) {
    const userList = document.getElementById('userList');
    const tbody = createElement('tbody');
    
    users.forEach(user => {
        const row = createUserRow(user);
        tbody.appendChild(row);
    });
    
    // Create table
    const table = createElement('table', { className: 'table table-hover' });
    const thead = createElement('thead');
    thead.innerHTML = `
        <tr>
            <th>Email</th>
            <th>Role</th>
            <th>Status</th>
            <th>Last Active</th>
            <th>Notes</th>
            <th>Actions</th>
        </tr>
    `;
    
    table.appendChild(thead);
    table.appendChild(tbody);
    
    // Clear and append
    userList.innerHTML = '';
    userList.appendChild(table);
}

function createUserRow(user) {
    const cells = [
        user.email,  // This is a string
        { element: createRoleSelect(user) },  // This returns a DOM element
        { element: createStatusBadge(user) },  // This returns a DOM element
        formatDate(user.last_login),  // This is a string
        { element: createNotesButton(user) },  // This returns a DOM element
        { element: createActionButtons([
            {
                text: user.is_active ? 'Deactivate' : 'Reactivate',
                className: user.is_active ? 'btn-outline-warning' : 'btn-outline-success',
                icon: user.is_active ? 'bi bi-person-slash' : 'bi bi-person-check',
                label: user.is_active ? 'Deactivate user' : 'Reactivate user',
                data: { action: 'toggle-user', userId: user.id }
            }
        ]) }  // This returns a DOM element
    ];
    
    const row = createTableRow(cells);
    row.dataset.userId = user.id;
    return row;
}

function createRoleSelect(user) {
    const select = createElement('select', {
        className: 'form-select form-select-sm',
        dataset: { action: 'update-role', userId: user.id },
        'aria-label': `Role for ${user.email}`
    });
    
    const roles = [
        { value: 'viewer', text: 'Viewer' },
        { value: 'editor', text: 'Editor' },
        { value: 'admin', text: 'Admin' }
    ];
    
    roles.forEach(role => {
        const option = createElement('option', { value: role.value }, role.text);
        if (role.value === user.role) {
            option.selected = true;
        }
        select.appendChild(option);
    });
    
    return select;
}

function createStatusBadge(user) {
    const badge = createElement('span', {
        className: `badge ${user.is_active ? 'bg-success' : 'bg-secondary'}`
    }, user.is_active ? 'Active' : 'Inactive');
    return badge;
}

function createNotesButton(user) {
    const noteCount = user.notes_count || 0;
    const button = createElement('button', {
        className: 'btn btn-sm btn-outline-info',
        type: 'button',
        dataset: { action: 'view-notes', userId: user.id },
        'aria-label': `View notes for ${user.email}`
    });
    
    const icon = createElement('i', { className: 'bi bi-sticky' });
    const text = document.createTextNode(` Notes (${noteCount})`);
    
    button.appendChild(icon);
    button.appendChild(text);
    
    return button;
}

// ===== User Action Handlers =====

async function handleAddUser() {
    const emailInput = document.getElementById('newUserEmail');
    const roleSelect = document.getElementById('newUserRole');
    
    const email = emailInput.value.trim();
    const role = roleSelect.value;
    
    if (!isValidEmail(email)) {
        showToast('Please enter a valid email address', true);
        return;
    }
    
    const submitButton = document.querySelector('#addUserForm button[type="submit"]');
    showLoading(submitButton, 'Adding...');
    
    try {
        const response = await authenticatedFetch('/admin/users/add', {
            method: 'POST',
            body: { email, role }
        });
        
        const data = await handleApiResponse(response);
        
        if (data.success) {
            showToast(`User ${email} has been granted ${role} powers!`);
            emailInput.value = '';
            roleSelect.value = 'viewer';
            await loadUsers();
        } else {
            showToast(data.message || 'Failed to add user', true);
        }
    } catch (error) {
        displayError(error, 'Failed to add user');
    } finally {
        hideLoading(submitButton);
    }
}

async function handleToggleUser(e) {
    const userId = this.dataset.userId;
    const userRow = this.closest('tr');
    const userEmail = userRow.querySelector('td:first-child').textContent;
    const isDeactivating = this.textContent.includes('Deactivate');
    
    const confirmed = await showConfirmModal({
        title: isDeactivating ? 'Deactivate User' : 'Reactivate User',
        message: isDeactivating 
            ? 'Are you sure you want to deactivate this user? They will lose access immediately.'
            : 'Are you sure you want to reactivate this user? They will regain their previous access level.',
        confirmText: isDeactivating ? 'Deactivate' : 'Reactivate',
        confirmClass: isDeactivating ? 'btn-warning' : 'btn-success'
    });
    
    if (!confirmed) return;
    
    try {
        const formData = new FormData();
        formData.append('email', userEmail);
        
        const response = await authenticatedFetch('/admin/users/delete', {
            method: 'POST',
            body: formData
        });
        
        const data = await handleApiResponse(response);
        
        if (data.success) {
            showToast(data.message);
            await loadUsers();
        } else {
            showToast(data.message || 'Failed to update user status', true);
        }
    } catch (error) {
        displayError(error, 'Failed to update user status');
    }
}

async function handleUpdateRole(e) {
    const userId = this.dataset.userId;
    const newRole = this.value;
    const userRow = this.closest('tr');
    const userEmail = userRow.querySelector('td:first-child').textContent;
    
    const confirmed = await showConfirmModal({
        title: 'Update User Role',
        message: `Change ${userEmail}'s role to ${newRole.toUpperCase()}?`,
        confirmText: 'Update Role'
    });
    
    if (!confirmed) {
        // Revert selection
        const user = await getUserData(userId);
        if (user) {
            this.value = user.role;
        }
        return;
    }
    
    try {
        const formData = new FormData();
        formData.append('email', userEmail);
        formData.append('role', newRole);
        
        const response = await authenticatedFetch('/admin/users/update', {
            method: 'POST',
            body: formData
        });
        
        const data = await handleApiResponse(response);
        
        if (data.success) {
            showToast(`Role updated to ${newRole}`);
        } else {
            showToast(data.message || 'Failed to update role', true);
            // Revert selection
            const user = await getUserData(userId);
            if (user) {
                this.value = user.role;
            }
        }
    } catch (error) {
        displayError(error, 'Failed to update role');
    }
}

// ===== Notes Management =====

async function handleViewNotes(e) {
    const userId = this.dataset.userId;
    const userRow = this.closest('tr');
    const userEmail = userRow.querySelector('td:first-child').textContent;
    
    // Show notes modal
    const modal = await createNotesModal(userId, userEmail);
    document.body.appendChild(modal);
    
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    // Load notes
    await loadUserNotes(userId);
    
    // Clean up on hide
    modal.addEventListener('hidden.bs.modal', () => {
        modal.remove();
    });
}

async function createNotesModal(userId, userEmail) {
    const modalId = `notesModal-${userId}`;
    
    const modal = createElement('div', {
        className: 'modal fade',
        id: modalId,
        tabindex: '-1',
        'aria-labelledby': `${modalId}Label`,
        'aria-hidden': 'true',
        dataset: { userId }
    });
    
    modal.innerHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="${modalId}Label">
                        <i class="bi bi-sticky"></i> Notes for ${escapeHtml(userEmail)}
                    </h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <div class="mb-3">
                        <textarea class="form-control" id="newNoteText-${userId}" rows="3" 
                                  placeholder="Add a new note..." aria-label="New note text"></textarea>
                        <button class="btn btn-primary mt-2" data-action="add-note" data-user-id="${userId}">
                            <i class="bi bi-plus-circle"></i> Add Note
                        </button>
                    </div>
                    <hr>
                    <div id="notesList-${userId}">
                        ${createLoadingSpinner('Loading notes...').outerHTML}
                    </div>
                </div>
            </div>
        </div>
    `;
    
    return modal;
}

async function loadUserNotes(userId) {
    const notesList = document.getElementById(`notesList-${userId}`);
    
    try {
        const response = await authenticatedFetch(`/admin/api/users/${userId}/notes`);
        const data = await handleApiResponse(response);
        
        notesList.innerHTML = '';
        
        if (data.notes && data.notes.length > 0) {
            data.notes.forEach(note => {
                const noteElement = createNoteElement(note);
                notesList.appendChild(noteElement);
            });
        } else {
            notesList.innerHTML = '<p class="text-muted">No notes yet. Be the first to document this user\'s quirks.</p>';
        }
    } catch (error) {
        displayError(error, 'Failed to load notes');
        notesList.innerHTML = '<p class="text-danger">Failed to load notes.</p>';
    }
}

function createNoteElement(note) {
    const noteDiv = createElement('div', { className: 'card mb-2' });
    
    const cardBody = createElement('div', { className: 'card-body' });
    const contentDiv = createElement('div', { className: 'd-flex justify-content-between align-items-start' });
    
    // Note content
    const textDiv = createElement('div', { className: 'flex-grow-1' });
    const noteText = createElement('p', { className: 'mb-1 note-text' }, note.note);
    const metadata = createElement('small', { className: 'text-muted' }, 
        `By ${note.created_by} on ${new Date(note.created_at).toLocaleDateString()}`
    );
    
    textDiv.appendChild(noteText);
    textDiv.appendChild(metadata);
    
    // Action buttons
    const actionsDiv = createActionButtons([
        {
            icon: 'bi bi-pencil',
            className: 'btn-outline-primary',
            label: 'Edit note',
            data: { action: 'edit-note', noteId: note.id }
        },
        {
            icon: 'bi bi-trash',
            className: 'btn-outline-danger',
            label: 'Delete note',
            data: { action: 'delete-note', noteId: note.id }
        }
    ]);
    
    contentDiv.appendChild(textDiv);
    contentDiv.appendChild(actionsDiv);
    cardBody.appendChild(contentDiv);
    noteDiv.appendChild(cardBody);
    
    noteDiv.dataset.noteId = note.id;
    return noteDiv;
}

async function handleAddNote(e) {
    const userId = this.dataset.userId;
    const noteTextarea = document.getElementById(`newNoteText-${userId}`);
    const noteText = noteTextarea.value.trim();
    
    if (!noteText) {
        showToast('Note cannot be empty', true);
        return;
    }
    
    showLoading(this, 'Adding...');
    
    try {
        const response = await authenticatedFetch(`/admin/api/users/${userId}/notes`, {
            method: 'POST',
            body: { note: noteText }
        });
        
        const data = await handleApiResponse(response);
        
        if (data.success) {
            noteTextarea.value = '';
            await loadUserNotes(userId);
            updateNotesCount(userId);
            showToast('Note added successfully');
        } else {
            showToast(data.message || 'Failed to add note', true);
        }
    } catch (error) {
        displayError(error, 'Failed to add note');
    } finally {
        hideLoading(this);
    }
}

async function handleEditNote(e) {
    const noteId = this.dataset.noteId;
    const noteCard = this.closest('.card');
    const noteText = noteCard.querySelector('.note-text');
    const currentText = noteText.textContent;
    
    // Create textarea
    const textarea = createElement('textarea', {
        className: 'form-control mb-2',
        value: currentText,
        rows: 3,
        'aria-label': 'Edit note text'
    });
    
    // Replace text with textarea
    noteText.replaceWith(textarea);
    
    // Update button
    this.innerHTML = '<i class="bi bi-check"></i>';
    this.dataset.action = 'save-note';
    this.dataset.originalText = currentText;
    this.setAttribute('aria-label', 'Save note');
    
    // Focus textarea
    textarea.focus();
}

async function handleSaveNote(e) {
    const noteId = this.dataset.noteId;
    const noteCard = this.closest('.card');
    const textarea = noteCard.querySelector('textarea');
    const newText = textarea.value.trim();
    const originalText = this.dataset.originalText;
    
    if (!newText) {
        showToast('Note cannot be empty', true);
        return;
    }
    
    showLoading(this);
    
    try {
        const response = await authenticatedFetch(`/admin/api/users/notes/${noteId}`, {
            method: 'PUT',
            body: { note: newText }
        });
        
        const data = await handleApiResponse(response);
        
        if (data.success) {
            // Replace textarea with updated text
            const p = createElement('p', { className: 'mb-1 note-text' }, newText);
            textarea.replaceWith(p);
            
            // Restore button
            this.innerHTML = '<i class="bi bi-pencil"></i>';
            this.dataset.action = 'edit-note';
            delete this.dataset.originalText;
            this.setAttribute('aria-label', 'Edit note');
            
            showToast('Note updated successfully');
        } else {
            showToast(data.message || 'Failed to update note', true);
        }
    } catch (error) {
        displayError(error, 'Failed to update note');
        // Restore original text on error
        const p = createElement('p', { className: 'mb-1 note-text' }, originalText);
        textarea.replaceWith(p);
        
        this.innerHTML = '<i class="bi bi-pencil"></i>';
        this.dataset.action = 'edit-note';
        delete this.dataset.originalText;
    } finally {
        hideLoading(this);
    }
}

async function handleDeleteNote(e) {
    const noteId = this.dataset.noteId;
    
    const confirmed = await showConfirmModal({
        title: 'Delete Note',
        message: 'Are you sure you want to delete this note?',
        confirmText: 'Delete',
        confirmClass: 'btn-danger'
    });
    
    if (!confirmed) return;
    
    try {
        const response = await authenticatedFetch(`/admin/api/users/notes/${noteId}`, {
            method: 'DELETE'
        });
        
        const data = await handleApiResponse(response);
        
        if (data.success) {
            const noteCard = this.closest('.card');
            const userId = noteCard.closest('.modal').dataset.userId;
            
            noteCard.remove();
            updateNotesCount(userId);
            showToast('Note deleted successfully');
            
            // Check if no notes remain
            const notesList = document.getElementById(`notesList-${userId}`);
            if (notesList && notesList.children.length === 0) {
                notesList.innerHTML = '<p class="text-muted">No notes yet. Be the first to document this user\'s quirks.</p>';
            }
        } else {
            showToast(data.message || 'Failed to delete note', true);
        }
    } catch (error) {
        displayError(error, 'Failed to delete note');
    }
}

// ===== Helper Functions =====

async function getUserData(userId) {
    try {
        const response = await authenticatedFetch('/admin/api/users');
        const data = await handleApiResponse(response);
        
        if (data.users) {
            return data.users.find(u => u.id === parseInt(userId));
        }
        return null;
    } catch (error) {
        console.error('Failed to get user data:', error);
        return null;
    }
}

async function updateNotesCount(userId) {
    try {
        const user = await getUserData(userId);
        
        if (user) {
            // Update notes button in main table
            const userRow = document.querySelector(`tr[data-user-id="${userId}"]`);
            if (userRow) {
                const notesButton = userRow.querySelector('[data-action="view-notes"]');
                if (notesButton) {
                    const count = user.notes_count || 0;
                    notesButton.innerHTML = `<i class="bi bi-sticky"></i> Notes (${count})`;
                }
            }
        }
    } catch (error) {
        console.error('Failed to update notes count:', error);
    }
}