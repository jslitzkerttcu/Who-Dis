/**
 * Admin Notes Management
 * Functions for handling admin notes on user profiles
 */

// Current user email for notes
let currentNotesUserEmail = null;

// Load admin notes for a user
async function loadAdminNotes(userEmail) {
    currentNotesUserEmail = userEmail;
    const notesContainer = document.getElementById('adminNotesContent');
    
    if (!notesContainer) return;
    
    try {
        const response = await fetch(`/admin/api/users/by-email/${encodeURIComponent(userEmail)}/notes`);
        const data = await response.json();
        
        displayNotes(data.notes);
    } catch (error) {
        console.error('Error loading notes:', error);
        notesContainer.innerHTML = '<p class="text-danger">Error loading notes</p>';
    }
}

// Display notes in the container
function displayNotes(notes) {
    const container = document.getElementById('adminNotesContent');
    
    if (!notes || notes.length === 0) {
        container.innerHTML = '<p class="text-muted">No notes yet</p>';
        return;
    }
    
    let html = '<div class="notes-list">';
    notes.forEach(note => {
        html += createNoteCard(note);
    });
    html += '</div>';
    
    container.innerHTML = html;
    attachNoteEventHandlers();
}

// Create a single note card
function createNoteCard(note) {
    const createdDate = note.created_at ? new Date(note.created_at) : null;
    const updatedDate = note.updated_at ? new Date(note.updated_at) : null;
    
    let dateInfo = '';
    if (createdDate) {
        const dateStr = `${createdDate.getMonth() + 1}/${createdDate.getDate()}/${createdDate.getFullYear()}`;
        dateInfo = `Created ${dateStr} by ${escapeHtml(note.created_by || 'Unknown')}`;
        
        if (updatedDate && updatedDate > createdDate) {
            const updateStr = `${updatedDate.getMonth() + 1}/${updatedDate.getDate()}/${updatedDate.getFullYear()}`;
            dateInfo += ` • Updated ${updateStr}`;
        }
    }
    
    return `
        <div class="card mb-2 note-card" data-note-id="${note.id}">
            <div class="card-body p-2">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1 note-content">
                        <p class="mb-1 note-text">${escapeHtml(note.note)}</p>
                        <small class="text-muted">${dateInfo}</small>
                    </div>
                    <div class="note-actions ms-2">
                        <button class="btn btn-sm btn-link p-0 me-2 edit-note" title="Edit">
                            <i class="bi bi-pencil"></i>
                        </button>
                        <button class="btn btn-sm btn-link p-0 text-danger delete-note" title="Delete">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Attach event handlers to note cards
function attachNoteEventHandlers() {
    // Edit buttons
    document.querySelectorAll('.edit-note').forEach(btn => {
        btn.addEventListener('click', function() {
            const noteCard = this.closest('.note-card');
            const noteId = noteCard.dataset.noteId;
            editNoteInline(noteId, noteCard);
        });
    });
    
    // Delete buttons
    document.querySelectorAll('.delete-note').forEach(btn => {
        btn.addEventListener('click', function() {
            const noteCard = this.closest('.note-card');
            const noteId = noteCard.dataset.noteId;
            if (confirm('Are you sure you want to delete this note?')) {
                deleteNote(noteId, noteCard);
            }
        });
    });
}

// Edit note inline
function editNoteInline(noteId, noteCard) {
    const noteText = noteCard.querySelector('.note-text').textContent;
    const noteContent = noteCard.querySelector('.note-content');
    
    const originalHtml = noteContent.innerHTML;
    
    noteContent.innerHTML = `
        <div class="edit-form">
            <textarea class="form-control form-control-sm mb-2" rows="2">${escapeHtml(noteText)}</textarea>
            <div class="btn-group btn-group-sm">
                <button class="btn btn-primary save-edit">Save</button>
                <button class="btn btn-secondary cancel-edit">Cancel</button>
            </div>
        </div>
    `;
    
    const textarea = noteContent.querySelector('textarea');
    const saveBtn = noteContent.querySelector('.save-edit');
    const cancelBtn = noteContent.querySelector('.cancel-edit');
    
    // Focus and select text
    textarea.focus();
    textarea.select();
    
    // Save handler
    saveBtn.addEventListener('click', () => {
        const newText = textarea.value.trim();
        if (newText && newText !== noteText) {
            saveNoteEdit(noteId, newText, noteCard);
        } else {
            noteContent.innerHTML = originalHtml;
        }
    });
    
    // Cancel handler
    cancelBtn.addEventListener('click', () => {
        noteContent.innerHTML = originalHtml;
    });
    
    // Enter to save, Escape to cancel
    textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            saveBtn.click();
        } else if (e.key === 'Escape') {
            cancelBtn.click();
        }
    });
}

// Save note edit
async function saveNoteEdit(noteId, newText, noteCard) {
    try {
        const response = await fetch(`/admin/api/users/notes/${noteId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCSRFToken()
            },
            body: JSON.stringify({ note: newText })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Reload notes to get updated timestamps
            loadAdminNotes(currentNotesUserEmail);
        } else {
            alert('Error updating note: ' + (data.message || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error updating note:', error);
        alert('Error updating note');
    }
}

// Delete note
async function deleteNote(noteId, noteCard) {
    try {
        const response = await fetch(`/admin/api/users/notes/${noteId}`, {
            method: 'DELETE',
            headers: {
                'X-CSRF-Token': getCSRFToken()
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Animate removal
            noteCard.style.transition = 'opacity 0.3s';
            noteCard.style.opacity = '0';
            setTimeout(() => {
                noteCard.remove();
                // Check if no notes left
                const container = document.getElementById('adminNotesContent');
                if (container && container.querySelectorAll('.note-card').length === 0) {
                    container.innerHTML = '<p class="text-muted">No notes yet</p>';
                }
            }, 300);
        } else {
            alert('Error deleting note: ' + (data.message || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error deleting note:', error);
        alert('Error deleting note');
    }
}

// Add new note
async function addNewNote() {
    if (!currentNotesUserEmail) {
        alert('No user selected');
        return;
    }
    
    const noteText = prompt('Enter note:');
    if (!noteText || !noteText.trim()) return;
    
    try {
        const response = await fetch(`/admin/api/users/by-email/${encodeURIComponent(currentNotesUserEmail)}/notes`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCSRFToken()
            },
            body: JSON.stringify({ note: noteText.trim() })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Reload notes to show the new one
            loadAdminNotes(currentNotesUserEmail);
        } else {
            alert('Error adding note: ' + (data.message || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error adding note:', error);
        alert('Error adding note');
    }
}

// Utility function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}