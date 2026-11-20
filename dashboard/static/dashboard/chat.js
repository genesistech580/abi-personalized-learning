(() => {
    const form = document.getElementById("chat-form");
    if (!form || !window.fetch) return;
    const button = form.querySelector('button[type="submit"]');
    const field = form.querySelector('textarea[name="message"]');
    const status = document.getElementById("chat-status");
    const error = document.getElementById("chat-error");
    const transcript = document.getElementById("chat-messages");
    let sending = false;
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (sending || !form.reportValidity()) return;
        sending = true;
        button.disabled = true;
        field.readOnly = true;
        error.hidden = true;
        status.textContent = "Thinking…";
        try {
            const response = await fetch(form.action, {method: "POST", body: new FormData(form), credentials: "same-origin", headers: {Accept: "application/json"}});
            if (response.redirected || (response.headers.get("Content-Type") || "").indexOf("application/json") < 0) {
                throw new Error("Your session may have expired. Open the dashboard and sign in again; your question is kept here.");
            }
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "The message could not be sent. Please try again.");
            if (!Array.isArray(data.history)) throw new Error("The reply could not be displayed. Please try again.");
            transcript.replaceChildren();
            for (const message of data.history) {
                const entry = document.createElement("div");
                entry.className = "chat-message " + (message.role === "user" ? "chat-user" : "chat-assistant");
                const label = document.createElement("strong");
                label.textContent = message.role === "user" ? "You" : "Assistant";
                const content = document.createElement("p");
                content.textContent = message.content;
                entry.append(label, content);
                transcript.append(entry);
            }
            field.value = "";
            document.dispatchEvent(new CustomEvent("abi:form-saved", {detail: {form}}));
            transcript.lastElementChild?.scrollIntoView({behavior: "smooth", block: "nearest"});
        } catch (failure) {
            error.textContent = failure instanceof TypeError ? "Connection interrupted. Your question is kept; try again." : failure.message;
            error.hidden = false;
        } finally {
            sending = false;
            button.disabled = false;
            field.readOnly = false;
            status.textContent = "";
            field.focus({preventScroll: true});
        }
    });
})();
