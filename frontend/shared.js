/**
 * Shared utilities — loaded on every page
 * Handles nav active state + white-label branding
 */

const API_BASE_URL = window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : `${window.location.protocol}//${window.location.hostname}:8000`;

// Highlight active nav link based on current filename
function initNav() {
    const currentPage = window.location.pathname.split('/').pop() || 'index.html';
    const navLinks = document.querySelectorAll('[data-nav-page]');
    navLinks.forEach(link => {
        const page = link.getAttribute('data-nav-page');
        if (page === currentPage) {
            link.classList.add('text-[#0d7377]', 'border-b-2', 'border-[#0d7377]', 'pb-1', 'font-semibold');
            link.classList.remove('text-[#506072]');
        } else {
            link.classList.add('text-[#506072]');
            link.classList.remove('text-[#0d7377]', 'border-b-2', 'border-[#0d7377]', 'pb-1', 'font-semibold');
        }
    });
}

// Fetch and apply branding
async function applyBranding() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/branding`);
        if (!response.ok) return;
        const branding = await response.json();

        // Update all elements with data-brand-title
        document.querySelectorAll('[data-brand-title]').forEach(el => {
            el.textContent = branding.title;
        });

        // For basaksehir mode, add stripe
        if (branding.show_stripe) {
            const nav = document.querySelector('nav');
            if (nav) nav.style.borderTop = `4px solid ${branding.stripe_color}`;
        }
    } catch (err) {
        console.log('Branding fetch failed, using defaults');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initNav();
    applyBranding();
});
