/**
 * Parts Browser JavaScript
 * Handles parts listing, filtering, search, and detail view
 */

let allParts = [];
let filteredParts = [];
let currentFilter = { type: '', level: '', search: '' };

/**
 * Initialize the parts browser
 */
async function initPartsBrowser() {
    // Set up event listeners
    document.getElementById('searchInput').addEventListener('input', handleSearch);
    document.getElementById('typeFilter').addEventListener('change', handleTypeFilter);
    document.getElementById('levelFilter').addEventListener('change', handleLevelFilter);
    document.getElementById('clearFilters').addEventListener('click', clearFilters);
    document.getElementById('closeModal').addEventListener('click', closeModal);
    document.getElementById('retryButton').addEventListener('click', loadParts);
    
    // Close modal when clicking overlay
    document.querySelector('.modal-overlay').addEventListener('click', closeModal);

    // Load parts
    await loadParts();
}

/**
 * Load all parts from the API
 */
async function loadParts() {
    showLoading();
    hideError();

    try {
        const response = await apiRequest('/api/parts');
        allParts = response.parts || [];
        filteredParts = [...allParts];
        renderParts();
    } catch (error) {
        showError(error.message || 'Failed to load parts');
    }
}

/**
 * Handle search input
 */
function handleSearch(event) {
    currentFilter.search = event.target.value.toLowerCase().trim();
    applyFilters();
}

/**
 * Handle type filter change
 */
function handleTypeFilter(event) {
    currentFilter.type = event.target.value;
    applyFilters();
}

/**
 * Handle level filter change
 */
function handleLevelFilter(event) {
    currentFilter.level = event.target.value;
    applyFilters();
}

/**
 * Calculate search relevance score for a part
 */
function calculateRelevanceScore(part, query) {
    if (!query) return 0;
    
    let score = 0;
    const lowerQuery = query.toLowerCase();
    
    // Helper function to check field match
    const checkField = (value, exactWeight, partialWeight) => {
        if (!value) return 0;
        const lowerValue = String(value).toLowerCase();
        if (lowerValue === lowerQuery) return exactWeight;
        if (lowerValue.includes(lowerQuery)) return partialWeight;
        // Fuzzy match: check if query words are in value
        const queryWords = lowerQuery.split(/\s+/);
        const matchedWords = queryWords.filter(word => lowerValue.includes(word));
        if (matchedWords.length > 0) {
            return (matchedWords.length / queryWords.length) * (partialWeight * 0.5);
        }
        return 0;
    };
    
    // High priority fields (exact match = 100, partial = 50)
    score += checkField(part.name, 100, 50);
    score += checkField(part.plasmid_id, 100, 50);
    
    // Medium priority fields (exact match = 80, partial = 30)
    score += checkField(part.part_type, 80, 30);
    score += checkField(part.unit, 80, 30);
    score += checkField(part.overhang_5prime, 80, 30);
    score += checkField(part.overhang_3prime, 80, 30);
    score += checkField(part.level, 80, 30);
    
    // Lower priority fields (exact match = 60, partial = 20)
    score += checkField(part.description, 60, 20);
    score += checkField(part.antibiotic, 60, 20);
    score += checkField(part.contributor, 60, 20);
    score += checkField(part.donor_organism, 60, 20);
    score += checkField(part.lab_source, 60, 20);
    score += checkField(part.location_80, 60, 20);
    score += checkField(part.location_96_plate, 60, 20);
    score += checkField(part.host_strain, 60, 20);
    score += checkField(part.reference, 60, 20);
    score += checkField(part.comments, 60, 20);
    
    // Very low priority (exact match = 40, partial = 10)
    score += checkField(part.id, 40, 10);
    
    return score;
}

/**
 * Apply current filters to parts list with relevance ranking
 */
function applyFilters() {
    // Start with all parts
    let filtered = allParts;
    
    // Apply type filter
    if (currentFilter.type) {
        filtered = filtered.filter(part => part.part_type === currentFilter.type);
    }
    
    // Apply level filter
    if (currentFilter.level) {
        // Extract numeric level from filter value (e.g., "Level 0" -> "0", "L1" -> "1", "0" -> "0")
        const filterNum = currentFilter.level.replace(/[^0-9]/g, '');
        filtered = filtered.filter(part => {
            // Parts with no level set are treated as Level 0
            const partLevel = part.level || '0';
            const partNum = String(partLevel).replace(/[^0-9]/g, '');
            return partNum === filterNum;
        });
    }

    // Apply search with scoring
    if (currentFilter.search) {
        const scoredParts = filtered.map(part => ({
            part,
            score: calculateRelevanceScore(part, currentFilter.search)
        }));
        
        // Filter out zero scores and sort by score (highest first)
        filteredParts = scoredParts
            .filter(item => item.score > 0)
            .sort((a, b) => b.score - a.score)
            .map(item => item.part);
    } else {
        filteredParts = filtered;
    }

    renderParts();
}

