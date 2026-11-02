(function () {
  const add = document.querySelector("[data-add-leg]");
  if (add) {
    add.addEventListener("click", function () {
      const board = document.querySelector("#legs");
      const last = board.querySelector(".leg");
      if (!last) return;
      const copy = last.cloneNode(true);
      copy.querySelectorAll("input").forEach(function (input) { input.value = ""; });
      const kind = copy.querySelector("select");
      if (kind) kind.value = "exit";
      board.appendChild(copy);
    });
  }

  const preview = document.querySelector("#grade-preview");
  function grade() {
    if (!preview) return;
    const boxes = document.querySelectorAll(".check-item");
    if (!boxes.length) {
      preview.textContent = "Add checklist items in Settings to grade plan adherence.";
      return;
    }
    const checked = document.querySelectorAll(".check-item:checked").length;
    const ratio = checked / boxes.length;
    let letter = "C";
    if (ratio >= 1) letter = "A+";
    else if (ratio >= 0.8) letter = "A";
    else if (ratio >= 0.6) letter = "B";
    preview.textContent = "Checklist grade if you save now: " + letter + " (" + checked + "/" + boxes.length + "). A manual grade overrides this.";
  }
  document.querySelectorAll(".check-item").forEach(function (box) {
    box.addEventListener("change", grade);
  });
  grade();

  const action = document.querySelector("[data-shot-action]");
  let slot = "entry";

  function upload(slotName, file) {
    if (!action) return;
    const token = document.querySelector("meta[name=csrf]");
    const body = new FormData();
    body.append("csrf", token ? token.content : "");
    body.append("slot", slotName);
    body.append("image", file, file.name || "chart.png");
    fetch(action.dataset.shotAction, { method: "POST", body: body }).then(function (response) {
      if (response.ok) window.location.reload();
      else response.text().then(function (text) { window.alert(text || "The image was not saved."); });
    });
  }

  document.querySelectorAll("[data-slot]").forEach(function (node) {
    node.addEventListener("mouseenter", function () { slot = node.dataset.slot; });
    node.addEventListener("dragover", function (event) { event.preventDefault(); });
    node.addEventListener("drop", function (event) {
      event.preventDefault();
      const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
      if (file) upload(node.dataset.slot, file);
    });
  });

  document.addEventListener("paste", function (event) {
    if (!action) return;
    const items = event.clipboardData && event.clipboardData.items;
    if (!items) return;
    for (let index = 0; index < items.length; index += 1) {
      if (items[index].type.indexOf("image/") === 0) {
        const file = items[index].getAsFile();
        if (file) {
          event.preventDefault();
          upload(slot, file);
        }
        break;
      }
    }
  });

  document.querySelectorAll("[data-capture]").forEach(function (button) {
    button.addEventListener("click", function () {
      const form = button.closest("form");
      const note = form ? form.querySelector(".capture-error") : null;
      if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
        if (note) note.textContent = "This browser cannot capture the screen here.";
        return;
      }
      navigator.mediaDevices.getDisplayMedia({ video: true, audio: false }).then(function (stream) {
        const video = document.createElement("video");
        video.srcObject = stream;
        return video.play().then(function () {
          const canvas = document.createElement("canvas");
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          canvas.getContext("2d").drawImage(video, 0, 0);
          stream.getTracks().forEach(function (track) { track.stop(); });
          return new Promise(function (resolve) { canvas.toBlob(resolve, "image/png"); });
        });
      }).then(function (blob) {
        if (blob) upload(button.dataset.capture, new File([blob], "capture.png", { type: "image/png" }));
      }).catch(function () {
        if (note) note.textContent = "Screen capture was cancelled or blocked.";
      });
    });
  });

  document.querySelectorAll("[data-print]").forEach(function (button) {
    button.addEventListener("click", function () { window.print(); });
  });
})();
