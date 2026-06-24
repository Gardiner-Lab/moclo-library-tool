/**
 * Backbones JavaScript
 * Handles backbone upload, listing, and management
 */

let allBackbones = [];
let filteredBackbones = [];
let searchQuery = '';

/**
 * Initialize the backbones page
 */
async function initBackbones() {
    // Ensure modal is hidden on page load
    const modal = document.getElementById('backboneDetailModal');
    if (modal) {
        modal.style.display = 'none';
    }
    
    // Set up event listeners
    document.getElementById('uploadForm').addEventListener('submit', handleUpload);
    document.getElementById('searchInput').addEventListener('input', handleSearch);
    document.getElementById('refreshBtn').addEventListener('click', loadBackbones);
    document.getElementById('backboneFile').addEventListener('change', handleFileSelect);

    // Load backbones
    await loadBackbones();
}

/**
 * Handle file selection
 */
function handleFileSelect(event) {
    const file = event.target.files[0];
    const errorElement = document.getElementById('backboneFileError');
    
    errorElement.style.display = 'none';
    
    if (file) {
        // Validate file type
        const validExtensions = ['.gb', '.gbk', '.genbank'];
        const fileName = file.name.toLowerCase();
        const isValid = validExtensions.some(ext => fileName.endsWith(ext));
        
        if (!isValid) {
            errorElement.textContent = 'Please select a GenBank file (.gb, .gbk, .genbank)';
            errorElement.style.display = 'block';
            event.target.value = '';
            return;
        }
        
        // Auto-fill name if empty
        const nameInput = document.getElementById('backboneName');
        if (!nameInput.value) {
            const baseName = file.name.replace(/\.(gb|gbk|genbank)$/i, '');
            nameInput.value = baseName;
        }
    }
}

/**
 * Handle backbone upload
 */
async function handleUpload(event) {
    event.preventDefault();
    
    const form = event.target;
    const button = document.getElementById('uploadBtn');
    const fileInput = document.getElementById('backboneFile');
    
    // Validate file
    if (!fileInput.files || fileInput.files.length === 0) {
        showError('backboneFileError', 'Please select a file');
        return;
    }
    
    // Clear errors
    clearAllErrors(form);
    
    // Set loading state
    setButtonLoading(button, true);
    
    try {
        // Create form data
        const formData = new FormData(form);
        
        // Upload backbone
        const response = await fetch('/api/backbones', {
            method: 'POST',
            credentials: 'same-origin',
            body: formData
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.message || data.error || 'Upload failed');
        }
        
        showFlashMessage('Backbone uploaded successfully!', 'success');
        
        // Reset form
        form.reset();
        
        // Reload backbones
        await loadBackbones();
        
    } catch (error) {
        showError('backboneFileError', error.message);
        showFlashMessage(error.message, 'error');
    } finally {
        setButtonLoading(button, false);
    }
}

/**
 * Load all backbones
 */
async function loadBackbones() {
    const container = document.getElementById('backbonesContainer');
    const loadingState = document.getElementById('loadingState');
    const errorState = document.getElementById('errorState');
    const emptyState = document.getElementById('emptyState');
    
    // Show loading, hide others
    container.style.display = 'none';
    loadingState.style.display = 'flex';
    errorState.style.display = 'none';
    emptyState.style.display = 'none';
    
    try {
        const response = await apiRequest('/api/backbones');
        allBackbones = response.backbones || [];
        filteredBackbones = [...allBackbones];
        
        // Hide loading
        loadingState.style.display = 'none';
        
        if (allBackbones.length === 0) {
            emptyState.style.display = 'block';
        } else {
            container.style.display = 'grid';
            renderBackbones();
        }
        
    } catch (error) {
        loadingState.style.display = 'none';
        errorState.style.display = 'block';
        errorState.querySelector('.error-message').textContent = `Failed to load backbones: ${error.message}`;
    }
}

/**
 * Handle search input
 */
function handleSearch(event) {
    searchQuery = event.target.value.toLowerCase().trim();
    applyFilter();
}

/**
 * Calculate search relevance score for a backbone
 */