/**
 * Clear all filters
 */
function clearFilters() {
    currentFilter = { type: '', level: '', search: '' };
    document.getElementById('searchInput').value = '';
    document.getElementById('typeFilter').value = '';
    document.getElementById('levelFilter').value = '';
    filteredParts = [...allParts];
    renderParts();
}

/**
 * Render the parts list
 */
function renderParts() {
    hideLoading();
    
    const container = document.getElementById('partsContainer');
    const emptyState = document.getElementById('emptyState');

    if (filteredParts.length === 0) {
        container.style.display = 'none';
        emptyState.style.display = 'block';
        return;
    }

    emptyState.style.display = 'none';
    container.style.display = 'grid';
    container.innerHTML = '';

    filteredParts.forEach(part => {
        const partCard = createPartCard(part);
        container.appendChild(partCard);
    });
}

/**
 * Create a part card element
 */
function createPartCard(part) {
    const card = document.createElement('div');
    card.className = 'part-card';
    card.onclick = () => showPartDetails(part.id);

    // Part visualization
    const visualization = document.createElement('div');
    visualization.className = 'part-visualization';
    visualization.innerHTML = `<img src="/api/visualize/part/${part.id}" alt="${part.name} visualization" onerror="this.style.display='none'">`;

    // Part info
    const info = document.createElement('div');
    info.className = 'part-info';

    const name = document.createElement('h3');
    name.className = 'part-name';
    name.textContent = part.name;

    const type = document.createElement('div');
    type.className = 'part-type';
    type.innerHTML = `<span class="type-badge type-${part.part_type.toLowerCase()}">${formatPartType(part.part_type)}</span>`;

    const compatibility = document.createElement('div');
    compatibility.className = 'part-compatibility';
    compatibility.innerHTML = `
        <div class="overhang-info">
            <span class="overhang-label">5':</span>
            <span class="overhang-value">${part.overhang_5prime}</span>
        </div>
        <div class="overhang-info">
            <span class="overhang-label">3':</span>
            <span class="overhang-value">${part.overhang_3prime}</span>
        </div>
    `;

    info.appendChild(name);
    info.appendChild(type);
    info.appendChild(compatibility);

    card.appendChild(visualization);
    card.appendChild(info);

    return card;
}

/**
 * Format part type for display
 */
function formatPartType(type) {
    const typeMap = {
        'Coding': 'Coding',
        'NonCodingPromoter': 'Promoter',
        'NonCodingTerminator': 'Terminator',
        'NonCodingIntron': 'Intron',
        'NonCodingOther': 'Other'
    };
    return typeMap[type] || type;
}

/**
 * Show part details in modal
 */
async function showPartDetails(partId) {
    const modal = document.getElementById('partModal');
    const detailsContainer = document.getElementById('partDetails');
    
    modal.style.display = 'block';
    detailsContainer.innerHTML = '<div class="loading-spinner">Loading...</div>';

    try {
        const part = await apiRequest(`/api/parts/${partId}`);
        renderPartDetails(part);
    } catch (error) {
        detailsContainer.innerHTML = `<div class="error-message">Failed to load part details: ${error.message}</div>`;
    }
}

/**
 * Render part details in modal
 */
