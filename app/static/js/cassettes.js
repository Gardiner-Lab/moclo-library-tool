/**
 * Cassettes Management JavaScript
 * Handles displaying, viewing, exporting, and deleting cassettes
 */

let cassettes = [];
let currentCassetteDetail = null;

/**
 * Initialize the cassettes page
 */
async function initCassettes() {
    // Set up event listeners
    document.getElementById('refreshCassettes').addEventListener('click', loadCassettes);

    // Load cassettes
    await loadCassettes();
}

/**
 * Load all cassettes for the current user
 */
async function loadCassettes() {
    const container = document.getElementById('cassettesContainer');
    container.innerHTML = `
        <div class="loading-state">
            <div class="spinner"></div>
            <p>Loading cassettes...</p>
        </div>
    `;

    try {
        const response = await apiRequest('/api/cassettes');
        cassettes = response.cassettes || [];
        renderCassettes();
    } catch (error) {
        container.innerHTML = `
            <div class="error-state">
                <div class="error-message">Failed to load cassettes: ${error.message}</div>
                <button class="btn btn-primary" onclick="loadCassettes()">Try Again</button>
            </div>
        `;
    }
}

/**
 * Render the cassettes grid
 */
function renderCassettes() {
    const container = document.getElementById('cassettesContainer');

    if (cassettes.length === 0) {
        container.innerHTML = `
            <div class="empty-cassettes">
                <div class="empty-cassettes-icon">🧬</div>
                <h2>No Cassettes Yet</h2>
                <p>You haven't created any cassettes yet. Start by assembling compatible parts.</p>
                <a href="/assembly" class="btn btn-primary">Create Your First Cassette</a>
            </div>
        `;
        return;
    }

    const grid = document.createElement('div');
    grid.className = 'cassettes-grid';

    cassettes.forEach(cassette => {
        const card = createCassetteCard(cassette);
        grid.appendChild(card);
    });

    container.innerHTML = '';
    container.appendChild(grid);
}

/**
 * Create a cassette card element
 */
function createCassetteCard(cassette) {
    const card = document.createElement('div');
    card.className = 'cassette-card';

    // Format date
    const createdDate = new Date(cassette.created_at).toLocaleDateString();

    // Card header
    const header = document.createElement('div');
    header.className = 'cassette-header';
    header.innerHTML = `
        <div class="cassette-name">${escapeHtml(cassette.name)}</div>
        <div class="cassette-meta">
            <span class="cassette-meta-item">
                <span>📅</span>
                <span>${createdDate}</span>
            </span>
            <span class="cassette-meta-item">
                <span>🧩</span>
                <span>${cassette.part_count} parts</span>
            </span>
            <span class="cassette-meta-item">
                <span>📏</span>
                <span>${cassette.length} bp</span>
            </span>
        </div>
    `;

    // Visualization
    const visualization = document.createElement('div');
    visualization.className = 'cassette-visualization';
    visualization.onclick = () => showCassetteDetail(cassette.id);
    
    // Load visualization
    const img = document.createElement('img');
    img.src = `/api/visualize/cassette/${cassette.id}`;
    img.alt = `Visualization of ${cassette.name}`;
    img.onerror = () => {
        visualization.innerHTML = '<p style="color: var(--text-secondary);">Visualization unavailable</p>';
    };
    visualization.appendChild(img);

    // Actions
    const actions = document.createElement('div');
    actions.className = 'cassette-actions';
    actions.innerHTML = `
        <button class="btn-export" onclick="exportCassette('${cassette.id}', 'fasta')" title="Export as FASTA">
            📄 FASTA
        </button>
        <button class="btn-export" onclick="exportCassette('${cassette.id}', 'genbank')" title="Export as GenBank">
            📄 GenBank
        </button>
        <button class="btn-export" onclick="exportCassette('${cassette.id}', 'image')" title="Export as Image">
            🖼️ Image
        </button>
        <button class="btn-delete" onclick="deleteCassette('${cassette.id}')" title="Delete cassette">
            🗑️
        </button>
    `;

    card.appendChild(header);
    card.appendChild(visualization);
    card.appendChild(actions);

    return card;
}

