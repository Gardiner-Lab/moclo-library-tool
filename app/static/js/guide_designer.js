/**
 * CRISPR Guide Designer
 * Collects guide sequences + options, calls the design API, and renders the
 * full tRNA-sgRNA Golden Gate cloning strategy (Levels -1, 0, 1, 2).
 */

let gdOptions = null;
let gdGuideCounter = 0;

async function initGuideDesigner() {
    try {
        gdOptions = await apiRequest('/api/guide-designer/options');
    } catch (e) {
        showFlashMessage('Failed to load designer options: ' + e.message, 'error');
        return;
    }

    // Populate promoter dropdown
    const promoterSel = document.getElementById('gdPromoter');
    gdOptions.promoters.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.key;
        opt.textContent = `${p.description} (${p.key}, start ${p.start_nt}, ${p.host})`;
        promoterSel.appendChild(opt);
    });

    // Populate L1 acceptor dropdown. The acceptor sets the guide cassette's
    // Level 2 position, which is "blocked" for the guide cassette.
    const l1Sel = document.getElementById('gdL1Acceptor');
    gdOptions.l1_acceptors.forEach(a => {
        const opt = document.createElement('option');
        opt.value = a.vector;
        opt.textContent = `${a.vector} (Position ${a.position})`;
        if (a.vector === 'pICH47742') opt.selected = true;
        l1Sel.appendChild(opt);
    });
    l1Sel.addEventListener('change', updateGuidePositionLabel);
    updateGuidePositionLabel();

    // Start with one guide row
    addGuideRow();

    // Set up the Cas / resistance / other part pickers.
    initPartPicker(document.getElementById('gdCasPick'));
    initPartPicker(document.getElementById('gdResPick'));
    initPartPicker(document.getElementById('gdOtherPick'));

    document.getElementById('gdAddGuide').addEventListener('click', addGuideRow);
    document.getElementById('gdDesign').addEventListener('click', runDesign);
    updateGenerateGate();

    // If we arrived here from a saved dashboard construct, regenerate its full
    // protocol read-only (no create actions, since the records already exist).
    maybeRenderSavedConstruct();
}

/**
 * If the dashboard handed us a saved construct (via sessionStorage), re-render
 * its full Guide Designer protocol in read-only mode.
 */
function maybeRenderSavedConstruct() {
    let raw;
    try {
        raw = sessionStorage.getItem('gdSavedConstruct');
        if (raw) sessionStorage.removeItem('gdSavedConstruct');
    } catch (e) { return; }
    if (!raw) return;
    let summary;
    try { summary = JSON.parse(raw); } catch (e) { return; }
    if (!summary || !summary.plan) {
        showFlashMessage('This saved construct has no stored protocol to regenerate.', 'warning');
        return;
    }
    renderPlan(summary.plan, {
        readOnly: true,
        savedResult: {
            records: summary.records || {},
            l2_layout: summary.l2_layout || [],
            reactions: summary.reactions || [],
        },
    });
}

// Selected parts by role
const gdSelected = { cas: null, resistance: null, other: [] };

function updateGuidePositionLabel() {
    const sel = document.getElementById('gdL1Acceptor');
    const opt = sel.options[sel.selectedIndex];
    const m = opt ? opt.textContent.match(/Position (\d+)/) : null;
    const posEl = document.getElementById('gdGuidePos');
    if (posEl && m) posEl.textContent = m[1];
}

/**
 * Wire up a searchable Level 1 part picker. role is read from data-role;
 * data-multi="1" allows multiple selections (the "other parts" picker).
 */
function initPartPicker(container) {
    const role = container.dataset.role;
    const multi = container.dataset.multi === '1';
    container.innerHTML = `
        <input type="text" class="form-control gd-partsearch" placeholder="Search your Level 1 parts...">
        <div class="gd-partpick-results gd-hidden"></div>
        <div class="gd-chosen"></div>
    `;
    const search = container.querySelector('.gd-partsearch');
    const results = container.querySelector('.gd-partpick-results');
    let timer = null;

    search.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(async () => {
            const q = search.value.trim();
            try {
                const res = await apiRequest(`/api/guide-designer/l1-parts?search=${encodeURIComponent(q)}`);
                results.classList.remove('gd-hidden');
                results.innerHTML = (res.parts || []).slice(0, 50).map(p => `
                    <div class="gd-partpick-opt" data-id="${esc(p.id)}" data-name="${esc(p.name)}">
                        <span>${esc(p.name)}</span>
                        <span class="oh">${esc(p.overhang_5prime)}/${esc(p.overhang_3prime)} · L${esc(p.level || '?')}</span>
                    </div>
                `).join('') || '<div class="gd-dg" style="padding:0.3rem 0.5rem;">No matching Level 1 parts.</div>';
                results.querySelectorAll('.gd-partpick-opt').forEach(opt => {
                    opt.addEventListener('click', () => {
                        choosePart(role, multi, { id: opt.dataset.id, name: opt.dataset.name });
                        results.classList.add('gd-hidden');
                        search.value = '';
                    });
                });
            } catch (e) { /* ignore */ }
        }, 250);
    });

    renderChosen(container, role, multi);
}

function choosePart(role, multi, part) {
    if (multi) {
        if (!gdSelected.other.some(p => p.id === part.id)) gdSelected.other.push(part);
    } else {
        gdSelected[role] = part;
    }
    const container = role === 'cas' ? document.getElementById('gdCasPick')
                    : role === 'resistance' ? document.getElementById('gdResPick')
                    : document.getElementById('gdOtherPick');
    renderChosen(container, role, multi);
    updateGenerateGate();
}