function calculateRelevanceScore(backbone, query) {
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
    score += checkField(backbone.name, 100, 50);
    score += checkField(backbone.plasmid_id, 100, 50);
    
    // Medium priority fields (exact match = 80, partial = 30)
    score += checkField(backbone.level, 80, 30);
    score += checkField(backbone.unit, 80, 30);
    score += checkField(backbone.overhang_5prime, 80, 30);
    score += checkField(backbone.overhang_3prime, 80, 30);
    
    // Lower priority fields (exact match = 60, partial = 20)
    score += checkField(backbone.description, 60, 20);
    score += checkField(backbone.antibiotic, 60, 20);
    score += checkField(backbone.contributor, 60, 20);
    score += checkField(backbone.donor_organism, 60, 20);
    score += checkField(backbone.lab_source, 60, 20);
    score += checkField(backbone.location_80, 60, 20);
    score += checkField(backbone.location_96_plate, 60, 20);
    score += checkField(backbone.ori_ecoli, 60, 20);
    score += checkField(backbone.ori_agro, 60, 20);
    score += checkField(backbone.host_strain, 60, 20);
    score += checkField(backbone.reference, 60, 20);
    score += checkField(backbone.comments, 60, 20);
    
    // Very low priority (exact match = 40, partial = 10)
    score += checkField(backbone.id, 40, 10);
    
    return score;
}

/**
 * Apply search filter with relevance ranking
 */
function applyFilter() {
    if (!searchQuery) {
        filteredBackbones = [...allBackbones];
    } else {
        // Calculate scores and filter
        const scoredBackbones = allBackbones.map(backbone => ({
            backbone,
            score: calculateRelevanceScore(backbone, searchQuery)
        }));
        
        // Filter out zero scores and sort by score (highest first)
        filteredBackbones = scoredBackbones
            .filter(item => item.score > 0)
            .sort((a, b) => b.score - a.score)
            .map(item => item.backbone);
    }
    renderBackbones();
}

/**
 * Render backbones list
 */
function renderBackbones() {
    const container = document.getElementById('backbonesContainer');
    const emptyState = document.getElementById('emptyState');
    
    container.innerHTML = '';
    
    if (filteredBackbones.length === 0) {
        container.style.display = 'none';
        emptyState.style.display = 'block';
        if (allBackbones.length > 0) {
            emptyState.querySelector('p').textContent = 'No backbones match your search.';
        }
        return;
    }
    
    container.style.display = 'grid';
    emptyState.style.display = 'none';
    
    filteredBackbones.forEach(backbone => {
        const card = createBackboneCard(backbone);
        container.appendChild(card);
    });
}

/**
 * Create a backbone card element
 */
function createBackboneCard(backbone) {
    const card = document.createElement('div');
    card.className = 'backbone-card';
    
    const slotsText = backbone.cassette_slots === 1 ? '1 slot' : `${backbone.cassette_slots} slots`;
    
    // Build badges
    let badges = `
        <span class="badge badge-primary">${slotsText}</span>
        <span class="badge badge-secondary">${backbone.size} bp</span>
    `;
    
    if (backbone.level) {
        badges += `<span class="badge badge-info">Level ${backbone.level}</span>`;
    }
    
    if (backbone.antibiotic) {
        badges += `<span class="badge badge-warning">${backbone.antibiotic}</span>`;
    }
    
    // Build metadata section
    let metaItems = `
        <div class="meta-item">
            <span class="meta-label">Created:</span>
            <span class="meta-value">${formatDate(backbone.created_at)}</span>
        </div>
    `;
    
    if (backbone.plasmid_id) {
        metaItems += `
            <div class="meta-item">
                <span class="meta-label">Plasmid ID:</span>
                <span class="meta-value">${backbone.plasmid_id}</span>
            </div>
        `;
    }
    
    if (backbone.ori_ecoli) {
        metaItems += `
            <div class="meta-item">
                <span class="meta-label">Ori (E. coli):</span>
                <span class="meta-value">${backbone.ori_ecoli}</span>
            </div>
        `;
    }
    
    if (backbone.ori_agro && backbone.ori_agro !== '-') {
        metaItems += `
            <div class="meta-item">
                <span class="meta-label">Ori (Agro):</span>
                <span class="meta-value">${backbone.ori_agro}</span>
            </div>
        `;
    }
    
    if (backbone.location_80) {
        metaItems += `
            <div class="meta-item">
                <span class="meta-label">Location:</span>
                <span class="meta-value">Freezer ${backbone.location_80}</span>
            </div>
        `;
    }
    
    card.innerHTML = `
        <div class="backbone-card-header">
            <h3>${backbone.name}</h3>
            <div class="backbone-card-badges">
                ${badges}
            </div>
        </div>
        <div class="backbone-card-body">
            <p class="backbone-description">${backbone.description || 'No description'}</p>
            <div class="backbone-meta">
                ${metaItems}
            </div>
        </div>
        <div class="backbone-card-actions">
            <button class="btn btn-sm btn-primary" onclick="viewBackbone('${backbone.id}')">
                View Details
            </button>
            <button class="btn btn-sm btn-secondary" onclick="viewCompatibleCassettes('${backbone.id}')">
                Compatible Cassettes
            </button>
            <button class="btn btn-sm btn-danger" onclick="deleteBackbone('${backbone.id}', '${escapeHtml(backbone.name)}')">
                Delete
            </button>
        </div>
    `;
    
    return card;
}

