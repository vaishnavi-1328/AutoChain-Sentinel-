window.CPToast = (function () {
  let active = null;
  function show(text, ms = 4000) {
    if (active) active.remove();
    const div = document.createElement('div');
    div.className = 'toast';
    div.textContent = text;
    document.body.appendChild(div);
    active = div;
    setTimeout(() => { if (div === active) { div.remove(); active = null; } }, ms);
  }
  return { show };
})();
