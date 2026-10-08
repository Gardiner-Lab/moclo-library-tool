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
            const featureText = getPlasmidFeatureLabels(plasmid).join(' ').toLowerCase();
            return plasmid.name.toLowerCase().includes(searchQuery) ||
                   plasmid.id.toLowerCase().includes(searchQuery) ||
                   featureText.includes(searchQuery);
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
 * Get feature labels from the plasmid's .gb features.
 * Extracts meaningful feature labels (CDS, promoter, gene, etc.)
 * that were annotated in the original GenBank files.
 * Returns array of "label (type)" strings.
 */
function getPlasmidFeatureLabels(plasmid) {
    if (!plasmid.features || plasmid.features.length === 0) {
        return [];
    }

    // Feature types we want to highlight on the card
    const interestingTypes = new Set([
        'CDS', 'gene', 'promoter', 'terminator', 'misc_feature',
        'regulatory', 'sig_peptide', 'transit_peptide'
    ]);

    // Labels to skip (generic/uninformative)
    const skipLabels = new Set([
        'source', 'ori', 'ORI', 'pMB1', 'pBR322ori-F', 'pBRforEco',
        'G to A'
    ]);

    const labels = [];
    const seen = new Set();

    for (const feature of plasmid.features) {
        if (!feature.label) continue;
        if (!interestingTypes.has(feature.type)) continue;
        if (skipLabels.has(feature.label)) continue;

        // Skip overhang markers
        if (feature.label.includes('4bp overhang')) continue;
        // Skip backbone resistance markers (SmR, AmpR) unless user's insert
        if (feature.label === 'SmR' || feature.label === 'AmpR') continue;

        const key = feature.label;
        if (seen.has(key)) continue;
        seen.add(key);

        labels.push(feature.label);
    }
    return labels;
}

/**
 * Create a plasmid card element
 */
function createPlasmidCard(plasmid) {
    const card = document.createElement('div');
    card.className = 'plasmid-card';
    
    const cassettesText = plasmid.cassette_count === 1 ? '1 cassette' : `${plasmid.cassette_count} cassettes`;
    const featureLabels = getPlasmidFeatureLabels(plasmid);
    
    let featuresHtml = '';
    if (featureLabels.length > 0) {
        featuresHtml = `
            <div class="plasmid-features">
                ${featureLabels.map(label => `<span class="feature-label">${escapeHtml(label)}</span>`).join('')}
            </div>
        `;
    }
    
    card.innerHTML = `
        <div class="plasmid-card-header">
            <h3>${escapeHtml(plasmid.name)}</h3>
            <div class="plasmid-card-badges">
                <span class="badge badge-success">${cassettesText}</span>
                <span class="badge badge-secondary">${plasmid.size} bp</span>
            </div>
        </div>
        <div class="plasmid-card-body">
            ${featuresHtml}
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
                    <span class="detail-value">${escapeHtml(plasmid.metadata.assembly_method)}</span>
                </div>
            `;
        }

        const strat = plasmid.metadata.moclo_strategy;
        if (strat && strat.enzyme) {
            html += `
                <div class="detail-item">
                    <span class="detail-label">Enzyme:</span>
                    <span class="detail-value">${escapeHtml(strat.enzyme)}${strat.level_label ? ' · ' + escapeHtml(strat.level_label) : ''}</span>
                </div>
            `;
        }

        html += `
                </div>
            </div>
        `;
    }

    // MoClo assembly strategy — the full fragment breakdown (promoter + all
    // Level 0 parts) with sizes and overhangs, for ALL plasmids. Rendered from
    // metadata.moclo_strategy (preferred) or built from cassette_details.
    html += renderMocloStrategy(plasmid);

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
    
    // Translation (per transcription unit) — filled in asynchronously
    html += `
        <div class="detail-section" id="plasmidTranslation">
            <h3>Translation</h3>
            <div>Analysing transcription units...</div>
        </div>
    `;

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

    // Edit metadata — shown to the owner, an admin, or a shared user.
    if (plasmid.can_edit) {
        html += `
            <div class="detail-section">
                <h3>Edit Metadata</h3>
                <div id="plasmidEditForm">${renderPlasmidEditForm(plasmid)}</div>
            </div>
        `;
    }

    // Manage access — admins only. Lets an admin grant/revoke edit access.
    if (plasmid.viewer_is_admin) {
        html += `
            <div class="detail-section">
                <h3>Manage Access</h3>
                <div class="text-muted" style="margin-bottom:0.5rem;">
                    Owner and admins always have access. Add users below to let
                    them edit this plasmid's metadata.
                </div>
                <div class="export-buttons" style="margin-bottom:0.5rem;">
                    <input type="text" id="plasmidShareUsername" placeholder="username"
                           style="padding:0.35rem 0.5rem; min-width:180px;">
                    <button class="btn btn-sm btn-primary"
                            onclick="addPlasmidShare('${plasmid.id}')">Add user</button>
                </div>
                <div id="plasmidShareList"></div>
            </div>
        `;
    }

    detailsElement.innerHTML = html;
    modal.style.display = 'block';

    if (plasmid.viewer_is_admin) {
        loadPlasmidShares(plasmid.id);
    }
    loadPlasmidTranslation(plasmid.id);
}

