/**
 * SVG Animation module using anime.js
 * Fetches SVG visualizations and animates them inline
 */

/**
 * Load an SVG from a URL, inject it inline, and animate it
 * @param {string} url - The SVG endpoint URL
 * @param {HTMLElement} container - The container element to inject into
 * @param {object} options - Animation options
 */
async function loadAndAnimateSVG(url, container, options = {}) {
    try {
        const response = await fetch(url, { credentials: 'same-origin' });
        if (!response.ok) return;
        
        const svgText = await response.text();
        container.innerHTML = svgText;
        
        const svg = container.querySelector('svg');
        if (!svg) return;
        
        // Make SVG responsive
        svg.style.width = '100%';
        svg.style.height = 'auto';
        svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
        
        // Animate based on type
        const animType = options.type || 'cassette';
        
        if (animType === 'cassette' || animType === 'features') {
            animateCassetteSVG(svg, options);
        } else if (animType === 'part') {
            animatePartSVG(svg, options);
        }
    } catch (e) {
        // Silently fail - show nothing if animation fails
    }
}

/**
 * Animate a cassette/features SVG - parts slide in sequentially
 */
function animateCassetteSVG(svg, options = {}) {
    const rects = svg.querySelectorAll('rect');
    const texts = svg.querySelectorAll('text');
    const paths = svg.querySelectorAll('path');
    
    // Initial state: hide all elements
    rects.forEach(r => {
        r.style.opacity = '0';
        r.style.transform = 'translateY(20px)';
    });
    texts.forEach(t => { t.style.opacity = '0'; });
    paths.forEach(p => { p.style.opacity = '0'; });
    
    // Animate rects (part blocks) sliding in from below
    anime({
        targets: Array.from(rects),
        opacity: [0, 1],
        translateY: [20, 0],
        duration: 600,
        delay: anime.stagger(120, { start: 100 }),
        easing: 'easeOutQuad'
    });
    
    // Animate text fading in after rects
    anime({
        targets: Array.from(texts),
        opacity: [0, 1],
        duration: 400,
        delay: anime.stagger(80, { start: 500 }),
        easing: 'easeOutQuad'
    });
    
    // Animate chevrons/paths
    anime({
        targets: Array.from(paths),
        opacity: [0, 0.6],
        duration: 300,
        delay: anime.stagger(50, { start: 700 }),
        easing: 'easeOutQuad'
    });
}

/**
 * Animate a single part SVG - scale in with a bounce
 */
function animatePartSVG(svg, options = {}) {
    const rects = svg.querySelectorAll('rect');
    const texts = svg.querySelectorAll('text');
    const paths = svg.querySelectorAll('path');
    
    // Initial state
    rects.forEach(r => {
        r.style.opacity = '0';
        r.style.transform = 'scale(0.8)';
        r.style.transformOrigin = 'center';
    });
    texts.forEach(t => { t.style.opacity = '0'; });
    paths.forEach(p => { p.style.opacity = '0'; });
    
    // Animate rect scaling in
    anime({
        targets: Array.from(rects),
        opacity: [0, 1],
        scale: [0.8, 1],
        duration: 500,
        easing: 'easeOutBack'
    });
    
    // Text fade in
    anime({
        targets: Array.from(texts),
        opacity: [0, 1],
        duration: 400,
        delay: 300,
        easing: 'easeOutQuad'
    });
    
    // Chevrons
    anime({
        targets: Array.from(paths),
        opacity: [0, 0.6],
        duration: 300,
        delay: 400,
        easing: 'easeOutQuad'
    });
}

/**
 * Auto-detect and animate all SVG visualization containers on the page
 * Call this after page content loads
 */
function animateAllSVGs() {
    // Find all visualization images and replace with inline animated SVGs
    document.querySelectorAll('.detail-visualization img, .part-visualization img').forEach(img => {
        const src = img.getAttribute('src');
        if (!src || !src.includes('/api/visualize/')) return;
        
        const container = document.createElement('div');
        container.className = 'svg-animated-container';
        img.parentNode.replaceChild(container, img);
        
        const type = src.includes('/features') ? 'features' : 
                     src.includes('/cassette/') ? 'cassette' : 'part';
        
        loadAndAnimateSVG(src, container, { type });
    });
}

// Export
window.loadAndAnimateSVG = loadAndAnimateSVG;
window.animateCassetteSVG = animateCassetteSVG;
window.animatePartSVG = animatePartSVG;
window.animateAllSVGs = animateAllSVGs;
