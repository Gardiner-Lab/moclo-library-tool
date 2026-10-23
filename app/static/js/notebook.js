/**
 * The Lab Notebook beside MoClo in Trellis Tools: a plasmid's map or a
 * cassette's diagram, with what it shows, put into a day's page there (the
 * notebook's /api/days/import). NOTEBOOK_URL tells MoClo where the notebook is;
 * without it the buttons are not shown.
 */

const NOTEBOOK_URL = (document.body.dataset.notebook || '').replace(/\/$/, '');

/** Whether there is a notebook to add to. */
function notebookEnabled() {
    return !!NOTEBOOK_URL;
}

/** Text made safe to put into the notebook's HTML. */
function notebookEscape(text) {
    return String(text ?? '').replace(/[&<>"]/g, (ch) => `&#${ch.charCodeAt(0)};`);
}

/** Today, as the notebook names days (YYYY-MM-DD), by this computer's clock. */
function notebookToday() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/**
 * An SVG served by MoClo as a PNG Blob, drawn at twice its size on a white
 * ground, so it stays sharp in the notebook and in its PDF exports.
 */
async function notebookSvgToPng(url) {
    const res = await fetch(url, { credentials: 'same-origin' });
    if (!res.ok) throw new Error(`Could not fetch the picture (${res.status})`);
    const node = new DOMParser().parseFromString(await res.text(), 'image/svg+xml').documentElement;
    if (node.nodeName !== 'svg') throw new Error('Could not read the picture');
    node.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    const box = node.viewBox && node.viewBox.baseVal;
    const width = parseFloat(node.getAttribute('width')) || (box && box.width) || 800;
    const height = parseFloat(node.getAttribute('height')) || (box && box.height) || 400;
    node.setAttribute('width', width);
    node.setAttribute('height', height);
    const source = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(node)], { type: 'image/svg+xml' }));
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => {
            const canvas = document.createElement('canvas');
            canvas.width = Math.round(width * 2);
            canvas.height = Math.round(height * 2);
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            URL.revokeObjectURL(source);
            canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('Could not draw the picture'))), 'image/png');
        };
        img.onerror = () => { URL.revokeObjectURL(source); reject(new Error('Could not draw the picture')); };
        img.src = source;
    });
}

/** A table for a notebook section: columns as [name, kind, unit], rows as lists of cells. */
function notebookTable(title, columns, rows) {
    return {
        type: 'table', title, scale: null,
        columns: columns.map(([name, kind = 'text', unit = '']) => ({ name, kind, unit })),
        rows: rows.map((cells) => ({ cells: cells.map((c) => (c === null || c === undefined ? null : String(c))) })),
    };
}

/** Put a section, and the pictures it shows, at the end of a day's page. Resolves to the day. */
async function notebookSend(section, pictures, day) {
    const form = new FormData();
    form.append('section', JSON.stringify(section));
    if (day) form.append('date', day);
    pictures.forEach((blob, i) => form.append('picture', blob, `figure-${i + 1}.png`));
    const res = await fetch(`${NOTEBOOK_URL}/api/days/import`, { method: 'POST', credentials: 'same-origin', body: form });
    let data = {};
    try { data = await res.json(); } catch (e) { /* not JSON */ }
    if (!res.ok) throw new Error(data.error || `Lab Notebook: ${res.status}`);
    return data.note;
}

/**
 * Ask which day - today unless another is chosen - then put what make() builds,
 * { section, pictures }, at the end of that day's page. `what` says what goes in.
 */
