const calendar = document.querySelector("[data-tradays-calendar]");
if (calendar) {
  function loadCalendar() {
    const frame = calendar.querySelector("template");
    if (calendar.open && frame) {
      frame.replaceWith(frame.content.cloneNode(true));
      calendar.removeEventListener("toggle", loadCalendar);
    }
  }

  calendar.addEventListener("toggle", loadCalendar);
  loadCalendar();
}
