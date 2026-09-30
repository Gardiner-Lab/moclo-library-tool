/**
 * Cassette Assembly JavaScript
 * Handles part selection, compatibility checking, and assembly preview
 */

let allParts = [];
let filteredParts = [];
let selectedParts = [];
let searchQuery = '';

/**
 * Reverse complement a DNA/overhang string.
 */
function reverseComplement(seq) {
    if (!seq) return seq;
    const comp = { A: 'T', T: 'A', C: 'G', G: 'C', N: 'N' };
    return seq.toUpperCase().split('').reverse().map(b => comp[b] || b).join('');
}

/**
 * Overhangs a part presents to the assembly in a given orientation.
 * Returns { fivePrime, threePrime }.
 * A reverse-oriented part is reverse-complemented, so its stored 3' becomes the
 * leading 5' fusion site and its stored 5' becomes the trailing 3'.
 */
function presentedOverhangs(part, orientation) {
    if (orientation === 'reverse') {
        return {
            fivePrime: reverseComplement(part.overhang_3prime),
            threePrime: reverseComplement(part.overhang_5prime)
        };
    }
    return { fivePrime: part.overhang_5prime, threePrime: part.overhang_3prime };
}

/**
 * Determine whether part2 can follow part1 (placed in part1Orientation), and in
 * which orientation. Returns 'forward', 'reverse', or null.
 */
function orientationToFollow(part1, part2, part1Orientation) {
    const junction = presentedOverhangs(part1, part1Orientation || 'forward').threePrime;
    for (const orientation of ['forward', 'reverse']) {
        if (presentedOverhangs(part2, orientation).fivePrime === junction) {
            return orientation;
        }
    }
    return null;
}

/**
 * Resolve orientation for each selected part. First part anchors forward.
 * Returns an array of orientations, or null if the chain breaks.
 */
function resolveOrientations(parts) {
    if (parts.length === 0) return [];
    if (parts.length === 1) return ['forward'];
    // The first part is a free anchor; a valid chain may need it reversed.
    for (const anchor of ['forward', 'reverse']) {
        const orientations = [anchor];
        let ok = true;
        for (let i = 1; i < parts.length; i++) {
            const chosen = orientationToFollow(parts[i - 1], parts[i], orientations[i - 1]);
            if (chosen === null) { ok = false; break; }
            orientations.push(chosen);
        }
        if (ok) return orientations;
    }
    return null;
}

/**
 * Initialize the assembly interface
 */
async function initAssembly() {
    // Set up event listeners
    document.getElementById('partsSearchInput').addEventListener('input', handlePartsSearch);
    document.getElementById('refreshParts').addEventListener('click', loadParts);
    document.getElementById('clearAssembly').addEventListener('click', clearAssembly);

    // Load parts
    await loadParts();
}

/**
 * Load all parts from the API
 */
async function loadParts() {
    const container = document.getElementById('partsListContainer');
    container.innerHTML = '<div class="loading-spinner">Loading parts...</div>';

    try {
        const response = await apiRequest('/api/parts');
        allParts = response.parts || [];
        filteredParts = [...allParts];
        renderPartsList();
    } catch (error) {
        container.innerHTML = `<div class="error-message">Failed to load parts: ${error.message}</div>`;
    }
}

/**
 * Handle parts search input
 */
function handlePartsSearch(event) {
    searchQuery = event.target.value.toLowerCase().trim();
    applyPartsFilter();
}

/**
 * Apply search filter to parts list
 */
function applyPartsFilter() {
    if (!searchQuery) {
        filteredParts = [...allParts];
    } else {
        filteredParts = allParts.filter(part => {
            return part.name.toLowerCase().includes(searchQuery) ||
                   part.id.toLowerCase().includes(searchQuery);
        });
    }
    renderPartsList();
}

/**
 * Render the parts list with compatibility indicators
 */
function renderPartsList() {
    const container = document.getElementById('partsListContainer');

    if (filteredParts.length === 0) {
        container.innerHTML = '<div class="assembly-empty"><p>No parts found</p></div>';
        return;
    }

    // Count compatible and incompatible parts
    let compatibleCount = 0;
    let incompatibleCount = 0;
    
    filteredParts.forEach(part => {
        const compatibility = getPartCompatibility(part);
        if (compatibility.disabled) {
            incompatibleCount++;
        } else {
            compatibleCount++;
        }
    });

    container.innerHTML = '';
    
    // Add info message if parts are hidden
    if (incompatibleCount > 0 && selectedParts.length > 0) {
        const infoMessage = document.createElement('div');
        infoMessage.className = 'parts-filter-info';
        infoMessage.innerHTML = `
            <span class="info-icon">ℹ️</span>
            <span>Showing ${compatibleCount} compatible part${compatibleCount !== 1 ? 's' : ''} (${incompatibleCount} incompatible part${incompatibleCount !== 1 ? 's' : ''} hidden)</span>
        `;
        container.appendChild(infoMessage);
    }

    filteredParts.forEach(part => {
        const partItem = createPartListItem(part);
        container.appendChild(partItem);
    });
}

