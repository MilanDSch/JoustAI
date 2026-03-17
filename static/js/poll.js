/**
 * Arena polling script.
 *
 * Include with data attributes on the <script> tag:
 *   data-status-url   – the JSON status endpoint (e.g. /arena/DRAGON/status)
 *   data-redirect-on  – comma-separated phase:url pairs
 *                        e.g. "siege:/arena/DRAGON/siege,intermission:/arena/DRAGON/intermission"
 *   data-reload-on-change – "true" to reload the page on any phase_version change
 *                           (useful for the spectator view)
 *   data-redirect-on-joined – URL to redirect to when attacker_joined becomes true
 */
(function () {
    var script = document.currentScript;
    if (!script) return;

    var statusUrl = script.dataset.statusUrl;
    if (!statusUrl) return;

    // Parse redirect mappings: phase -> url
    var redirectMap = {};
    (script.dataset.redirectOn || '').split(',').forEach(function (pair) {
        var parts = pair.split(':');
        if (parts.length >= 2) {
            var phase = parts[0].trim();
            var url = parts.slice(1).join(':').trim();
            if (phase && url) redirectMap[phase] = url;
        }
    });

    var reloadOnChange = script.dataset.reloadOnChange === 'true';
    var redirectOnJoined = script.dataset.redirectOnJoined || '';
    var lastVersion = -1;
    var navigating = false;

    function poll() {
        if (navigating) return;
        fetch(statusUrl)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (navigating) return;

                // Redirect when attacker joins (for lobby page)
                if (redirectOnJoined && data.attacker_joined) {
                    navigating = true;
                    window.location.href = redirectOnJoined;
                    return;
                }

                if (data.phase_version !== lastVersion && lastVersion !== -1) {
                    // Phase-based redirect
                    var target = redirectMap[data.phase];
                    if (target) {
                        navigating = true;
                        window.location.href = target;
                        return;
                    }
                    // Reload on any change (spectator mode)
                    if (reloadOnChange) {
                        navigating = true;
                        window.location.reload();
                        return;
                    }
                }
                lastVersion = data.phase_version;
            })
            .catch(function () { /* silently retry next interval */ });
    }

    poll();
    setInterval(poll, 2500);
})();
