(() => {
  const form = document.getElementById("playbook-editor");
  if (!form || document.body.dataset.demo === "true") return;

  const inputs = [...form.querySelectorAll('input:not([type="hidden"]), textarea')];
  const messages = new Map([...form.querySelectorAll("[data-field-error]")].map(node => [node.dataset.fieldError, node]));
  const status = form.querySelector("[data-save-status]");
  const save = form.querySelector('[type="submit"]');
  const dialog = document.getElementById("playbook-discard");
  const name = form.elements.namedItem("name");
  const snapshot = () => JSON.stringify(inputs.map(field => field.value));
  const initial = snapshot();
  let dirtyDraft = form.dataset.draft === "true";
  let saving = false;
  let leaving = false;
  let destination;

  function dirty() {
    return dirtyDraft || snapshot() !== initial;
  }

  function showStatus(message, failed = false) {
    status.textContent = message;
    status.classList.toggle("negative", failed);
  }

  function showFieldError(field, message) {
    const note = messages.get(field.name);
    note.textContent = message;
    note.hidden = !message;
    if (message) field.setAttribute("aria-invalid", "true");
    else field.removeAttribute("aria-invalid");
  }

  form.addEventListener("input", event => {
    if (!inputs.includes(event.target)) return;
    showFieldError(event.target, "");
    showStatus(dirty() ? "Unsaved changes" : "No unsaved changes");
  });
  form.addEventListener("invalid", event => {
    if (!inputs.includes(event.target)) return;
    const message = event.target === name && !name.value.trim() ? "Enter a setup name." : event.target.validationMessage;
    showFieldError(event.target, message);
  }, true);

  document.addEventListener("click", event => {
    const link = event.target.closest("a[href]");
    if (!link || event.defaultPrevented || (link.target && link.target !== "_self") ||
        event.button !== 0 || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
    if (!dirty() && !saving) return;
    event.preventDefault();
    if (saving || dialog.open) return;
    destination = link.href;
    dialog.returnValue = "cancel";
    dialog.showModal();
  });
  dialog.addEventListener("close", () => {
    if (dialog.returnValue !== "discard") return;
    leaving = true;
    location.assign(destination);
  });
  window.addEventListener("beforeunload", event => {
    if (!leaving && (dirty() || saving)) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
  window.addEventListener("pageshow", () => { leaving = false; });

  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (saving) return;
    if (!name.value.trim()) {
      showFieldError(name, "Enter a setup name.");
      name.focus();
      return;
    }
    const data = new FormData(form);
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 20000);
    saving = true;
    save.disabled = true;
    inputs.forEach(field => { field.readOnly = true; });
    showStatus("Saving…");
    let firstInvalid;
    try {
      const response = await fetch(form.action, {
        method: "POST", body: data, headers: {Accept: "application/json"}, signal: controller.signal
      });
      const result = response.headers.get("content-type")?.includes("application/json") ? await response.json() : null;
      if (response.ok && result?.saved === true && result.url) {
        leaving = true;
        showStatus("Saved");
        location.assign(result.url);
        return;
      }
      dirtyDraft = true;
      for (const field of inputs) {
        const message = result?.fields?.[field.name] || "";
        showFieldError(field, message);
        if (message && !firstInvalid) firstInvalid = field;
      }
      const fallback = response.redirected ? "Your session has ended. Sign in again before retrying. Your edits are still here."
        : "Save could not be confirmed. Your edits are still here.";
      showStatus(result?.error || fallback, true);
    } catch {
      dirtyDraft = true;
      showStatus("Save could not be confirmed. Your edits are still here.", true);
    } finally {
      window.clearTimeout(timeout);
      saving = false;
      if (!leaving) {
        save.disabled = false;
        inputs.forEach(field => { field.readOnly = false; });
        firstInvalid?.focus();
      }
    }
  });
})();