/**
 * Create a part list item element
 */
function createPartListItem(part) {
    const item = document.createElement('div');
    item.className = 'part-item';

    // Check compatibility with last selected part
    const compatibility = getPartCompatibility(part);
    
    if (compatibility.disabled) {
        item.classList.add('disabled');
    } else {
        item.onclick = () => addPartToAssembly(part);
    }

    // Part info
    const info = document.createElement('div');
    info.className = 'part-item-info';

    const name = document.createElement('div');
    name.className = 'part-item-name';
    name.textContent = part.name;

    const meta = document.createElement('div');
    meta.className = 'part-item-meta';
    meta.innerHTML = `
        <span class="type-badge type-${part.part_type.toLowerCase()}">${formatPartType(part.part_type)}</span>
        <span>5': ${part.overhang_5prime}</span>
        <span>3': ${part.overhang_3prime}</span>
    `;

    info.appendChild(name);
    info.appendChild(meta);

    // Compatibility indicator
    const indicator = document.createElement('div');
    indicator.className = 'compatibility-indicator';

    const icon = document.createElement('div');
    icon.className = `compatibility-icon ${compatibility.status}`;
    icon.textContent = compatibility.icon;

    const text = document.createElement('span');
    text.textContent = compatibility.text;

    indicator.appendChild(icon);
    indicator.appendChild(text);

    item.appendChild(info);
    item.appendChild(indicator);

    return item;
}

/**
 * Get compatibility status for a part
 */
function getPartCompatibility(part) {
    if (selectedParts.length === 0) {
        return {
            status: 'neutral',
            icon: '○',
            text: 'First part',
            disabled: false
        };
    }

    const lastPart = selectedParts[selectedParts.length - 1];
    // Orientation the last selected part is placed in (chain resolved from the start).
    const orientations = resolveOrientations(selectedParts) || selectedParts.map(() => 'forward');
    const lastOrientation = orientations[orientations.length - 1];
    const chosen = orientationToFollow(lastPart, part, lastOrientation);

    if (chosen === 'forward') {
        return { status: 'compatible', icon: '✓', text: 'Compatible', disabled: false };
    } else if (chosen === 'reverse') {
        return { status: 'compatible', icon: '⇄', text: 'Compatible (reverse)', disabled: false };
    } else {
        return { status: 'incompatible', icon: '✗', text: 'Incompatible', disabled: true };
    }
}

/**
 * Add a part to the assembly
 */
function addPartToAssembly(part) {
    // Check if already selected
    if (selectedParts.some(p => p.id === part.id)) {
        showFlashMessage('Part already in assembly', 'warning');
        return;
    }

    // Check compatibility if not first part (in either orientation)
    if (selectedParts.length > 0) {
        const lastPart = selectedParts[selectedParts.length - 1];
        const orientations = resolveOrientations(selectedParts) || selectedParts.map(() => 'forward');
        const lastOrientation = orientations[orientations.length - 1];
        if (orientationToFollow(lastPart, part, lastOrientation) === null) {
            showFlashMessage('Part is not compatible with the last part in assembly (in either orientation)', 'error');
            return;
        }
    }

    selectedParts.push(part);
    renderAssemblyPreview();
    renderPartsList(); // Update compatibility indicators
}

/**
 * Remove a part from the assembly
 */
function removePartFromAssembly(index) {
    selectedParts.splice(index, 1);
    renderAssemblyPreview();
    renderPartsList(); // Update compatibility indicators
}

/**
 * Move a part up in the assembly order
 */
function movePartUp(index) {
    if (index === 0) return;
    
    const temp = selectedParts[index];
    selectedParts[index] = selectedParts[index - 1];
    selectedParts[index - 1] = temp;
    
    renderAssemblyPreview();
}

/**
 * Move a part down in the assembly order
 */
function movePartDown(index) {
    if (index === selectedParts.length - 1) return;
    
    const temp = selectedParts[index];
    selectedParts[index] = selectedParts[index + 1];
    selectedParts[index + 1] = temp;
    
    renderAssemblyPreview();
}

/**
 * Clear all parts from assembly
 */