function removePart(role, multi, id) {
    if (multi) gdSelected.other = gdSelected.other.filter(p => p.id !== id);
    else gdSelected[role] = null;
    const container = role === 'cas' ? document.getElementById('gdCasPick')
                    : role === 'resistance' ? document.getElementById('gdResPick')
                    : document.getElementById('gdOtherPick');
    renderChosen(container, role, multi);
    updateGenerateGate();
}

function renderChosen(container, role, multi) {
    const chosen = container.querySelector('.gd-chosen');
    const items = multi ? gdSelected.other : (gdSelected[role] ? [gdSelected[role]] : []);
    chosen.innerHTML = items.map(p => `
        <span class="gd-chosen-tag">${esc(p.name)}
            <span class="x" data-id="${esc(p.id)}">✕</span></span>
    `).join('');
    chosen.querySelectorAll('.x').forEach(x => {
        x.addEventListener('click', () => removePart(role, multi, x.dataset.id));
    });
}

function updateGenerateGate() {
    const ready = !!(gdSelected.cas && gdSelected.resistance);
    const btn = document.getElementById('gdDesign');
    const gate = document.getElementById('gdGate');
    if (btn) btn.disabled = !ready;
    if (gate) gate.textContent = ready
        ? 'Ready — a Cas part and a resistance part are selected.'
        : 'Select a Cas part and a resistance part to enable.';
}

function addGuideRow() {
    const list = document.getElementById('gdGuidesList');
    const rows = list.querySelectorAll('.gd-guide-row');
    if (rows.length >= (gdOptions ? gdOptions.max_guides : 6)) {
        showFlashMessage(`Maximum ${gdOptions.max_guides} guides per Level 1 unit`, 'warning');
        return;
    }
    gdGuideCounter++;
    const idx = rows.length + 1;
    const row = document.createElement('div');
    row.className = 'gd-guide-row';
    row.dataset.id = gdGuideCounter;
    row.innerHTML = `
        <div class="pos-badge">${idx}</div>
        <input type="text" class="form-control gd-guide-input" maxlength="20"
               placeholder="20 bp guide, e.g. GGGGCATTGGATTGGGATTA" spellcheck="false">
        <span class="valid-mark"></span>
        <button class="btn-icon gd-remove" title="Remove">✕</button>
    `;
    list.appendChild(row);

    const input = row.querySelector('.gd-guide-input');
    input.addEventListener('input', () => onGuideInput(input));
    row.querySelector('.gd-remove').addEventListener('click', () => {
        row.remove();
        renumberGuides();
    });
}

function renumberGuides() {
    document.querySelectorAll('#gdGuidesList .gd-guide-row').forEach((row, i) => {
        row.querySelector('.pos-badge').textContent = i + 1;
    });
}

let gdValidateTimer = null;
function onGuideInput(input) {
    input.value = input.value.toUpperCase().replace(/[^ACGT]/g, '');
    const mark = input.parentElement.querySelector('.valid-mark');
    mark.textContent = '';
    mark.className = 'valid-mark';
    if (input.value.length !== 20) return;

    clearTimeout(gdValidateTimer);
    gdValidateTimer = setTimeout(async () => {
        try {
            const res = await apiRequest('/api/guide-designer/validate', {
                method: 'POST',
                body: JSON.stringify({ guide: input.value, guide_length: 20 })
            });
            if (res.valid) {
                mark.textContent = '✓';
                mark.className = 'valid-mark ok';
                mark.title = 'Valid guide';
            } else {
                mark.textContent = '✗';
                mark.className = 'valid-mark bad';
                mark.title = res.error || 'Invalid';
            }
        } catch (e) {
            // ignore transient validation errors
        }
    }, 300);
}

function collectGuides() {
    return Array.from(document.querySelectorAll('#gdGuidesList .gd-guide-input'))
        .map(i => i.value.trim())
        .filter(v => v.length > 0);
}

async function runDesign() {
    const guides = collectGuides();
    if (guides.length === 0) {
        showFlashMessage('Enter at least one guide sequence', 'warning');
        return;
    }
    const btn = document.getElementById('gdDesign');
    setButtonLoading(btn, true);
    try {
        const res = await apiRequest('/api/guide-designer/design', {
            method: 'POST',
            body: JSON.stringify({
                guides: guides,
                promoter: document.getElementById('gdPromoter').value,
                backbone_flavor: document.getElementById('gdBackbone').value,
                l1_acceptor: document.getElementById('gdL1Acceptor').value,
            })
        });
        renderPlan(res.plan);
    } catch (e) {
        showFlashMessage(e.message || 'Design failed', 'error');
    } finally {
        setButtonLoading(btn, false);
    }
}

function copyToClipboard(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
        const orig = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(() => { btn.textContent = orig; }, 1200);
    });
}

function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
}

