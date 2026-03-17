// Auto-scroll chat history to bottom so newest messages are always visible
var chat = document.getElementById('chat-history');
if (chat) chat.scrollTop = chat.scrollHeight;

// Focus textarea on page load for quick play
var promptArea = document.getElementById('attacker_prompt');
if (promptArea) promptArea.focus();

var form = document.getElementById('attack-form');
if (form) {
    form.addEventListener('submit', function() {
        var btn = document.getElementById('submit-btn');
        btn.disabled = true;
        btn.innerHTML = '&#9889; Casting...';

        var surBtn = document.getElementById('surrender-btn');
        if(surBtn) surBtn.disabled = true;

        document.getElementById('loading').style.display = 'block';
    });
}
