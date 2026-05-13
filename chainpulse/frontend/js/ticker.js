window.CPTicker = (function () {
  const track = document.getElementById('ticker-track');
  const items = [];
  let offset = 0;

  function add(event) {
    if (event.predicted_delay_max_days == null && event.predicted_delay_min_days == null) return;
    const sev = (event.severity || 'low').toLowerCase();
    const icon = ({
      critical: '⚠', high: '⚠', medium: '◐', low: '·'
    })[sev] || '·';
    const loc = event.location_name || event.country_code || 'Unknown';
    const dMin = event.predicted_delay_min_days ?? '?';
    const dMax = event.predicted_delay_max_days ?? '?';
    items.push(
      `<span class="tk-icon--${sev}">${icon}</span> ${loc} → ${dMin}–${dMax}d delay`
    );
    if (items.length > 30) items.shift();
    render();
  }

  function render() {
    const html = items.map((s) => s).join(' <span class="tk-sep">·</span> ');
    track.innerHTML = html + ' <span class="tk-sep">·</span> ' + html;
  }

  function loop() {
    offset -= 0.7; // px per frame ≈ 40px/sec @ 60fps
    if (Math.abs(offset) > track.scrollWidth / 2) offset = 0;
    track.style.transform = `translateX(${offset}px)`;
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
  return { add };
})();
