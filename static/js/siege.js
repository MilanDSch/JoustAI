// Smooth-scroll chat history to bottom so newest messages are always visible
var chat = document.getElementById('chat-history');
if (chat) {
    chat.scrollTo({ top: chat.scrollHeight, behavior: 'smooth' });
}

// Focus textarea on page load for quick play
var promptArea = document.getElementById('attacker_prompt');
if (promptArea) promptArea.focus();

// Persist <details> open/closed state across page reloads
(function() {
    var KEY = 'siege_details_state';
    var details = document.querySelectorAll('.arsenal-panel details');

    // Restore state on load
    try {
        var saved = JSON.parse(sessionStorage.getItem(KEY));
        if (saved) {
            details.forEach(function(el, i) {
                if (saved[i]) el.setAttribute('open', '');
                else el.removeAttribute('open');
            });
        }
    } catch(e) {}

    // Save state before any form submission or unload
    function saveState() {
        var state = [];
        details.forEach(function(el) { state.push(el.hasAttribute('open')); });
        sessionStorage.setItem(KEY, JSON.stringify(state));
    }

    document.querySelectorAll('form').forEach(function(f) {
        f.addEventListener('submit', saveState);
    });
    window.addEventListener('beforeunload', saveState);
})();

var form = document.getElementById('attack-form');
if (form) {
    form.addEventListener('submit', function() {
        var btn = document.getElementById('submit-btn');
        btn.disabled = true;
        btn.innerHTML = '&#9889; Casting...';

        var surBtn = document.getElementById('surrender-btn');
        if(surBtn) surBtn.disabled = true;

        var loadEl = document.getElementById('loading');
        loadEl.style.display = 'block';
        loadEl.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>' +
            '<span class="siege-loading-text">The Oracle is interpreting your words...</span>';
    });
}
