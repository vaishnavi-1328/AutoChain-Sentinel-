window.CPWS = (function () {
  const dot = document.getElementById('tb-ws-dot');
  const txt = document.getElementById('tb-ws-text');
  let ws = null, backoff = 2000;
  const subscribers = [];

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

  function connect() {
    setStatus('connecting');
    const url = window.CP.WS_URL + (localStorage.getItem('cp_token') ? `?token=${localStorage.getItem('cp_token')}` : '');
    try { ws = new WebSocket(url); }
    catch (e) { console.error('ws ctor failed', e); scheduleReconnect(); return; }

    ws.onopen = () => { setStatus('connected'); backoff = 2000; };
    ws.onclose = () => { setStatus('disconnected'); scheduleReconnect(); };
    ws.onerror = () => { try { ws.close(); } catch {} };
    ws.onmessage = (msg) => {
      let payload;
      try { payload = JSON.parse(msg.data); } catch { return; }
      subscribers.forEach((fn) => { try { fn(payload); } catch (e) { console.error(e); } });
    };
  }

  function scheduleReconnect() {
    setTimeout(connect, backoff);
    backoff = Math.min(backoff * 1.6, 30000);
  }

  function onEvent(fn) { subscribers.push(fn); }

  return { connect, onEvent };
})();