// Keep the editable metadata keys in sync with the backend allowlist
// (EDITABLE_PLASMID_METADATA_KEYS in app/api/plasmids.py).
const PLASMID_EDITABLE_FIELDS = [
    ['description', 'Description'],
    ['notes', 'Notes'],
    ['reference', 'Reference'],
    ['antibiotic', 'Antibiotic'],
    ['host_strain', 'Host strain'],
    ['location_80', 'Location (-80)'],
    ['location_96_plate', '96-well plate location'],
    ['sequenced', 'Sequenced'],
    ['comments', 'Comments'],
    ['contributor', 'Contributor'],
    ['donor_organism', 'Donor organism'],
    ['lab_source', 'Lab source'],
];

/**
 * Render the metadata edit form for a plasmid.
 */
function renderPlasmidEditForm(plasmid) {
    const md = plasmid.metadata || {};
    let rows = `
        <div class="detail-item" style="margin-bottom:0.5rem;">
            <label class="detail-label" for="peditName">Name</label>
            <input type="text" id="peditName" value="${escapeHtml(plasmid.name || '')}"
                   style="width:100%; padding:0.35rem 0.5rem;">
        </div>
    `;
    PLASMID_EDITABLE_FIELDS.forEach(([key, label]) => {
        const val = md[key] == null ? '' : String(md[key]);
        rows += `
            <div class="detail-item" style="margin-bottom:0.5rem;">
                <label class="detail-label" for="pedit_${key}">${escapeHtml(label)}</label>
                <input type="text" id="pedit_${key}" value="${escapeHtml(val)}"
                       style="width:100%; padding:0.35rem 0.5rem;">
            </div>
        `;
    });
    rows += `
        <button class="btn btn-sm btn-primary" onclick="savePlasmidMetadata('${plasmid.id}')">
            Save metadata
        </button>
    `;
    return rows;
}

/**
 * Collect the edit form values and PUT them to the plasmid endpoint.
 */