/**
 * Show detailed view of a cassette
 */
async function showCassetteDetail(cassetteId) {
    const modal = document.getElementById('cassetteDetailModal');
    const content = document.getElementById('cassetteDetailContent');
    const nameElement = document.getElementById('modalCassetteName');

    // Show modal with loading state
    modal.style.display = 'block';
    content.innerHTML = '<div class="loading-spinner">Loading details...</div>';
    nameElement.textContent = 'Loading...';

    try {
        // Fetch cassette details
        const cassette = await apiRequest(`/api/cassettes/${cassetteId}`);
        currentCassetteDetail = cassette;

        // Update modal title
        nameElement.textContent = cassette.name;

        // Render detail content
        renderCassetteDetail(cassette);
    } catch (error) {
        content.innerHTML = `
            <div class="error-state">
                <div class="error-message">Failed to load cassette details: ${error.message}</div>
                <button class="btn btn-primary" onclick="showCassetteDetail('${cassetteId}')">Try Again</button>
            </div>
        `;
    }
}

/**
 * Render cassette detail content
 */
function renderCassetteDetail(cassette) {
    const content = document.getElementById('cassetteDetailContent');

    const createdDate = new Date(cassette.created_at).toLocaleString();

    let html = '';

    // Visualization section
    html += `
        <div class="detail-section">
            <h3>Visualization</h3>
            <div class="detail-visualization">
                <img src="/api/visualize/cassette/${cassette.id}" 
                     alt="Cassette visualization"
                     onerror="this.parentElement.innerHTML='<p style=\\'color: var(--text-secondary)\\'>Visualization unavailable</p>'">
            </div>
        </div>
    `;

    // Information section
    html += `
        <div class="detail-section">
            <h3>Information</h3>
            <div class="detail-info-grid">
                <div class="detail-info-item">
                    <div class="detail-info-label">Parts</div>
                    <div class="detail-info-value">${cassette.part_count}</div>
                </div>
                <div class="detail-info-item">
                    <div class="detail-info-label">Length</div>
                    <div class="detail-info-value">${cassette.length} bp</div>
                </div>
                <div class="detail-info-item">
                    <div class="detail-info-label">Created</div>
                    <div class="detail-info-value" style="font-size: 0.875rem;">${createdDate}</div>
                </div>
            </div>
        </div>
    `;

    // Parts section
    if (cassette.parts && cassette.parts.length > 0) {
        html += `
            <div class="detail-section">
                <h3>Component Parts</h3>
                <div class="parts-list">
        `;

        cassette.parts.forEach((part, index) => {
            html += `
                <div class="part-list-item clickable" onclick="showPartDetails('${part.id}')" style="cursor: pointer;">
                    <div class="part-order-number">${index + 1}</div>
                    <div class="part-list-info">
                        <div class="part-list-name">${escapeHtml(part.name)}</div>
                        <div class="part-list-meta">
                            <span class="type-badge type-${part.part_type.toLowerCase()}">${formatPartType(part.part_type)}</span>
                            <span>5': ${part.overhang_5prime}</span>
                            <span>3': ${part.overhang_3prime}</span>
                            <span>${part.sequence.length} bp</span>
                        </div>
                    </div>
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;
    }

    // Translation Analysis section (for coding sequences)
    if (cassette.translation_analysis && cassette.translation_analysis.has_coding) {
        const trans = cassette.translation_analysis;
        html += `
            <div class="detail-section">
                <h3>Translation Analysis</h3>
        `;
        
        // Show splicing warning prominently if introns/exons are present
        if (trans.requires_splicing) {
            html += `
                <div class="splicing-notice">
                    <div class="splicing-icon">🧬</div>
                    <div class="splicing-content">
                        <div class="splicing-title">RNA Splicing Required</div>
                        <div class="splicing-message">
                            This cassette contains ${trans.has_introns ? 'introns' : ''}${trans.has_introns && trans.has_exons ? ' and ' : ''}${trans.has_exons ? 'exons' : ''}.
                            The protein sequence shown is from genomic DNA and will differ from the final mRNA after splicing.
                        </div>
            `;
            
            if (trans.intron_parts && trans.intron_parts.length > 0) {
                html += `
                        <div class="splicing-parts">
                            <strong>Intron parts:</strong> ${trans.intron_parts.map(p => escapeHtml(p)).join(', ')}
                        </div>
                `;
            }
            
            if (trans.exon_parts && trans.exon_parts.length > 0) {
                html += `
                        <div class="splicing-parts">
                            <strong>Exon parts:</strong> ${trans.exon_parts.map(p => escapeHtml(p)).join(', ')}
                        </div>
                `;
            }
            
            html += `
                    </div>
                </div>
            `;
        }
        
        html += `
                <div class="translation-info">
        `;
        
        if (trans.protein_sequence) {
            html += `
                    <div class="translation-item">
                        <div class="translation-label">Protein Sequence ${trans.requires_splicing ? '(Genomic - Pre-Splicing)' : ''}:</div>
                        <div class="sequence-container">
                            <pre class="sequence-display protein-sequence">${formatProteinSequence(trans.protein_sequence)}</pre>
                        </div>
                        <div class="translation-meta">
                            Length: ${trans.protein_sequence.length} amino acids
                            ${trans.start_codon_pos !== null ? ` | Start codon at position ${trans.start_codon_pos}` : ''}
                        </div>
                    </div>
            `;
        }
        
        if (trans.stop_codons && trans.stop_codons.length > 0) {
            html += `
                    <div class="translation-item">
                        <div class="translation-label">Stop Codons:</div>
                        <div class="stop-codons-list">
            `;
            trans.stop_codons.forEach((stop, idx) => {
                html += `<span class="stop-codon-badge">${stop[1]} at position ${stop[0]}</span>`;
            });
            html += `
                        </div>
                    </div>
            `;
        }
        
        if (trans.warnings && trans.warnings.length > 0) {
            html += `
                    <div class="translation-warnings">
            `;
            trans.warnings.forEach(warning => {
                html += `
                        <div class="warning-message">
                            <span class="warning-icon">⚠️</span>
                            <span>${escapeHtml(warning)}</span>
                        </div>
                `;
            });
            html += `
                    </div>
            `;
        }
        
        // Show spliced mRNA and protein if introns were processed
        if (trans.protein_sequence_spliced && trans.intron_positions && trans.intron_positions.length > 0) {
            html += `
                    <div class="translation-item">
                        <div class="translation-label">
                            Spliced mRNA (after removing ${trans.intron_positions.length} intron(s)):
                        </div>
                        <div class="sequence-container">
                            <pre class="sequence-display">${formatSequence(trans.spliced_dna_sequence)}</pre>
                        </div>
                        <div class="translation-meta">
                            Length: ${trans.spliced_dna_sequence.length} bp
                        </div>
                    </div>
                    <div class="translation-item">
                        <div class="translation-label">
                            Spliced Protein (translated from spliced mRNA):
                        </div>
                        <div class="sequence-container">
                            <pre class="sequence-display protein-sequence spliced">${formatProteinSequence(trans.protein_sequence_spliced)}</pre>
                        </div>
                        <div class="translation-meta">
                            Length: ${trans.protein_sequence_spliced.length} amino acids
                        </div>
                        <div class="intron-info">
                            <strong>Introns removed:</strong>
                            <ul>
            `;
            trans.intron_positions.forEach((intron, idx) => {
                html += `
                                <li>Position ${intron.start}-${intron.end} (${intron.length} bp) - ${escapeHtml(intron.source)}</li>
                `;
            });
            html += `
                            </ul>
                        </div>
            `;
            
            // Show splice site context if available
            if (trans.splice_sites && trans.splice_sites.length > 0) {
                html += `
                        <div class="splice-sites-info">
                            <strong>Splice Site Context:</strong>
                            <div class="splice-sites-table">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Intron</th>
                                            <th>5' Donor (GT)</th>
                                            <th>Position</th>
                                            <th>3' Acceptor (AG)</th>
                                            <th>Position</th>
                                            <th>Status</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                `;
                trans.splice_sites.forEach((site, idx) => {
                    const statusBadge = site.corrected 
                        ? '<span class="status-corrected">✓ AGGT Found</span>' 
                        : '<span class="status-annotation">Annotation</span>';
                    const correctionNote = site.corrected && site.original_donor !== site.donor_pos
                        ? `<br><small>Corrected from ${site.original_donor} → ${site.donor_pos}, ${site.original_acceptor} → ${site.acceptor_pos}</small>`
                        : '';
                    
                    html += `
                                        <tr>
                                            <td>${escapeHtml(site.intron_name)}</td>
                                            <td><code>${site.donor_site}</code></td>
                                            <td>${site.donor_pos}</td>
                                            <td><code>${site.acceptor_site}</code></td>
                                            <td>${site.acceptor_pos}</td>
                                            <td>${statusBadge}${correctionNote}</td>
                                        </tr>
                    `;
                });
                html += `
                                    </tbody>
                                </table>
                            </div>
                            <div class="splice-note">
                                <small>✓ Splice sites automatically corrected to use AGGT sequence (AG at acceptor, GT at donor). 
                                Context shows sequence around each splice site.</small>
                            </div>
                        </div>
                `;
            }
            
            html += `
                    </div>
            `;
            
            // Show stop codons in spliced sequence
            if (trans.stop_codons_spliced && trans.stop_codons_spliced.length > 0) {
                html += `
                    <div class="translation-item">
                        <div class="translation-label">Stop Codons (in spliced sequence):</div>
                        <div class="stop-codons-list">
                `;
                trans.stop_codons_spliced.forEach((stop, idx) => {
                    html += `<span class="stop-codon-badge">${stop[1]} at position ${stop[0]}</span>`;
                });
                html += `
                        </div>
                    </div>
                `;
            }
        }
        
        html += `
                </div>
            </div>
        `;
    }

    // Sequence section
    html += `
        <div class="detail-section">
            <h3>Assembled Sequence</h3>
            <div class="sequence-section">
                <div class="sequence-container">
                    <pre class="sequence-display">${formatSequence(cassette.assembled_sequence)}</pre>
                </div>
            </div>
        </div>
    `;

    // Compatible Backbones section
    html += `
        <div class="detail-section">
            <h3>Compatible Backbones</h3>
            <div id="compatibleBackbones">
                <div class="loading-spinner">Loading compatible backbones...</div>
            </div>
        </div>
    `;

    // Actions section
    html += `
        <div class="detail-actions">
            <button class="btn btn-primary" onclick="exportCassette('${cassette.id}', 'fasta')">
                📄 Export FASTA
            </button>
            <button class="btn btn-primary" onclick="exportCassette('${cassette.id}', 'genbank')">
                📄 Export GenBank
            </button>
            <button class="btn btn-primary" onclick="exportCassette('${cassette.id}', 'image')">
                🖼️ Export Image
            </button>
            <button class="btn btn-danger" onclick="deleteCassetteFromDetail('${cassette.id}')">
                🗑️ Delete Cassette
            </button>
        </div>
    `;

    content.innerHTML = html;

    // Load compatible backbones
    loadCompatibleBackbones(cassette.id);
}

/**
 * Close cassette detail modal
 */
function closeCassetteDetail() {
    const modal = document.getElementById('cassetteDetailModal');
    modal.style.display = 'none';
    currentCassetteDetail = null;
}

/**
 * Export a cassette in the specified format
 */
async function exportCassette(cassetteId, format) {
    try {
        // Create a temporary link and trigger download
        const url = `/api/cassettes/${cassetteId}/export/${format}`;
        const link = document.createElement('a');
        link.href = url;
        link.download = ''; // Let the server set the filename
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        showFlashMessage(`Exporting cassette as ${format.toUpperCase()}...`, 'success');
    } catch (error) {
        showFlashMessage(`Failed to export cassette: ${error.message}`, 'error');
    }
}

/**
 * Delete a cassette
 */
async function deleteCassette(cassetteId) {
    // Find cassette name for confirmation
    const cassette = cassettes.find(c => c.id === cassetteId);
    const cassetteName = cassette ? cassette.name : 'this cassette';

    if (!confirm(`Are you sure you want to delete "${cassetteName}"? This action cannot be undone.`)) {
        return;
    }

    try {
        await apiRequest(`/api/cassettes/${cassetteId}`, {
            method: 'DELETE'
        });

        showFlashMessage('Cassette deleted successfully', 'success');

        // Reload cassettes
        await loadCassettes();
    } catch (error) {
        showFlashMessage(`Failed to delete cassette: ${error.message}`, 'error');
    }
}

/**
 * Delete a cassette from the detail modal
 */
async function deleteCassetteFromDetail(cassetteId) {
    await deleteCassette(cassetteId);
    closeCassetteDetail();
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
 * Format DNA sequence for display (add line breaks every 60 characters)
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
 * Load compatible backbones for a cassette
 */
async function loadCompatibleBackbones(cassetteId) {
    const container = document.getElementById('compatibleBackbones');
    
    try {
        const response = await apiRequest(`/api/cassettes/${cassetteId}/compatible-backbones`);
        const backbones = response.compatible_backbones || [];
        
        if (backbones.length === 0) {
            container.innerHTML = `
                <div class="text-muted">
                    No compatible backbones found. <a href="/backbones">Upload a backbone</a> to get started.
                </div>
            `;
            return;
        }

        let html = '<div class="compatible-backbones-list">';
        backbones.forEach(backbone => {
            const compatScore = backbone.compatibility_score || 0;
            let compatClass = 'low';
            if (compatScore >= 80) compatClass = 'high';
            else if (compatScore >= 50) compatClass = 'medium';

            html += `
                <div class="compatible-backbone-item">
                    <div class="backbone-item-info">
                        <div class="backbone-item-name">${escapeHtml(backbone.backbone_name)}</div>
                        <div class="backbone-item-meta">
                            <span>${backbone.backbone_length} bp</span>
                            <span>${backbone.slot_count} slot${backbone.slot_count !== 1 ? 's' : ''}</span>
                            <span class="compatibility-badge ${compatClass}">${compatScore}% match</span>
                        </div>
                    </div>
                    <div>
                        <a href="/plasmid-assembly?backbone=${backbone.backbone_id}&cassette=${cassetteId}" 
                           class="btn btn-primary" style="white-space: nowrap;">
                            🧬 Assemble
                        </a>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        
        container.innerHTML = html;
    } catch (error) {
        container.innerHTML = `
            <div class="error-message">Failed to load compatible backbones: ${error.message}</div>
        `;
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
 * Format protein sequence with line breaks
 */
function formatProteinSequence(sequence) {
    const charsPerLine = 60;
    let formatted = '';
    for (let i = 0; i < sequence.length; i += charsPerLine) {
        formatted += sequence.substring(i, i + charsPerLine) + '\n';
    }
    return formatted.trim();
}

// Export functions for use in HTML
window.initCassettes = initCassettes;
window.loadCassettes = loadCassettes;
window.showCassetteDetail = showCassetteDetail;
window.closeCassetteDetail = closeCassetteDetail;
window.exportCassette = exportCassette;
window.deleteCassette = deleteCassette;
window.deleteCassetteFromDetail = deleteCassetteFromDetail;
