(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const state = { data: null, toastTimer: null, pollBusy: false, chartResize: null };
  const money = (value) => '$' + Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const price = (value) => Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 5 });

  async function api(path, options = {}) {
    const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || result.message || `Request failed (${response.status})`);
    return result;
  }
  function toast(message) {
    const node = $('#toast'); node.textContent = message; node.classList.add('visible');
    clearTimeout(state.toastTimer); state.toastTimer = setTimeout(() => node.classList.remove('visible'), 3200);
  }
  function safeText(value) { return String(value ?? '—'); }
  function renderAssets(data) {
    const select = $('#asset-select');
    if (select.options.length !== data.assets.length) {
      select.innerHTML = data.assets.map(asset => `<option value="${asset}">${asset}</option>`).join('');
    }
    select.value = data.asset;
    $('#asset-tabs').innerHTML = data.assets.map(asset => `<button class="asset-tab ${asset === data.asset ? 'active' : ''}" data-asset="${asset}">${asset}</button>`).join('');
    $('#asset-tabs').querySelectorAll('[data-asset]').forEach(button => button.addEventListener('click', () => chooseAsset(button.dataset.asset)));
    const symbols = { 'EUR/USD': '€', 'BTC/USD': '₿', GOLD: 'Au', NASDAQ: 'N' };
    $('#instrument-icon').textContent = symbols[data.asset] || '◈';
    $('#instrument-name').textContent = data.asset;
  }
  function renderSignal(data) {
    const analysis = data.signal || {};
    const signal = analysis.signal || 'WAIT';
    const badge = $('#signal-badge');
    badge.className = `signal-badge ${signal === 'BUY' ? 'buy' : signal === 'SELL' ? 'sell' : 'wait'}`;
    $('#signal-label').textContent = signal;
    $('#signal-reason').textContent = analysis.reason || 'Waiting for enough sample data.';
    const indicators = analysis.indicators || {};
    $('#fast-sma').textContent = indicators.fast_sma == null ? '—' : price(indicators.fast_sma);
    $('#slow-sma').textContent = indicators.slow_sma == null ? '—' : price(indicators.slow_sma);
    $('#rsi-value').textContent = indicators.rsi == null ? '—' : indicators.rsi.toFixed(1);
    $('#sample-count').textContent = indicators.samples ?? '—';
  }
  function renderHistory(data) {
    const history = data.history || [];
    $('#history-count').textContent = `${history.length} ${history.length === 1 ? 'trade' : 'trades'}`;
    if (!history.length) {
      $('#history-body').innerHTML = '<tr><td colspan="4" class="empty-row">No completed demo trades yet</td></tr>'; return;
    }
    $('#history-body').innerHTML = history.slice(0, 8).map(trade => {
      const resultClass = trade.result === 'WIN' ? 'result-win' : trade.result === 'LOSS' ? 'result-loss' : '';
      const time = new Date(trade.closed_at || trade.opened_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      return `<tr><td>${trade.asset}<br><span class="${trade.direction === 'UP' ? 'result-win' : 'result-loss'}">${trade.direction} · ${time}</span></td><td>${price(trade.entry_price)} → ${price(trade.expiry_price)}</td><td class="${resultClass}">${trade.result}</td><td class="${Number(trade.profit_loss) >= 0 ? 'result-win' : 'result-loss'}">${Number(trade.profit_loss) > 0 ? '+' : ''}${money(trade.profit_loss)}</td></tr>`;
    }).join('');
  }
  function renderPosition(data) {
    const position = data.open_position;
    const card = $('#countdown-card');
    const button = $('#agent-button');
    if (position) {
      const seconds = Math.max(0, Math.ceil((new Date(position.expires_at).getTime() - Date.now()) / 1000));
      $('#countdown-label').textContent = `${position.direction} POSITION · ${position.asset}`;
      $('#countdown').textContent = `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${(seconds % 60).toString().padStart(2, '0')}`;
      $('#countdown-state').textContent = 'OPEN'; card.classList.add('open');
      $('#position-status').textContent = `${position.direction} · ${money(position.investment)}`;
    } else {
      $('#countdown-label').textContent = 'TRADE TIMER'; $('#countdown').textContent = 'READY';
      $('#countdown-state').textContent = data.agent_running ? 'ANALYZING' : 'IDLE'; card.classList.remove('open');
      $('#position-status').textContent = 'None';
    }
    button.classList.toggle('stop', data.agent_running);
    button.innerHTML = data.agent_running ? '<span>■</span> Stop Trading' : '<span>▶</span> Start Trading';
    $('#agent-status').textContent = data.state || (data.agent_running ? 'ANALYZING' : 'STOPPED');
    $('.status-light').classList.toggle('running', data.agent_running);
    $('#agent-error').textContent = data.error || '';
    $('#agent-error').classList.toggle('hidden', !data.error);
    $('#up-button').disabled = !!position; $('#down-button').disabled = !!position;
  }
  function render(data) {
    state.data = data;
    renderAssets(data); renderSignal(data); renderHistory(data); renderPosition(data);
    $('#top-balance').textContent = money(data.balance);
    $('#account-balance').textContent = money(data.balance);
    $('#starting-balance').textContent = money(data.initial_balance);
    $('#chart-price').textContent = price(data.latest_price);
    $('#payout-value').textContent = money(data.payout_estimate);
    $('#clock').textContent = new Date(data.server_time).toLocaleTimeString([], { hour12: false, timeZone: 'UTC' }) + ' UTC';
    if (document.activeElement !== $('#investment-input')) $('#investment-input').value = data.settings.investment;
    if (document.activeElement !== $('#duration-select')) $('#duration-select').value = String(data.settings.duration_seconds);
    drawChart(data.candles || []);
    if ($('#settings-view').classList.contains('hidden')) return;
    populateSettings(data.settings);
  }
  async function refresh() {
    if (state.pollBusy) return;
    state.pollBusy = true;
    try { render(await api('/api/status')); }
    catch (error) { toast(error.message); }
    finally { state.pollBusy = false; }
  }
  async function chooseAsset(asset) {
    try { render(await api('/api/asset', { method: 'POST', body: JSON.stringify({ asset }) })); $('#sidebar').classList.remove('open'); }
    catch (error) { toast(error.message); }
  }
  async function changeSetting(key, value) {
    try { render(await api('/api/settings', { method: 'PATCH', body: JSON.stringify({ [key]: value }) })); }
    catch (error) { toast(error.message); if (state.data) render(state.data); }
  }
  function populateSettings(settings) {
    const form = $('#settings-form');
    Object.entries(settings).forEach(([key, value]) => { if (form.elements[key] && document.activeElement !== form.elements[key]) form.elements[key].value = value; });
  }
  async function toggleAgent() {
    const button = $('#agent-button'); button.disabled = true;
    try {
      const result = await api(state.data?.agent_running ? '/api/agent/stop' : '/api/agent/start', { method: 'POST' });
      render(result); toast(result.agent_running ? 'Demo agent started.' : 'Demo agent stopped.');
    } catch (error) { toast(error.message); }
    finally { button.disabled = false; }
  }
  async function manualTrade(direction) {
    if (!state.data) return;
    const investment = Number($('#investment-input').value);
    const duration = Number($('#duration-select').value);
    $('#up-button').disabled = $('#down-button').disabled = true;
    try {
      const result = await api('/api/trade', { method: 'POST', body: JSON.stringify({ direction, investment, duration_seconds: duration }) });
      toast(`${direction} demo trade opened at ${price(result.trade.entry_price)}.`); await refresh();
    } catch (error) { toast(error.message); }
    finally { if (!state.data?.open_position) $('#up-button').disabled = $('#down-button').disabled = false; }
  }
  function drawChart(candles) {
    const canvas = $('#market-chart'); if (!canvas || !candles.length) return;
    const bounds = canvas.getBoundingClientRect(); if (!bounds.width || !bounds.height) return;
    const ratio = Math.max(1, window.devicePixelRatio || 1);
    canvas.width = Math.round(bounds.width * ratio); canvas.height = Math.round(bounds.height * ratio);
    const ctx = canvas.getContext('2d'); ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    const width = bounds.width, height = bounds.height;
    ctx.clearRect(0, 0, width, height);
    const pad = { top: 23, right: 64, bottom: 23, left: 12 };
    const view = candles.slice(-Math.max(22, Math.floor((width - pad.left - pad.right) / 9)));
    let min = Math.min(...view.map(c => c.low)), max = Math.max(...view.map(c => c.high));
    const margin = (max - min || max * .001) * .15; min -= margin; max += margin;
    const chartH = height - pad.top - pad.bottom, chartW = width - pad.left - pad.right;
    const y = (value) => pad.top + (max - value) / (max - min) * chartH;
    ctx.font = '9px DM Mono, monospace'; ctx.textBaseline = 'middle';
    for (let i = 0; i <= 4; i++) {
      const yy = pad.top + chartH * i / 4; const label = max - (max - min) * i / 4;
      ctx.strokeStyle = '#1b2a3c'; ctx.lineWidth = 1; ctx.setLineDash([3, 5]);
      ctx.beginPath(); ctx.moveTo(pad.left, yy); ctx.lineTo(width - pad.right + 5, yy); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = '#718199'; ctx.fillText(label.toFixed(label < 10 ? 4 : 2), width - pad.right + 9, yy);
    }
    const slot = chartW / view.length, bodyW = Math.max(3, Math.min(9, slot * .58));
    view.forEach((candle, index) => {
      const x = pad.left + slot * (index + .5), bullish = candle.close >= candle.open;
      const color = bullish ? '#35d49a' : '#ff647d';
      ctx.strokeStyle = color; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x, y(candle.high)); ctx.lineTo(x, y(candle.low)); ctx.stroke();
      const openY = y(candle.open), closeY = y(candle.close), bodyY = Math.min(openY, closeY), bodyH = Math.max(1.5, Math.abs(closeY - openY));
      ctx.fillStyle = color; ctx.fillRect(x - bodyW / 2, bodyY, bodyW, bodyH);
    });
    const last = view[view.length - 1]; const currentY = y(last.close);
    ctx.strokeStyle = '#42d9df77'; ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.moveTo(pad.left, currentY); ctx.lineTo(width - pad.right + 2, currentY); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = '#174348'; ctx.fillRect(width - pad.right + 4, currentY - 9, pad.right - 7, 18);
    ctx.fillStyle = '#75eff0'; ctx.fillText(last.close.toFixed(last.close < 10 ? 4 : 2), width - pad.right + 8, currentY);
    canvas.onmousemove = (event) => {
      const rect = canvas.getBoundingClientRect(); const index = Math.floor((event.clientX - rect.left - pad.left) / slot);
      const candle = view[Math.max(0, Math.min(view.length - 1, index))];
      const tooltip = $('#chart-tooltip');
      tooltip.textContent = `O ${price(candle.open)}   H ${price(candle.high)}\nL ${price(candle.low)}   C ${price(candle.close)}`;
      tooltip.style.display = 'block'; tooltip.style.left = `${Math.min(event.clientX - rect.left + 12, width - 185)}px`; tooltip.style.top = '12px';
    };
    canvas.onmouseleave = () => { $('#chart-tooltip').style.display = 'none'; };
  }
  function showView(view) {
    const settings = view === 'settings';
    $('#dashboard-view').classList.toggle('hidden', settings);
    $('#settings-view').classList.toggle('hidden', !settings);
    document.querySelectorAll('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.view === view));
    $('#breadcrumb-view').textContent = view.toUpperCase();
    $('.page-heading h1').textContent = settings ? 'Agent settings' : 'Trading terminal';
    $('.page-heading p').textContent = settings ? 'Tune your sample analysis and demo risk limits.' : 'Read the market. Simulate with virtual funds.';
    $('#sidebar').classList.remove('open');
    if (settings && state.data) populateSettings(state.data.settings);
  }
  function init() {
    $('#agent-button').addEventListener('click', toggleAgent);
    $('#up-button').addEventListener('click', () => manualTrade('UP'));
    $('#down-button').addEventListener('click', () => manualTrade('DOWN'));
    $('#asset-select').addEventListener('change', event => chooseAsset(event.target.value));
    $('#investment-input').addEventListener('change', event => { const value = Number(event.target.value); if (Number.isFinite(value)) changeSetting('investment', value); });
    $('#duration-select').addEventListener('change', event => changeSetting('duration_seconds', Number(event.target.value)));
    document.querySelectorAll('.nav-item').forEach(item => item.addEventListener('click', () => showView(item.dataset.view)));
    $('#menu-toggle').addEventListener('click', () => $('#sidebar').classList.toggle('open'));
    $('#settings-form').addEventListener('submit', async event => {
      event.preventDefault(); const form = new FormData(event.currentTarget); const values = {};
      for (const [key, value] of form.entries()) values[key] = key === 'data_source' ? value : Number(value);
      $('#settings-message').textContent = 'Saving…';
      try { render(await api('/api/settings', { method: 'PATCH', body: JSON.stringify(values) })); $('#settings-message').textContent = 'Settings saved'; toast('Demo settings saved.'); }
      catch (error) { $('#settings-message').textContent = error.message; }
    });
    $('#reset-settings').addEventListener('click', async () => {
      if (!window.confirm('Reset settings, sample chart, demo balance, and trade history to defaults?')) return;
      try { render(await api('/api/settings/reset', { method: 'POST' })); $('#settings-message').textContent = 'Defaults restored'; toast('Demo settings reset.'); }
      catch (error) { toast(error.message); }
    });
    window.addEventListener('resize', () => { if (state.data) drawChart(state.data.candles); });
    refresh(); window.setInterval(refresh, 1000);
  }
  document.addEventListener('DOMContentLoaded', init);
})();
