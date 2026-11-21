/**
 * Pipettable volumes for the Golden Gate reaction calculators.
 *
 * A reaction mix is only useful if every volume in it can be measured. Below
 * the smallest volume a P2 pipette measures reliably (0.2 µL) the numbers
 * round to 0.00, and a mix with a "0.00 µL" line looks valid while it cannot
 * be set up. So instead of a table, the calculators show an error saying what
 * to change:
 *
 *   - a reagent that scales with the reaction (buffer, ATP, enzyme, ligase)
 *     or water that is too little: make the reaction larger, to at least the
 *     volume worked out here;
 *   - a DNA volume that is too small: the amount of DNA (fmol) does not change
 *     with the reaction volume, so the stock has to be diluted, to at most the
 *     concentration worked out here.
 */
(function (global) {
    'use strict';

    // Smallest volume pipetted reliably (µL): the bottom of a P2's range.
    const MIN_PIPETTE_UL = 0.2;
    // The reaction volume input steps by 5 µL.
    const VOLUME_STEP_UL = 5;
    // Allow for floating point: 0.2 µL of ATP in 20 µL is exactly the minimum.
    const EPS = 1e-9;

    function tooSmall(v) {
        return v > EPS && v < MIN_PIPETTE_UL - EPS;
    }

    function roundUpToStep(v) {
        return Math.ceil((v - EPS) / VOLUME_STEP_UL) * VOLUME_STEP_UL;
    }

    // A concentration rounded down to two significant figures, so diluting to
    // it always gives at least the minimum volume.
    function floorTwoSig(v) {
        if (!(v > 0)) return 0;
        const p = Math.pow(10, Math.floor(Math.log10(v)) - 1);
        return Math.floor(v / p + EPS) * p;
    }

    function fmt(v) {
        return String(Number(v.toPrecision(3)));
    }

    /**
     * Check a reaction mix.
     *
     *   totalVolume  reaction volume (µL)
     *   reagents     [{name, volume}]: volumes that scale with totalVolume
     *   dna          [{name, volume, ng, conc}]: volume to add, mass, stock ng/µL
     *   fixedTotal   sum of the scaling reagents (µL), to work out water
     *   dnaTotal     sum of the DNA volumes (µL)
     *
     * Returns {ok, problems: [text], minTotal}. minTotal is the smallest
     * reaction volume (rounded up to the input's step) at which every reagent
     * and the water are pipettable, or null when the volume is not the issue.
     */
    function checkReaction({ totalVolume, reagents, dna, fixedTotal, dnaTotal }) {
        const problems = [];
        let minTotal = null;

        const needVolume = (v) => { minTotal = Math.max(minTotal || 0, v); };

        // Scaling reagents: each is volume/totalVolume of the reaction.
        reagents.forEach(r => {
            if (tooSmall(r.volume) || (r.volume <= EPS && totalVolume > 0)) {
                const need = MIN_PIPETTE_UL * totalVolume / Math.max(r.volume, EPS);
                needVolume(need);
                problems.push(`${r.name}: ${fmt(r.volume)} µL is below the ${MIN_PIPETTE_UL} µL that can be pipetted.`);
            }
        });

        // DNA: a fixed amount, so only diluting the stock makes the volume larger.
        dna.forEach(d => {
            if (tooSmall(d.volume) || d.volume <= EPS) {
                const maxConc = floorTwoSig(d.ng / MIN_PIPETTE_UL);
                problems.push(
                    `${d.name}: ${fmt(d.volume)} µL is below the ${MIN_PIPETTE_UL} µL that can be pipetted. ` +
                    `Dilute the stock from ${fmt(d.conc)} to ${fmt(maxConc)} ng/µL or less ` +
                    `(${fmt(d.ng)} ng is needed; the reaction volume does not change that).`
                );
            }
        });

        // Water: whatever is left over. A sliver of water cannot be pipetted
        // either; a larger reaction leaves more of it.
        const water = totalVolume - fixedTotal - dnaTotal;
        if (tooSmall(water)) {
            // Water grows by (1 - fixedTotal/totalVolume) per µL of reaction.
            const perUl = 1 - fixedTotal / totalVolume;
            if (perUl > EPS) needVolume((MIN_PIPETTE_UL + dnaTotal) / perUl);
            problems.push(`MQ Water: ${fmt(water)} µL is below the ${MIN_PIPETTE_UL} µL that can be pipetted.`);
        }

        if (minTotal !== null) {
            minTotal = Math.max(roundUpToStep(minTotal), roundUpToStep(totalVolume + EPS));
        }
        return { ok: problems.length === 0, problems, minTotal, water };
    }

    /** The error box both calculators show, as HTML. */
    function errorHtml(result, { totalVolume, canChangeVolume }) {
        const esc = (s) => String(s).replace(/[&<>"']/g, c => (
            { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
        let html = '<div class="pipette-error" role="alert">' +
            '<strong>Can’t make this mix: some volumes are too small to pipette.</strong>';
        if (result.minTotal !== null) {
            html += canChangeVolume
                ? `<p>Increase the reaction volume from ${fmt(totalVolume)} µL to at least ` +
                  `<strong>${result.minTotal} µL</strong>, so every volume is at least ${MIN_PIPETTE_UL} µL, and calculate again.</p>`
                : `<p>A reaction of at least <strong>${result.minTotal} µL</strong> is needed ` +
                  `so every volume is at least ${MIN_PIPETTE_UL} µL; work it out on the Protocol page's calculator.</p>`;
        }
        html += '<ul>' + result.problems.map(p => `<li>${esc(p)}</li>`).join('') + '</ul></div>';
        return html;
    }

    const api = { MIN_PIPETTE_UL, checkReaction, errorHtml, floorTwoSig };
    global.ReactionVolumes = api;
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
