(() => {
  'use strict';
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const nav = $('#main-navigation');
  const mobileToggle = $('.mobile-toggle');
  function closeMenus(except) {
    $$('.nav-dropdown > button').forEach(button => {
      if (button === except) return;
      button.setAttribute('aria-expanded', 'false');
      document.getElementById(button.getAttribute('aria-controls')).hidden = true;
    });
  }
  $$('.nav-dropdown > button').forEach(button => button.addEventListener('click', () => {
    const open = button.getAttribute('aria-expanded') !== 'true';
    closeMenus(button);
    button.setAttribute('aria-expanded', String(open));
    document.getElementById(button.getAttribute('aria-controls')).hidden = !open;
  }));
  mobileToggle.addEventListener('click', () => {
    const open = mobileToggle.getAttribute('aria-expanded') !== 'true';
    mobileToggle.setAttribute('aria-expanded', String(open));
    mobileToggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    nav.classList.toggle('is-open', open);
    if (!open) closeMenus();
  });
  function closeNavigation() {
    closeMenus();
    mobileToggle.setAttribute('aria-expanded', 'false');
    mobileToggle.setAttribute('aria-label', 'Open navigation');
    nav.classList.remove('is-open');
  }
  document.addEventListener('click', event => {
    if (!event.target.closest('.nav-dropdown')) closeMenus();
    if (event.target.closest('.main-navigation a')) closeNavigation();
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const expanded = $('.nav-dropdown > button[aria-expanded="true"]');
    if (expanded) { closeMenus(); expanded.focus(); }
    else if (nav.classList.contains('is-open')) { closeNavigation(); mobileToggle.focus(); }
  });
  const tabs = $$('[data-product]');
  function selectProduct(key, focus = false) {
    const selected = tabs.find(tab => tab.dataset.product === key);
    if (!selected) return;
    tabs.forEach(tab => {
      const on = tab === selected;
      tab.setAttribute('aria-selected', String(on));
      tab.tabIndex = on ? 0 : -1;
      document.getElementById(tab.getAttribute('aria-controls')).hidden = !on;
    });
    selected.parentElement.scrollTo({ left: selected.offsetLeft - tabs[0].offsetLeft, behavior: reduceMotion ? 'instant' : 'smooth' });
    if (focus) {
      selected.focus({ preventScroll: true });
      selected.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: reduceMotion ? 'instant' : 'smooth' });
    }
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectProduct(tab.dataset.product));
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next !== undefined) { event.preventDefault(); selectProduct(tabs[next].dataset.product, true); }
    });
  });
  $$('[data-select-product]').forEach(link => link.addEventListener('click', () => {
    selectProduct(link.dataset.selectProduct);
    closeNavigation();
  }));
  $$('[data-preview-view]').forEach(button => button.addEventListener('click', () => {
    $$('[data-preview-view]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
    $$('[data-preview-pane]').forEach(pane => pane.hidden = pane.dataset.previewPane !== button.dataset.previewView);
  }));
  const dialogs = $$('dialog');
  let lastDialogTrigger;
  function openDialog(dialog, trigger) {
    const previous = dialogs.find(other => other.open);
    if (previous) previous.close();
    closeNavigation();
    if (!trigger.closest('dialog')) lastDialogTrigger = trigger;
    document.body.classList.add('modal-open');
    dialog.showModal();
  }
  dialogs.forEach(dialog => {
    dialog.addEventListener('click', event => {
      if (event.target !== dialog) return;
      const rect = dialog.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
    });
    dialog.addEventListener('close', () => {
      if (!dialogs.some(d => d.open)) {
        document.body.classList.remove('modal-open');
        if (lastDialogTrigger?.isConnected && !lastDialogTrigger.closest('dialog')) lastDialogTrigger.focus({ preventScroll: true });
      }
    });
    $('[data-close-dialog]', dialog).addEventListener('click', () => dialog.close());
  });
  const guides = {
    review: ['A review worth coming back to.', '<p>A useful review connects what you planned with what you actually did.</p><ol><li><b>Start with the setup.</b> Name the idea, the market context, and the level you were watching.</li><li><b>Review the execution.</b> Add your entry and exit charts. Did your size, stop, and target follow the plan?</li><li><b>Name the emotion.</b> Log how you felt and tag any mistakes without judging the outcome alone.</li><li><b>Choose one thing to repeat.</b> Write one clear lesson for your next session. Review the pattern again at the end of the week.</li></ol>'],
    imports: ['Your fills. One place.', '<p>Export your fill history as a CSV, then use Import in your journal. Check the instrument, timestamps, quantities, fees, and account before saving.</p><ul class="import-list"><li>Topstep CSV import</li></ul><p>CSV import and manual trade entry are available. Automatic broker synchronization is not currently included.</p>'],
    privacy: ['Your journal stays yours.', '<p>Omensite stores your journal in a local SQLite database, with chart images in the app’s data folder. Each sign-in sees its own trades.</p><p>You can export your fills as CSV and create a JSON backup from Settings. Keep your backups somewhere you trust.</p><p>The local app is available on this computer at the address shown in your browser. The preview numbers on the homepage are illustrative examples.</p>'],
    help: ['Make yourself at home.', '<p>Omensite brings your fills, chart images, setup rules, and performance reviews into one journal.</p><ul><li><b>New here?</b> Try the demo to explore a sample journal.</li><li><b>Have a journal?</b> Use the Log In page to return to your journal.</li><li><b>Ready to add trades?</b> Import a CSV or log a fill after you sign in.</li><li><b>Need a routine?</b> Start with your daily plan, tag your setups, then review your session.</li></ul><p>Use the questions and answers below for more detail. This help panel is a local guide.</p>']
  };
  $$('[data-guide]').forEach(button => button.addEventListener('click', () => {
    const guide = guides[button.dataset.guide];
    if (!guide) return;
    $('#guide-content').innerHTML = '<p class="label">OMENSITE JOURNAL</p><h2 id="guide-title">' + guide[0] + '</h2>' + guide[1] + '<a href="/signup" class="gradient-button guide-action">Create your journal →</a>';
    $('#guide-dialog').setAttribute('aria-labelledby', 'guide-title');
    openDialog($('#guide-dialog'), button);
  }));
  const track = $('#routine-track');
  if (!track) return;
  const cards = $$('.routine-card', track);
  const dots = $$('[data-slide]');
  let currentSlide = 0;
  function lastStart() {
    const visible = Math.max(1, Math.round(track.clientWidth / (cards[0].getBoundingClientRect().width + 16)));
    const last = Math.max(0, cards.length - visible);
    dots.forEach((dot, i) => dot.hidden = i > last);
    return last;
  }
  function slideTo(index) {
    const last = lastStart();
    currentSlide = Math.max(0, Math.min(index, last));
    if (index > last) currentSlide = 0;
    if (index < 0) currentSlide = last;
    track.scrollTo({ left: cards[currentSlide].offsetLeft - cards[0].offsetLeft, behavior: reduceMotion ? 'instant' : 'smooth' });
    dots.forEach((dot, i) => { dot.classList.toggle('active', i === currentSlide); dot.setAttribute('aria-pressed', String(i === currentSlide)); });
  }
  $$('[data-carousel]').forEach(button => button.addEventListener('click', () => slideTo(currentSlide + (button.dataset.carousel === 'next' ? 1 : -1))));
  dots.forEach(dot => dot.addEventListener('click', () => slideTo(Number(dot.dataset.slide))));
  lastStart();
  window.addEventListener('resize', () => { lastStart(); });
  let scrollFrame;
  track.addEventListener('scroll', () => {
    cancelAnimationFrame(scrollFrame);
    scrollFrame = requestAnimationFrame(() => {
      let nearest = 0;
      cards.forEach((card, i) => { if (Math.abs(card.offsetLeft - cards[0].offsetLeft - track.scrollLeft) < Math.abs(cards[nearest].offsetLeft - cards[0].offsetLeft - track.scrollLeft)) nearest = i; });
      currentSlide = nearest;
      dots.forEach((dot, i) => { dot.classList.toggle('active', i === nearest); dot.setAttribute('aria-pressed', String(i === nearest)); });
    });
  }, { passive: true });
})();