function renderPlan(plan, opts) {
    opts = opts || {};
    const readOnly = !!opts.readOnly;   // true when regenerating a saved construct
    const c = document.getElementById('gdResults');
    c.classList.remove('gd-hidden');

    let html = '';
    if (readOnly) {
        html += `<div class="gd-panel" style="border-left:4px solid var(--primary-color, #6b21a8);">
            <h2 style="margin-top:0;">Saved construct protocol</h2>
            <p class="gd-subtitle">Regenerated from your dashboard. The parts and plasmids for this
                construct were already created, so creation actions are hidden.</p>
        </div>`;
    }

    // Summary
    html += `<div class="gd-panel">
        <h2>Cloning strategy: ${esc(plan.strategy)}</h2>
        <p class="gd-subtitle">
            ${plan.guide_count} guide(s) &middot; ${esc(plan.nuclease_family)} &middot;
            promoter <strong>${esc(plan.promoter.description)}</strong> (${esc(plan.promoter.key)}) &middot;
            <strong>${esc(plan.backbone_flavor)}</strong> sgRNA backbone
        </p>
    </div>`;

    // Level -1: oligos
    html += `<div class="gd-panel"><div class="gd-step">
        <h3>Level −1: Oligos to order <span class="gd-enzyme-tag">${esc(plan.level_minus1.enzyme)}</span></h3>
        <p class="gd-subtitle">${esc(plan.level_minus1.description)}</p></div>`;

    plan.level_minus1.guides.forEach(g => {
        const o = g.oligos;
        html += `<div class="gd-oligo-block">
            <div class="gd-oligo-title">Position ${g.position} &mdash; guide <code>${esc(g.guide)}</code>
                <span class="gd-pill">into ${esc(g.level0_vector)}</span></div>
            <div class="gd-layout">${esc(o.annotated_layout)}</div>
            <div style="margin-top:0.5rem;">
                <div><strong>FW</strong> (${o.forward_length} nt)
                    <button class="gd-copy-btn" data-seq="${esc(o.forward_oligo)}">copy</button>
                    <code class="gd-mono">${esc(o.forward_oligo)}</code></div>
                <div><strong>REV</strong> (${o.reverse_length} nt)
                    <button class="gd-copy-btn" data-seq="${esc(o.reverse_oligo)}">copy</button>
                    <code class="gd-mono">${esc(o.reverse_oligo)}</code></div>
            </div>
            <div class="gd-dg">Pads: 5′ <code>${esc(o.pad_left)}</code>, 3′ <code>${esc(o.pad_right)}</code>
                ${o.hairpin.pads_identical ? '(identical)' : '(independent)'} &middot;
                hairpin fwd ΔG ${o.hairpin.top_strand_dg} kcal/mol${o.hairpin.top_strand_tm != null ? ', Tm ' + o.hairpin.top_strand_tm + '°C' : ''};
                rev ΔG ${o.hairpin.bottom_strand_dg} kcal/mol${o.hairpin.bottom_strand_tm != null ? ', Tm ' + o.hairpin.bottom_strand_tm + '°C' : ''}</div>
            ${(o.warnings || []).map(w => `<div class="gd-warn">⚠ ${esc(w)}</div>`).join('')}
        </div>`;
    });
    html += `</div>`;

    // Level 0
    html += `<div class="gd-panel"><div class="gd-step">
        <h3>Level 0: Insert guides into position modules <span class="gd-enzyme-tag">${esc(plan.level0.enzyme)}</span></h3>
        <p class="gd-subtitle">${esc(plan.level0.description)}</p></div>
        <table class="gd-module-table">
            <thead><tr><th>Array position</th><th>Level 0 tRNA-sgRNA vector</th></tr></thead>
            <tbody>
            ${plan.level0.modules.map(m => `<tr><td>${m.position}</td><td><code>${esc(m.level0_vector)}</code></td></tr>`).join('')}
            </tbody>
        </table></div>`;

    // Level 1
    const l1 = plan.level1;
    html += `<div class="gd-panel"><div class="gd-step">
        <h3>Level 1: Build the transcription unit <span class="gd-enzyme-tag">${esc(l1.enzyme)}</span></h3>
        <p class="gd-subtitle">${esc(l1.description)}</p></div>
        <table class="gd-module-table"><tbody>
            <tr><td>Pol III promoter module</td><td><code>${esc(l1.promoter_module)}</code></td></tr>
            <tr><td>Level 1 acceptor</td><td><code>${esc(l1.l1_acceptor)}</code> (Position ${l1.l1_position})</td></tr>
            <tr><td>Endlinker</td><td>${l1.endlinker ? `<code>${esc(l1.endlinker)}</code> (required for ${plan.guide_count} &lt; 6 guides)` : 'Not required (6 guides fill the array)'}</td></tr>
        </tbody></table></div>`;

    // Level 2
    const l2 = plan.level2;
    html += `<div class="gd-panel"><div class="gd-step">
        <h3>Level 2: Assemble the final construct <span class="gd-enzyme-tag">${esc(l2.enzyme)}</span></h3>
        <p class="gd-subtitle">${esc(l2.description)}</p></div>
        <ul>${l2.required_units.map(u => `<li>${esc(u)}</li>`).join('')}</ul></div>`;

    // In read-only mode (regenerating a saved construct), the parts/plasmids
    // already exist — show the created records + reactions instead of the
    // creation action panels, then finish.
    if (readOnly) {
        html += renderSavedConstructRecords(opts.savedResult || {});
        html += `<div class="gd-panel gd-dg">Reference: ${esc(plan.reference)}</div>`;
        c.innerHTML = html;
        c.querySelectorAll('.gd-copy-btn').forEach(b => {
            b.addEventListener('click', () => copyToClipboard(b.dataset.seq, b));
        });
        // Wire per-level reaction buttons from the stored reactions.
        const savedReactions = (opts.savedResult && opts.savedResult.reactions) || [];
        c.querySelectorAll('.gd-saved-calc-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const rx = savedReactions[parseInt(btn.dataset.rx, 10)];
                if (rx) sendReactionToCalculator(rx);
            });
        });
        gdLastPlan = plan;
        c.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
    }

    // Action: create Level 0 parts (oligo modules only)
    html += `<div class="gd-panel">
        <h3>Add Level 0 guide modules to library</h3>
        <p class="gd-subtitle">Generate the fully assembled Level 0 guide-cassette module(s)
            (real toolkit vector with your guide spliced in) and save them as parts,
            each with the MoClo cloning strategy and oligo annealing protocol.</p>
        <button id="gdCreateParts" class="btn btn-secondary">Generate Level 0 cassette part(s)</button>
    </div>`;

    // Action: create the full construct (L1 guide cassette + L2 cassette + plasmid)
    html += `<div class="gd-panel">
        <h3>Build the full construct</h3>
        <p class="gd-subtitle">Assemble the Level&nbsp;1 guide cassette and, optionally, the
            Level&nbsp;2 cassette (guide + Cas + resistance + others) and the final Level&nbsp;2 plasmid.</p>
        <div class="form-group">
            <label>Guide cassette name (Level 1)</label>
            <input type="text" id="gdGuideCassetteName" class="form-control"
                   value="gRNA_L1_${esc(plan.guide_count || 1)}guides_${new Date().toISOString().split('T')[0]}">
        </div>
        <label style="display:block; margin:0.4rem 0;">
            <input type="checkbox" id="gdMakeL2" checked> Also create the Level&nbsp;2 cassette
            (guide + Cas <code>${esc(gdSelected.cas ? gdSelected.cas.name : '')}</code>
             + resistance <code>${esc(gdSelected.resistance ? gdSelected.resistance.name : '')}</code>${gdSelected.other.length ? ' + ' + gdSelected.other.length + ' other' : ''})
        </label>
        <div id="gdL2Name" class="form-group">
            <label>Level 2 cassette name</label>
            <input type="text" id="gdL2CassetteName" class="form-control"
                   value="L2_construct_${new Date().toISOString().split('T')[0]}">
        </div>
        <label style="display:block; margin:0.4rem 0;">
            <input type="checkbox" id="gdMakeL1Plasmid"> Assemble the Level&nbsp;1 guide plasmid into a
            Level&nbsp;1 acceptor backbone (recommended &mdash; creates a real Level&nbsp;1 unit)
        </label>
        <div id="gdL1PlasmidBlock" class="gd-hidden">
            <div class="form-group">
                <label>Level 1 acceptor backbone</label>
                <div id="gdL1BackbonePick" class="gd-partpick"></div>
            </div>
            <div class="form-group">
                <label>Level 1 plasmid name</label>
                <input type="text" id="gdL1PlasmidName" class="form-control" value="">
            </div>
        </div>
        <label style="display:block; margin:0.4rem 0;">
            <input type="checkbox" id="gdMakePlasmid"> Also assemble the final Level&nbsp;2 plasmid
        </label>
        <div id="gdPlasmidBlock" class="gd-hidden">
            <div class="form-group">
                <label>Level 2 acceptor backbone</label>
                <div id="gdBackbonePick" class="gd-partpick"></div>
            </div>
            <div class="form-group">
                <label>Plasmid name</label>
                <input type="text" id="gdPlasmidName" class="form-control" value="">
            </div>
        </div>
        <button id="gdCreateConstruct" class="btn btn-success">Create construct</button>
    </div>`;

    // Reference
    html += `<div class="gd-panel gd-dg">Reference: ${esc(plan.reference)}</div>`;

    c.innerHTML = html;

    // Wire copy buttons
    c.querySelectorAll('.gd-copy-btn').forEach(b => {
        b.addEventListener('click', () => copyToClipboard(b.dataset.seq, b));
    });

    // Wire the create-parts (Level 0 only) button
    gdLastPlan = plan;
    const cpBtn = document.getElementById('gdCreateParts');
    if (cpBtn) cpBtn.addEventListener('click', openCreatePartsModal);

    // Wire the full-construct controls
    const makePlasmid = document.getElementById('gdMakePlasmid');
    const plasmidBlock = document.getElementById('gdPlasmidBlock');
    const backbonePickEl = document.getElementById('gdBackbonePick');
    gdSelectedBackbone = null;
    makePlasmid.addEventListener('change', () => {
        plasmidBlock.classList.toggle('gd-hidden', !makePlasmid.checked);
        if (makePlasmid.checked && !backbonePickEl.dataset.inited) {
            initBackbonePicker(backbonePickEl,
                (b) => { gdSelectedBackbone = b; },
                () => gdSelectedBackbone);
            backbonePickEl.dataset.inited = '1';
        }
    });

    // Wire the Level 1 acceptor backbone picker (assemble the guide plasmid).
    const makeL1Plasmid = document.getElementById('gdMakeL1Plasmid');
    const l1PlasmidBlock = document.getElementById('gdL1PlasmidBlock');
    const l1BackbonePickEl = document.getElementById('gdL1BackbonePick');
    gdSelectedL1Backbone = null;
    makeL1Plasmid.addEventListener('change', () => {
        l1PlasmidBlock.classList.toggle('gd-hidden', !makeL1Plasmid.checked);
        if (makeL1Plasmid.checked && !l1BackbonePickEl.dataset.inited) {
            initBackbonePicker(l1BackbonePickEl,
                (b) => { gdSelectedL1Backbone = b; },
                () => gdSelectedL1Backbone);
            l1BackbonePickEl.dataset.inited = '1';
        }
    });
    const makeL2 = document.getElementById('gdMakeL2');
    makeL2.addEventListener('change', () => {
        document.getElementById('gdL2Name').classList.toggle('gd-hidden', !makeL2.checked);
        if (!makeL2.checked) { makePlasmid.checked = false; makePlasmid.disabled = true; plasmidBlock.classList.add('gd-hidden'); }
        else { makePlasmid.disabled = false; }
    });
    document.getElementById('gdCreateConstruct').addEventListener('click', createConstruct);

    c.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