function addToNotebook(what, make) {
    document.getElementById('notebookDialog')?.remove();
    const dialog = document.createElement('div');
    dialog.id = 'notebookDialog';
    dialog.className = 'notebook-dialog';
    dialog.innerHTML = `
        <div class="notebook-dialog-box" role="dialog" aria-label="Add to the Lab Notebook">
            <h3>Add to the Lab Notebook</h3>
            <p>${notebookEscape(what)} It goes at the end of the day's page.</p>
            <label for="notebookDay">Day</label>
            <input type="date" id="notebookDay" value="${notebookToday()}">
            <p class="notebook-dialog-hint">Started in your notebook if it is not there yet.</p>
            <p class="notebook-dialog-error" hidden></p>
            <div class="notebook-dialog-buttons">
                <button class="btn btn-secondary" type="button" data-act="cancel">Cancel</button>
                <button class="btn btn-primary" type="button" data-act="add">Add to notebook</button>
            </div>
        </div>`;
    document.body.appendChild(dialog);
    const close = () => dialog.remove();
    dialog.addEventListener('mousedown', (e) => { if (e.target === dialog) close(); });
    dialog.querySelector('[data-act="cancel"]').addEventListener('click', close);
    const add = dialog.querySelector('[data-act="add"]');
    add.addEventListener('click', async () => {
        const error = dialog.querySelector('.notebook-dialog-error');
        add.disabled = true;
        add.textContent = 'Adding…';
        try {
            const { section, pictures = [] } = await make();
            const note = await notebookSend(section, pictures, dialog.querySelector('#notebookDay').value || notebookToday());
            close();
            const message = `Added to ${note.title} in your Lab Notebook`;
            if (typeof showFlashMessage === 'function') showFlashMessage(message, 'success');
            else alert(message);
        } catch (err) {
            error.textContent = err.message;
            error.hidden = false;
            add.disabled = false;
            add.textContent = 'Add to notebook';
        }
    });
}

/** The "📓 Add to notebook" button's HTML, calling `call` (a global function call, as a string); '' without a notebook. */
function notebookButtonHtml(call, className = 'btn btn-primary') {
    return notebookEnabled()
        ? `<button class="${className}" type="button" onclick="${call}" title="Put this into a day's page of your Lab Notebook">📓 Add to notebook</button>`
        : '';
}

/** A MoClo plasmid as a notebook section: its map, how it is assembled, and its fragments. */
async function mocloPlasmidSection(plasmid) {
    const meta = plasmid.metadata || {};
    const strat = meta.moclo_strategy || {};
    const facts = [`${plasmid.size} bp`];
    if (meta.backbone_name) facts.push(`backbone ${notebookEscape(meta.backbone_name)}`);
    if (meta.assembly_method) facts.push(notebookEscape(meta.assembly_method));
    if (strat.enzyme) facts.push(`${notebookEscape(strat.enzyme)}${strat.level_label ? ` (${notebookEscape(strat.level_label)})` : ''}`);
    const blocks = [{
        type: 'text',
        html: `<p><b>${notebookEscape(plasmid.name)}</b>, from the MoClo Library Tool: ${facts.join(', ')}.</p>`
            + `<p><img data-attachment="picture" alt="Map of ${notebookEscape(plasmid.name)}"></p>`,
    }];
    const fragments = typeof buildStrategyFragments === 'function' ? buildStrategyFragments(plasmid) : null;
    if (fragments && fragments.fragments && fragments.fragments.length) {
        blocks.push(notebookTable('MoClo assembly strategy',
            [['Fragment'], ['Role'], ['Type'], ['Size', 'number', 'bp'], ["5' overhang"], ["3' overhang"], ['Added', 'check']],
            fragments.fragments.map((f) => [f.name, f.role || '', f.part_type || '', f.size || '',
                f.overhang_5prime || '', f.overhang_3prime || '', null])));
    }
    return {
        section: {
            type: 'section', title: `MoClo plasmid: ${plasmid.name}`,
            source: { kind: 'moclo-plasmid', id: String(plasmid.id), name: plasmid.name },
            blocks,
        },
        pictures: [await notebookSvgToPng(`/api/plasmids/${encodeURIComponent(plasmid.id)}/map.svg`)],
    };
}

/** A MoClo cassette as a notebook section: its diagram and its parts, in order, with their overhangs. */
async function mocloCassetteSection(cassette) {
    const parts = cassette.parts || [];
    const level = cassette.level ? `Level ${notebookEscape(cassette.level)} ` : '';
    return {
        section: {
            type: 'section', title: `MoClo cassette: ${cassette.name}`,
            source: { kind: 'moclo-cassette', id: String(cassette.id), name: cassette.name },
            blocks: [
                {
                    type: 'text',
                    html: `<p><b>${notebookEscape(cassette.name)}</b>, a ${level}cassette from the MoClo Library Tool: `
                        + `${cassette.length} bp, ${parts.length} part${parts.length === 1 ? '' : 's'}.</p>`
                        + `<p><img data-attachment="picture" alt="Diagram of ${notebookEscape(cassette.name)}"></p>`,
                },
                notebookTable('Parts', [['Order', 'number'], ['Part'], ['Type'], ["5' overhang"], ["3' overhang"], ['Length', 'number', 'bp']],
                    parts.map((p, i) => [i + 1, p.name, p.part_type || '', p.overhang_5prime || '', p.overhang_3prime || '',
                        p.sequence ? p.sequence.length : ''])),
            ],
        },
        pictures: [await notebookSvgToPng(`/api/cassettes/${encodeURIComponent(cassette.id)}/export/svg`)],
    };
}