async function savePlasmidMetadata(plasmidId) {
    const nameEl = document.getElementById('peditName');
    const body = { name: nameEl ? nameEl.value.trim() : undefined, metadata: {} };
    PLASMID_EDITABLE_FIELDS.forEach(([key]) => {
        const el = document.getElementById(`pedit_${key}`);
        if (el) body.metadata[key] = el.value;
    });
    try {
        const res = await apiRequest(`/api/plasmids/${plasmidId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        showFlashMessage('Plasmid metadata saved', 'success');
        // Re-render the modal with the fresh data.
        if (res && res.plasmid) {
            // get_plasmid adds permission hints; re-fetch to keep them.
            await viewPlasmid(plasmidId);
        }
    } catch (error) {
        showFlashMessage(`Failed to save: ${error.message}`, 'error');
    }
}

/**
 * Load and render the share list for an admin (Manage Access).
 */
async function loadPlasmidShares(plasmidId) {
    const container = document.getElementById('plasmidShareList');
    if (!container) return;
    try {
        const data = await apiRequest(`/api/admin/plasmids/${plasmidId}/share`);
        const shared = data.shared_with || [];
        let html = `<div class="text-muted" style="margin-bottom:0.35rem;">Owner: ${escapeHtml(data.owner_username || '')}</div>`;
        if (shared.length === 0) {
            html += '<div class="text-muted">Not shared with anyone yet.</div>';
        } else {
            html += '<ul style="margin:0; padding-left:1rem;">';
            shared.forEach(u => {
                html += `
                    <li style="margin-bottom:0.25rem;">
                        ${escapeHtml(u.username)}${u.exists ? '' : ' (missing)'}
                        <button class="btn btn-sm btn-danger" style="margin-left:0.5rem;"
                                onclick="removePlasmidShare('${plasmidId}', '${u.id}')">Remove</button>
                    </li>
                `;
            });
            html += '</ul>';
        }
        container.innerHTML = html;
    } catch (error) {
        container.innerHTML = `<div class="error-message">Failed to load access list: ${escapeHtml(error.message)}</div>`;
    }
}

/**
 * Admin: grant a user edit access to a plasmid.
 */
async function addPlasmidShare(plasmidId) {
    const input = document.getElementById('plasmidShareUsername');
    const username = input ? input.value.trim() : '';
    if (!username) {
        showFlashMessage('Enter a username to add', 'error');
        return;
    }
    try {
        await apiRequest(`/api/admin/plasmids/${plasmidId}/share`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username }),
        });
        if (input) input.value = '';
        showFlashMessage(`Shared with ${username}`, 'success');
        loadPlasmidShares(plasmidId);
    } catch (error) {
        showFlashMessage(`Failed to share: ${error.message}`, 'error');
    }
}

/**
 * Admin: revoke a user's edit access to a plasmid.
 */
async function removePlasmidShare(plasmidId, userId) {
    try {
        await apiRequest(`/api/admin/plasmids/${plasmidId}/share/${userId}`, {
            method: 'DELETE',
        });
        showFlashMessage('Access removed', 'success');
        loadPlasmidShares(plasmidId);
    } catch (error) {
        showFlashMessage(`Failed to remove access: ${error.message}`, 'error');
    }
}

/**
 * Fetch and render per-transcription-unit translation for a Level 2+ plasmid.
 */
async function loadPlasmidTranslation(plasmidId) {
    const container = document.getElementById('plasmidTranslation');
    if (!container) return;

    try {
        const data = await apiRequest(`/api/plasmids/${plasmidId}/translation`);
        const units = data.transcription_units || [];

        let html = '<h3>Translation</h3>';
        if (units.length === 0) {
            html += '<div class="text-muted">No transcription units found.</div>';
            container.innerHTML = html;
            return;
        }

        const codingUnits = data.coding_units || [];
        html += `<div class="text-muted">${codingUnits.length} of ${units.length} unit(s) contain a coding sequence.</div>`;

        units.forEach(tu => {
            const t = tu.translation || {};
            const spliced = t.protein_sequence_spliced || '';
            const protein = spliced || t.protein_sequence || '';
            html += `<div class="translation-item">`;
            html += `<div class="detail-label">${escapeHtml(tu.cassette_name || 'unit')} — `;
            html += tu.has_coding
                ? `${(protein || '').replace(/\*$/, '').length} aa${spliced ? ' (spliced)' : ''}`
                : 'no coding sequence';
            html += `</div>`;
            if (tu.coding_parts && tu.coding_parts.length > 0) {
                html += `<div class="text-muted">Coding part(s): ${tu.coding_parts.map(p => escapeHtml(p)).join(', ')}</div>`;
            }
            if (protein) {
                html += `<pre class="sequence-display protein-sequence">${protein.replace(/(.{60})/g, '$1\n')}</pre>`;
            }
            html += `</div>`;
        });

        container.innerHTML = html;
    } catch (error) {
        container.innerHTML =
            `<h3>Translation</h3><div class="error-message">Failed to analyse translation: ${escapeHtml(error.message)}</div>`;
    }
}

/**
 * Build the flat MoClo strategy fragment list for a plasmid. Prefers the
 * stored metadata.moclo_strategy; otherwise reconstructs it from
 * metadata.cassette_details (expanding any captured Level 0 sub_parts) so older
 * plasmids still show a full breakdown.
 *
 * Returns { enzyme, level_label, fragments: [{name,size,role,part_type,
 *           overhang_5prime,overhang_3prime,source_vector,cassette_name}] } or null.
 */
function buildStrategyFragments(plasmid) {
    const meta = plasmid.metadata || {};
    if (meta.moclo_strategy && Array.isArray(meta.moclo_strategy.fragments) && meta.moclo_strategy.fragments.length) {
        return meta.moclo_strategy;
    }

    // Fallback: reconstruct from cassette_details.
    const details = meta.cassette_details;
    if (!Array.isArray(details) || details.length === 0) return null;

    const level = meta.moclo_level;
    const enzyme = level === 2 ? 'BpiI' : 'BsaI';
    const levelLabel = level === 2 ? 'Level 1 → Level 2' : 'Level 0 → Level 1';

    const fragments = [];
    if (meta.backbone_name) {
        fragments.push({
            name: meta.backbone_name, size: meta.backbone_size || 0, role: 'vector',
            part_type: 'Backbone', source_vector: meta.backbone_plasmid_id || null,
        });
    }
    details.forEach(d => {
        (d.parts || []).forEach(p => {
            const rows = (Array.isArray(p.sub_parts) && p.sub_parts.length) ? p.sub_parts : [p];
            rows.forEach(r => {
                fragments.push({
                    name: r.part_name || 'Part',
                    size: r.size || r.sequence_length || 0,
                    role: 'insert',
                    part_type: r.part_type || '',
                    level: r.level,
                    overhang_5prime: r.overhang_5prime,
                    overhang_3prime: r.overhang_3prime,
                    source_vector: r.source_vector,
                    cassette_name: d.cassette_name,
                });
            });
        });
    });

    if (fragments.length === 0) return null;
    return { enzyme: enzyme, level_label: levelLabel, moclo_level: level, fragments: fragments };
}

/**
 * Render the "MoClo Assembly Strategy" detail section for a plasmid: a table of
 * every fragment (backbone + each Level 0 part) with type, size and overhangs,
 * plus a button to pre-fill the protocol-page reaction calculator.
 */
function renderMocloStrategy(plasmid) {
    const strat = buildStrategyFragments(plasmid);
    if (!strat) return '';

    const typeLabel = {
        'Backbone': 'Backbone', 'Coding': 'Coding', 'NonCodingPromoter': 'Promoter',
        'NonCodingTerminator': 'Terminator', 'NonCodingIntron': 'Intron',
        'NonCodingOther': 'Other', 'ExpressionCassette': 'Expression cassette',
    };

    let rows = '';
    strat.fragments.forEach(f => {
        const roleTag = f.role === 'vector'
            ? '<span class="strategy-role strategy-role-vector">vector</span>'
            : '<span class="strategy-role strategy-role-insert">insert</span>';
        const oh = (f.overhang_5prime || f.overhang_3prime)
            ? `${escapeHtml(f.overhang_5prime || '—')} / ${escapeHtml(f.overhang_3prime || '—')}`
            : '—';
        // Append the source plasmid id in parentheses after the name when it is
        // a meaningful id (not a UUID record-link) and not already in the name,
        // e.g. "zCas9 unit (pICH47802)".
        const rawPid = f.source_vector || f.plasmid_id;
        const isUuid = rawPid && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(rawPid));
        const pid = (rawPid && !isUuid) ? String(rawPid) : null;
        const nameWithPid = (pid && !String(f.name || '').toLowerCase().includes(pid.toLowerCase()))
            ? `${escapeHtml(f.name)} <span class="text-muted">(${escapeHtml(pid)})</span>`
            : escapeHtml(f.name);
        rows += `
            <tr>
                <td>${nameWithPid}</td>
                <td>${roleTag}</td>
                <td>${escapeHtml(typeLabel[f.part_type] || f.part_type || '')}</td>
                <td style="text-align:right;">${f.size ? f.size + ' bp' : '—'}</td>
                <td><code>${oh}</code></td>
            </tr>`;
    });

    const insertCount = strat.fragments.filter(f => f.role === 'insert').length;

    // Stash the strategy on the plasmid so the calculator handoff can read it.
    window._plasmidStrategies = window._plasmidStrategies || {};
    window._plasmidStrategies[plasmid.id] = { strat: strat, name: plasmid.name };

    return `
        <div class="detail-section">
            <h3>MoClo Assembly Strategy</h3>
            <p class="text-muted" style="margin-top:-0.25rem;">
                ${escapeHtml(strat.enzyme)} assembly${strat.level_label ? ' · ' + escapeHtml(strat.level_label) : ''}
                — 1 acceptor vector + ${insertCount} insert fragment(s). Each part is supplied as its own plasmid;
                sizes shown are the fragment/insert sizes.
            </p>
            <table class="strategy-table">
                <thead>
                    <tr><th>Fragment</th><th>Role</th><th>Type</th><th style="text-align:right;">Size</th><th>Overhangs (5'/3')</th></tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
            <div style="margin-top:0.75rem; display:flex; gap:0.5rem; flex-wrap:wrap; align-items:center;">
                <button class="btn btn-primary"
                        onclick="sendStrategyToCalculator('${plasmid.id}')">
                    Send to reaction calculator →
                </button>
                <button class="btn btn-success"
                        onclick="savePlasmidToDashboard('${plasmid.id}')">
                    ★ Save to dashboard
                </button>
            </div>
        </div>
    `;
}

/**
 * Save a plasmid (its MoClo strategy summary) to the user's dashboard so it can
 * be revisited and re-opened in the reaction calculator later.
 */
async function savePlasmidToDashboard(plasmidId) {
    const entry = (window._plasmidStrategies || {})[plasmidId];
    if (!entry) return;
    const strat = entry.strat;
    const payload = {
        item_type: 'plasmid',
        ref_id: plasmidId,
        title: entry.name || 'Plasmid',
        summary: {
            kind: 'plasmid',
            reactions: [{
                label: strat.level_label || ('Level ' + (strat.moclo_level || '')),
                level: strat.moclo_level === 1 ? '1' : '2',
                enzyme: strat.enzyme,
                fragments: strat.fragments.map(f => ({
                    name: f.name, size: f.size || 0,
                    role: f.role === 'vector' ? 'vector' : 'insert',
                })),
            }],
            records: { plasmid_id: plasmidId },
        },
    };
    try {
        await apiRequest('/api/me/saved', { method: 'POST', body: JSON.stringify(payload) });
        showFlashMessage('Saved "' + (entry.name || 'plasmid') + '" to your dashboard.', 'success');
    } catch (e) {
        showFlashMessage(e.message || 'Failed to save to dashboard', 'error');
    }
}

/**
 * Hand the plasmid's MoClo strategy to the protocol-page reaction calculator.
 * Stores a fragment list in sessionStorage and navigates to /protocol, which
 * reads it and pre-fills the DNA fragment rows + reaction level.
 */
function sendStrategyToCalculator(plasmidId) {
    const entry = (window._plasmidStrategies || {})[plasmidId];
    if (!entry) return;
    const strat = entry.strat;

    const payload = {
        source: 'plasmid',
        plasmid_name: entry.name,
        level: strat.moclo_level === 1 ? '1' : '2',
        enzyme: strat.enzyme,
        fragments: strat.fragments.map(f => ({
            name: f.name,
            size: f.size || 0,
            role: f.role === 'vector' ? 'vector' : 'insert',
        })),
    };
    try {
        sessionStorage.setItem('mocloCalculatorPrefill', JSON.stringify(payload));
    } catch (e) {
        // sessionStorage may be unavailable; fall back to a query flag.
    }
    window.location.href = '/protocol#calculator';
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
window.savePlasmidMetadata = savePlasmidMetadata;
window.addPlasmidShare = addPlasmidShare;
window.removePlasmidShare = removePlasmidShare;
