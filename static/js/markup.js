(function () {
  document.querySelectorAll(".mark").forEach(function (root) {
    const canvas = root.querySelector("canvas");
    const image = root.querySelector("img");
    if (!canvas || !image) return;
    const ctx = canvas.getContext("2d");
    let shapes = [];
    try { shapes = JSON.parse(canvas.dataset.shapes || "[]"); } catch (error) { shapes = []; }
    let tool = "arrow";
    let color = root.querySelector('[data-color]').dataset.color;
    let draft = null;
    let start = null;

    function resize() {
      const width = image.clientWidth;
      const height = image.clientHeight;
      if (!width || !height) return;
      canvas.width = width;
      canvas.height = height;
      draw();
    }

    function point(event) {
      const rect = canvas.getBoundingClientRect();
      return {
        x: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)),
        y: Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height)),
      };
    }

    function stroke(shape) {
      const x1 = shape.x1 * canvas.width;
      const y1 = shape.y1 * canvas.height;
      const x2 = shape.x2 * canvas.width;
      const y2 = shape.y2 * canvas.height;
      ctx.strokeStyle = shape.color;
      ctx.fillStyle = shape.color;
      ctx.lineWidth = 2;
      if (shape.type === "box") {
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
        return;
      }
      if (shape.type === "text") {
        ctx.font = "14px Segoe UI, sans-serif";
        ctx.fillText(shape.text || "", x1, y1);
        return;
      }
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
      if (shape.type === "arrow") {
        const angle = Math.atan2(y2 - y1, x2 - x1);
        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x2 - 12 * Math.cos(angle - 0.45), y2 - 12 * Math.sin(angle - 0.45));
        ctx.lineTo(x2 - 12 * Math.cos(angle + 0.45), y2 - 12 * Math.sin(angle + 0.45));
        ctx.closePath();
        ctx.fill();
      }
    }

    function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      shapes.forEach(stroke);
      if (draft) stroke(draft);
    }

    root.querySelectorAll("[data-tool]").forEach(function (button) {
      button.addEventListener("click", function () {
        tool = button.dataset.tool;
        root.querySelectorAll("[data-tool]").forEach(function (other) { other.classList.remove("on"); });
        button.classList.add("on");
      });
    });
    root.querySelectorAll("[data-color]").forEach(function (button) {
      button.addEventListener("click", function () {
        color = button.dataset.color;
        root.querySelectorAll(".swatch").forEach(function (other) { other.classList.remove("on"); });
        button.classList.add("on");
      });
    });

    canvas.addEventListener("pointerdown", function (event) {
      const at = point(event);
      if (tool === "text") {
        const text = window.prompt("Label");
        if (text) shapes.push({ type: "text", color: color, text: text, x1: at.x, y1: at.y, x2: at.x, y2: at.y });
        draw();
        return;
      }
      start = at;
      draft = { type: tool, color: color, text: "", x1: at.x, y1: at.y, x2: at.x, y2: at.y };
    });
    canvas.addEventListener("pointermove", function (event) {
      if (!draft) return;
      const at = point(event);
      draft.x2 = at.x;
      draft.y2 = at.y;
      draw();
    });
    function finish() {
      if (!draft) return;
      shapes.push(draft);
      draft = null;
      start = null;
      draw();
    }
    canvas.addEventListener("pointerup", finish);
    canvas.addEventListener("pointerleave", function () { if (draft) finish(); });

    const undo = root.querySelector("[data-undo]");
    if (undo) undo.addEventListener("click", function () { shapes.pop(); draw(); });
    const clear = root.querySelector("[data-clear]");
    if (clear) clear.addEventListener("click", function () { shapes = []; draw(); });
    const save = root.querySelector("[data-save-markup]");
    if (save) {
      save.addEventListener("click", function () {
        const status = root.querySelector(".markup-status");
        fetch(root.dataset.save, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF": root.dataset.csrf },
          body: JSON.stringify({ shapes: shapes }),
        }).then(function (response) {
          if (status) status.textContent = response.ok ? "Markup saved." : "Markup was not saved.";
        });
      });
    }
    if (image.complete) resize();
    image.addEventListener("load", resize);
    window.addEventListener("resize", resize);
  });
})();
