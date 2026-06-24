/**
 * Plasmid Assembly JavaScript
 * Handles the workflow for assembling cassettes into backbones
 */

let backbones = [];
let cassettes = [];
let selectedBackbone = null;
let selectedCassettes = [];
let cassetteOrientations = [];  // Track orientation for each cassette
let simulationResult = null;

/**
 * Initialize the plasmid assembly page
 */
async function initPlasmidAssembly() {
    // Check for URL parameters to pre-select backbone and cassette
    const urlParams = new URLSearchParams(window.location.search);
    const backboneId = urlParams.get('backbone');
    const cassetteId = urlParams.get('cassette');
    
    await loadBackbones();
    
    // If backbone ID is provided, auto-select it
    if (backboneId) {
        const backbone = backbones.find(b => b.id === backboneId);
        if (backbone) {
            await selectBackbone(backbone);
            
            // If cassette ID is also provided, auto-select it after cassettes load
            if (cassetteId) {
                // Wait for cassettes to load
                const maxWait = 50; // 5 seconds max
                let attempts = 0;
                const checkCassettes = setInterval(() => {
                    attempts++;
                    if (cassettes.length > 0 || attempts >= maxWait) {
                        clearInterval(checkCassettes);
                        const cassette = cassettes.find(c => c.id === cassetteId);
                        if (cassette) {
                            toggleCassette(cassette);
                        }
                    }
                }, 100);
            }
        }
    }
}

/**
 * Load all available backbones
 */
async function loadBackbones() {
    const container = document.getElementById('backboneList');
    container.innerHTML = '<div class="loading-spinner">Loading backbones...</div>';

    try {
        const response = await apiRequest('/api/backbones');
        backbones = response.backbones || [];
        renderBackbones();
    } catch (error) {
        container.innerHTML = `
            <div class="error-state">
                <div class="error-message">Failed to load backbones: ${error.message}</div>
                <button class="btn btn-primary" onclick="loadBackbones()">Try Again</button>
            </div>
        `;
    }
}

/**
 * Render backbone selection list
 */
function renderBackbones() {
    const container = document.getElementById('backboneList');

    if (backbones.length === 0) {
        container.innerHTML = `
            <div class="text-muted" style="padding: 1rem;">
                No backbones available. <a href="/backbones">Upload a backbone</a> first.
            </div>
        `;
        return;
    }

    container.innerHTML = '';
    backbones.forEach(backbone => {
        const item = document.createElement('div');
        item.className = 'selection-item';
        if (selectedBackbone && selectedBackbone.id === backbone.id) {
            item.classList.add('selected');
        }

        item.innerHTML = `
            <div class="item-name">${escapeHtml(backbone.name)}</div>
            <div class="item-meta">
                <span>${backbone.length} bp</span>
                <span>${backbone.slot_count} slot${backbone.slot_count !== 1 ? 's' : ''}</span>
            </div>
        `;

        item.onclick = () => selectBackbone(backbone);
        container.appendChild(item);
    });
}

/**
 * Select a backbone
 */
async function selectBackbone(backbone) {
    selectedBackbone = backbone;
    selectedCassettes = [];
    cassetteOrientations = [];
    simulationResult = null;

    renderBackbones();
    await loadCompatibleCassettes();
    updatePreview();
}

/**
 * Load cassettes compatible with selected backbone
 */
async function loadCompatibleCassettes() {
    const container = document.getElementById('cassetteList');
    container.innerHTML = '<div class="loading-spinner">Loading compatible cassettes...</div>';

    try {
        const response = await apiRequest(`/api/backbones/${selectedBackbone.id}/compatible-cassettes`);
        // Extract cassette objects from the compatibility results
        const compatibleResults = response.compatible_cassettes || [];
        cassettes = compatibleResults.map(item => ({
            ...item.cassette,
            compatibility: item.compatibility
        }));
        renderCassettes();
    } catch (error) {
        container.innerHTML = `
            <div class="error-state">
                <div class="error-message">Failed to load cassettes: ${error.message}</div>
            </div>
        `;
    }
}

/**
 * Render cassette selection list
 */
