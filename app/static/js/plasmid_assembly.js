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
                <span>${backbone.size || backbone.length || 0} bp</span>
                <span>${backbone.slot_count || backbone.cassette_slots || 0} slot${(backbone.slot_count || backbone.cassette_slots || 0) !== 1 ? 's' : ''}</span>
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
    const expectedSize = selectedBackbone.size + totalCassetteSize;
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

        // Show concentration input form before showing full results
        showConcentrationForm(response);
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
 * Show form to collect DNA concentrations before displaying reaction mix.
 * For plasmid assembly (Level 1→2), the cassettes are already assembled Level 1 plasmids,
 * so each cassette IS a plasmid. We also list the individual parts within each cassette
 * so the user knows what's in the reaction.
 */
function showConcentrationForm(assemblyResult) {
    const content = document.getElementById('assemblyResultContent');
    const plasmid = assemblyResult.plasmid || assemblyResult;
    const plasmidName = plasmid.name || assemblyResult.name || 'Unnamed';

    let fragmentRows = '';

    // Backbone (Level 2 acceptor vector)
    const backboneSize = selectedBackbone ? selectedBackbone.size : 5000;
    fragmentRows += `
        <div class="conc-row">
            <span class="conc-name">${escapeHtml(selectedBackbone ? selectedBackbone.name : 'Backbone')} <em>(Level 2 acceptor vector, ${backboneSize} bp)</em></span>
            <div class="conc-input-wrap">
                <input type="number" class="conc-input" id="conc-backbone" value="" min="1" step="0.1" placeholder="ng/µL">
                <span class="conc-unit">ng/µL</span>
            </div>
        </div>`;

    // Each cassette is a Level 1 plasmid containing multiple parts
    selectedCassettes.forEach((cassette, i) => {
        const size = cassette.length || (cassette.assembled_sequence ? cassette.assembled_sequence.length : 0);
        // Show the parts inside this cassette if available
        let partsInfo = '';
        if (cassette.parts_metadata && cassette.parts_metadata.length > 0) {
            const partNames = cassette.parts_metadata.map(p => p.part_name).join(', ');
            partsInfo = ` — contains: ${partNames}`;
        } else if (cassette.part_count) {
            partsInfo = ` — ${cassette.part_count} parts`;
        }
        fragmentRows += `
            <div class="conc-row">
                <span class="conc-name">${escapeHtml(cassette.name)} <em>(Level 1 cassette plasmid, ${size} bp${partsInfo})</em></span>
                <div class="conc-input-wrap">
                    <input type="number" class="conc-input" id="conc-cassette-${i}" value="" min="1" step="0.1" placeholder="ng/µL">
                    <span class="conc-unit">ng/µL</span>
                </div>
            </div>`;
    });

    content.innerHTML = `
        <div class="alert alert-success">
            <h3 style="margin-bottom: 0.5rem;">✓ Plasmid "${escapeHtml(plasmidName)}" Assembled Successfully!</h3>
            <p style="margin: 0;">Enter your DNA concentrations below to generate the reaction mix.</p>
        </div>

        <h3 style="margin: 1.5rem 0 0.75rem; font-size: 1.15rem;">Enter DNA Concentrations</h3>
        <p style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 1rem;">
            Each cassette is a Level 1 plasmid. Enter the concentration of each plasmid as measured (e.g. NanoDrop).
            The volume needed is calculated based on the full plasmid size to deliver the correct fmol.
        </p>

        <div class="conc-form" id="concForm">
            ${fragmentRows}
        </div>

        <div style="display: flex; gap: 0.75rem; margin-top: 1.5rem;">
            <button class="btn btn-primary" style="flex: 1;" onclick="generateReactionMix(window._lastAssemblyResult)">
                Calculate Reaction Mix
            </button>
            <button class="btn btn-secondary" style="flex: 0 0 auto;" onclick="generateReactionMix(window._lastAssemblyResult, true)">
                Skip (use 100 ng/µL)
            </button>
        </div>
    `;

    // Store result for use after concentrations are entered
    window._lastAssemblyResult = assemblyResult;
}

/**
 * Generate reaction mix table with user-provided concentrations
 */