let gdSelectedBackbone = null;    // Level 2 acceptor
let gdSelectedL1Backbone = null;  // Level 1 acceptor

/**
 * Searchable backbone picker. onSelect(backbone|null) is called whenever the
 * selection changes, so the caller can store it (L1 vs L2 acceptor).
 */
function initBackbonePicker(container, onSelect, getSelected) {
    container.innerHTML = `
        <input type="text" class="form-control gd-partsearch" placeholder="Search backbones...">
        <div class="gd-partpick-results gd-hidden"></div>
        <div class="gd-chosen"></div>
    `;
    const search = container.querySelector('.gd-partsearch');
    const results = container.querySelector('.gd-partpick-results');
    const chosen = container.querySelector('.gd-chosen');
    let timer = null;
    const renderChosenBB = () => {
        const sel = getSelected();
        chosen.innerHTML = sel
            ? `<span class="gd-chosen-tag">${esc(sel.name)}${sel.size ? ' · ' + sel.size + ' bp' : ''} <span class="x">✕</span></span>` : '';
        const x = chosen.querySelector('.x');
        if (x) x.addEventListener('click', () => { onSelect(null); renderChosenBB(); });
    };
    search.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(async () => {
            try {
                const res = await apiRequest(`/api/guide-designer/backbones?search=${encodeURIComponent(search.value.trim())}`);
                results.classList.remove('gd-hidden');
                results.innerHTML = (res.backbones || []).slice(0, 50).map(b => `
                    <div class="gd-partpick-opt" data-id="${esc(b.id)}" data-name="${esc(b.name)}" data-size="${esc(b.size || '')}">
                        <span>${esc(b.name)}</span>
                        <span class="oh">${esc(b.size || '?')} bp · ${esc(b.slot_count || '?')} slot(s)</span>
                    </div>`).join('') || '<div class="gd-dg" style="padding:0.3rem 0.5rem;">No backbones found.</div>';
                results.querySelectorAll('.gd-partpick-opt').forEach(opt => {
                    opt.addEventListener('click', () => {
                        onSelect({ id: opt.dataset.id, name: opt.dataset.name,
                                   size: opt.dataset.size ? parseInt(opt.dataset.size, 10) : null });
                        results.classList.add('gd-hidden'); search.value = ''; renderChosenBB();
                    });
                });
            } catch (e) { /* ignore */ }
        }, 250);
    });
    renderChosenBB();
}