function renderCassettes() {
    const container = document.getElementById('cassetteList');

    if (cassettes.length === 0) {
        container.innerHTML = `
            <div class="text-muted" style="padding: 1rem;">
                No compatible cassettes found. <a href="/assembly">Create a cassette</a> first.
            </div>
        `;
        return;
    }

    container.innerHTML = '';
    cassettes.forEach(cassette => {
        const item = document.createElement('div');
        item.className = 'selection-item';
        if (selectedCassettes.some(c => c.id === cassette.id)) {
            item.classList.add('selected');
        }

        // Extract overhangs from assembled sequence (first 4 and last 4 bases)
        const overhang5 = cassette.assembled_sequence ? cassette.assembled_sequence.substring(0, 4) : 'N/A';
        const overhang3 = cassette.assembled_sequence ? cassette.assembled_sequence.substring(cassette.assembled_sequence.length - 4) : 'N/A';
        const compatScore = cassette.compatibility ? cassette.compatibility.score : 100;

        item.innerHTML = `
            <div class="item-name">${escapeHtml(cassette.name)}</div>
            <div class="item-meta">
                <span>${cassette.length || cassette.assembled_sequence.length} bp</span>
                <span>5': ${overhang5}</span>
                <span>3': ${overhang3}</span>
                <span>Score: ${compatScore}%</span>
            </div>
        `;

        item.onclick = () => toggleCassette(cassette);
        container.appendChild(item);
    });
}

/**
 * Toggle cassette selection
 */
function toggleCassette(cassette) {
    const index = selectedCassettes.findIndex(c => c.id === cassette.id);
    
    if (index >= 0) {
        selectedCassettes.splice(index, 1);
        cassetteOrientations.splice(index, 1);
    } else {
        // Check if we can add more cassettes
        if (selectedCassettes.length >= selectedBackbone.slot_count) {
            showFlashMessage(`This backbone only has ${selectedBackbone.slot_count} slot(s)`, 'warning');
            return;
        }
        selectedCassettes.push(cassette);
        
        // Determine default orientation based on compatibility
        const defaultOrientation = cassette.compatibility && cassette.compatibility.orientation 
            ? cassette.compatibility.orientation 
            : 'forward';
        cassetteOrientations.push(defaultOrientation);
    }

    simulationResult = null;
    renderCassettes();
    updatePreview();
}

/**
 * Update assembly preview
 */
function updatePreview() {
    const preview = document.getElementById('assemblyPreview');
    
    if (!selectedBackbone || selectedCassettes.length === 0) {
        preview.style.display = 'none';
        return;
    }

    preview.style.display = 'block';

    // Update stats
    document.getElementById('previewBackboneName').textContent = selectedBackbone.name;
    document.getElementById('previewSlotCount').textContent = 
        `${selectedCassettes.length} / ${selectedBackbone.slot_count}`;
    
    // Calculate expected size
    const totalCassetteSize = selectedCassettes.reduce((sum, c) => {
        const length = c.length || (c.assembled_sequence ? c.assembled_sequence.length : 0);
        return sum + length;
    }, 0);
    const expectedSize = selectedBackbone.length + totalCassetteSize;
    document.getElementById('previewSize').textContent = `~${expectedSize} bp`;

    // Render cassette slots
    renderCassetteSlots();

    // Update assemble button state
    const assembleBtn = document.getElementById('assembleBtn');
    assembleBtn.disabled = !simulationResult || !simulationResult.success;
}

/**
 * Render cassette slot assignments
 */
