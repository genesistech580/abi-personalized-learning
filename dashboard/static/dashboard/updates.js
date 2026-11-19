(() => {
    const script = document.currentScript;
    const version = script.dataset.version;
    let dirty = false;
    let checking = false;
    let pending = false;
    document.addEventListener("input", () => { dirty = true; });
    document.addEventListener("change", () => { dirty = true; });
    async function check() {
        if (document.hidden || checking || pending) return;
        checking = true;
        try {
            const response = await fetch(script.dataset.url, {cache: "no-store", credentials: "same-origin"});
            if (!response.ok) return;
            const data = await response.json();
            if (!data.version || data.version === version) return;
            pending = true;
            if (!dirty) { window.location.reload(); return; }
            const notice = document.createElement("p");
            notice.className = "notice";
            notice.setAttribute("role", "status");
            notice.append("An update is ready. Save your work, then ");
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = "Refresh";
            button.addEventListener("click", () => {
                if (window.confirm("Refresh now? Unsaved changes will be lost.")) window.location.reload();
            });
            notice.append(button);
            document.querySelector("main").prepend(notice);
        } catch (_) {
            // Retry after temporary connection failures.
        } finally { checking = false; }
    }
    window.setInterval(check, 10000);
    document.addEventListener("visibilitychange", check);
    window.addEventListener("pageshow", check);
})();