async function createConstruct() {
    if (!gdLastPlan) return;
    const makeL2 = document.getElementById('gdMakeL2').checked;
    const makePlasmid = document.getElementById('gdMakePlasmid').checked;
    const makeL1Plasmid = (document.getElementById('gdMakeL1Plasmid') || {}).checked;
    if (makePlasmid && !gdSelectedBackbone) {
        showFlashMessage('Select a Level 2 backbone to assemble the plasmid.', 'warning');
        return;
    }
    if (makeL1Plasmid && !gdSelectedL1Backbone) {
        showFlashMessage('Select a Level 1 acceptor backbone to assemble the Level 1 plasmid.', 'warning');
        return;
    }
    const btn = document.getElementById('gdCreateConstruct');
    setButtonLoading(btn, true);
    try {
        const body = {
            guides: collectGuides(),
            promoter: document.getElementById('gdPromoter').value,
            backbone_flavor: document.getElementById('gdBackbone').value,
            l1_acceptor: document.getElementById('gdL1Acceptor').value,
            guide_cassette_name: document.getElementById('gdGuideCassetteName').value.trim(),
            cas_part_id: gdSelected.cas.id,
            resistance_part_id: gdSelected.resistance.id,
            other_part_ids: gdSelected.other.map(p => p.id),
            l1_backbone_id: (makeL1Plasmid && gdSelectedL1Backbone) ? gdSelectedL1Backbone.id : null,
            l1_plasmid_name: (document.getElementById('gdL1PlasmidName') || {}).value || '',
            create_l2_cassette: makeL2,
            l2_cassette_name: document.getElementById('gdL2CassetteName').value.trim(),
            create_plasmid: makePlasmid,
            l2_backbone_id: gdSelectedBackbone ? gdSelectedBackbone.id : null,
            plasmid_name: (document.getElementById('gdPlasmidName') || {}).value || '',
        };
        const res = await apiRequest('/api/guide-designer/create-construct', {
            method: 'POST', body: JSON.stringify(body)
        });
        (res.messages || []).forEach(m => showFlashMessage(m, 'success'));
        renderConstructResult(res);
    } catch (e) {
        showFlashMessage(e.message || 'Failed to create construct', 'error');
    } finally {
        setButtonLoading(btn, false);
    }
}