function renderCassetteSlots() {
    const container = document.getElementById('cassetteSlots');
    container.innerHTML = '';

    for (let i = 0; i < selectedBackbone.slot_count; i++) {
        const cassette = selectedCassettes[i];
        const orientation = cassetteOrientations[i] || 'forward';
        const slot = document.createElement('div');
        slot.className = 'slot-item';
        
        if (cassette) {
            slot.classList.add('filled');
            // Extract overhangs from assembled sequence
            const overhang5 = cassette.assembled_sequence ? cassette.assembled_sequence.substring(0, 4) : 'N/A';
            const overhang3 = cassette.assembled_sequence ? cassette.assembled_sequence.substring(cassette.assembled_sequence.length - 4) : 'N/A';
            
            // Check which orientations are compatible
            const compatibility = cassette.compatibility || {};
            const details = compatibility.details || {};
            const slotDetails = details[`slot_${i + 1}`] || {};
            const forwardCompatible = slotDetails.forward ? slotDetails.forward.compatible : true;
            const reverseCompatible = slotDetails.reverse ? slotDetails.reverse.compatible : false;
            
            slot.innerHTML = `
                <div class="slot-number">${i + 1}</div>
                <div class="slot-info">
                    <div class="slot-cassette-name">${escapeHtml(cassette.name)}</div>
                    <div class="slot-overhangs">5': ${overhang5} → 3': ${overhang3}</div>
                    <div class="slot-orientation">
                        <span class="orientation-label">Orientation:</span>
                        <button 
                            class="orientation-btn ${orientation === 'forward' ? 'active' : ''} ${!forwardCompatible ? 'disabled' : ''}" 
                            onclick="setOrientation(${i}, 'forward')"
                            ${!forwardCompatible ? 'disabled' : ''}
                            title="${forwardCompatible ? 'Forward orientation' : 'Not compatible in forward orientation'}">
                            → Forward
                        </button>
                        <button 
                            class="orientation-btn ${orientation === 'reverse' ? 'active' : ''} ${!reverseCompatible ? 'disabled' : ''}" 
                            onclick="setOrientation(${i}, 'reverse')"
                            ${!reverseCompatible ? 'disabled' : ''}
                            title="${reverseCompatible ? 'Reverse complement orientation' : 'Not compatible in reverse orientation'}">
                            ← Reverse
                        </button>
                    </div>
                </div>
                <div class="slot-actions">
                    <button class="btn btn-secondary" onclick="removeCassette(${i})">Remove</button>
                </div>
            `;
        } else {
            slot.innerHTML = `
                <div class="slot-number">${i + 1}</div>
                <div class="slot-info">
                    <div class="text-muted">Empty slot</div>
                </div>
            `;
        }

        container.appendChild(slot);
    }
}

/**
 * Set orientation for a cassette slot
 */
function setOrientation(slotIndex, orientation) {
    if (slotIndex < cassetteOrientations.length) {
        cassetteOrientations[slotIndex] = orientation;
        simulationResult = null;
        renderCassetteSlots();
    }
}

/**
 * Remove cassette from slot
 */
function removeCassette(index) {
    selectedCassettes.splice(index, 1);
    cassetteOrientations.splice(index, 1);
    simulationResult = null;
    renderCassettes();
    updatePreview();
}

/**
 * Simulate assembly before performing it
 */
async function simulateAssembly() {
    const btn = document.getElementById('simulateBtn');
    const messagesContainer = document.getElementById('compatibilityMessages');
    
    btn.disabled = true;
    btn.textContent = '🔬 Simulating...';
    messagesContainer.innerHTML = '<div class="loading-spinner">Simulating assembly...</div>';

    try {
        const response = await apiRequest('/api/plasmids/simulate', {
            method: 'POST',
            body: JSON.stringify({
                backbone_id: selectedBackbone.id,
                cassette_ids: selectedCassettes.map(c => c.id),
                orientations: cassetteOrientations
            })
        });

        simulationResult = response;
        renderSimulationResult();
    } catch (error) {
        messagesContainer.innerHTML = `
            <div class="compatibility-error">
                <strong>Simulation Failed:</strong> ${error.message}
            </div>
        `;
        simulationResult = null;
    } finally {
        btn.disabled = false;
        btn.textContent = '🔬 Simulate Assembly';
        updatePreview();
    }
}

/**
 * Render simulation result
 */
function renderSimulationResult() {
    const container = document.getElementById('compatibilityMessages');
    
    if (!simulationResult) {
        container.innerHTML = '';
        return;
    }

    let html = '';

    if (simulationResult.success) {
        html += `
            <div class="alert alert-success">
                <strong>✓ Assembly Valid</strong><br>
                Expected plasmid size: ${simulationResult.expected_length} bp<br>
                Features: ${simulationResult.feature_count} total
            </div>
        `;
    } else {
        html += `
            <div class="compatibility-error">
                <strong>✗ Assembly Invalid</strong><br>
                ${escapeHtml(simulationResult.error || 'Unknown error')}
            </div>
        `;
    }

    if (simulationResult.warnings && simulationResult.warnings.length > 0) {
        html += '<div class="compatibility-warning"><strong>Warnings:</strong><ul style="margin: 0.5rem 0 0 1.5rem;">';
        simulationResult.warnings.forEach(warning => {
            html += `<li>${escapeHtml(warning)}</li>`;
        });
        html += '</ul></div>';
    }

    container.innerHTML = html;
}

