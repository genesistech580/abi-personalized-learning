document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll('input[type="password"]').forEach((input) => {
        const wrapper = document.createElement("div");
        wrapper.className = "password-control";
        input.before(wrapper);
        wrapper.append(input);

        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "password-toggle";
        toggle.textContent = "Show";
        toggle.setAttribute("aria-label", "Show password");
        toggle.setAttribute("aria-pressed", "false");
        if (input.id) toggle.setAttribute("aria-controls", input.id);
        toggle.addEventListener("click", () => {
            const show = input.type === "password";
            input.type = show ? "text" : "password";
            toggle.textContent = show ? "Hide" : "Show";
            toggle.setAttribute("aria-label", show ? "Hide password" : "Show password");
            toggle.setAttribute("aria-pressed", String(show));
        });
        wrapper.append(toggle);
    });
});