function renderConstructResult(res) {
    const c = document.getElementById('gdResults');
    const panel = document.createElement('div');
    panel.className = 'gd-panel';
    let rows = '';
    if (res.guide_cassette_part) {
        const g = res.guide_cassette_part;
        rows += `<tr><td>Level 1 guide cassette</td><td><code>${esc(g.name)}</code></td><td>${g.length} bp, pos ${g.position}</td></tr>`;
    }
    if (res.l1_plasmid) {
        const p1 = res.l1_plasmid;
        const bb = p1.backbone_name ? ` in <code>${esc(p1.backbone_name)}</code>${p1.backbone_size ? ' (' + p1.backbone_size + ' bp)' : ''}` : '';
        rows += `<tr><td>Level 1 plasmid</td><td><code>${esc(p1.name)}</code></td><td>${p1.length} bp${bb}</td></tr>`;
        if (p1.l1_part_name) {
            rows += `<tr><td>Level 1 unit (part)</td><td><code>${esc(p1.l1_part_name)}</code></td><td>used in Level 2</td></tr>`;
        }
    }
    if (res.l2_cassette) {
        const l2 = res.l2_cassette;
        rows += `<tr><td>Level 2 cassette</td><td><code>${esc(l2.name)}</code></td><td>${l2.length} bp, ${l2.part_count} parts</td></tr>`;
    }
    if (res.plasmid) {
        const bb = res.plasmid.backbone_name ? ` in <code>${esc(res.plasmid.backbone_name)}</code>${res.plasmid.backbone_size ? ' (' + res.plasmid.backbone_size + ' bp)' : ''}` : '';
        rows += `<tr><td>Level 2 plasmid</td><td><code>${esc(res.plasmid.name)}</code></td><td>${res.plasmid.length} bp${bb}</td></tr>`;
    }

    // Level 2 layout: show each unit by real part name + position + role.
    let layoutHtml = '';
    if (Array.isArray(res.l2_layout) && res.l2_layout.length) {
        const roleLabel = {
            'selected': 'selected',
            'dummy': 'auto dummy',
            'end-linker': 'auto end-linker',
        };
        const layoutRows = res.l2_layout.map(u => {
            const role = roleLabel[u.role] || esc(u.role || '');
            const roleClass = u.role === 'selected' ? 'gd-role-selected' : 'gd-role-auto';
            const size = (u.size != null) ? `${u.size} bp` : '—';
            return `<tr>
                <td style="text-align:center;">${esc(String(u.position))}</td>
                <td><code>${esc(u.part_name)}</code></td>
                <td><span class="gd-role-tag ${roleClass}">${role}</span></td>
                <td style="text-align:right;">${size}</td>
            </tr>`;
        }).join('');

        // Append the acceptor backbone row so the layout shows the full set of
        // fragments that go into the reaction, with sizes.
        let backboneRow = '';
        if (res.plasmid && res.plasmid.backbone_name) {
            const bbSize = (res.plasmid.backbone_size != null) ? `${res.plasmid.backbone_size} bp` : '—';
            backboneRow = `<tr>
                <td style="text-align:center;">—</td>
                <td><code>${esc(res.plasmid.backbone_name)}</code></td>
                <td><span class="gd-role-tag gd-role-selected">acceptor backbone</span></td>
                <td style="text-align:right;">${bbSize}</td>
            </tr>`;
        }
        layoutHtml = `
            <h4 style="margin:0.75rem 0 0.25rem;">Level 2 layout</h4>
            <p class="gd-subtitle" style="margin-top:0;">Each Level 1 unit mapped to its Level 2 position.
                Internal gaps are filled with dummies and the ring is closed with an end-linker.</p>
            <table class="gd-module-table">
                <thead><tr><th style="width:4rem;">Position</th><th>Part</th><th>Role</th><th style="text-align:right;">Size</th></tr></thead>
                <tbody>${layoutRows}${backboneRow}</tbody>
            </table>`;
    }

    // Per-level reaction buttons: build each reaction's fragment list once and
    // stash it so the buttons can hand it to the shared reaction calculator.
    const reactions = buildConstructReactions(res);
    gdLastConstruct = { res: res, reactions: reactions };
    let calcButtons = '';
    reactions.forEach((rx, i) => {
        calcButtons += `<button class="btn btn-secondary gd-calc-btn" data-rx="${i}">
            Calculate ${esc(rx.label)} reaction (${esc(rx.enzyme)})</button>`;
    });

    panel.innerHTML = `
        <h3>✓ Construct created</h3>
        <table class="gd-module-table"><tbody>${rows}</tbody></table>
        ${layoutHtml}
        <div class="gd-dg" style="margin-top:0.5rem;">
            ${(res.messages || []).map(m => esc(m)).join('<br>')}
        </div>
        <div style="margin-top:0.75rem; display:flex; gap:0.5rem; flex-wrap:wrap;">
            ${calcButtons}
        </div>
        <div style="margin-top:0.5rem; display:flex; gap:0.5rem; flex-wrap:wrap; align-items:center;">
            <button class="btn btn-success" id="gdSaveDashboard">★ Save to dashboard</button>
            <span id="gdSaveMsg" class="gd-dg"></span>
            <a href="/parts" class="btn btn-secondary">Open Parts</a>
            <a href="/cassettes" class="btn btn-secondary">Open Cassettes</a>
            ${res.plasmid ? '<a href="/plasmids" class="btn btn-secondary">Open Plasmids</a>' : ''}
        </div>`;
    c.insertBefore(panel, c.firstChild);

    // Wire per-level calculator buttons.
    panel.querySelectorAll('.gd-calc-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const rx = reactions[parseInt(btn.dataset.rx, 10)];
            if (rx) sendReactionToCalculator(rx);
        });
    });
    // Wire save-to-dashboard.
    const saveBtn = panel.querySelector('#gdSaveDashboard');
    if (saveBtn) saveBtn.addEventListener('click', () => saveConstructToDashboard(res, reactions, saveBtn));

    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

let gdLastConstruct = null;

/**
 * Build the per-level MoClo reaction fragment lists for a created construct.
 * Returns an array of {label, level, enzyme, fragments:[{name,size,role}]}.
 * Enzyme/level mapping: Level 0 and Level 2 use BpiI (calculator level '2');
 * Level 1 uses BsaI (calculator level '1').
 */
function buildConstructReactions(res) {
    const reactions = [];

    // Level 0: oligos -> Level 0 modules (BpiI). Each module is cloned into its
    // Level 0 position vector; list the modules as the fragments.
    const l0 = res.level0_fragments || [];
    if (l0.length) {
        reactions.push({
            label: 'Level 0',
            level: '2',          // BpiI in the shared calculator
            enzyme: 'BpiI',
            fragments: l0.map(m => ({
                name: m.part_name || m.source_vector || 'Level 0 module',
                size: m.size || m.sequence_length || 0,
                role: 'insert',
            })),
        });
    }

    // Level 1: Level 0 modules -> Level 1 unit in the acceptor (BsaI).
    if (res.l1_acceptor_backbone && l0.length) {
        const frags = [{
            name: res.l1_acceptor_backbone.name,
            size: res.l1_acceptor_backbone.size || 0,
            role: 'vector',
        }];
        l0.forEach(m => frags.push({
            name: m.part_name || m.source_vector || 'Level 0 module',
            size: m.size || m.sequence_length || 0,
            role: 'insert',
        }));
        reactions.push({ label: 'Level 1', level: '1', enzyme: 'BsaI', fragments: frags });
    }

    // Level 2: Level 1 units -> Level 2 plasmid (BpiI). Use the layout + the
    // acceptor backbone.
    if (Array.isArray(res.l2_layout) && res.l2_layout.length) {
        const frags = [];
        if (res.plasmid && res.plasmid.backbone_name) {
            frags.push({
                name: res.plasmid.backbone_name,
                size: res.plasmid.backbone_size || 0,
                role: 'vector',
            });
        }
        res.l2_layout.forEach(u => frags.push({
            name: u.part_name, size: u.size || 0, role: 'insert',
        }));
        reactions.push({ label: 'Level 2', level: '2', enzyme: 'BpiI', fragments: frags });
    }

    return reactions;
}