function renderPartDetails(part) {
    const detailsContainer = document.getElementById('partDetails');
    document.getElementById('modalPartName').textContent = part.name;
    
    // Add delete button if user is the contributor (not system parts)
    const modalHeader = document.querySelector('.modal-header');
    let deleteBtn = document.getElementById('deletePartBtn');
    
    // Remove existing delete button if present
    if (deleteBtn) {
        deleteBtn.remove();
    }
    
    // Add download button
    let downloadBtn = document.getElementById('downloadPartBtn');
    if (downloadBtn) {
        downloadBtn.remove();
    }
    
    downloadBtn = document.createElement('button');
    downloadBtn.id = 'downloadPartBtn';
    downloadBtn.className = 'btn btn-primary btn-sm';
    downloadBtn.textContent = 'Download GenBank';
    downloadBtn.style.marginRight = '10px';
    downloadBtn.onclick = (e) => {
        e.stopPropagation();
        downloadPartGenBank(part.id);
    };
    modalHeader.insertBefore(downloadBtn, document.getElementById('closeModal'));
    
    // Add edit button for user-uploaded parts (not system parts) or if user is admin
    const isAdmin = document.body.dataset.isAdmin === 'true';
    const currentUsername = document.body.dataset.username;
    if (isAdmin || (part.contributor && part.contributor !== 'system')) {
        let editBtn = document.getElementById('editPartBtn');
        if (editBtn) {
            editBtn.remove();
        }
        
        editBtn = document.createElement('button');
        editBtn.id = 'editPartBtn';
        editBtn.className = 'btn btn-secondary btn-sm';
        editBtn.textContent = 'Edit Metadata';
        editBtn.style.marginRight = '10px';
        editBtn.onclick = (e) => {
            e.stopPropagation();
            showEditPartModal(part);
        };
        modalHeader.insertBefore(editBtn, document.getElementById('closeModal'));
    }
    
    // Add delete button for user-uploaded parts (not system parts)
    if (part.contributor && part.contributor !== 'system') {
        deleteBtn = document.createElement('button');
        deleteBtn.id = 'deletePartBtn';
        deleteBtn.className = 'btn btn-danger btn-sm';
        deleteBtn.textContent = 'Delete Part';
        deleteBtn.style.marginRight = '10px';
        deleteBtn.onclick = (e) => {
            e.stopPropagation();
            deletePart(part.id, part.name);
        };
        modalHeader.insertBefore(deleteBtn, document.getElementById('closeModal'));
    }

    const html = `
        <div class="part-detail-section">
            <div class="detail-visualization">
                <img src="/api/visualize/part/${part.id}" alt="${part.name} visualization" style="max-width: 100%; height: auto;">
            </div>
        </div>

        <div class="part-detail-section">
            <h3>Basic Information</h3>
            <div class="detail-grid">
                <div class="detail-item">
                    <span class="detail-label">Part ID:</span>
                    <span class="detail-value">${part.id}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Name:</span>
                    <span class="detail-value">${part.name}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Type:</span>
                    <span class="detail-value"><span class="type-badge type-${part.part_type.toLowerCase()}">${formatPartType(part.part_type)}</span></span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Length:</span>
                    <span class="detail-value">${part.sequence.length} bp</span>
                </div>
            </div>
        </div>

        <div class="part-detail-section">
            <h3>Compatibility Information</h3>
            <div class="detail-grid">
                <div class="detail-item">
                    <span class="detail-label">5' Overhang:</span>
                    <span class="detail-value overhang-value">${part.overhang_5prime}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">3' Overhang:</span>
                    <span class="detail-value overhang-value">${part.overhang_3prime}</span>
                </div>
            </div>
        </div>

        <div class="part-detail-section">
            <h3>Metadata</h3>
            <div class="detail-grid">
                ${part.plasmid_id ? `
                <div class="detail-item">
                    <span class="detail-label">Plasmid ID:</span>
                    <span class="detail-value">${part.plasmid_id}</span>
                </div>
                ` : ''}
                ${part.level ? `
                <div class="detail-item">
                    <span class="detail-label">Level:</span>
                    <span class="detail-value">${part.level}</span>
                </div>
                ` : ''}
                ${part.unit ? `
                <div class="detail-item">
                    <span class="detail-label">Unit:</span>
                    <span class="detail-value">${part.unit}</span>
                </div>
                ` : ''}
                ${part.antibiotic ? `
                <div class="detail-item">
                    <span class="detail-label">Antibiotic:</span>
                    <span class="detail-value">${part.antibiotic}</span>
                </div>
                ` : ''}
                <div class="detail-item">
                    <span class="detail-label">Lab Source:</span>
                    <span class="detail-value">${part.lab_source || 'N/A'}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Contributor:</span>
                    <span class="detail-value">${part.contributor || 'N/A'}</span>
                </div>
                ${part.donor_organism ? `
                <div class="detail-item">
                    <span class="detail-label">Donor Organism:</span>
                    <span class="detail-value">${part.donor_organism}</span>
                </div>
                ` : ''}
                ${part.host_strain ? `
                <div class="detail-item">
                    <span class="detail-label">Host Strain:</span>
                    <span class="detail-value">${part.host_strain}</span>
                </div>
                ` : ''}
                ${part.location_80 ? `
                <div class="detail-item">
                    <span class="detail-label">Location (80-box):</span>
                    <span class="detail-value">${part.location_80}</span>
                </div>
                ` : ''}
                ${part.location_96_plate ? `
                <div class="detail-item">
                    <span class="detail-label">Location (96-plate):</span>
                    <span class="detail-value">${part.location_96_plate}</span>
                </div>
                ` : ''}
                ${part.reference ? `
                <div class="detail-item">
                    <span class="detail-label">Reference:</span>
                    <span class="detail-value">${part.reference}</span>
                </div>
                ` : ''}
                ${part.sequenced ? `
                <div class="detail-item">
                    <span class="detail-label">Sequenced:</span>
                    <span class="detail-value">${part.sequenced}</span>
                </div>
                ` : ''}
                <div class="detail-item">
                    <span class="detail-label">Upload Date:</span>
                    <span class="detail-value">${formatDate(part.upload_date)}</span>
                </div>
            </div>
            ${part.description ? `
                <div class="detail-item full-width">
                    <span class="detail-label">Description:</span>
                    <span class="detail-value">${part.description}</span>
                </div>
            ` : ''}
            ${part.comments ? `
                <div class="detail-item full-width">
                    <span class="detail-label">Comments:</span>
                    <span class="detail-value">${part.comments}</span>
                </div>
            ` : ''}
        </div>

        <div class="part-detail-section">
            <h3>DNA Sequence</h3>
            <div class="sequence-container">
                <pre class="sequence-display">${formatSequence(part.sequence)}</pre>
            </div>
        </div>

        <div class="part-detail-section">
            <h3>Compatible Parts</h3>
            <div id="compatibleParts">Loading compatible parts...</div>
        </div>
    `;

    detailsContainer.innerHTML = html;

    // Load compatible parts
    loadCompatibleParts(part.id);
}

