// Runtime config. Override via window.CHAINPULSE_CONFIG before this loads.
(function () {
  const def = {
    API_BASE: 'https://chainpulse.onrender.com',
    WS_URL:   'wss://chainpulse.onrender.com/ws/events',
    EVENT_TTL_MS: 5 * 60 * 1000,      // pin lifetime
    EVENT_FADE_START_MS: 4 * 60 * 1000,
    SIDEBAR_MAX: 200,
  };
  window.CP = Object.assign({}, def, window.CHAINPULSE_CONFIG || {});
})();
