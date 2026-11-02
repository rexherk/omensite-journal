(function () {
  document.documentElement.classList.add("js");
  if (document.body.dataset.demo === "true") {
    document.querySelectorAll('form[method="post"]').forEach(function (form) {
      if (new URL(form.action, location.href).pathname === "/logout") return;
      form.setAttribute("data-demo-readonly", "true");
      form.addEventListener("submit", function (event) { event.preventDefault(); });
      form.querySelectorAll("input, select, textarea, button").forEach(function (field) {
        field.disabled = true;
        field.title = "Create an account to save your own records.";
      });
    });
  }

  var stack = document.getElementById("toasts");
  document.querySelectorAll("[data-toast]").forEach(function (node) {
    if (!stack) return;
    var toast = document.createElement("p");
    toast.className = node.classList.contains("error") ? "toast bad" : "toast";
    toast.textContent = node.textContent;
    stack.appendChild(toast);
    node.hidden = true;
    window.setTimeout(function () { toast.classList.add("out"); }, 4200);
  });

  function format(kind, value, suffix) {
    if (kind === "money") {
      var sign = value < 0 ? "-" : "";
      return sign + "$" + Math.abs(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    if (kind === "pct") return (value * 100).toFixed(1) + "%";
    if (kind === "factor") return value.toFixed(2);
    if (kind === "r") return (value >= 0 ? "+" : "") + value.toFixed(2) + "R";
    if (kind === "int") return String(Math.round(value)) + (suffix || "");
    return String(value);
  }

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.querySelectorAll("[data-count]").forEach(function (node) {
    var target = Number(node.getAttribute("data-count"));
    if (!isFinite(target) || reduced) return;
    var kind = node.getAttribute("data-kind") || "";
    var suffix = node.getAttribute("data-suffix") || "";
    var started = 0;
    function step(now) {
      if (!started) started = now;
      var t = Math.min(1, (now - started) / 700);
      var eased = 1 - Math.pow(1 - t, 3);
      node.textContent = format(kind, target * eased, suffix);
      if (t < 1) requestAnimationFrame(step);
      else node.textContent = format(kind, target, suffix);
    }
    requestAnimationFrame(step);
  });

  document.querySelectorAll("[data-steps]").forEach(function (form) {
    var panels = form.querySelectorAll("[data-step-panel]");
    function show(index) {
      panels.forEach(function (panel) {
        panel.classList.toggle("on", panel.getAttribute("data-step-panel") === String(index));
      });
      form.querySelectorAll("[data-step]").forEach(function (button) {
        button.classList.toggle("on", button.getAttribute("data-step") === String(index));
      });
    }
    form.querySelectorAll("[data-step]").forEach(function (button) {
      button.addEventListener("click", function () { show(button.getAttribute("data-step")); });
    });
    form.querySelectorAll("[data-next]").forEach(function (button) {
      button.addEventListener("click", function () {
        var current = form.querySelector("[data-step-panel].on");
        show(Number(current.getAttribute("data-step-panel")) + 1);
      });
    });
    form.querySelectorAll("[data-prev]").forEach(function (button) {
      button.addEventListener("click", function () {
        var current = form.querySelector("[data-step-panel].on");
        show(Number(current.getAttribute("data-step-panel")) - 1);
      });
    });
  });

  document.querySelectorAll("[data-tabs]").forEach(function (bar) {
    var root = bar.parentElement;
    function show(name) {
      bar.querySelectorAll("[data-tab]").forEach(function (button) {
        button.classList.toggle("on", button.getAttribute("data-tab") === name);
      });
      root.querySelectorAll("[data-tab-panel]").forEach(function (panel) {
        panel.hidden = panel.getAttribute("data-tab-panel") !== name;
      });
      window.dispatchEvent(new Event("resize"));
    }
    bar.querySelectorAll("[data-tab]").forEach(function (button) {
      button.addEventListener("click", function () { show(button.getAttribute("data-tab")); });
    });
    show("overview");
  });

  var card = document.querySelector(".login-card");
  if (card && !reduced) {
    card.addEventListener("pointermove", function (event) {
      var box = card.getBoundingClientRect();
      card.style.setProperty("--mx", ((event.clientX - box.left) / box.width * 100) + "%");
      card.style.setProperty("--my", ((event.clientY - box.top) / box.height * 100) + "%");
    });
  }

  document.querySelectorAll(".firm-head input").forEach(function (box) {
    box.addEventListener("change", function () {
      box.closest(".firm").classList.toggle("picked", box.checked);
    });
  });

  var root = document.documentElement;
  var sideToggle = document.getElementById("sidebar-toggle");
  if (sideToggle) {
    function sideLabel() {
      sideToggle.setAttribute("aria-label", root.classList.contains("compact") ? "Expand sidebar" : "Collapse sidebar");
    }
    sideLabel();
    sideToggle.addEventListener("click", function () {
      root.classList.toggle("compact");
      try {
        localStorage.setItem("omensite_sidebar", root.classList.contains("compact") ? "compact" : "expanded");
      } catch (err) {}
      sideLabel();
    });
  }

  var palette = document.getElementById("palette");
  var paletteOpen = document.getElementById("palette-open");
  var paletteField = document.getElementById("palette-q");
  var paletteList = document.getElementById("palette-list");
  if (palette && paletteList) {
    var jumps = Array.prototype.map.call(document.querySelectorAll(".side-nav a"), function (link) {
      var label = link.querySelector("span");
      return { href: link.getAttribute("href"), label: label ? label.textContent : link.textContent };
    });
    function renderJumps(query) {
      var needle = (query || "").trim().toLowerCase();
      paletteList.innerHTML = "";
      jumps.forEach(function (item) {
        if (needle && item.label.toLowerCase().indexOf(needle) === -1) return;
        var row = document.createElement("li");
        var link = document.createElement("a");
        link.href = item.href;
        link.textContent = item.label;
        row.appendChild(link);
        paletteList.appendChild(row);
      });
    }
    function openPalette() {
      palette.hidden = false;
      renderJumps("");
      if (paletteField) {
        paletteField.value = "";
        paletteField.focus();
      }
    }
    function closePalette() { palette.hidden = true; }
    if (paletteOpen) paletteOpen.addEventListener("click", openPalette);
    palette.addEventListener("click", function (event) {
      if (event.target === palette) closePalette();
    });
    if (paletteField) paletteField.addEventListener("input", function () { renderJumps(paletteField.value); });
    document.addEventListener("keydown", function (event) {
      var key = event.key.toLowerCase();
      if ((event.ctrlKey || event.metaKey) && key === "k") {
        event.preventDefault();
        if (palette.hidden) openPalette();
        else closePalette();
      } else if (event.key === "Escape" && !palette.hidden) {
        closePalette();
      }
    });
  }
})();
