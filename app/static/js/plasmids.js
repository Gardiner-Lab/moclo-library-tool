/**
 * Plasmids JavaScript
 * Handles plasmid listing, viewing, and export
 */

let allPlasmids = [];
let filteredPlasmids = [];
let searchQuery = '';

/**
 * Initialize the plasmids page
 */
async function initPlasmids() {
    // Set up event listeners
    document.getElementById('searchInput').addEventListener('input', handleSearch);
    document.getElementById('refreshBtn').addEventListener('click', loadPlasmids);

    // Load plasmids
    await loadPlasmids();
    
    // Auto-open plasmid detail if ?view=<id> is in the URL
    const urlParams = new URLSearchParams(window.location.search);
    const viewId = urlParams.get('view');
    if (viewId) {
        viewPlasmid(viewId);
    }
}

/**
 * Load all plasmids
 */
async function loadPlasmids() {
    const container = document.getElementById('plasmidsContainer');
    const loadingState = document.getElementById('loadingState');
    const errorState = document.getElementById('errorState');
    const emptyState = document.getElementById('emptyState');
    
    // Show loading, hide others
    container.style.display = 'none';
    loadingState.style.display = 'flex';
    errorState.style.display = 'none';
    emptyState.style.display = 'none';
    
    try {
        const response = await apiRequest('/api/plasmids');
        allPlasmids = response.plasmids || [];
        filteredPlasmids = [...allPlasmids];
        
        // Hide loading
        loadingState.style.display = 'none';
        
        if (allPlasmids.length === 0) {
            emptyState.style.display = 'block';
        } else {
            container.style.display = 'grid';
            renderPlasmids();
        }
        
    } catch (error) {
        loadingState.style.display = 'none';
        errorState.style.display = 'block';
        errorState.querySelector('.error-message').textContent = `Failed to load plasmids: ${error.message}`;
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
 * Apply search filter
 */
function applyFilter() {
    if (!searchQuery) {
        filteredPlasmids = [...allPlasmids];
    } else {
        filteredPlasmids = allPlasmids.filter(plasmid => {
            return plasmid.name.toLowerCase().includes(searchQuery) ||
                   plasmid.id.toLowerCase().includes(searchQuery);
        });
    }
    renderPlasmids();
}

/**
 * Render plasmids list
 */
function renderPlasmids() {
    const container = document.getElementById('plasmidsContainer');
    const emptyState = document.getElementById('emptyState');
    
    container.innerHTML = '';
    
    if (filteredPlasmids.length === 0) {
        container.style.display = 'none';
        emptyState.style.display = 'block';
        if (allPlasmids.length > 0) {
            emptyState.querySelector('p').textContent = 'No plasmids match your search.';
        }
        return;
    }
    
    container.style.display = 'grid';
    emptyState.style.display = 'none';
    
    filteredPlasmids.forEach(plasmid => {
        const card = createPlasmidCard(plasmid);
        container.appendChild(card);
    });
}

/**
 * Create a plasmid card element
 */
function createPlasmidCard(plasmid) {
    const card = document.createElement('div');
    card.className = 'plasmid-card';
    
    const cassettesText = plasmid.cassette_count === 1 ? '1 cassette' : `${plasmid.cassette_count} cassettes`;
    
    card.innerHTML = `
        <div class="plasmid-card-header">
            <h3>${plasmid.name}</h3>
            <div class="plasmid-card-badges">
                <span class="badge badge-success">${cassettesText}</span>
                <span class="badge badge-secondary">${plasmid.size} bp</span>
            </div>
        </div>
        <div class="plasmid-card-body">
            <div class="plasmid-meta">
                <div class="meta-item">
                    <span class="meta-label">Created:</span>
                    <span class="meta-value">${formatDate(plasmid.created_at)}</span>
                </div>
                ${plasmid.metadata && plasmid.metadata.assembly_method ? `
                <div class="meta-item">
                    <span class="meta-label">Method:</span>
                    <span class="meta-value">${plasmid.metadata.assembly_method}</span>
                </div>
                ` : ''}
            </div>
        </div>
        <div class="plasmid-card-actions">
            <button class="btn btn-sm btn-primary" onclick="viewPlasmid('${plasmid.id}')">
                View Details
            </button>
            <div class="btn-group">
                <button class="btn btn-sm btn-secondary" onclick="exportPlasmid('${plasmid.id}', 'genbank')">
                    GenBank
                </button>
                <button class="btn btn-sm btn-secondary" onclick="exportPlasmid('${plasmid.id}', 'fasta')">
                    FASTA
                </button>
                <button class="btn btn-sm btn-secondary" onclick="exportPlasmid('${plasmid.id}', 'image')">
                    Image
                </button>
            </div>
            <button class="btn btn-sm btn-danger" onclick="deletePlasmid('${plasmid.id}', '${plasmid.name}')">
                Delete
            </button>
        </div>
    `;
    
    return card;
}

/**
 * View plasmid details
 */
async function viewPlasmid(plasmidId) {
    try {
        const response = await apiRequest(`/api/plasmids/${plasmidId}`);
        showPlasmidModal(response);
    } catch (error) {
        showFlashMessage(`Failed to load plasmid: ${error.message}`, 'error');
    }
}

/**
 * Show plasmid detail modal
 */
function showPlasmidModal(plasmid) {
    const modal = document.getElementById('plasmidDetailModal');
    const nameElement = document.getElementById('modalPlasmidName');
    const detailsElement = document.getElementById('plasmidDetailContent');
    
    nameElement.textContent = plasmid.name;
    
    // Build details HTML
    let html = `
        <div class="detail-section">
            <h3>Basic Information</h3>
            <div class="detail-grid">
                <div class="detail-item">
                    <span class="detail-label">Size:</span>
                    <span class="detail-value">${plasmid.size} bp</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Cassettes:</span>
                    <span class="detail-value">${plasmid.cassette_count}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Created:</span>
                    <span class="detail-value">${formatDate(plasmid.created_at)}</span>
                </div>
            </div>
        </div>
    `;
    
    // Metadata
    if (plasmid.metadata) {
        html += `
            <div class="detail-section">
                <h3>Assembly Information</h3>
                <div class="detail-grid">
        `;
        
        if (plasmid.metadata.backbone_name) {
            html += `
                <div class="detail-item">
                    <span class="detail-label">Backbone:</span>
                    <span class="detail-value">${escapeHtml(plasmid.metadata.backbone_name)}</span>
                </div>
            `;
        }
        
        if (plasmid.metadata.assembly_method) {
            html += `
                <div class="detail-item">
                    <span class="detail-label">Method:</span>
                    <span class="detail-value">${plasmid.metadata.assembly_method}</span>
                </div>
            `;
        }
        
        html += `
                </div>
            </div>
        `;
    }
    
    // Cassettes section with images
    if (plasmid.cassette_ids && plasmid.cassette_ids.length > 0) {
        html += `
            <div class="detail-section">
                <h3>Cassettes (${plasmid.cassette_ids.length})</h3>
                <div class="cassettes-with-images">
        `;
        
        plasmid.cassette_ids.forEach((cassetteId, index) => {
            const cassetteName = plasmid.metadata && plasmid.metadata.cassette_names 
                ? plasmid.metadata.cassette_names[index] 
                : `Cassette ${index + 1}`;
            
            html += `
                <div class="cassette-image-item">
                    <div class="cassette-image-wrapper">
                        <img src="/api/visualize/cassette/${cassetteId}" 
                             alt="${escapeHtml(cassetteName)}"
                             onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%2260%22%3E%3Crect width=%22200%22 height=%2260%22 fill=%22%23f0f0f0%22/%3E%3Ctext x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 dy=%22.3em%22 fill=%22%23999%22%3ENo Image%3C/text%3E%3C/svg%3E'"
                             class="cassette-image">
                    </div>
                    <div class="cassette-name-full" title="${escapeHtml(cassetteName)}">
                        ${escapeHtml(cassetteName)}
                    </div>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
    }
    
    // Features
    if (plasmid.features && plasmid.features.length > 0) {
        html += `
            <div class="detail-section">
                <h3>Features (${plasmid.features.length})</h3>
                <div class="features-list">
        `;
        
        // Show all features
        plasmid.features.forEach(feature => {
            html += `
                <div class="feature-item">
                    <span class="feature-type">${feature.type}</span>
                    <span class="feature-label" title="${escapeHtml(feature.label)}">${escapeHtml(feature.label)}</span>
                    <span class="feature-position">${feature.start}-${feature.end}</span>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
    }
    
    // Export buttons
    html += `
        <div class="detail-section">
            <h3>Export Options</h3>
            <div class="export-buttons">
                <button class="btn btn-primary" onclick="exportPlasmid('${plasmid.id}', 'genbank')">
                    Download GenBank
                </button>
                <button class="btn btn-primary" onclick="exportPlasmid('${plasmid.id}', 'fasta')">
                    Download FASTA
                </button>
                <button class="btn btn-primary" onclick="exportPlasmid('${plasmid.id}', 'image')">
                    Download Circular Map
                </button>
            </div>
        </div>
    `;
    
    detailsElement.innerHTML = html;
    modal.style.display = 'block';
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
 * Close plasmid modal
 */
function closePlasmidModal() {
    const modal = document.getElementById('plasmidDetailModal');
    modal.style.display = 'none';
}

// Alias for template
window.closePlasmidDetail = closePlasmidModal;

/**
 * Export plasmid
 */
async function exportPlasmid(plasmidId, format) {
    try {
        const formatMap = {
            'genbank': 'genbank',
            'fasta': 'fasta',
            'image': 'image'
        };
        
        const endpoint = `/api/plasmids/${plasmidId}/export/${formatMap[format]}`;
        
        // Create a temporary link and click it to download
        const link = document.createElement('a');
        link.href = endpoint;
        link.download = '';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        showFlashMessage(`Exporting plasmid as ${format}...`, 'success');
        
    } catch (error) {
        showFlashMessage(`Failed to export plasmid: ${error.message}`, 'error');
    }
}

/**
 * Delete plasmid
 */
async function deletePlasmid(plasmidId, plasmidName) {
    if (!confirm(`Are you sure you want to delete "${plasmidName}"? This action cannot be undone.`)) {
        return;
    }
    
    try {
        await apiRequest(`/api/plasmids/${plasmidId}`, {
            method: 'DELETE'
        });
        
        showFlashMessage('Plasmid deleted successfully', 'success');
        await loadPlasmids();
        
    } catch (error) {
        showFlashMessage(`Failed to delete plasmid: ${error.message}`, 'error');
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
window.initPlasmids = initPlasmids;
window.viewPlasmid = viewPlasmid;
window.closePlasmidModal = closePlasmidModal;
window.exportPlasmid = exportPlasmid;
window.deletePlasmid = deletePlasmid;
