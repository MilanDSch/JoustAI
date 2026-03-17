document.getElementById('defend-form').addEventListener('submit', function() {
    document.getElementById('submit-btn').disabled = true;
    document.getElementById('submit-btn').innerHTML = '&#9878; Sealing Vault...';
    document.getElementById('loading').style.display = 'block';
});

function toggleArtifactFields() {
    var selected = document.querySelector('input[name="defender_power_up"]:checked');
    if (!selected) return;
    var val = selected.value;
    var rune = document.getElementById('artifact-rune');
    var decree = document.getElementById('artifact-decree');
    var decoy = document.getElementById('artifact-decoy');
    if (rune) rune.style.display = val === 'rune_of_silence' ? 'block' : 'none';
    if (decree) decree.style.display = val === 'mad_kings_decree' ? 'block' : 'none';
    if (decoy) decoy.style.display = val === 'decoy_cipher' ? 'block' : 'none';
}