/**
 * Load and display compatible parts
 */
async function loadCompatibleParts(partId) {
    const container = document.getElementById('compatibleParts');
    
    try {
        const response = await apiRequest(`/api/parts/${partId}/compatible`);
        const { before, after } = response.compatible;

        if (before.length === 0 && after.length === 0) {
            container.innerHTML = '<p class="text-muted">No compatible parts found.</p>';
            return;
        }

        let html = '';

        if (before.length > 0) {
            html += '<h4>Can be placed before this part:</h4>';
            html += '<div class="compatible-parts-list">';
            before.forEach(part => {
                html += `<div class="compatible-part-item" onclick="showPartDetails('${part.id}')">
                    <span class="part-name">${part.name}</span>
                    <span class="type-badge type-${part.part_type.toLowerCase()}">${formatPartType(part.part_type)}</span>
                </div>`;
            });
            html += '</div>';
        }

        if (after.length > 0) {
            html += '<h4>Can be placed after this part:</h4>';
            html += '<div class="compatible-parts-list">';
            after.forEach(part => {
                html += `<div class="compatible-part-item" onclick="showPartDetails('${part.id}')">
                    <span class="part-name">${part.name}</span>
                    <span class="type-badge type-${part.part_type.toLowerCase()}">${formatPartType(part.part_type)}</span>
                </div>`;
            });
            html += '</div>';
        }

        container.innerHTML = html;
    } catch (error) {
        container.innerHTML = `<p class="error-message">Failed to load compatible parts: ${error.message}</p>`;
    }
}

/**
 * Format DNA sequence with line breaks
 */
function formatSequence(sequence) {
    const charsPerLine = 60;
    let formatted = '';
    for (let i = 0; i < sequence.length; i += charsPerLine) {
        formatted += sequence.substring(i, i + charsPerLine) + '\n';
    }
    return formatted.trim();
}

/**
 * Format date for display
 */
function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
    });
}

/**
 * Close the modal
 */
function closeModal() {
    document.getElementById('partModal').style.display = 'none';
}

/**
 * Show loading state
 */
function showLoading() {
    document.getElementById('loadingState').style.display = 'flex';
    document.getElementById('partsContainer').style.display = 'none';
    document.getElementById('emptyState').style.display = 'none';
}

/**
 * Hide loading state
 */
function hideLoading() {
    document.getElementById('loadingState').style.display = 'none';
}

/**
 * Show error state
 */