/** A MoClo part as a notebook section: its diagram, what it is, where it is kept, and its features. */
async function mocloPartSection(part) {
    const length = part.sequence ? part.sequence.length : null;
    const level = part.level !== undefined && part.level !== null && part.level !== '' ? `, Level ${notebookEscape(part.level)}` : '';
    const overhangs = part.overhang_5prime || part.overhang_3prime
        ? `, overhangs ${notebookEscape(part.overhang_5prime || '—')} / ${notebookEscape(part.overhang_3prime || '—')}` : '';
    const details = [
        ['Type', part.part_type], ['Level', part.level], ["5' overhang", part.overhang_5prime], ["3' overhang", part.overhang_3prime],
        ['Length', length ? `${length} bp` : ''], ['Plasmid', part.plasmid_id], ['Antibiotic', part.antibiotic],
        ['Host strain', part.host_strain], ['Location (80)', part.location_80], ['Location (96-well plate)', part.location_96_plate],
        ['Donor organism', part.donor_organism], ['Reference', part.reference], ['Unit', part.unit],
        ['Sequenced', part.sequenced === true ? 'yes' : part.sequenced === false ? 'no' : part.sequenced],
        ['Contributor', part.contributor], ['Lab source', part.lab_source], ['Comments', part.comments],
    ].filter(([, value]) => value !== undefined && value !== null && String(value).trim() !== '');
    const features = part.features || [];
    const blocks = [
        {
            type: 'text',
            html: `<p><b>${notebookEscape(part.name)}</b>, a ${notebookEscape(part.part_type || '')} part${level} from the MoClo `
                + `Library Tool${length ? `: ${length} bp` : ''}${overhangs}.`
                + `${part.description ? ` ${notebookEscape(part.description)}` : ''}</p>`
                + `<p><img data-attachment="picture" alt="Diagram of ${notebookEscape(part.name)}"></p>`,
        },
        notebookTable('Details', [['Property'], ['Value']], details),
    ];
    if (features.length) {
        blocks.push(notebookTable('Features', [['Name'], ['Type'], ['Start', 'number'], ['End', 'number'], ['Strand']],
            features.map((f) => [f.label || f.name || '', f.type || '', (f.start ?? 0) + 1, f.end ?? '',
                f.strand === -1 ? 'reverse' : f.strand === 1 ? 'forward' : ''])));
    }
    const picture = `/api/visualize/part/${encodeURIComponent(part.id)}${features.length ? '/features' : ''}`;
    return {
        section: {
            type: 'section', title: `MoClo part: ${part.name}`,
            source: { kind: 'moclo-part', id: String(part.id), name: part.name },
            blocks,
        },
        pictures: [await notebookSvgToPng(picture)],
    };
}

/** The part shown in its detail window, into a day's page. */
function addShownPartToNotebook() {
    const part = window._shownPart;
    if (!part) return;
    addToNotebook(`The diagram of ${part.name} and its details${(part.features || []).length ? ' and features' : ''}.`,
        () => mocloPartSection(part));
}

/** The plasmid shown in its detail window, into a day's page. */
function addShownPlasmidToNotebook() {
    const plasmid = window._shownPlasmid;
    if (!plasmid) return;
    addToNotebook(`The map of ${plasmid.name} (${plasmid.size} bp) and its MoClo assembly strategy.`,
        () => mocloPlasmidSection(plasmid));
}

/** The cassette shown in its detail window, into a day's page. */
function addShownCassetteToNotebook() {
    const cassette = window.currentCassetteDetail || (typeof currentCassetteDetail !== 'undefined' ? currentCassetteDetail : null);
    if (!cassette) return;
    addToNotebook(`The diagram of ${cassette.name} and its ${(cassette.parts || []).length} parts, in order.`,
        () => mocloCassetteSection(cassette));
}
