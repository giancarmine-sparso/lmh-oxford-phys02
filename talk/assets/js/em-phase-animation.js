/* =====================================================================
   em-phase — "Electromagnetic potentials shift the phase of psi".

   PHYSICS CONTRACT — the drawing makes exactly one claim, and the code
   is arranged so that the claim cannot be broken by tweaking numbers.

   (1) PURE PHASE.  Both waves are the SAME path element geometry:

           y(u) = -amp * sin(K u),     K = 2*pi / LAM

       drawn once, then placed by a translate() only.  Amplitude,
       wavelength and shape are therefore identical by construction --
       not by agreement between two formulas.  Nothing in this file may
       scale a wave or recompute the path with a different K.

   (2) THE TRANSLATION IS THE PHASE.  For the displayed field
       sin(k x - omega t + dTheta), the crest condition gives an offset
       of (omega t - dTheta) / K in x.  The reference wave uses
       dTheta = 0, the shifted wave uses dTheta = dThetaEM.  Their
       separation is exactly -dThetaEM / K: positive phase leads, so the
       yellow wave sits to the LEFT.  Both offsets are reduced modulo
       LAM, which is invisible (the path is periodic) and keeps the
       translate() bounded.

   (3) dThetaEM = dThetaA + dThetaV, with, for uniform potentials over a
       fixed path of length L,

           dThetaA = (q/hbar) * A * L      accumulated along space
           dThetaV = -(q/hbar) * V * t     accumulated in time

       dThetaA is revealed with an ease (it is a spatial integral, so
       its growth in the animation is a reveal, not a rate); dThetaV
       grows LINEARLY in t, because that is what integrating a constant
       V over time does.  Both are drawn as positive here (i.e. qV < 0),
       so the second stage continues the first instead of undoing it.

   (4) TOTAL PHASE STAYS BELOW 2*pi.  0.6*pi + 0.8*pi = 1.4*pi.  The
       wave never wraps past a full period during the sequence, so the
       readout and the visible displacement always agree.  Raising the
       constants past 2*pi would make the two disagree.
   ===================================================================== */

