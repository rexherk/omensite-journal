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
document.querySelectorAll('[data-account-filter]').forEach(form => {
  form.querySelector('select').addEventListener('change', () => form.requestSubmit());
});

document.querySelectorAll('[data-equity-chart]').forEach((chart, chartIndex) => {
  const data = JSON.parse(chart.querySelector('[data-equity-data]').textContent);
  const svg = chart.querySelector('svg');
  const tooltip = chart.querySelector('.equity-tooltip');
  const offset = data.rules ? data.rules.size + data.baseline : 0;
  const seriesName = data.rules ? 'Account balance' : 'Cumulative net P&L';
  const dollars = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
  const axisDollars = new Intl.NumberFormat('en-US', {
    style: 'currency', currency: 'USD', maximumFractionDigits: 0
  });
  const dates = new Intl.DateTimeFormat('en-US', {
    month: 'short', day: 'numeric', year: '2-digit', timeZone: data.timezone
  });
  let activeIndex = data.points.length - 1;
  let cursor;
  let x;
  let y;
  let lastWidth = 0;

  function element(tag, attributes, text) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function linePath(rows, value, scale, stepped = false) {
    return rows.map((row, index) => {
      const position = x(row.time);
      const height = scale(value(row));
      if (!index) return 'M' + position + ',' + height;
      return stepped ? 'H' + position + 'V' + height : 'L' + position + ',' + height;
    }).join(' ');
  }

  function showPoint(index) {
    activeIndex = Math.max(0, Math.min(data.points.length - 1, index));
    const point = data.points[activeIndex];
    tooltip.replaceChildren();
    const title = document.createElement('strong');
    title.textContent = point.instrument + ' · ' + point.label;
    tooltip.append(title);
    const values = [
      ...(data.rules ? [['Account balance', point.net + offset]] : []),
      ['Trade net P&L', point.trade_net],
      ['Cumulative net P&L', point.net],
      ['Closed-trade drawdown', point.drawdown]
    ];
    if (data.rules) {
      values.push(['Minimum account balance at trade', data.rules.size + point.floor]);
      values.push(['Required total account profit', point.target]);
    }
    values.forEach(([label, amount]) => {
      const row = document.createElement('div');
      const name = document.createElement('span');
      const value = document.createElement('b');
      name.textContent = label;
      value.textContent = dollars.format(amount);
      row.append(name, value);
      tooltip.append(row);
    });
    tooltip.hidden = false;
    cursor.replaceChildren(
      element('line', { x1: x(point.time), x2: x(point.time), y1: 38, y2: 310 }),
      element('line', { x1: x(point.time), x2: x(point.time), y1: y(point.net + point.drawdown + offset), y2: y(point.net + offset), class: 'equity-drawdown-marker' }),
      element('circle', { cx: x(point.time), cy: y(point.net + offset), r: 5 })
    );
  }

  function render() {
    const width = Math.floor(chart.clientWidth);
    if (width < 1 || width === lastWidth) return;
    lastWidth = width;
    const left = width < 480 ? 70 : 82;
    const right = width - 16;
    const end = Math.max(data.end, data.start + 60000);
    x = stamp => left + (stamp - data.start) / (end - data.start) * (right - left);
    const rows = [{time: data.start, net: 0, drawdown: data.initial_drawdown || 0}, ...data.points];
    // Extend the last recorded balance through the final EOD limit update.
    if (rows.at(-1).time < data.end) rows.push({...rows.at(-1), time: data.end});
    const values = rows.flatMap(point => [point.net + offset, point.net + point.drawdown + offset]);
    data.limits.forEach(point => values.push(point.floor + offset, point.target + offset));
    const low = Math.min(...values);
    const high = Math.max(...values);
    const padding = (high - low || 100) * .08;
    const rawStep = (high - low + padding * 2) / 4;
    const magnitude = 10 ** Math.floor(Math.log10(rawStep));
    const step = [1, 2, 5, 10].map(factor => factor * magnitude).find(value => value >= rawStep);
    const bottomValue = Math.floor((low - padding) / step) * step;
    const topValue = Math.ceil((high + padding) / step) * step;
    y = value => 310 - (value - bottomValue) / (topValue - bottomValue) * 272;

    svg.replaceChildren();
    svg.setAttribute('viewBox', '0 0 ' + width + ' 356');
    const fillId = 'equity-fill-' + chartIndex;
    const gradient = element('linearGradient', {id: fillId, x1: 0, x2: 0, y1: 0, y2: 1});
    gradient.append(element('stop', {offset: '0%', 'stop-color': 'var(--oj-secondary)', 'stop-opacity': '.16'}),
      element('stop', {offset: '100%', 'stop-color': 'var(--oj-secondary)', 'stop-opacity': '.01'}));
    const defs = element('defs', {});
    defs.append(gradient);
    svg.append(defs);
    svg.append(element('text', { x: left, y: 16, class: 'equity-axis-title' }, (data.rules ? 'Balance' : 'Net P&L') + ' · USD'));
    for (let value = bottomValue; value <= topValue; value += step) {
      const height = y(value);
      svg.append(element('line', { x1: left, x2: right, y1: height, y2: height, class: value === 0 ? 'equity-zero' : 'equity-grid' }));
      svg.append(element('text', { x: left - 10, y: height + 4, 'text-anchor': 'end', class: 'equity-axis' }, (step < 1 ? dollars : axisDollars).format(value)));
    }
    const tickCount = width < 310 ? 1 : width < 480 ? 2 : 4;
    for (let tick = 0; tick <= tickCount; tick++) {
      const stamp = data.start + (end - data.start) * tick / tickCount;
      svg.append(element('text', {
        x: x(stamp), y: 340, class: 'equity-axis',
        'text-anchor': tick === 0 ? 'start' : tick === tickCount ? 'end' : 'middle'
      }, dates.format(new Date(stamp))));
    }
    const netPath = linePath(rows, row => row.net + offset, y);
    svg.append(element('path', {d: netPath + 'L' + x(rows.at(-1).time) + ',310L' + x(data.start) + ',310Z', fill: 'url(#' + fillId + ')', class: 'equity-balance-area'}));
    const peakPath = linePath(rows, row => row.net + row.drawdown + offset, y);
    svg.append(element('path', {
      d: peakPath + ' ' + linePath([...rows].reverse(), row => row.net + offset, y).replace(/^M/, 'L') + 'Z',
      class: 'equity-drawdown-area'
    }));
    svg.append(element('path', {d: peakPath, class: 'equity-peak-line'}));
    svg.append(element('path', {d: netPath, class: 'equity-net-line'}));
    if (data.rules) {
      svg.append(element('path', { d: linePath(data.limits, row => row.target + offset, y, true), class: 'equity-target-line' }));
      svg.append(element('path', { d: linePath(data.limits, row => row.floor + offset, y, true), class: 'equity-limit-line' }));
      const last = data.limits.at(-1);
      const targetName = data.rules.current_target > data.rules.base_target ? 'Adjusted target' : 'Profit target';
      [[last.target, targetName, 'target'], [last.floor, 'Loss floor', 'limit']].forEach(([amount, label, style]) => {
        svg.append(element('text', {x: right, y: y(amount + offset) - 9, 'text-anchor': 'end', class: 'equity-line-label equity-' + style + '-label'}, label + ' ' + dollars.format(amount + offset)));
      });
    }
    data.points.forEach(point => {
      const dot = element('circle', { cx: x(point.time), cy: y(point.net + offset), r: 2.5, class: 'equity-trade-dot' });
      dot.append(element('title', {}, point.instrument + ' · ' + point.label + ' · ' + seriesName + ' ' + dollars.format(point.net + offset)));
      svg.append(dot);
    });
    cursor = element('g', { class: 'equity-cursor', 'aria-hidden': 'true' });
    svg.append(cursor);
    svg.setAttribute('tabindex', '0');
    svg.setAttribute('aria-label', seriesName + ' and drawdown in one USD chart. Use left and right arrow keys for each trade.');
    if (!tooltip.hidden) showPoint(activeIndex);
  }

  function nearest(event) {
    const bounds = svg.getBoundingClientRect();
    const stamp = data.start + (event.clientX - bounds.left - (lastWidth < 480 ? 70 : 82))
      / (lastWidth - 16 - (lastWidth < 480 ? 70 : 82)) * (Math.max(data.end, data.start + 60000) - data.start);
    let closest = 0;
    data.points.forEach((point, index) => {
      if (Math.abs(point.time - stamp) < Math.abs(data.points[closest].time - stamp)) closest = index;
    });
    showPoint(closest);
  }

  svg.addEventListener('pointermove', event => { if (event.pointerType === 'mouse') nearest(event); });
  svg.addEventListener('click', nearest);
  svg.addEventListener('focus', () => showPoint(activeIndex));
  svg.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      tooltip.hidden = true;
      cursor.replaceChildren();
    } else if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      if (event.key === 'Home') showPoint(0);
      else if (event.key === 'End') showPoint(data.points.length - 1);
      else showPoint(activeIndex + (event.key === 'ArrowRight' ? 1 : -1));
    }
  });
  new ResizeObserver(render).observe(chart);
  render();
});
