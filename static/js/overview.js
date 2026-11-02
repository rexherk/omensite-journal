document.querySelectorAll('[data-overview]').forEach(overview => {
  const buttons = Array.from(overview.querySelectorAll('[data-overview-view]'));
  function show(button) {
    buttons.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    overview.querySelectorAll('[data-overview-pane]').forEach(pane => {
      pane.hidden = pane.dataset.overviewPane !== button.dataset.overviewView;
    });
  }
  buttons.forEach((button, index) => {
    button.addEventListener('click', () => show(button));
    button.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
      event.preventDefault();
      const next = buttons[(index + 1) % buttons.length];
      show(next);
      next.focus();
    });
  });
});