(function () {
  'use strict';

  if (window.emPhaseAnimationLoaded) { return; }
  window.emPhaseAnimationLoaded = true;

  var TAU = Math.PI * 2;

  var CFG = {
    /* Geometry, in viewBox units (the SVG is 1400 x 330).  These five
       numbers must agree with the static markup: the wave window, the
       two baselines and the guide lines are drawn there. */
    x0: 120,               // left edge of the wave window
    x1: 1360,              // right edge of the wave window
    periods: 7,            // periods across that window -> LAM
    amp: 52,               // ONE amplitude, shared by both waves
    baseRef: 112,          // baseline of the reference row
    baseShift: 264,        // baseline of the shifted row
    step: 3,               // sampling step of the path, in x units

    /* motion */
    waveSpeed: 0.08,       // wavelengths per second the crests travel.
                           // Deliberately slow: the propagation is the
                           // backdrop, the relative slide is the subject.
                           // It also keeps the marked crest inside the
                           // window for the whole sequence, so the crest
                           // guide never has to jump to a neighbour.

    /* phase budget -- see physics note (4) */
    thetaA: 0.60 * Math.PI,
    thetaV: 0.80 * Math.PI,

    stages: [
      { d: 2000, label: 'No additional phase' },
      { d: 3000, label: 'Vector potential: phase accumulated along space' },
      { d: 3000, label: 'Scalar potential: phase accumulated in time' },
      { d: 2000, label: 'Total electromagnetic phase' }
    ]
  };

  var W = CFG.x1 - CFG.x0;
  var LAM = W / CFG.periods;
  var K = TAU / LAM;
  var OMEGA = TAU * CFG.waveSpeed / 1000;   // rad per millisecond

  var BOUNDS = [];
  var TOTAL = 0;
  for (var si = 0; si < CFG.stages.length; si++) {
    TOTAL += CFG.stages[si].d;
    BOUNDS.push(TOTAL);
  }

  /* The crest that carries the guide lines.  Picked once, from the
     geometry, so that at t = 0 it sits about a third of the way in and
     still has room for the drift plus the full leftward displacement. */
  var CREST_N = Math.round((K * (0.35 * W) - Math.PI / 2) / TAU);

  function smoothstep(u) {
    if (u <= 0) { return 0; }
    if (u >= 1) { return 1; }
    return u * u * (3 - 2 * u);
  }

  function wrap(x) {
    var r = x % LAM;
    return r < 0 ? r + LAM : r;
  }

  /* The one path both waves are drawn from -- physics note (1).  It runs
     one wavelength past the left edge so that a translate() in [0, LAM)
     never exposes its end. */
  function buildWavePath() {
    var from = -LAM - CFG.step;
    var to = W + CFG.step;
    var parts = [];
    var u = from;
    while (u <= to) {
      parts.push((parts.length ? 'L' : 'M') + u.toFixed(1) + ' ' +
                 (-CFG.amp * Math.sin(K * u)).toFixed(2));
      u += CFG.step;
    }
    return parts.join(' ');
  }

  function phasesAt(t) {
    var a = 0;
    var v = 0;
    if (t >= BOUNDS[0]) {
      // stage 2: reveal of the spatial integral, eased
      a = CFG.thetaA * smoothstep((t - BOUNDS[0]) / CFG.stages[1].d);
    }
    if (t >= BOUNDS[1]) {
      a = CFG.thetaA;
      // stage 3: linear in t, because it IS an integral over time
      v = CFG.thetaV * Math.min(1, (t - BOUNDS[1]) / CFG.stages[2].d);
    }
    return { a: a, v: v, total: a + v };
  }

  function stageAt(t) {
    for (var i = 0; i < BOUNDS.length; i++) {
      if (t < BOUNDS[i]) { return i; }
    }
    return BOUNDS.length - 1;
  }

  function init(root) {
    var el = {
      strip: root.querySelector('#em-phase-strip-pattern'),
      refWave: root.querySelector('#em-phase-reference-wave'),
      shiftWave: root.querySelector('#em-phase-shifted-wave'),
      refPath: root.querySelector('#em-phase-reference-path'),
      shiftPath: root.querySelector('#em-phase-shifted-path'),
      guideRef: root.querySelector('#em-phase-guide-ref'),
      guideShift: root.querySelector('#em-phase-guide-shift'),
      offset: root.querySelector('#em-phase-offset'),
      offsetLine: root.querySelector('#em-phase-offset-line'),
      offsetLabel: root.querySelector('#em-phase-offset-label'),
      termA: root.querySelector('#em-phase-term-a'),
      termV: root.querySelector('#em-phase-term-v'),
      total: root.querySelector('#em-phase-total'),
      valueA: root.querySelector('#em-phase-value-a'),
      valueV: root.querySelector('#em-phase-value-v'),
      stageLabel: root.querySelector('#em-phase-stage-label'),
      readout: root.querySelector('#em-phase-readout'),
      takeaway: root.querySelector('#em-phase-takeaway'),
      playPause: root.querySelector('#em-phase-playpause'),
      restart: root.querySelector('#em-phase-restart'),
      scrub: root.querySelector('#em-phase-scrub')
    };

    var name;
    for (name in el) {
      if (Object.prototype.hasOwnProperty.call(el, name) && !el[name]) {
        return null;                        // markup incomplete: stay out
      }
    }

    var d = buildWavePath();
    el.refPath.setAttribute('d', d);
    el.shiftPath.setAttribute('d', d);      // same geometry, no exceptions

    /* the slider spans the sequence, so the markup never has to know how
       long the sequence is */
    el.scrub.min = '0';
    el.scrub.max = String(TOTAL);
    el.scrub.step = '10';

    var reduceMotion = window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    var clock = 0;
    var playing = false;
    var scrubbing = false;
    var rafId = 0;
    var lastTs = 0;
    var lastStage = -1;

    function setStage(stage) {
      if (stage === lastStage) { return; }
      lastStage = stage;
      el.stageLabel.textContent = CFG.stages[stage].label;
      el.termA.className = 'em-phase-term' +
        (stage === 1 ? ' em-phase-is-active' : stage > 1 ? ' em-phase-is-past' : '');
      el.termV.className = 'em-phase-term' +
        (stage === 2 ? ' em-phase-is-active' : stage > 2 ? ' em-phase-is-past' : '');
      el.total.className = 'em-phase-total' +
        (stage === 3 ? ' em-phase-is-active' : '');
      el.takeaway.className = 'em-phase-takeaway' +
        (stage === 3 ? ' em-phase-is-visible' : '');
    }

    function fmt(theta) {
      return (theta / Math.PI).toFixed(2) + ' π';
    }

    function render(t) {
      var p = phasesAt(t);
      var omegaT = OMEGA * t;

      /* physics note (2): translate only -- never scale, never rebuild */
      var sRef = wrap(omegaT / K);
      var sShift = wrap((omegaT - p.total) / K);

      el.refWave.setAttribute('transform',
        'translate(' + (CFG.x0 + sRef).toFixed(2) + ' ' + CFG.baseRef + ')');
      el.shiftWave.setAttribute('transform',
        'translate(' + (CFG.x0 + sShift).toFixed(2) + ' ' + CFG.baseShift + ')');

      /* the phase strip is the same translation, so its stripe spacing
         is fixed by the pattern tile and can never breathe */
      el.strip.setAttribute('patternTransform',
        'translate(' + (CFG.x0 + sShift).toFixed(2) + ' 0)');

      var xRef = CFG.x0 + (Math.PI / 2 + omegaT + TAU * CREST_N) / K;
      var xShift = xRef - p.total / K;
      el.guideRef.setAttribute('x1', xRef.toFixed(2));
      el.guideRef.setAttribute('x2', xRef.toFixed(2));
      el.guideShift.setAttribute('x1', xShift.toFixed(2));
      el.guideShift.setAttribute('x2', xShift.toFixed(2));

      var gap = xRef - xShift;
      if (gap > 8) {
        el.offset.setAttribute('opacity', '1');
        el.offsetLine.setAttribute('x1', xShift.toFixed(2));
        el.offsetLine.setAttribute('x2', xRef.toFixed(2));
        el.offsetLabel.setAttribute('x', (xShift + gap / 2).toFixed(2));
      } else {
        el.offset.setAttribute('opacity', '0');
      }

      el.valueA.textContent = '= ' + fmt(p.a);
      el.valueV.textContent = '= ' + fmt(p.v);
      el.readout.textContent = fmt(p.total);

      /* the slider doubles as the progress bar: keep the knob and the
         painted-in fill on the clock, unless the user is dragging it */
      if (!scrubbing) { el.scrub.value = String(Math.round(t)); }
      el.scrub.style.setProperty('--em-phase-progress',
        (100 * t / TOTAL).toFixed(2) + '%');

      setStage(stageAt(t));
    }

    function setPlaying(state) {
      playing = state;
      el.playPause.textContent = state ? 'Pause' : 'Play';
      el.playPause.setAttribute('aria-label',
        state ? 'Pause the animation' : 'Play the animation');
      if (!state && rafId) { cancelAnimationFrame(rafId); rafId = 0; }
    }

    function frame(ts) {
      rafId = 0;
      if (!playing) { return; }
      var dt = lastTs ? ts - lastTs : 0;
      lastTs = ts;
      if (dt > 100) { dt = 100; }           // returning from a hidden tab
      clock += dt;
      if (clock >= TOTAL) {
        clock = TOTAL;
        render(clock);
        setPlaying(false);                  // hold the final comparison
        return;
      }
      render(clock);
      rafId = requestAnimationFrame(frame);
    }

    function play() {
      if (playing) { return; }
      if (clock >= TOTAL) { clock = 0; }
      lastTs = 0;
      setPlaying(true);
      rafId = requestAnimationFrame(frame);
    }

    function pause() {
      setPlaying(false);
    }

    function reset(toEnd) {
      setPlaying(false);
      clock = toEnd ? TOTAL : 0;
      lastTs = 0;
      render(clock);
    }

    el.playPause.addEventListener('click', function () {
      if (playing) { pause(); } else { play(); }
      el.playPause.blur();                  // keep arrow keys on reveal.js
    });
    el.restart.addEventListener('click', function () {
      reset(false);
      play();
      el.restart.blur();
    });

    /* Dragging the slider takes over the clock: the sequence is a
       function of t alone, so seeking is the whole of manual control --
       park on any phase, then hand the clock back with Play. */
    el.scrub.addEventListener('input', function () {
      scrubbing = true;
      pause();
      var v = parseFloat(el.scrub.value);
      clock = isNaN(v) ? 0 : Math.max(0, Math.min(TOTAL, v));
      render(clock);
      scrubbing = false;
    });
    ['change', 'mouseup', 'touchend'].forEach(function (ev) {
      el.scrub.addEventListener(ev, function () { el.scrub.blur(); });
    });

    /* a focused control must never swallow, or duplicate, a slide change */
    ['keydown', 'keyup', 'keypress'].forEach(function (ev) {
      root.addEventListener(ev, function (e) {
        if (e.target === el.playPause || e.target === el.restart ||
            e.target === el.scrub) {
          e.stopPropagation();
        }
      });
    });

    reset(reduceMotion);

    return {
      enter: function () {
        /* reduced motion: the final static comparison, phase offset
           already at 1.4 pi, and nothing moves unless asked */
        reset(reduceMotion);
        if (!reduceMotion) { play(); }
      },
      leave: function () {
        pause();
      }
    };
  }

  function boot() {
    var root = document.getElementById('em-phase-root');
    if (!root || root.getAttribute('data-em-phase-ready') === '1') { return; }
    var api = init(root);
    if (!api) { return; }
    root.setAttribute('data-em-phase-ready', '1');

    function sync(slide) {
      if (slide && slide.contains(root)) { api.enter(); } else { api.leave(); }
    }

    if (window.Reveal && typeof window.Reveal.on === 'function') {
      window.Reveal.on('ready', function (e) { sync(e.currentSlide); });
      window.Reveal.on('slidechanged', function (e) { sync(e.currentSlide); });
      if (window.Reveal.isReady && window.Reveal.isReady()) {
        sync(window.Reveal.getCurrentSlide());
      }
    } else {
      /* standalone HTML opened without reveal.js: fall back to visibility */
      if (window.IntersectionObserver) {
        new IntersectionObserver(function (entries) {
          if (entries[0].isIntersecting) { api.enter(); } else { api.leave(); }
        }, { threshold: 0.25 }).observe(root);
      } else {
        api.enter();
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
}());
