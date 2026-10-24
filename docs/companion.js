(() => {
  'use strict';
  const companion = document.getElementById('writher-companion');
  if (!companion) return;
  const desktop = matchMedia('(min-width: 1280px) and (pointer: fine)');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const hello = companion.querySelector('.companion-hello');
  const pause = companion.querySelector('.companion-pause');
  const whisper = companion.querySelector('.companion-whisper');
  const closingLogo = document.querySelector('.closing > .brand-logo');
  const stops = [
    ['.hero', 'right', .46, 'A little company.', '#38bdf8'],
    ['#modes', 'left', .42, 'Thoughts into words.', '#38bdf8'],
    ['#features', 'right', .55, 'Close to you. Local to your PC.', '#a78bfa'],
    ['#demo', 'right', .4, 'This is me at work.', '#38bdf8'],
    ['#community', 'left', .5, 'A little different. Together.', '#a78bfa'],
    ['#download', 'right', .58, 'Ready when you are.', '#38bdf8'],
    ['.questions-section', 'left', .42, 'Curiosity welcome.', '#a78bfa'],
    ['#compare', 'right', .5, 'Find your own flow.', '#38bdf8'],
    ['.closing', 'right', .55, 'See you on your desktop.', '#a78bfa']
  ].map(([selector, side, height, message, color]) => ({element: document.querySelector(selector), side, height, message, color, top: 0}));
  let active = -1, position = null, flight = null, frame = 0, scheduled = 0;
  let paused = false, held = false, enabled = false, greeted = false;
  try { paused = sessionStorage.getItem('writher-flight-paused') === 'true'; } catch (_) { /* Storage is optional. */ }
  const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
  const ease = value => value * value * (3 - 2 * value);
  const mix = (a, b, amount) => a + (b - a) * amount;

  function measure() {
    stops.forEach(stop => { stop.top = stop.element.getBoundingClientRect().top + scrollY; });
  }
  function rail(side) {
    const margin = (innerWidth - 1160) / 2 + 32;
    return side === 'left' ? (margin - 48) / 2 : innerWidth - (margin + 48) / 2;
  }
  function target(stop) {
    const drift = Math.sin((scrollY - stop.top) / 320) * 24;
    return {x: rail(stop.side), y: clamp(innerHeight * stop.height + drift, 110, innerHeight - 160)};
  }
  function paint(point, tilt = 0) {
    position = point;
    companion.style.transform = `translate3d(${point.x.toFixed(2)}px,${point.y.toFixed(2)}px,0)`;
    companion.style.setProperty('--companion-tilt', `${tilt.toFixed(1)}deg`);
  }
  function stopFlight() {
    cancelAnimationFrame(frame); frame = 0; flight = null;
    companion.dataset.flying = 'false';
    hello.disabled = false; pause.disabled = false;
    companion.style.setProperty('--companion-tilt', '0deg');
  }
  function tick(now) {
    frame = 0;
    if (!flight || !enabled || paused || held || document.hidden) return;
    const t = clamp((now - flight.started) / flight.duration, 0, 1);
    const destination = target(stops[active]);
    let point;
    if (flight.crossing) {
      // Cross only the empty padding above a section. If it scrolls away,
      // the crossing travels offscreen, never through the reading area.
      const corridor = clamp(flight.corridor - scrollY + 16, -130, innerHeight + 40);
      if (t < .25) {
        point = {x: flight.from.x, y: mix(flight.from.y, corridor, ease(t * 4))};
      } else if (t < .75) {
        const progress = ease((t - .25) * 2);
        point = {x: mix(flight.from.x, destination.x, progress), y: corridor + Math.sin(progress * Math.PI) * 7};
      } else {
        point = {x: destination.x, y: mix(corridor, destination.y, ease((t - .75) * 4))};
      }
    } else {
      const progress = ease(t);
      point = {x: mix(flight.from.x, destination.x, progress) + Math.sin(t * Math.PI) * 8, y: mix(flight.from.y, destination.y, progress)};
    }
    paint(point, Math.sin(t * Math.PI * 2) * (flight.crossing ? 14 : 7));
    if (t < 1) frame = requestAnimationFrame(tick);
    else { stopFlight(); queueUpdate(); }
  }
  function update() {
    scheduled = 0;
    if (!enabled || paused || held || document.hidden) return;
    const focus = scrollY + innerHeight * .5;
    let next = 0;
    stops.forEach((stop, index) => { if (stop.top <= focus) next = index; });
    // Finish the current crossing before accepting a new destination.
    // Rapid scrolling can otherwise strand the mascot over the text.
    if (flight && next !== active) return;
    const changed = next !== active;
    const previous = active;
    active = next;
    const stop = stops[active];
    companion.dataset.section = stop.element.id || stop.element.classList[0];
    companion.style.setProperty('--companion-color', stop.color);
    whisper.textContent = stop.message;
    if (!position || previous < 0) { paint(target(stop)); return; }
    if (flight) return;
    const destination = target(stop);
    if (!changed && Math.hypot(position.x - destination.x, position.y - destination.y) < 1) return;
    const crossing = changed && previous >= 0 && stops[previous].side !== stop.side;
    flight = {from: {...position}, started: performance.now(), duration: crossing ? 1350 : 550, crossing, corridor: stops[Math.max(previous, active)].top};
    companion.dataset.flying = 'true';
    hello.disabled = true; pause.disabled = true;
    frame = requestAnimationFrame(tick);
  }
  function queueUpdate() {
    if (!scheduled && enabled && !paused && !held && !document.hidden) scheduled = requestAnimationFrame(update);
  }
  function pauseLabel() {
    companion.dataset.paused = String(paused);
    pause.textContent = paused ? 'Fly' : 'Pause';
    pause.setAttribute('aria-label', paused ? "Resume WritHer's flight" : "Pause WritHer's flight");
  }
  function sync() {
    stopFlight(); cancelAnimationFrame(scheduled); scheduled = 0;
    enabled = desktop.matches && !reduced.matches;
    companion.hidden = !enabled;
    companion.getAnimations({subtree: true}).forEach(animation => animation.cancel());
    closingLogo.getAnimations().forEach(animation => animation.cancel());
    position = null; active = -1; held = false;
    measure(); pauseLabel();
    if (enabled) {
      paint(target(stops[0]));
      if (!paused) update();
    }
  }
  pause.addEventListener('click', () => {
    paused = !paused; stopFlight(); pauseLabel();
    hello.getAnimations().forEach(animation => animation.cancel());
    try { sessionStorage.setItem('writher-flight-paused', String(paused)); } catch (_) { /* Storage is optional. */ }
    if (!paused) queueUpdate();
  });
  hello.addEventListener('click', () => {
    if (paused || reduced.matches) return;
    hello.getAnimations().forEach(animation => animation.cancel());
    hello.animate([
      {transform: 'translateY(0) rotate(0)'},
      {transform: 'translateY(-12px) rotate(-18deg)', offset: .3},
      {transform: 'translateY(-7px) rotate(14deg)', offset: .6},
      {transform: 'translateY(0) rotate(0)'}
    ], {duration: 850, easing: 'ease-in-out'});
  });
  companion.addEventListener('pointerenter', () => { held = true; stopFlight(); });
  companion.addEventListener('pointerleave', () => { held = companion.contains(document.activeElement); queueUpdate(); });
  companion.addEventListener('focusin', () => { held = true; stopFlight(); });
  companion.addEventListener('focusout', event => { held = companion.contains(event.relatedTarget) || companion.matches(':hover'); queueUpdate(); });
  addEventListener('scroll', queueUpdate, {passive: true});
  addEventListener('resize', sync);
  desktop.addEventListener('change', sync);
  reduced.addEventListener('change', sync);
  document.addEventListener('toggle', () => { measure(); queueUpdate(); }, true);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { stopFlight(); cancelAnimationFrame(scheduled); scheduled = 0; }
    else sync();
  });
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(entries => {
      if (!entries[0].isIntersecting || greeted || desktop.matches || reduced.matches || paused) return;
      greeted = true;
      closingLogo.animate([{transform: 'rotate(0)'}, {transform: 'translateY(-8px) rotate(-12deg)'}, {transform: 'rotate(8deg)'}, {transform: 'rotate(0)'}], {duration: 850, easing: 'ease-in-out'});
    }, {threshold: 1}).observe(closingLogo);
  }
  if (document.fonts) document.fonts.ready.then(() => { measure(); queueUpdate(); });
  sync();
})();
