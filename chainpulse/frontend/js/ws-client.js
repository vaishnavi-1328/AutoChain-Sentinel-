window.CPWS = (function () {
  const dot = document.getElementById('tb-ws-dot');
  const txt = document.getElementById('tb-ws-text');
  let ws = null, backoff = 2000;
  const channels = {}; // channel name → [fn,...]

  function setStatus(state) {
    if (state === 'connected') {
      dot.className = 'tb-dot tb-dot--ok';
      txt.textContent = 'LIVE';
    } else if (state === 'connecting') {
      dot.className = 'tb-dot tb-dot--off';
      txt.textContent = 'CONNECTING';
    } else {
      dot.className = 'tb-dot';
      txt.textContent = 'RECONNECTING';
    }
  }

  function on(channel, fn) {
    (channels[channel] = channels[channel] || []).push(fn);
  }
  function emit(channel, payload) {
    (channels[channel] || []).forEach((fn) => { try { fn(payload); } catch (e) { console.error(e); } });
  }

  function connect() {
    setStatus('connecting');
    const tok = localStorage.getItem('cp_token');
    const url = window.CP.WS_URL + (tok ? `?token=${encodeURIComponent(tok)}` : '');
    try { ws = new WebSocket(url); }
    catch (e) { console.error('ws ctor failed', e); scheduleReconnect(); return; }

    ws.onopen = () => { setStatus('connected'); backoff = 2000; };
    ws.onclose = () => { setStatus('disconnected'); scheduleReconnect(); };
    ws.onerror = () => { try { ws.close(); } catch {} };
    ws.onmessage = (msg) => {
      let payload;
      try { payload = JSON.parse(msg.data); } catch { return; }
      const mt = payload && payload.msg_type;
      if (mt === 'order_delay_update') {
        emit('order_delay_update', payload);
      } else if (mt === 'event') {
        // strip wrapper for backward-compat with existing event handlers
        const { msg_type, ...rest } = payload;
        emit('event', rest);
      } else {
        // bare event (legacy back-compat)
        emit('event', payload);
      }
    };
  }

  function scheduleReconnect() {
    setTimeout(connect, backoff);
    backoff = Math.min(backoff * 1.6, 30000);
  }

  // legacy alias used by app.js
  function onEvent(fn) { on('event', fn); }

  return { connect, on, onEvent };
})();
