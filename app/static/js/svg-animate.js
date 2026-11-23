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
        
        // Without anime.js (the CDN unreachable) the diagram is shown as drawn
        if (typeof anime === 'undefined') return;

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
 * Hide elements before they are animated in, and give back the opacity each is meant to end at.
 *
 * anime.js animates an SVG element's opacity ATTRIBUTE when it has one (the feature blocks are
 * drawn with opacity="0.9"), so a style.opacity of 0 set here would never be lifted and the blocks
 * stayed invisible behind their white labels. The attribute's value moves into the style instead.
 */
function hideForAnimation(elements, fallback = 1) {
    elements.forEach(el => {
        const attr = el.getAttribute('opacity');
        el.dataset.endOpacity = attr !== null ? attr : String(fallback);
        el.removeAttribute('opacity');
        el.style.opacity = '0';
    });
    return el => [0, parseFloat(el.dataset.endOpacity)];
}

/**
 * Animate a cassette/features SVG - parts slide in sequentially
 */
function animateCassetteSVG(svg, options = {}) {
    const rects = svg.querySelectorAll('rect');
    const texts = svg.querySelectorAll('text');
    const paths = svg.querySelectorAll('path');
    
    // Initial state: hide all elements
    const rectOpacity = hideForAnimation(rects);
    const textOpacity = hideForAnimation(texts);
    const pathOpacity = hideForAnimation(paths, 0.6);
    rects.forEach(r => { r.style.transform = 'translateY(20px)'; });
    
    // Animate rects (part blocks) sliding in from below
    anime({
        targets: Array.from(rects),
        opacity: rectOpacity,
        translateY: [20, 0],
        duration: 600,
        delay: anime.stagger(120, { start: 100 }),
        easing: 'easeOutQuad'
    });
    
    // Animate text fading in after rects
    anime({
        targets: Array.from(texts),
        opacity: textOpacity,
        duration: 400,
        delay: anime.stagger(80, { start: 500 }),
        easing: 'easeOutQuad'
    });
    
    // Animate chevrons/paths
    anime({
        targets: Array.from(paths),
        opacity: pathOpacity,
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
    const rectOpacity = hideForAnimation(rects);
    const textOpacity = hideForAnimation(texts);
    const pathOpacity = hideForAnimation(paths, 0.6);
    rects.forEach(r => {
        r.style.transform = 'scale(0.8)';
        r.style.transformOrigin = 'center';
    });
    
    // Animate rect scaling in
    anime({
        targets: Array.from(rects),
        opacity: rectOpacity,
        scale: [0.8, 1],
        duration: 500,
        easing: 'easeOutBack'
    });
    
    // Text fade in
    anime({
        targets: Array.from(texts),
        opacity: textOpacity,
        duration: 400,
        delay: 300,
        easing: 'easeOutQuad'
    });
    
    // Chevrons
    anime({
        targets: Array.from(paths),
        opacity: pathOpacity,
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
