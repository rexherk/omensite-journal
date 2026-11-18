(function () {
  var form = document.getElementById("day-plan");
  if (!form) return;
  if (document.body.dataset.demo === "true") {
    var demoDates = document.querySelector("[data-plan-date]");
    demoDates.elements.day.addEventListener("change", function () { if (demoDates.checkValidity()) demoDates.requestSubmit(); });
    form.querySelector("[data-copy-plan]").hidden = false;
    return;
  }
  var fields = ["bias", "key_levels", "draw", "news_to_watch", "eod_review", "plan_followed", "tomorrow_change"];
  var prepFields = fields.slice(0, 4);
  var status = form.querySelector("[data-plan-status]");
  var saveButton = form.querySelector("[data-save-plan]");
  var dateForm = document.querySelector("[data-plan-date]");
  var dateInput = dateForm.elements.day;
  var failedDraft = form.dataset.saveError === "true";
  var saving = false;
  var navigating = false;
  function snapshot() { return JSON.stringify(fields.map(function (key) { return form.elements[key].value; })); }
  var saved = snapshot();
  function dirty() { return failedDraft || snapshot() !== saved; }
  function show(message, error) {
    status.textContent = message;
    status.classList.toggle("negative", Boolean(error));
  }
  form.addEventListener("input", function () { show(dirty() ? "Unsaved changes" : "No unsaved changes"); });
  form.addEventListener("change", function () { show(dirty() ? "Unsaved changes" : "No unsaved changes"); });
  var dialog = document.getElementById("plan-confirm");
  function confirmChange(title, message, action) {
    dialog.querySelector("h2").textContent = title;
    dialog.querySelector("p").textContent = message;
    dialog.querySelector("[data-confirm-action]").textContent = action;
    dialog.returnValue = "cancel";
    return new Promise(function (resolve) {
      dialog.addEventListener("close", function () { resolve(dialog.returnValue === "confirm"); }, {once:true});
      dialog.showModal();
    });
  }
  async function mayLeave() {
    if (saving) { show("Saving… Please wait before changing pages."); return false; }
    return !dirty() || await confirmChange("Leave without saving?", "You have unsaved changes for " + form.elements.day.value + ". Save your plan first, or discard these changes to continue.", "Discard changes");
  }
  dateInput.addEventListener("change", function () { if (dateForm.checkValidity()) dateForm.requestSubmit(); });
  dateForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    var destination = dateInput.value;
    if (!await mayLeave()) dateInput.value = form.elements.day.value;
    else { navigating = true; location.assign(dateForm.action + "?day=" + encodeURIComponent(destination)); }
  });
  document.addEventListener("click", async function (event) {
    var link = event.target.closest("a[href]");
    if (!link || link.target === "_blank" || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
    var url = new URL(link.href, location.href);
    if (url.pathname === location.pathname && url.search === location.search && url.hash) return;
    if (!dirty() && !saving) { navigating = true; return; }
    event.preventDefault();
    if (await mayLeave()) { navigating = true; location.assign(link.href); }
  });
  window.addEventListener("beforeunload", function (event) {
    if (!navigating && (dirty() || saving)) { event.preventDefault(); event.returnValue = ""; }
  });
  window.addEventListener("pageshow", function () { navigating = false; });
  var previous = JSON.parse(document.getElementById("previous-plan-data").textContent);
  var copyButton = form.querySelector("[data-copy-plan]");
  copyButton.hidden = false;
  copyButton.addEventListener("click", async function () {
    if (!previous || saving) return;
    var hasPrep = prepFields.some(function (key) { return form.elements[key].value.trim(); });
    if (hasPrep && !await confirmChange("Replace this day’s prep?", "Copy prep from " + previous.day + " over the bias, levels, liquidity target, and news entered here? Your review and trades will stay unchanged.", "Replace prep")) return;
    prepFields.forEach(function (key) { form.elements[key].value = previous[key] || ""; });
    var copied = form.querySelector("[data-copy-status]");
    copied.hidden = false;
    copied.textContent = "Prep copied from " + previous.day + ". Review it, then save. Your review is unchanged.";
    show(dirty() ? "Unsaved changes" : "No unsaved changes");
  });
  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    if (saving) return;
    var submitted = snapshot();
    var payload = new FormData(form);
    var controller = new AbortController();
    var timer = window.setTimeout(function () { controller.abort(); }, 20000);
    saving = true;
    saveButton.disabled = true;
    saveButton.textContent = "Saving…";
    show("Saving…");
    try {
      var response = await fetch(form.action, {method: "POST", body: payload, headers: {Accept: "application/json"}, signal: controller.signal});
      var result = response.headers.get("content-type")?.includes("application/json") ? await response.json() : null;
      if (!response.ok || !result || result.saved !== true || result.day !== form.elements.day.value) {
        throw new Error(result?.error || (response.status === 403 ? "Your session could not be verified. Keep this page open and sign in again in another tab before retrying." : "Save was not confirmed. Your edits are still here. Please try again."));
      }
      saved = submitted;
      failedDraft = false;
      if (!dirty()) form.querySelector("[data-copy-status]").hidden = true;
      show(dirty() ? "Earlier edits saved · Unsaved changes" : "Saved");
    } catch (error) {
      failedDraft = true;
      show(error.name === "AbortError" ? "Save was not confirmed. Your edits are still here. Please retry." : error instanceof TypeError ? "Could not reach the server. Your edits are still here. Please try again." : (error.message || "Could not save. Your edits are still here."), true);
    } finally {
      window.clearTimeout(timer);
      saving = false;
      saveButton.disabled = false;
      saveButton.textContent = "Save plan";
    }
  });
})();