/**
 * Hand a reaction fragment list to the shared protocol-page reaction calculator
 * via the same sessionStorage handoff the plasmid detail uses.
 */
function sendReactionToCalculator(rx) {
    const payload = {
        source: 'guide-designer',
        plasmid_name: rx.label + ' reaction',
        level: rx.level,
        enzyme: rx.enzyme,
        fragments: rx.fragments,
    };
    try {
        sessionStorage.setItem('mocloCalculatorPrefill', JSON.stringify(payload));
    } catch (e) { /* ignore */ }
    window.location.href = '/protocol#calculator';
}

/**
 * Save the construct (summary + per-level reactions) to the user's dashboard.
 */
async function saveConstructToDashboard(res, reactions, btn) {
    const title = (res.plasmid && res.plasmid.name)
        || (res.l1_plasmid && res.l1_plasmid.name)
        || (res.guide_cassette_part && res.guide_cassette_part.name)
        || 'CRISPR construct';
    const summary = {
        kind: 'guide-designer-construct',
        // The full design plan (Level -1 oligos ... Level 2 strategy) so the
        // whole protocol can be regenerated read-only from the dashboard.
        plan: gdLastPlan || null,
        records: {
            guide_cassette_part: res.guide_cassette_part || null,
            l1_plasmid: res.l1_plasmid || null,
            l2_cassette: res.l2_cassette || null,
            plasmid: res.plasmid || null,
        },
        l2_layout: res.l2_layout || [],
        reactions: reactions,
        messages: res.messages || [],
    };
    const msg = document.getElementById('gdSaveMsg');
    try {
        if (btn) setButtonLoading(btn, true);
        await apiRequest('/api/me/saved', {
            method: 'POST',
            body: JSON.stringify({
                item_type: 'construct',
                title: title,
                ref_id: res.plasmid ? res.plasmid.id : null,
                summary: summary,
            }),
        });
        if (msg) msg.textContent = 'Saved to your dashboard.';
        showFlashMessage('Saved to your dashboard.', 'success');
    } catch (e) {
        showFlashMessage(e.message || 'Failed to save to dashboard', 'error');
    } finally {
        if (btn) setButtonLoading(btn, false);
    }
}

/**
 * Read-only panel for a regenerated saved construct: the created records
 * (parts/plasmids), the Level 2 layout, and per-level reaction buttons. No
 * creation controls, since the records already exist.
 */
function renderSavedConstructRecords(saved) {
    const records = saved.records || {};
    let rows = '';
    const g = records.guide_cassette_part;
    if (g) rows += `<tr><td>Level 1 guide cassette</td><td><code>${esc(g.name)}</code></td><td>${g.length || '?'} bp${g.position ? ', pos ' + g.position : ''}</td></tr>`;
    const p1 = records.l1_plasmid;
    if (p1) {
        const bb = p1.backbone_name ? ` in <code>${esc(p1.backbone_name)}</code>${p1.backbone_size ? ' (' + p1.backbone_size + ' bp)' : ''}` : '';
        rows += `<tr><td>Level 1 plasmid</td><td><code>${esc(p1.name)}</code></td><td>${p1.length || '?'} bp${bb}</td></tr>`;
        if (p1.l1_part_name) rows += `<tr><td>Level 1 unit (part)</td><td><code>${esc(p1.l1_part_name)}</code></td><td>used in Level 2</td></tr>`;
    }
    const l2 = records.l2_cassette;
    if (l2) rows += `<tr><td>Level 2 cassette</td><td><code>${esc(l2.name)}</code></td><td>${l2.length || '?'} bp, ${l2.part_count || '?'} parts</td></tr>`;
    const pl = records.plasmid;
    if (pl) {
        const bb = pl.backbone_name ? ` in <code>${esc(pl.backbone_name)}</code>${pl.backbone_size ? ' (' + pl.backbone_size + ' bp)' : ''}` : '';
        rows += `<tr><td>Level 2 plasmid</td><td><code>${esc(pl.name)}</code></td><td>${pl.length || '?'} bp${bb}</td></tr>`;
    }

    // Level 2 layout table with sizes.
    let layoutHtml = '';
    const layout = saved.l2_layout || [];
    if (layout.length) {
        const roleLabel = { 'selected': 'selected', 'dummy': 'auto dummy', 'end-linker': 'auto end-linker' };
        const lrows = layout.map(u => {
            const role = roleLabel[u.role] || esc(u.role || '');
            const roleClass = u.role === 'selected' ? 'gd-role-selected' : 'gd-role-auto';
            const size = (u.size != null) ? `${u.size} bp` : '—';
            return `<tr><td style="text-align:center;">${esc(String(u.position))}</td>
                <td><code>${esc(u.part_name)}</code></td>
                <td><span class="gd-role-tag ${roleClass}">${role}</span></td>
                <td style="text-align:right;">${size}</td></tr>`;
        }).join('');
        layoutHtml = `<h4 style="margin:0.75rem 0 0.25rem;">Level 2 layout</h4>
            <table class="gd-module-table">
                <thead><tr><th style="width:4rem;">Position</th><th>Part</th><th>Role</th><th style="text-align:right;">Size</th></tr></thead>
                <tbody>${lrows}</tbody></table>`;
    }

    // Per-level reaction buttons from the stored reactions.
    const reactions = saved.reactions || [];
    let calcButtons = '';
    reactions.forEach((rx, i) => {
        calcButtons += `<button class="btn btn-secondary gd-saved-calc-btn" data-rx="${i}">
            Calculate ${esc(rx.label)} reaction (${esc(rx.enzyme)})</button>`;
    });

    return `<div class="gd-panel">
        <h3>Created records</h3>
        <table class="gd-module-table"><tbody>${rows || '<tr><td colspan="3">No records stored.</td></tr>'}</tbody></table>
        ${layoutHtml}
        <div style="margin-top:0.75rem; display:flex; gap:0.5rem; flex-wrap:wrap;">${calcButtons}</div>
        <div style="margin-top:0.5rem; display:flex; gap:0.5rem; flex-wrap:wrap;">
            <a href="/parts" class="btn btn-secondary">Open Parts</a>
            <a href="/cassettes" class="btn btn-secondary">Open Cassettes</a>
            ${records.plasmid ? '<a href="/plasmids" class="btn btn-secondary">Open Plasmids</a>' : ''}
        </div>
    </div>`;
}

