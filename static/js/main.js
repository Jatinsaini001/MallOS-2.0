// Auto-dismiss flash messages after 4 seconds
document.addEventListener('DOMContentLoaded', () => {
    const flashes = document.querySelectorAll('.flash');
    flashes.forEach(f => {
        setTimeout(() => {
            f.style.opacity = '0';
            f.style.transition = 'opacity .4s ease';
            setTimeout(() => f.remove(), 400);
        }, 4000);
    });

    // Animate stat values counting up
    document.querySelectorAll('.stat-value').forEach(el => {
        const text = el.textContent.trim();
        // Only animate plain numbers
        if (/^\d+$/.test(text)) {
            const target = parseInt(text);
            let current = 0;
            const step = Math.ceil(target / 30);
            const timer = setInterval(() => {
                current = Math.min(current + step, target);
                el.textContent = current;
                if (current >= target) clearInterval(timer);
            }, 30);
        }
    });

    // Animate breakdown bars on load
    document.querySelectorAll('.breakdown-bar').forEach(bar => {
        const w = bar.style.width;
        bar.style.width = '0';
        setTimeout(() => { bar.style.width = w; }, 200);
    });
});