function showError(message) {
    hideLoading();
    const errorState = document.getElementById('errorState');
    errorState.querySelector('.error-message').textContent = message;
    errorState.style.display = 'block';
    document.getElementById('partsContainer').style.display = 'none';
    document.getElementById('emptyState').style.display = 'none';
}

/**
 * Hide error state
 */
function hideError() {
    document.getElementById('errorState').style.display = 'none';
}

/**
 * Delete a part
 */
async function deletePart(partId, partName) {
    // Confirm deletion
    if (!confirm(`Are you sure you want to delete "${partName}"?\n\nThis action cannot be undone.`)) {
        return;
    }
    
    try {
        await apiRequest(`/api/parts/${partId}`, {
            method: 'DELETE'
        });
        
        // Close modal
        closeModal();
        
        // Show success message
        alert('Part deleted successfully');
        
        // Reload parts list
        await loadParts();
        
    } catch (error) {
        alert(`Failed to delete part: ${error.message}`);
    }
}

/**
 * Download part as GenBank file
 */
function downloadPartGenBank(partId) {
    // Create a temporary link and trigger download
    const link = document.createElement('a');
    link.href = `/api/parts/${partId}/download/genbank`;
    link.download = '';  // Filename will be set by server
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

/**
 * Show edit part modal
 */
function showEditPartModal(part) {
    const modal = document.getElementById('editPartModal');
    
    // Populate form fields
    document.getElementById('editDescription').value = part.description || '';
    document.getElementById('editPlasmidId').value = part.plasmid_id || '';
    document.getElementById('editLevel').value = part.level || '';
    document.getElementById('editUnit').value = part.unit || '';
    document.getElementById('editAntibiotic').value = part.antibiotic || '';
    document.getElementById('editOriEcoli').value = part.ori_ecoli || '';
    document.getElementById('editOriAgro').value = part.ori_agro || '';
    document.getElementById('editDonorOrganism').value = part.donor_organism || '';
    document.getElementById('editHostStrain').value = part.host_strain || '';
    document.getElementById('editLocation80').value = part.location_80 || '';
    document.getElementById('editLocation96').value = part.location_96_plate || '';
    document.getElementById('editReference').value = part.reference || '';
    document.getElementById('editPrimerForSeq').value = part.primer_for_seq || '';
    document.getElementById('editSequenced').value = part.sequenced || '';
    document.getElementById('editComments').value = part.comments || '';
    
    // Store part ID for submission
    modal.dataset.partId = part.id;
    
    // Show modal
    modal.style.display = 'block';
}

/**
 * Close edit part modal
 */
function closeEditPartModal() {
    const modal = document.getElementById('editPartModal');
    modal.style.display = 'none';
}

/**
 * Handle edit part form submission
 */
document.addEventListener('DOMContentLoaded', function() {
    const editForm = document.getElementById('editPartForm');
    if (editForm) {
        editForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const modal = document.getElementById('editPartModal');
            const partId = modal.dataset.partId;
            
            if (!partId) {
                alert('Error: Part ID not found');
                return;
            }
            
            // Collect form data
            const data = {
                description: document.getElementById('editDescription').value || null,
                plasmid_id: document.getElementById('editPlasmidId').value || null,
                level: document.getElementById('editLevel').value || null,
                unit: document.getElementById('editUnit').value || null,
                antibiotic: document.getElementById('editAntibiotic').value || null,
                ori_ecoli: document.getElementById('editOriEcoli').value || null,
                ori_agro: document.getElementById('editOriAgro').value || null,
                donor_organism: document.getElementById('editDonorOrganism').value || null,
                host_strain: document.getElementById('editHostStrain').value || null,
                location_80: document.getElementById('editLocation80').value || null,
                location_96_plate: document.getElementById('editLocation96').value || null,
                reference: document.getElementById('editReference').value || null,
                primer_for_seq: document.getElementById('editPrimerForSeq').value || null,
                sequenced: document.getElementById('editSequenced').value || null,
                comments: document.getElementById('editComments').value || null
            };
            
            try {
                const response = await apiRequest(`/api/parts/${partId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                });
                
                // Close edit modal
                closeEditPartModal();
                
                // Show success message
                alert('Part metadata updated successfully');
                
                // Reload part details
                await showPartDetails(partId);
                
            } catch (error) {
                alert(`Failed to update part: ${error.message}`);
            }
        });
    }
});

// Export for use in other modules
window.initPartsBrowser = initPartsBrowser;
window.showPartDetails = showPartDetails;
window.closeEditPartModal = closeEditPartModal;