/**
 * View backbone details
 */
async function viewBackbone(backboneId) {
    try {
        const response = await apiRequest(`/api/backbones/${backboneId}`);
        showBackboneModal(response);
    } catch (error) {
        showFlashMessage(`Failed to load backbone: ${error.message}`, 'error');
    }
}

/**
 * Show backbone detail modal
 */
function showBackboneModal(backbone) {
    const modal = document.getElementById('backboneDetailModal');
    const nameElement = document.getElementById('modalBackboneName');
    const detailsElement = document.getElementById('backboneDetailContent');
    
    // Ensure modal exists
    if (!modal || !nameElement || !detailsElement) {
        console.error('Modal elements not found');
        return;
    }
    
    nameElement.textContent = backbone.name;
    
    // Add download button to modal header
    const modalHeader = modal.querySelector('.modal-header');
    let downloadBtn = document.getElementById('downloadBackboneBtn');
    if (downloadBtn) {
        downloadBtn.remove();
    }
    
    downloadBtn = document.createElement('button');
    downloadBtn.id = 'downloadBackboneBtn';
    downloadBtn.className = 'btn btn-primary btn-sm';
    downloadBtn.textContent = 'Download GenBank';
    downloadBtn.style.marginRight = '10px';
    downloadBtn.onclick = (e) => {
        e.stopPropagation();
        downloadBackboneGenBank(backbone.id);
    };
    modalHeader.insertBefore(downloadBtn, modalHeader.querySelector('.modal-close'));
    
    // Build details HTML
    let html = `
        <div class="detail-section">
            <h3>Basic Information</h3>
            <div class="detail-grid">
                <div class="detail-item">
                    <span class="detail-label">Size:</span>
                    <span class="detail-value">${backbone.size} bp</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Cassette Slots:</span>
                    <span class="detail-value">${backbone.cassette_slots}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Created:</span>
                    <span class="detail-value">${formatDate(backbone.created_at)}</span>
                </div>
                ${backbone.plasmid_id ? `
                <div class="detail-item">
                    <span class="detail-label">Plasmid ID:</span>
                    <span class="detail-value">${backbone.plasmid_id}</span>
                </div>
                ` : ''}
                ${backbone.level ? `
                <div class="detail-item">
                    <span class="detail-label">Level:</span>
                    <span class="detail-value">${backbone.level}</span>
                </div>
                ` : ''}
                ${backbone.antibiotic ? `
                <div class="detail-item">
                    <span class="detail-label">Antibiotic:</span>
                    <span class="detail-value">${backbone.antibiotic}</span>
                </div>
                ` : ''}
                ${backbone.contributor ? `
                <div class="detail-item">
                    <span class="detail-label">Contributor:</span>
                    <span class="detail-value">${backbone.contributor}</span>
                </div>
                ` : ''}
                ${backbone.donor_organism ? `
                <div class="detail-item">
                    <span class="detail-label">Donor Organism:</span>
                    <span class="detail-value">${backbone.donor_organism}</span>
                </div>
                ` : ''}
                ${backbone.lab_source ? `
                <div class="detail-item">
                    <span class="detail-label">Lab Source:</span>
                    <span class="detail-value">${backbone.lab_source}</span>
                </div>
                ` : ''}
                ${backbone.overhang_5prime ? `
                <div class="detail-item">
                    <span class="detail-label">5' Overhang:</span>
                    <span class="detail-value">${backbone.overhang_5prime}</span>
                </div>
                ` : ''}
                ${backbone.overhang_3prime ? `
                <div class="detail-item">
                    <span class="detail-label">3' Overhang:</span>
                    <span class="detail-value">${backbone.overhang_3prime}</span>
                </div>
                ` : ''}
                ${backbone.reference ? `
                <div class="detail-item">
                    <span class="detail-label">Reference:</span>
                    <span class="detail-value">${backbone.reference}</span>
                </div>
                ` : ''}
                ${backbone.upload_date ? `
                <div class="detail-item">
                    <span class="detail-label">Upload Date:</span>
                    <span class="detail-value">${backbone.upload_date}</span>
                </div>
                ` : ''}
                ${backbone.ori_ecoli ? `
                <div class="detail-item">
                    <span class="detail-label">Ori (E. coli):</span>
                    <span class="detail-value">${backbone.ori_ecoli}</span>
                </div>
                ` : ''}
                ${backbone.ori_agro && backbone.ori_agro !== '-' ? `
                <div class="detail-item">
                    <span class="detail-label">Ori (Agro):</span>
                    <span class="detail-value">${backbone.ori_agro}</span>
                </div>
                ` : ''}
                ${backbone.host_strain ? `
                <div class="detail-item">
                    <span class="detail-label">Host Strain:</span>
                    <span class="detail-value">${backbone.host_strain}</span>
                </div>
                ` : ''}
                ${backbone.location_80 ? `
                <div class="detail-item">
                    <span class="detail-label">Location (80-box):</span>
                    <span class="detail-value">${backbone.location_80}</span>
                </div>
                ` : ''}
                ${backbone.location_96_plate ? `
                <div class="detail-item">
                    <span class="detail-label">Location (96-plate):</span>
                    <span class="detail-value">${backbone.location_96_plate}</span>
                </div>
                ` : ''}
            </div>
            ${backbone.description ? `<p class="detail-description">${backbone.description}</p>` : ''}
        </div>
    `;
    
    // Restriction sites
    if (backbone.restriction_sites && backbone.restriction_sites.length > 0) {
        html += `
            <div class="detail-section">
                <h3>Restriction Sites (${backbone.restriction_sites.length})</h3>
                <div class="sites-list">
        `;
        
        backbone.restriction_sites.forEach(site => {
            html += `
                <div class="site-item">
                    <span class="site-enzyme">${site.enzyme}</span>
                    <span class="site-position">Position: ${site.position}</span>
                    <span class="site-strand">${site.strand}</span>
                    ${site.slot_number ? `<span class="site-slot">Slot ${site.slot_number}</span>` : ''}
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
    }
    
    // Features
    if (backbone.genbank_data && backbone.genbank_data.features && backbone.genbank_data.features.length > 0) {
        html += `
            <div class="detail-section">
                <h3>Features (${backbone.genbank_data.features.length})</h3>
                <div class="features-list">
        `;
        
        // Show all features
        backbone.genbank_data.features.forEach(feature => {
            html += `
                <div class="feature-item">
                    <span class="feature-type">${feature.type}</span>
                    <span class="feature-label">${feature.label || 'Unnamed'}</span>
                    <span class="feature-position">${feature.start}-${feature.end}</span>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
    }
    
    // Add Edit button for user's own backbones
    html += `
        <div class="detail-section">
            <button class="btn btn-primary" onclick="editBackbone('${backbone.id}')">
                ✏️ Edit Metadata
            </button>
        </div>
    `;
    
    detailsElement.innerHTML = html;
    
    // Store backbone data for editing
    window.currentBackbone = backbone;
    
    // Show modal with a slight delay to ensure content is rendered
    setTimeout(() => {
        modal.style.display = 'block';
    }, 10);
}

/**
 * Close backbone modal
 */
function closeBackboneModal() {
    const modal = document.getElementById('backboneDetailModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * View compatible cassettes
 */
async function viewCompatibleCassettes(backboneId) {
    const modal = document.getElementById('compatibleCassettesModal');
    const content = document.getElementById('compatibleCassettesContent');
    
    // Show modal with loading state
    modal.style.display = 'block';
    content.innerHTML = '<div class="loading-spinner">Loading compatible cassettes...</div>';
    
    try {
        const response = await apiRequest(`/api/backbones/${backboneId}/compatible-cassettes`);
        
        // Get backbone name for title
        const backbone = allBackbones.find(b => b.id === backboneId);
        const backboneName = backbone ? backbone.name : 'Backbone';
        document.getElementById('modalCompatibleTitle').textContent = 
            `Compatible Cassettes for ${backboneName}`;
        
        if (response.count === 0) {
            content.innerHTML = `
                <div class="empty-state">
                    <p>No compatible cassettes found for this backbone.</p>
                    <p class="text-muted">Create cassettes with matching overhangs to see them here.</p>
                </div>
            `;
            return;
        }
        
        // Display compatible cassettes
        showCompatibleCassettesList(response.compatible_cassettes);
        
    } catch (error) {
        content.innerHTML = `
            <div class="error-state">
                <p class="error-message">Failed to load compatible cassettes: ${error.message}</p>
                <button class="btn btn-primary" onclick="viewCompatibleCassettes('${backboneId}')">
                    Try Again
                </button>
            </div>
        `;
    }
}

/**
 * Show compatible cassettes list
 */
function showCompatibleCassettesList(cassettes) {
    const content = document.getElementById('compatibleCassettesContent');
    
    let html = `
        <div class="detail-section">
            <p class="text-muted" style="margin-bottom: 1rem;">
                Found ${cassettes.length} compatible cassette${cassettes.length !== 1 ? 's' : ''}
            </p>
            <div class="cassettes-list">
    `;
    
    cassettes.forEach(item => {
        const cassette = item.cassette;
        const compatibility = item.compatibility;
        
        // Extract overhangs from sequence
        const overhang5 = cassette.assembled_sequence ? 
            cassette.assembled_sequence.substring(0, 4) : 'N/A';
        const overhang3 = cassette.assembled_sequence ? 
            cassette.assembled_sequence.substring(cassette.assembled_sequence.length - 4) : 'N/A';
        
        html += `
            <div class="cassette-compat-item">
                <div class="cassette-compat-header">
                    <h4>${escapeHtml(cassette.name)}</h4>
                    <span class="badge badge-success">Score: ${compatibility.score}</span>
                </div>
                <div class="cassette-compat-body">
                    <div class="cassette-compat-info">
                        <div class="info-row">
                            <span class="info-label">Length:</span>
                            <span class="info-value">${cassette.length || cassette.assembled_sequence.length} bp</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Overhangs:</span>
                            <span class="info-value">5' ${overhang5} → 3' ${overhang3}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Compatibility:</span>
                            <span class="info-value">${escapeHtml(compatibility.reason)}</span>
                        </div>
                        ${compatibility.matching_slots && compatibility.matching_slots.length > 0 ? `
                        <div class="info-row">
                            <span class="info-label">Matching Slots:</span>
                            <span class="info-value">${compatibility.matching_slots.join(', ')}</span>
                        </div>
                        ` : ''}
                    </div>
                    <div class="cassette-compat-image">
                        <img src="/api/visualize/cassette/${cassette.id}" 
                             alt="${escapeHtml(cassette.name)}"
                             onerror="this.style.display='none'"
                             style="max-width: 100%; height: auto; max-height: 80px;">
                    </div>
                </div>
            </div>
        `;
    });
    
    html += `
            </div>
        </div>
    `;
    
    content.innerHTML = html;
}

/**
 * Close compatible cassettes modal
 */
function closeCompatibleCassettes() {
    const modal = document.getElementById('compatibleCassettesModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Delete backbone
 */
async function deleteBackbone(backboneId, backboneName) {
    if (!confirm(`Are you sure you want to delete "${backboneName}"? This action cannot be undone.`)) {
        return;
    }
    
    try {
        await apiRequest(`/api/backbones/${backboneId}`, {
            method: 'DELETE'
        });
        
        showFlashMessage('Backbone deleted successfully', 'success');
        await loadBackbones();
        
    } catch (error) {
        showFlashMessage(`Failed to delete backbone: ${error.message}`, 'error');
    }
}

/**
 * Format date for display
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

// Export functions for use in HTML
window.initBackbones = initBackbones;
window.viewBackbone = viewBackbone;
window.closeBackboneModal = closeBackboneModal;
window.closeBackboneDetail = closeBackboneModal; // Alias for template
window.viewCompatibleCassettes = viewCompatibleCassettes;
window.closeCompatibleCassettes = closeCompatibleCassettes;
window.deleteBackbone = deleteBackbone;

/**
 * Open edit backbone modal
 */
function editBackbone(backboneId) {
    const backbone = window.currentBackbone;
    
    if (!backbone) {
        console.error('No backbone data available');
        return;
    }
    
    // Populate form
    document.getElementById('editBackboneId').value = backbone.id;
    document.getElementById('editName').value = backbone.name || '';
    document.getElementById('editDescription').value = backbone.description || '';
    document.getElementById('editPlasmidId').value = backbone.plasmid_id || '';
    document.getElementById('editLevel').value = backbone.level || '';
    document.getElementById('editUnit').value = backbone.unit || '';
    document.getElementById('editAntibiotic').value = backbone.antibiotic || '';
    document.getElementById('editOriEcoli').value = backbone.ori_ecoli || '';
    document.getElementById('editOriAgro').value = backbone.ori_agro || '';
    document.getElementById('editHostStrain').value = backbone.host_strain || '';
    document.getElementById('editContributor').value = backbone.contributor || '';
    document.getElementById('editDonorOrganism').value = backbone.donor_organism || '';
    document.getElementById('editLabSource').value = backbone.lab_source || '';
    document.getElementById('editReference').value = backbone.reference || '';
    document.getElementById('editLocation80').value = backbone.location_80 || '';
    document.getElementById('editLocation96').value = backbone.location_96_plate || '';
    document.getElementById('editComments').value = backbone.comments || '';
    
    // Close detail modal
    closeBackboneModal();
    
    // Show edit modal
    document.getElementById('editBackboneModal').style.display = 'block';
}

/**
 * Close edit backbone modal
 */
function closeEditBackbone() {
    document.getElementById('editBackboneModal').style.display = 'none';
}

/**
 * Handle edit form submission
 */
document.addEventListener('DOMContentLoaded', () => {
    const editForm = document.getElementById('editBackboneForm');
    
    if (editForm) {
        editForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const backboneId = document.getElementById('editBackboneId').value;
            
            // Collect form data
            const data = {
                name: document.getElementById('editName').value,
                description: document.getElementById('editDescription').value,
                plasmid_id: document.getElementById('editPlasmidId').value || null,
                level: document.getElementById('editLevel').value || null,
                unit: document.getElementById('editUnit').value || null,
                antibiotic: document.getElementById('editAntibiotic').value || null,
                ori_ecoli: document.getElementById('editOriEcoli').value || null,
                ori_agro: document.getElementById('editOriAgro').value || null,
                host_strain: document.getElementById('editHostStrain').value || null,
                contributor: document.getElementById('editContributor').value || null,
                donor_organism: document.getElementById('editDonorOrganism').value || null,
                lab_source: document.getElementById('editLabSource').value || null,
                reference: document.getElementById('editReference').value || null,
                location_80: document.getElementById('editLocation80').value || null,
                location_96_plate: document.getElementById('editLocation96').value || null,
                comments: document.getElementById('editComments').value || null
            };
            
            try {
                const response = await fetch(`/api/backbones/${backboneId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    showFlashMessage('Backbone updated successfully', 'success');
                    closeEditBackbone();
                    // Refresh the list
                    initBackbones();
                } else {
                    showFlashMessage(result.message || 'Failed to update backbone', 'error');
                }
            } catch (error) {
                console.error('Error updating backbone:', error);
                showFlashMessage('Error updating backbone', 'error');
            }
        });
    }
});

// Export edit functions
window.editBackbone = editBackbone;
window.closeEditBackbone = closeEditBackbone;

/**
 * Download backbone as GenBank file
 */
function downloadBackboneGenBank(backboneId) {
    // Create a temporary link and trigger download
    const link = document.createElement('a');
    link.href = `/api/backbones/${backboneId}/download/genbank`;
    link.download = '';  // Filename will be set by server
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