/**
 * Perform the actual assembly
 */
async function performAssembly() {
    if (!simulationResult || !simulationResult.success) {
        showFlashMessage('Please simulate the assembly first', 'warning');
        return;
    }

    // Prompt for plasmid name
    const plasmidName = prompt('Enter a name for the assembled plasmid:');
    if (!plasmidName || plasmidName.trim() === '') {
        return;
    }

    const modal = document.getElementById('assemblyResultModal');
    const content = document.getElementById('assemblyResultContent');
    
    modal.style.display = 'block';
    content.innerHTML = '<div class="loading-spinner">Assembling plasmid...</div>';

    try {
        const response = await apiRequest('/api/plasmids', {
            method: 'POST',
            body: JSON.stringify({
                name: plasmidName.trim(),
                backbone_id: selectedBackbone.id,
                cassette_ids: selectedCassettes.map(c => c.id),
                orientations: cassetteOrientations
            })
        });

        renderAssemblyResult(response);
    } catch (error) {
        content.innerHTML = `
            <div class="error-state">
                <div class="error-message">Assembly failed: ${error.message}</div>
                <button class="btn btn-primary" onclick="closeAssemblyResult()">Close</button>
            </div>
        `;
    }
}

/**
 * Render assembly result
 */
function renderAssemblyResult(result) {
    const content = document.getElementById('assemblyResultContent');
    
    content.innerHTML = `
        <div class="alert alert-success">
            <h3 style="margin-bottom: 0.5rem;">✓ Plasmid Assembled Successfully!</h3>
            <p style="margin: 0;">Your plasmid "${escapeHtml(result.name)}" has been created.</p>
        </div>

        <div class="detail-info-grid" style="margin: 1.5rem 0;">
            <div class="detail-info-item">
                <div class="detail-info-label">Plasmid ID</div>
                <div class="detail-info-value" style="font-size: 1rem;">${result.id}</div>
            </div>
            <div class="detail-info-item">
                <div class="detail-info-label">Final Size</div>
                <div class="detail-info-value">${result.length} bp</div>
            </div>
            <div class="detail-info-item">
                <div class="detail-info-label">Features</div>
                <div class="detail-info-value">${result.feature_count}</div>
            </div>
        </div>

        <div style="display: flex; gap: 0.75rem; margin-top: 1.5rem;">
            <a href="/plasmids" class="btn btn-primary" style="flex: 1;">View All Plasmids</a>
            <button class="btn btn-secondary" onclick="resetAndClose()" style="flex: 1;">Create Another</button>
        </div>
    `;
}

/**
 * Close assembly result modal
 */
function closeAssemblyResult() {
    const modal = document.getElementById('assemblyResultModal');
    modal.style.display = 'none';
}

/**
 * Reset assembly and close modal
 */
function resetAndClose() {
    closeAssemblyResult();
    resetAssembly();
}

/**
 * Reset the assembly
 */
function resetAssembly() {
    selectedBackbone = null;
    selectedCassettes = [];
    cassetteOrientations = [];
    simulationResult = null;
    
    renderBackbones();
    document.getElementById('cassetteList').innerHTML = 
        '<div class="text-muted" style="padding: 1rem;">Select a backbone first</div>';
    document.getElementById('assemblyPreview').style.display = 'none';
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Export functions for use in HTML
window.initPlasmidAssembly = initPlasmidAssembly;
window.loadBackbones = loadBackbones;
window.selectBackbone = selectBackbone;
window.toggleCassette = toggleCassette;
window.removeCassette = removeCassette;
window.setOrientation = setOrientation;
window.simulateAssembly = simulateAssembly;
window.performAssembly = performAssembly;
window.closeAssemblyResult = closeAssemblyResult;
window.resetAndClose = resetAndClose;
window.resetAssembly = resetAssembly;
