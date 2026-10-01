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

    // Populate L1 acceptor dropdown
    const l1Sel = document.getElementById('gdL1Acceptor');
    gdOptions.l1_acceptors.forEach(a => {
        const opt = document.createElement('option');
        opt.value = a.vector;
        opt.textContent = `${a.vector} (Position ${a.position})`;
        if (a.vector === 'pICH47742') opt.selected = true;
        l1Sel.appendChild(opt);
    });

    // Start with one guide row
    addGuideRow();

    document.getElementById('gdAddGuide').addEventListener('click', addGuideRow);
    document.getElementById('gdDesign').addEventListener('click', runDesign);
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

function renderPlan(plan) {
    const c = document.getElementById('gdResults');
    c.classList.remove('gd-hidden');

    let html = '';

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
                hairpin ΔG fwd ${o.hairpin.top_strand_dg}, rev ${o.hairpin.bottom_strand_dg} kcal/mol</div>
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

    // Action: create Level 0 parts
    html += `<div class="gd-panel">
        <h3>Add to parts library</h3>
        <p class="gd-subtitle">Generate the fully assembled Level 0 guide-cassette module(s)
            (real toolkit vector with your guide spliced in) and save them as parts,
            each with the MoClo cloning strategy and oligo annealing protocol.</p>
        <button id="gdCreateParts" class="btn btn-success">Generate Level 0 cassette part(s) &amp; add to library</button>
    </div>`;

    // Reference
    html += `<div class="gd-panel gd-dg">Reference: ${esc(plan.reference)}</div>`;

    c.innerHTML = html;

    // Wire copy buttons
    c.querySelectorAll('.gd-copy-btn').forEach(b => {
        b.addEventListener('click', () => copyToClipboard(b.dataset.seq, b));
    });

    // Wire the create-parts button (stash the plan for the modal)
    gdLastPlan = plan;
    const cpBtn = document.getElementById('gdCreateParts');
    if (cpBtn) cpBtn.addEventListener('click', openCreatePartsModal);

    c.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