function clearAssembly() {
    if (selectedParts.length === 0) return;
    
    if (confirm('Are you sure you want to clear the assembly?')) {
        selectedParts = [];
        renderAssemblyPreview();
        renderPartsList();
    }
}

/**
 * Render the assembly preview
 */
function renderAssemblyPreview() {
    const container = document.getElementById('assemblyPreview');

    if (selectedParts.length === 0) {
        container.innerHTML = `
            <div class="assembly-empty">
                <div class="assembly-empty-icon">🧬</div>
                <p>No parts selected</p>
                <p style="font-size: 0.875rem;">Click on parts from the left panel to add them to your assembly</p>
            </div>
        `;
        return;
    }

    // Validate assembly
    const validation = validateAssembly();

    let html = '';

    // Show errors if any
    if (!validation.valid) {
        html += `
            <div class="assembly-error">
                <div class="assembly-error-title">Assembly Error</div>
                <div>${validation.error}</div>
            </div>
        `;
    }

    // Show selected parts
    html += '<div class="selected-parts-list">';

    // Orientation of each selected part (for display of presented overhangs).
    const partOrientations = validation.orientations
        || resolveOrientations(selectedParts)
        || selectedParts.map(() => 'forward');
    
    selectedParts.forEach((part, index) => {
        const isError = validation.incompatiblePair && 
                       (validation.incompatiblePair[0] === index || 
                        validation.incompatiblePair[1] === index);

        const orientation = partOrientations[index] || 'forward';
        const presented = presentedOverhangs(part, orientation);
        const orientBadge = orientation === 'reverse'
            ? '<span class="type-badge" title="Placed in reverse orientation" style="background:#6b46c1;color:#fff;">⇄ Reverse</span>'
            : '';
        
        html += `
            <div class="selected-part ${isError ? 'error' : ''}">
                <div class="part-order">${index + 1}</div>
                <div class="selected-part-info">
                    <div class="selected-part-name">${part.name}</div>
                    <div class="selected-part-overhangs">
                        <div class="overhang-display">
                            <span class="label">5':</span>
                            <span class="value">${presented.fivePrime}</span>
                        </div>
                        <div class="overhang-display">
                            <span class="label">3':</span>
                            <span class="value">${presented.threePrime}</span>
                        </div>
                        <span class="type-badge type-${part.part_type.toLowerCase()}">${formatPartType(part.part_type)}</span>
                        ${orientBadge}
                    </div>
                </div>
                <div class="part-actions">
                    <button class="btn-icon" onclick="movePartUp(${index})" ${index === 0 ? 'disabled' : ''} title="Move up">
                        ▲
                    </button>
                    <button class="btn-icon" onclick="movePartDown(${index})" ${index === selectedParts.length - 1 ? 'disabled' : ''} title="Move down">
                        ▼
                    </button>
                    <button class="btn-icon" onclick="removePartFromAssembly(${index})" title="Remove">
                        ✕
                    </button>
                </div>
            </div>
        `;

        // Add junction indicator between parts (orientation-aware)
        if (index < selectedParts.length - 1) {
            const nextPart = selectedParts[index + 1];
            const thisPresented3 = presented.threePrime;
            const nextOrientation = partOrientations[index + 1] || 'forward';
            const nextPresented5 = presentedOverhangs(nextPart, nextOrientation).fivePrime;
            const compatible = thisPresented3 === nextPresented5;

            html += `
                <div class="junction-indicator ${compatible ? 'compatible' : 'incompatible'}">
                    <span class="junction-text">
                        ${compatible ? '✓ Compatible junction (' + thisPresented3 + ')' : '✗ Incompatible: ' + thisPresented3 + ' ≠ ' + nextPresented5}
                    </span>
                </div>
            `;
        }
    });
    
    html += '</div>';

    // Show assembly info
    if (validation.valid) {
        const totalLength = calculateAssemblyLength();
        html += `
            <div class="assembly-info">
                <div class="info-item">
                    <div class="info-label">Parts</div>
                    <div class="info-value">${selectedParts.length}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Length</div>
                    <div class="info-value">${totalLength} bp</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Status</div>
                    <div class="info-value" style="color: var(--success-color);">✓</div>
                </div>
            </div>
        `;

        // Show visualization placeholder
        html += `
            <div class="assembly-visualization">
                <p style="color: var(--text-secondary);">Assembly visualization will appear here</p>
            </div>
        `;
    }

    // Assembly actions
    html += '<div class="assembly-actions">';
    
    if (validation.valid) {
        html += `
            <div class="form-group cassette-name-input">
                <label for="cassetteName">Cassette Name</label>
                <input 
                    type="text" 
                    id="cassetteName" 
                    class="form-control" 
                    placeholder="Enter cassette name..."
                    value="Cassette_${new Date().toISOString().split('T')[0]}"
                >
                <div id="cassetteNameError" class="error-message"></div>
            </div>
            <button id="createCassetteBtn" class="btn btn-success btn-block" onclick="createCassette()">
                Create Cassette
            </button>
        `;
    }
    
    html += `
        <button class="btn btn-danger btn-block" onclick="clearAssembly()">
            Clear Assembly
        </button>
    `;
    
    html += '</div>';

    container.innerHTML = html;
}