let gdLastPlan = null;

function openCreatePartsModal() {
    if (!gdLastPlan) return;
    const plan = gdLastPlan;

    // Build a modal asking for a name (+ optional lab/description) per guide.
    const overlay = document.createElement('div');
    overlay.id = 'gdModalOverlay';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:1000;';

    const dateStr = new Date().toISOString().split('T')[0];
    let rows = '';
    plan.level_minus1.guides.forEach(g => {
        rows += `
            <div class="gd-oligo-block">
                <div class="gd-oligo-title">Position ${g.position} &mdash; <code>${esc(g.guide)}</code>
                    <span class="gd-pill">${esc(g.level0_vector)}</span></div>
                <div class="gd-form-row">
                    <div class="form-group">
                        <label>Part name *</label>
                        <input class="form-control gd-part-name" data-guide="${esc(g.guide)}"
                               data-position="${g.position}" value="gRNA_pos${g.position}_${dateStr}">
                    </div>
                    <div class="form-group">
                        <label>Lab source</label>
                        <input class="form-control gd-part-lab" value="">
                    </div>
                </div>
                <div class="form-group">
                    <label>Description</label>
                    <input class="form-control gd-part-desc" value="">
                </div>
            </div>`;
    });

    overlay.innerHTML = `
        <div class="gd-panel" style="max-width:700px;width:90%;max-height:85vh;overflow:auto;margin:0;">
            <h2>Name the Level 0 guide cassette part(s)</h2>
            <p class="gd-subtitle">One part per guide. The stored sequence is the full assembled
                Level 0 module (${esc(plan.promoter.key)} / ${esc(plan.backbone_flavor)} backbone).</p>
            ${rows}
            <div style="display:flex;gap:0.5rem;justify-content:flex-end;margin-top:1rem;">
                <button id="gdModalCancel" class="btn btn-secondary">Cancel</button>
                <button id="gdModalCreate" class="btn btn-success">Create part(s)</button>
            </div>
        </div>`;
    document.body.appendChild(overlay);

    document.getElementById('gdModalCancel').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    document.getElementById('gdModalCreate').addEventListener('click', () => submitCreateParts(overlay, plan));
}

async function submitCreateParts(overlay, plan) {
    const nameInputs = overlay.querySelectorAll('.gd-part-name');
    const labInputs = overlay.querySelectorAll('.gd-part-lab');
    const descInputs = overlay.querySelectorAll('.gd-part-desc');

    const guides = [];
    for (let i = 0; i < nameInputs.length; i++) {
        const name = nameInputs[i].value.trim();
        if (!name) {
            showFlashMessage(`Name required for position ${nameInputs[i].dataset.position}`, 'error');
            return;
        }
        guides.push({
            guide: nameInputs[i].dataset.guide,
            name: name,
            lab_source: labInputs[i].value.trim(),
            description: descInputs[i].value.trim(),
        });
    }

    const btn = document.getElementById('gdModalCreate');
    setButtonLoading(btn, true);
    try {
        const res = await apiRequest('/api/guide-designer/create-parts', {
            method: 'POST',
            body: JSON.stringify({
                promoter: plan.promoter.key,
                backbone_flavor: plan.backbone_flavor,
                guides: guides,
            })
        });
        overlay.remove();
        showFlashMessage(res.message + ' View them under Parts.', 'success');
        renderCreatedParts(res.parts);
    } catch (e) {
        showFlashMessage(e.message || 'Failed to create parts', 'error');
    } finally {
        setButtonLoading(btn, false);
    }
}

function renderCreatedParts(parts) {
    const c = document.getElementById('gdResults');
    const panel = document.createElement('div');
    panel.className = 'gd-panel';
    panel.innerHTML = `
        <h3>✓ Created ${parts.length} Level 0 part(s)</h3>
        <table class="gd-module-table">
            <thead><tr><th>Name</th><th>Vector</th><th>Pos</th><th>Module length</th><th></th></tr></thead>
            <tbody>
            ${parts.map(p => `<tr>
                <td><code>${esc(p.name)}</code></td>
                <td>${esc(p.vector)}</td>
                <td>${p.position}</td>
                <td>${p.length} bp</td>
                <td><a href="/parts" class="btn btn-secondary" style="padding:0.15rem 0.6rem;font-size:0.8rem;">Open in Parts</a></td>
            </tr>`).join('')}
            </tbody>
        </table>`;
    c.insertBefore(panel, c.firstChild);
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

window.initGuideDesigner = initGuideDesigner;
