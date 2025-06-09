/**
 * Genesys Blocked Numbers Management
 * Handles CRUD operations for blocked phone numbers
 */

class BlockedNumbersManager {
    constructor() {
        this.blockedNumbers = [];
        this.filteredNumbers = [];
        this.isEditing = false;
        this.editingAni = null;
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadBlockedNumbers();
    }

    setupEventListeners() {
        // Search functionality
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.addEventListener('input', () => this.filterNumbers());
        }

        // Refresh button
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.showToast('Refreshing blocked numbers...', 'info');
                this.loadBlockedNumbers();
            });
        }

        // Add number button
        const addBtn = document.getElementById('add-number-btn');
        if (addBtn) {
            addBtn.addEventListener('click', () => this.openAddModal());
        }

        // Modal controls
        this.setupModalEvents();
        
        // Form validation
        this.setupFormValidation();
    }

    setupModalEvents() {
        // Add/Edit modal
        const modal = document.getElementById('number-modal');
        const cancelBtn = document.getElementById('cancel-btn');
        const form = document.getElementById('number-form');

        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.closeModal());
        }

        if (form) {
            form.addEventListener('submit', (e) => this.handleFormSubmit(e));
        }

        // Delete modal
        const deleteModal = document.getElementById('delete-modal');
        const cancelDeleteBtn = document.getElementById('cancel-delete-btn');
        const confirmDeleteBtn = document.getElementById('confirm-delete-btn');

        if (cancelDeleteBtn) {
            cancelDeleteBtn.addEventListener('click', () => this.closeDeleteModal());
        }

        if (confirmDeleteBtn) {
            confirmDeleteBtn.addEventListener('click', () => this.confirmDelete());
        }

        // Close modals on background click
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) this.closeModal();
            });
        }

        if (deleteModal) {
            deleteModal.addEventListener('click', (e) => {
                if (e.target === deleteModal) this.closeDeleteModal();
            });
        }
    }

    setupFormValidation() {
        const aniInput = document.getElementById('ani-input');
        const reasonInput = document.getElementById('reason-input');
        const charCount = document.getElementById('char-count');

        // ANI input validation (digits only)
        if (aniInput) {
            aniInput.addEventListener('input', (e) => {
                // Remove non-digits
                e.target.value = e.target.value.replace(/\D/g, '');
                
                // Limit to 11 digits
                if (e.target.value.length > 11) {
                    e.target.value = e.target.value.slice(0, 11);
                }

                this.validateForm();
            });
        }

        // Reason input character count
        if (reasonInput && charCount) {
            reasonInput.addEventListener('input', (e) => {
                const count = e.target.value.length;
                charCount.textContent = count;
                
                if (count > 200) {
                    charCount.parentElement.classList.add('text-red-500');
                } else {
                    charCount.parentElement.classList.remove('text-red-500');
                }

                this.validateForm();
            });
        }
    }

    validateForm() {
        const aniInput = document.getElementById('ani-input');
        const reasonInput = document.getElementById('reason-input');
        const saveBtn = document.getElementById('save-btn');

        if (!aniInput || !reasonInput || !saveBtn) return;

        const aniValid = aniInput.value.length === 11;
        const reasonValid = reasonInput.value.trim().length > 0 && reasonInput.value.length <= 200;

        saveBtn.disabled = !(aniValid && reasonValid);
        
        if (saveBtn.disabled) {
            saveBtn.classList.add('opacity-50', 'cursor-not-allowed');
        } else {
            saveBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    }

    async loadBlockedNumbers() {
        this.showLoading();
        
        try {
            const response = await fetch('/utilities/api/blocked-numbers', {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.blockedNumbers = data.entities || [];
            this.filteredNumbers = [...this.blockedNumbers];
            
            this.updateStatistics();
            this.renderTable();
            this.showMainContent();
            
            // Show success toast for successful load
            this.showToast(`Loaded ${this.blockedNumbers.length} blocked numbers from Genesys`, 'success');

        } catch (error) {
            console.error('Error loading blocked numbers:', error);
            this.showError(`Failed to load blocked numbers: ${error.message}`);
            this.showToast('Failed to load blocked numbers from Genesys', 'error');
        }
    }

    filterNumbers() {
        const searchInput = document.getElementById('search-input');
        if (!searchInput) return;

        const searchTerm = searchInput.value.toLowerCase().trim();
        
        if (!searchTerm) {
            this.filteredNumbers = [...this.blockedNumbers];
        } else {
            this.filteredNumbers = this.blockedNumbers.filter(number => 
                number.key.toLowerCase().includes(searchTerm) ||
                (number['Reason Blocked'] && number['Reason Blocked'].toLowerCase().includes(searchTerm))
            );
        }

        this.updateStatistics();
        this.renderTable();
    }

    updateStatistics() {
        const totalCount = document.getElementById('total-count');
        const filteredCount = document.getElementById('filtered-count');
        const lastUpdated = document.getElementById('last-updated');

        if (totalCount) totalCount.textContent = this.blockedNumbers.length;
        if (filteredCount) filteredCount.textContent = this.filteredNumbers.length;
        if (lastUpdated) lastUpdated.textContent = new Date().toLocaleString();
    }

    renderTable() {
        const tbody = document.getElementById('blocked-numbers-table');
        const emptyState = document.getElementById('empty-state');
        
        if (!tbody) return;

        if (this.filteredNumbers.length === 0) {
            tbody.innerHTML = '';
            if (emptyState) emptyState.classList.remove('hidden');
            return;
        }

        if (emptyState) emptyState.classList.add('hidden');

        tbody.innerHTML = this.filteredNumbers.map(number => {
            const ani = this.escapeHtml(number.key || '');
            const reason = this.escapeHtml(number['Reason Blocked'] || '');
            const hasEditPermission = window.userRole === 'editor' || window.userRole === 'admin';
            const hasDeletePermission = window.userRole === 'admin';

            return `
                <tr class="hover:bg-gray-50">
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="flex items-center">
                            <i class="fas fa-phone text-gray-400 mr-2"></i>
                            <span class="text-sm font-medium text-gray-900">${this.formatPhoneNumber(ani)}</span>
                        </div>
                    </td>
                    <td class="px-6 py-4">
                        <div class="text-sm text-gray-900 max-w-md">${reason}</div>
                    </td>
                    ${hasEditPermission || hasDeletePermission ? `
                    <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <div class="flex justify-end space-x-2">
                            ${hasEditPermission ? `
                            <button onclick="blockedNumbersManager.openEditModal('${ani}', '${reason.replace(/'/g, '&#39;')}')" 
                                    class="text-indigo-600 hover:text-indigo-900 transition-colors duration-200">
                                <i class="fas fa-edit"></i>
                            </button>
                            ` : ''}
                            ${hasDeletePermission ? `
                            <button onclick="blockedNumbersManager.openDeleteModal('${ani}', '${reason.replace(/'/g, '&#39;')}')" 
                                    class="bg-red-600 hover:bg-red-700 text-white px-2 py-1 rounded text-xs transition-colors duration-200 ml-2">
                                <i class="fas fa-trash"></i>
                            </button>
                            ` : ''}
                        </div>
                    </td>
                    ` : ''}
                </tr>
            `;
        }).join('');
    }

    formatPhoneNumber(number) {
        if (!number || number.length !== 11) return number;
        return `+1 ${number.slice(1, 4)}-${number.slice(4, 7)}-${number.slice(7)}`;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    openAddModal() {
        const modal = document.getElementById('number-modal');
        const title = document.getElementById('modal-title');
        const aniInput = document.getElementById('ani-input');
        const reasonInput = document.getElementById('reason-input');
        const charCount = document.getElementById('char-count');

        if (title) title.textContent = 'Add Blocked Number';
        if (aniInput) {
            aniInput.value = '';
            aniInput.disabled = false;
        }
        if (reasonInput) reasonInput.value = '';
        if (charCount) charCount.textContent = '0';

        this.isEditing = false;
        this.editingAni = null;

        this.validateForm();
        this.showModal();
    }

    openEditModal(ani, reason) {
        const modal = document.getElementById('number-modal');
        const title = document.getElementById('modal-title');
        const aniInput = document.getElementById('ani-input');
        const reasonInput = document.getElementById('reason-input');
        const charCount = document.getElementById('char-count');

        if (title) title.textContent = 'Edit Blocked Number';
        if (aniInput) {
            aniInput.value = ani;
            aniInput.disabled = false; // Allow editing ANI
        }
        if (reasonInput) {
            reasonInput.value = reason;
            if (charCount) charCount.textContent = reason.length.toString();
        }

        this.isEditing = true;
        this.editingAni = ani;

        this.validateForm();
        this.showModal();
    }

    async handleFormSubmit(e) {
        e.preventDefault();

        const aniInput = document.getElementById('ani-input');
        const reasonInput = document.getElementById('reason-input');
        
        if (!aniInput || !reasonInput) return;

        const ani = aniInput.value.trim();
        const reason = reasonInput.value.trim();

        if (ani.length !== 11) {
            this.showToast('ANI must be exactly 11 digits', 'error');
            return;
        }

        if (!reason || reason.length > 200) {
            this.showToast('Reason must be 1-200 characters', 'error');
            return;
        }

        const saveBtn = document.getElementById('save-btn');
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Saving...';
        }

        try {
            if (this.isEditing) {
                await this.updateNumber(this.editingAni, ani, reason);
            } else {
                await this.addNumber(ani, reason);
            }

            this.closeModal();
            await this.loadBlockedNumbers();
            
            if (this.isEditing) {
                this.showToast(`Blocked number ${this.formatPhoneNumber(ani)} updated successfully`, 'success');
            } else {
                this.showToast(`Blocked number ${this.formatPhoneNumber(ani)} added successfully`, 'success');
            }

        } catch (error) {
            console.error('Error saving number:', error);
            this.showToast(`Failed to save: ${error.message}`, 'error');
        } finally {
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.innerHTML = 'Save';
            }
        }
    }

    async addNumber(ani, reason) {
        const response = await fetch('/utilities/api/blocked-numbers', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                key: ani,
                'Reason Blocked': reason
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || `HTTP ${response.status}`);
        }

        return response.json();
    }

    async updateNumber(oldAni, newAni, reason) {
        const response = await fetch(`/utilities/api/blocked-numbers/${oldAni}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                key: newAni,
                'Reason Blocked': reason
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || `HTTP ${response.status}`);
        }

        return response.json();
    }

    openDeleteModal(ani, reason) {
        const deleteAni = document.getElementById('delete-ani');
        const deleteReason = document.getElementById('delete-reason');

        if (deleteAni) deleteAni.textContent = this.formatPhoneNumber(ani);
        if (deleteReason) deleteReason.textContent = reason;

        this.deletingAni = ani;
        this.showDeleteModal();
    }

    async confirmDelete() {
        const confirmBtn = document.getElementById('confirm-delete-btn');
        
        if (confirmBtn) {
            confirmBtn.disabled = true;
            confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Deleting...';
        }

        try {
            const response = await fetch(`/utilities/api/blocked-numbers/${this.deletingAni}`, {
                method: 'DELETE',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }

            this.closeDeleteModal();
            await this.loadBlockedNumbers();
            this.showToast(`Blocked number ${this.formatPhoneNumber(this.deletingAni)} deleted successfully`, 'success');

        } catch (error) {
            console.error('Error deleting number:', error);
            this.showToast(`Failed to delete: ${error.message}`, 'error');
        } finally {
            if (confirmBtn) {
                confirmBtn.disabled = false;
                confirmBtn.innerHTML = 'Delete';
            }
        }
    }

    showModal() {
        const modal = document.getElementById('number-modal');
        if (modal) {
            modal.classList.remove('hidden');
            modal.classList.add('flex');
            
            // Focus on first input
            const aniInput = document.getElementById('ani-input');
            if (aniInput) {
                setTimeout(() => aniInput.focus(), 100);
            }
        }
    }

    closeModal() {
        const modal = document.getElementById('number-modal');
        if (modal) {
            modal.classList.add('hidden');
            modal.classList.remove('flex');
        }
    }

    showDeleteModal() {
        const modal = document.getElementById('delete-modal');
        if (modal) {
            modal.classList.remove('hidden');
            modal.classList.add('flex');
        }
    }

    closeDeleteModal() {
        const modal = document.getElementById('delete-modal');
        if (modal) {
            modal.classList.add('hidden');
            modal.classList.remove('flex');
        }
    }

    showLoading() {
        const loading = document.getElementById('loading-state');
        const main = document.getElementById('main-content');
        const error = document.getElementById('error-state');

        if (loading) loading.classList.remove('hidden');
        if (main) main.classList.add('hidden');
        if (error) error.classList.add('hidden');
    }

    showMainContent() {
        const loading = document.getElementById('loading-state');
        const main = document.getElementById('main-content');
        const error = document.getElementById('error-state');

        if (loading) loading.classList.add('hidden');
        if (main) main.classList.remove('hidden');
        if (error) error.classList.add('hidden');
    }

    showError(message) {
        const loading = document.getElementById('loading-state');
        const main = document.getElementById('main-content');
        const error = document.getElementById('error-state');
        const errorMessage = document.getElementById('error-message');

        if (loading) loading.classList.add('hidden');
        if (main) main.classList.add('hidden');
        if (error) error.classList.remove('hidden');
        if (errorMessage) errorMessage.textContent = message;
    }

    showToast(message, type = 'info') {
        // Use the global showToast function from base.html
        if (typeof showToast === 'function') {
            showToast(message, type);
        } else {
            // Fallback if toast function is not available
            console.log(`Toast: ${message} (${type})`);
        }
    }
}

// Initialize the manager when the page loads
let blockedNumbersManager;

document.addEventListener('DOMContentLoaded', function() {
    // Make user role available to JavaScript
    window.userRole = window.g?.role || 'viewer';
    
    blockedNumbersManager = new BlockedNumbersManager();
});

// Handle escape key to close modals
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        if (blockedNumbersManager) {
            blockedNumbersManager.closeModal();
            blockedNumbersManager.closeDeleteModal();
        }
    }
});