/**
 * Validate the current assembly
 */
function validateAssembly() {
    if (selectedParts.length < 2) {
        return {
            valid: false,
            error: 'Assembly requires at least 2 parts',
            incompatiblePair: null
        };
    }

    // Resolve orientations for the whole chain (first part is a free anchor,
    // tried in both orientations). Each part may be placed forward or
    // reverse-complemented to make its fusion site match.
    const orientations = resolveOrientations(selectedParts);
    if (orientations) {
        return { valid: true, error: '', incompatiblePair: null, orientations };
    }

    // Report the first failing junction using a forward-anchor walk.
    const walk = ['forward'];
    for (let i = 0; i < selectedParts.length - 1; i++) {
        const part1 = selectedParts[i];
        const part2 = selectedParts[i + 1];
        const chosen = orientationToFollow(part1, part2, walk[i]);
        if (chosen === null) {
            const presented3 = presentedOverhangs(part1, walk[i]).threePrime;
            return {
                valid: false,
                error: `Parts at positions ${i + 1} and ${i + 2} have incompatible overhangs: ${presented3} matches neither ${part2.overhang_5prime} nor rc(${part2.overhang_3prime})`,
                incompatiblePair: [i, i + 1],
                orientations: null
            };
        }
        walk.push(chosen);
    }
    return {
        valid: false,
        error: 'Parts cannot be assembled into a contiguous chain in any orientation',
        incompatiblePair: null,
        orientations: null
    };
}

/**
 * Calculate the total length of the assembly
 */
function calculateAssemblyLength() {
    if (selectedParts.length === 0) return 0;
    
    // First part contributes full length
    let length = selectedParts[0].sequence.length;
    
    // Subsequent parts contribute (length - 4) because overhang is shared
    for (let i = 1; i < selectedParts.length; i++) {
        length += selectedParts[i].sequence.length - 4;
    }
    
    return length;
}

/**
 * Create a cassette from the selected parts
 */
async function createCassette() {
    const nameInput = document.getElementById('cassetteName');
    const name = nameInput.value.trim();
    const errorElement = document.getElementById('cassetteNameError');
    const button = document.getElementById('createCassetteBtn');

    // Clear previous errors
    errorElement.textContent = '';
    errorElement.style.display = 'none';
    nameInput.classList.remove('error');

    // Validate name
    if (!name) {
        errorElement.textContent = 'Cassette name is required';
        errorElement.style.display = 'block';
        nameInput.classList.add('error');
        return;
    }

    // Validate assembly
    const validation = validateAssembly();
    if (!validation.valid) {
        showFlashMessage(validation.error, 'error');
        return;
    }

    // Set loading state
    setButtonLoading(button, true);

    try {
        // Create cassette via API
        const partIds = selectedParts.map(p => p.id);
        const response = await apiRequest('/api/cassettes', {
            method: 'POST',
            body: JSON.stringify({
                name: name,
                part_ids: partIds
            })
        });

        showFlashMessage('Cassette created successfully!', 'success');
        
        // Clear assembly and redirect to cassettes
        selectedParts = [];
        renderAssemblyPreview();
        renderPartsList();

        setTimeout(() => {
            window.location.href = '/cassettes';
        }, 1500);

    } catch (error) {
        errorElement.textContent = error.message || 'Failed to create cassette';
        errorElement.style.display = 'block';
        showFlashMessage(error.message || 'Failed to create cassette', 'error');
    } finally {
        setButtonLoading(button, false);
    }
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
        'NonCodingOther': 'Other',
        'ExpressionCassette': 'Expression Cassette'
    };
    return typeMap[type] || type;
}

// Export functions for use in HTML
window.initAssembly = initAssembly;
window.addPartToAssembly = addPartToAssembly;
window.removePartFromAssembly = removePartFromAssembly;
window.movePartUp = movePartUp;
window.movePartDown = movePartDown;
window.clearAssembly = clearAssembly;
window.createCassette = createCassette;
