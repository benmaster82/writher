(() => {
  'use strict';
  document.documentElement.classList.add('js');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const menu = document.querySelector('.menu-toggle');
  const nav = document.getElementById('site-nav');
  if (menu && nav) {
    menu.hidden = false;
    const closeMenu = () => { menu.setAttribute('aria-expanded', 'false'); nav.classList.remove('is-open'); };
    menu.addEventListener('click', () => {
      const open = menu.getAttribute('aria-expanded') !== 'true';
      menu.setAttribute('aria-expanded', String(open)); nav.classList.toggle('is-open', open);
    });
    nav.addEventListener('click', event => { if (event.target.closest('a')) closeMenu(); });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && menu.getAttribute('aria-expanded') === 'true') { closeMenu(); menu.focus(); }
    });
  }

  const experience = document.getElementById('hero-experience');
  if (experience) {
    const button = document.getElementById('play-demo');
    const selector = document.querySelector('.demo-selector');
    const status = experience.querySelector('.widget-status');
    const text = document.getElementById('demo-text');
    const title = document.getElementById('demo-title');
    const shortcut = document.getElementById('demo-shortcut');
    const live = document.getElementById('demo-live');
    const modes = {
      dictation: { title:'A note to your team', shortcut:'Hold AltGr, speak, release', quote:'“The first draft is ready. Let’s review it together tomorrow.”', text:'The first draft is ready. Let’s review it together tomorrow.', thinking:'Writing…', done:'Text written.' },
      assistant: { title:'Your reminders', shortcut:'Hold Ctrl + Alt + R', quote:'“Remind me to review the draft tomorrow at ten.”', text:'Review the draft\nTomorrow at 10:00', thinking:'Thinking…', done:'Reminder saved.' }
    };
    let timers = [], running = false;
    const schedule = (fn, delay) => timers.push(window.setTimeout(fn, delay));
    function clearTimers() { timers.forEach(window.clearTimeout); timers = []; running = false; }
    function reset(mode) {
      clearTimers(); experience.dataset.mode = mode; experience.dataset.phase = 'idle';
      status.textContent = 'Ready to listen'; title.textContent = modes[mode].title;
      shortcut.textContent = modes[mode].shortcut; text.textContent = modes[mode].quote;
      button.textContent = 'Play demo'; live.textContent = '';
      selector.querySelectorAll('button').forEach(item => item.setAttribute('aria-pressed', String(item.dataset.demo === mode)));
    }
    function finish(data) {
      running = false; experience.dataset.phase = 'done'; status.textContent = 'Done!';
      button.textContent = 'Replay demo'; live.textContent = data.done + ' ' + data.text;
    }
    button.hidden = false; selector.hidden = false;
    button.addEventListener('click', () => {
      if (running) { reset(experience.dataset.mode); return; }
      clearTimers(); running = true; const data = modes[experience.dataset.mode];
      if (reduced.matches) { text.textContent = data.text; finish(data); return; }
      experience.dataset.phase = 'listening'; status.textContent = 'Listening…'; text.textContent = data.quote;
      button.textContent = 'Stop demo'; live.textContent = 'Illustrative demo: listening.';
      schedule(() => { experience.dataset.phase = 'thinking'; status.textContent = data.thinking; }, 1500);
      schedule(() => {
        let index = 0; text.textContent = '';
        function type() { index += 2; text.textContent = data.text.slice(0,index); if (index < data.text.length) schedule(type,35); else finish(data); }
        type();
      }, 2300);
    });
    selector.querySelectorAll('button').forEach(item => item.addEventListener('click', () => reset(item.dataset.demo)));
    const hero = document.querySelector('.hero');
    hero.addEventListener('pointermove', event => {
      if (reduced.matches || event.pointerType !== 'mouse') return;
      const bounds = experience.querySelector('.hero-widget').getBoundingClientRect();
      experience.style.setProperty('--eye-x', Math.max(-3,Math.min(3,(event.clientX-bounds.left-bounds.width/2)/80))+'px');
      experience.style.setProperty('--eye-y', Math.max(-2,Math.min(2,(event.clientY-bounds.top-bounds.height/2)/100))+'px');
    });
    hero.addEventListener('pointerleave', () => { experience.style.setProperty('--eye-x','0px'); experience.style.setProperty('--eye-y','0px'); });
    reduced.addEventListener('change', () => { reset(experience.dataset.mode); experience.style.setProperty('--eye-x','0px'); experience.style.setProperty('--eye-y','0px'); });
    document.addEventListener('visibilitychange', () => { if (document.hidden && running) reset(experience.dataset.mode); });
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(entries => { if (!entries[0].isIntersecting && running) reset(experience.dataset.mode); }).observe(hero);
    }
  }

  const stage = document.getElementById('flow-stage');
  if (stage) {
    const scenes = {
      write: {app:'Draft · Email', label:'To the team', heading:'A little less typing.', text:'The first draft is ready. Let’s review it together tomorrow.', result:'Written where you work.', status:'Done!'},
      note: {app:'WritHer · Notes', label:'A thought worth keeping', heading:'Try a shorter introduction.', text:'Lead with the example. Move the background into the second paragraph.', result:'Note saved on your PC.', status:'Note saved'},
      remind: {app:'WritHer · Reminders', label:'Tomorrow at 10:00', heading:'Review the draft.', text:'A reminder for the next step, so you can get back to this one.', result:'Reminder added.', status:'Reminder set'}
    };
    const steps = Array.from(document.querySelectorAll('.flow-step'));
    const previewButtons = document.querySelectorAll('[data-show-scene]');
    function showScene(name) {
      const data = scenes[name]; stage.dataset.scene = name;
      ['app','label','heading','text','result'].forEach(field => { document.getElementById('flow-'+field).textContent = data[field]; });
      stage.querySelector('.flow-widget-label').textContent = data.status;
      steps.forEach(step => step.classList.toggle('is-active', step.dataset.scene === name));
      previewButtons.forEach(item => item.setAttribute('aria-pressed', String(item.dataset.showScene === name)));
    }
    previewButtons.forEach(item => {
      item.hidden = false;
      item.addEventListener('click', () => {
        showScene(item.dataset.showScene);
        if (window.innerWidth <= 760) stage.scrollIntoView({behavior:reduced.matches?'instant':'smooth',block:'start'});
      });
    });
    let frame = null;
    function onScroll() {
      if (frame !== null || window.innerWidth <= 760 || reduced.matches) return;
      frame = window.requestAnimationFrame(() => {
        frame = null;
        const middle = window.innerHeight * .5;
        const visible = steps.filter(step => { const rect=step.getBoundingClientRect(); return rect.top < window.innerHeight && rect.bottom > 0; });
        if (visible.length) {
          const nearest = visible.reduce((best, step) => Math.abs(step.getBoundingClientRect().top + step.offsetHeight/2-middle) < Math.abs(best.getBoundingClientRect().top + best.offsetHeight/2-middle) ? step : best);
          if (stage.dataset.scene !== nearest.dataset.scene) showScene(nearest.dataset.scene);
        }
      });
    }
    window.addEventListener('scroll',onScroll,{passive:true});
  }

  const videoButton = document.getElementById('load-video');
  if (videoButton) {
    videoButton.hidden = false;
    videoButton.addEventListener('click', () => {
      const iframe = document.createElement('iframe');
      iframe.src = 'https://www.youtube-nocookie.com/embed/lfV0LF3EGMw?autoplay=1';
      iframe.title = 'WritHer demo: offline voice dictation and local voice assistant for Windows';
      iframe.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
      iframe.referrerPolicy = 'strict-origin-when-cross-origin';
      document.getElementById('video-container').replaceChildren(iframe);
      iframe.focus();
    });
  }
})();