function generateReactionMix(assemblyResult, useDefault) {
    // Gather concentrations
    const bbConcInput = document.getElementById('conc-backbone');
    const bbConc = useDefault ? 100 : parseFloat(bbConcInput.value);

    if (!useDefault && (!bbConc || bbConc <= 0)) {
        alert('Please enter the backbone concentration.');
        bbConcInput.focus();
        return;
    }

    const cassetteConcs = [];
    for (let i = 0; i < selectedCassettes.length; i++) {
        const input = document.getElementById(`conc-cassette-${i}`);
        const val = useDefault ? 100 : parseFloat(input.value);
        if (!useDefault && (!val || val <= 0)) {
            alert(`Please enter the concentration for ${selectedCassettes[i].name}.`);
            input.focus();
            return;
        }
        cassetteConcs.push(val);
    }

    renderAssemblyResult(assemblyResult, bbConc, cassetteConcs);
}

/**
 * Render assembly result
 */
function renderAssemblyResult(result, bbConc, cassetteConcs) {
    const content = document.getElementById('assemblyResultContent');
    const plasmid = result.plasmid || result;
    const plasmidName = plasmid.name || result.name || 'Unnamed';
    const plasmidSize = plasmid.size || result.length || 0;
    const featureCount = (plasmid.features || []).length || result.feature_count || 0;

    // Determine enzyme based on backbone
    const enzyme = selectedBackbone && selectedBackbone.level === '2' ? 'BpiI' : 'BsaI';
    const levelLabel = enzyme === 'BsaI' ? 'Level 0 → Level 1' : 'Level 1 → Level 2';

    // Generate reaction mix
    const vectorFmol = 40;
    const insertFmol = 80;
    const totalVolume = 20;
    const bufferVol = 2;
    const atpVol = 0.2;
    const enzymeVol = 1;
    const ligaseVol = 0.4;

    // Calculate DNA volumes
    const backboneSize = selectedBackbone ? selectedBackbone.size : 5000;
    const backboneNg = (vectorFmol * backboneSize * 660) / 1000000;

    let dnaRows = '';
    let totalDnaVol = 0;

    // Backbone row
    const bbVol = backboneNg / bbConc;
    totalDnaVol += bbVol;
    dnaRows += `<tr>
        <td>${escapeHtml(selectedBackbone ? selectedBackbone.name : 'Backbone')} <em>(vector)</em></td>
        <td>${bbVol.toFixed(2)}</td>
        <td>${backboneNg.toFixed(1)} ng (${vectorFmol} fmol)</td>
        <td>${backboneSize} bp @ ${bbConc} ng/µL</td>
    </tr>`;

    // Cassette rows — each cassette is a Level 1 plasmid
    selectedCassettes.forEach((cassette, i) => {
        const cassetteSize = cassette.length || (cassette.assembled_sequence ? cassette.assembled_sequence.length : 3000);
        const cassetteNg = (insertFmol * cassetteSize * 660) / 1000000;
        const conc = cassetteConcs[i];
        const cassetteVol = cassetteNg / conc;
        totalDnaVol += cassetteVol;
        dnaRows += `<tr>
            <td>${escapeHtml(cassette.name)} <em>(L1 cassette plasmid)</em></td>
            <td>${cassetteVol.toFixed(2)}</td>
            <td>${cassetteNg.toFixed(1)} ng (${insertFmol} fmol)</td>
            <td>${cassetteSize} bp @ ${conc} ng/µL</td>
        </tr>`;
    });

    const waterVol = totalVolume - bufferVol - atpVol - enzymeVol - ligaseVol - totalDnaVol;

    content.innerHTML = `
        <div class="alert alert-success">
            <h3 style="margin-bottom: 0.5rem;">✓ Plasmid Assembled Successfully!</h3>
            <p style="margin: 0;">Your plasmid "${escapeHtml(plasmidName)}" has been created.</p>
        </div>

        <div class="detail-info-grid" style="margin: 1.5rem 0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;">
            <div style="background: var(--bg-color); padding: 1rem; border-radius: 0.375rem; text-align: center;">
                <div style="font-size: 0.875rem; color: var(--text-secondary);">Final Size</div>
                <div style="font-size: 1.5rem; font-weight: 600;">${plasmidSize} bp</div>
            </div>
            <div style="background: var(--bg-color); padding: 1rem; border-radius: 0.375rem; text-align: center;">
                <div style="font-size: 0.875rem; color: var(--text-secondary);">Features</div>
                <div style="font-size: 1.5rem; font-weight: 600;">${featureCount}</div>
            </div>
            <div style="background: var(--bg-color); padding: 1rem; border-radius: 0.375rem; text-align: center;">
                <div style="font-size: 0.875rem; color: var(--text-secondary);">Enzyme</div>
                <div style="font-size: 1.5rem; font-weight: 600;">${enzyme}</div>
            </div>
        </div>

        <h3 style="margin: 2rem 0 1rem; font-size: 1.25rem; border-bottom: 2px solid var(--border-color); padding-bottom: 0.5rem;">
            🧪 Reaction Mix (${totalVolume} µL)
        </h3>
        <p style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 1rem;">
            ${levelLabel} assembly using ${enzyme}. 2:1 molar ratio (${insertFmol} fmol insert : ${vectorFmol} fmol vector).
        </p>
        <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
            <thead>
                <tr style="background: var(--primary-color); color: white;">
                    <th style="padding: 0.6rem 1rem; text-align: left;">Component</th>
                    <th style="padding: 0.6rem 1rem; text-align: left;">Volume (µL)</th>
                    <th style="padding: 0.6rem 1rem; text-align: left;">Amount</th>
                    <th style="padding: 0.6rem 1rem; text-align: left;">Notes</th>
                </tr>
            </thead>
            <tbody>
                <tr><td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">10x Buffer G</td>
                    <td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">${bufferVol.toFixed(1)}</td>
                    <td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">1x final</td>
                    <td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">Thermo Fisher</td></tr>
                <tr><td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">100 mM ATP</td>
                    <td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">${atpVol.toFixed(2)}</td>
                    <td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">1 mM final</td>
                    <td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">Thermo Fisher</td></tr>
                ${dnaRows}
                <tr><td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">${enzyme}</td>
                    <td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">${enzymeVol.toFixed(1)}</td>
                    <td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">10 units</td>
                    <td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">Type IIS enzyme</td></tr>
                <tr><td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">T4 DNA Ligase</td>
                    <td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">${ligaseVol.toFixed(2)}</td>
                    <td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">2 units</td>
                    <td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">Thermo Fisher</td></tr>
                <tr><td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">MQ Water</td>
                    <td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">${waterVol < 0 ? '0.00' : waterVol.toFixed(2)}</td>
                    <td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">—</td>
                    <td style="padding: 0.5rem 1rem; border-bottom: 1px solid var(--border-color);">Molecular grade</td></tr>
                <tr style="font-weight: 700; background: var(--bg-color);">
                    <td style="padding: 0.6rem 1rem; border-top: 2px solid var(--primary-color);"><strong>Total</strong></td>
                    <td style="padding: 0.6rem 1rem; border-top: 2px solid var(--primary-color);"><strong>${totalVolume.toFixed(1)}</strong></td>
                    <td style="padding: 0.6rem 1rem; border-top: 2px solid var(--primary-color);"></td>
                    <td style="padding: 0.6rem 1rem; border-top: 2px solid var(--primary-color);"></td></tr>
            </tbody>
        </table>

        ${waterVol < 0 ? '<div style="background: #fef3c7; border: 1px solid #f59e0b; padding: 0.75rem; border-radius: 0.375rem; margin-top: 1rem; font-size: 0.875rem;"><strong>⚠️ Warning:</strong> DNA volumes exceed reaction volume! Increase total volume or dilute your DNA.</div>' : ''}

        <div style="background: #dbeafe; padding: 1rem; border-radius: 0.5rem; margin-top: 1rem; font-size: 0.875rem;">
            <strong>Thermal cycling:</strong> 60 cycles of 37°C (10 min) / 22°C (10 min), then 37°C (10 min), 65°C (20 min), hold 12°C.
        </div>

        <div style="display: flex; gap: 0.75rem; margin-top: 1.5rem;">
            <a href="/plasmids" class="btn btn-primary" style="flex: 1; text-align: center;">View All Plasmids</a>
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
