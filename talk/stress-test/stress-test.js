(function () {
  'use strict';

  var STAGE_ORDER = [
    'calibration',
    'dom',
    'canvas',
    'ab-single',
    'representative',
    'ab-multi',
    'gpu',
    'cpu',
    'soak'
  ];

  var STAGE_LABELS = {
    calibration: 'Calibrazione',
    dom: 'DOM e compositing',
    canvas: 'Canvas sintetico',
    'ab-single': 'Animazione HTML ×1',
    representative: 'HTML + video 1080p',
    'ab-multi': 'Animazione HTML ×4',
    gpu: 'Shader WebGL',
    cpu: 'Carico CPU',
    soak: 'Picco e soak'
  };

  var DURATIONS = {
    quick: {
      calibration: 10,
      dom: 15,
      canvas: 20,
      'ab-single': 20,
      representative: 25,
      'ab-multi': 25,
      gpu: 20,
      cpu: 20,
      soak: 25
    },
    full: {
      calibration: 30,
      dom: 60,
      canvas: 60,
      'ab-single': 60,
      representative: 90,
      'ab-multi': 90,
      gpu: 90,
      cpu: 90,
      soak: 330
    }
  };

  var DIAGNOSTIC_DURATIONS = {
    calibration: 1.5,
    dom: 1.5,
    canvas: 1.5,
    'ab-single': 1.8,
    representative: 2.5,
    'ab-multi': 2.2,
    gpu: 2,
    cpu: 2,
    soak: 3
  };

  var params = new URLSearchParams(window.location.search);
  var diagnosticMode = params.get('diagnostic') === '1';
  var autoStart = params.get('autostart') === '1';
  var AB_ASSET = new URL('assets/ab-animation.html', document.baseURI).href;
  var VIDEO_ASSET = new URL('assets/constant-shift-1080p.mp4', document.baseURI).href;

  var state = {
    initialized: false,
    running: false,
    profile: null,
    durations: null,
    stage: null,
    current: null,
    workload: null,
    reports: [],
    report: null,
    runStartedAt: 0,
    refreshHz: 60,
    baselineMs: 1000 / 60,
    liveFps: 60,
    monitorRaf: 0,
    lastRaf: 0,
    lastHudUpdate: 0,
    lowFpsSince: 0,
    advancing: false,
    abortReason: null,
    abortKind: null,
    stableLoads: {
      domNodes: 240,
      canvasParticles: 20000,
      abCopies: 4,
      gpuIterations: 12,
      cpuWorkers: 1,
      cpuMainMs: 1.5
    },
    environment: null,
    hud: null,
    toastTimer: 0
  };

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function sum(values) {
    var total = 0;
    for (var i = 0; i < values.length; i++) total += values[i];
    return total;
  }

  function mean(values) {
    return values.length ? sum(values) / values.length : 0;
  }

  function quantile(values, q) {
    if (!values.length) return 0;
    var sorted = values.slice().sort(function (a, b) { return a - b; });
    var index = (sorted.length - 1) * q;
    var lower = Math.floor(index);
    var upper = Math.ceil(index);
    if (lower === upper) return sorted[lower];
    return sorted[lower] + (sorted[upper] - sorted[lower]) * (index - lower);
  }

  function median(values) {
    return quantile(values, 0.5);
  }

  function round(value, digits) {
    var factor = Math.pow(10, digits || 0);
    return Math.round(value * factor) / factor;
  }

  function makeElement(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function setStyles(node, styles) {
    Object.keys(styles).forEach(function (key) {
      node.style[key] = styles[key];
    });
    return node;
  }

  function formatClock(seconds) {
    var safe = Math.max(0, Math.ceil(seconds));
    var minutes = Math.floor(safe / 60);
    var remainder = safe % 60;
    return String(minutes).padStart(2, '0') + ':' + String(remainder).padStart(2, '0');
  }

  function stageOf(section) {
    return section && section.dataset ? section.dataset.stressStage || null : null;
  }

  function presentStage() {
    if (!window.Reveal || !window.Reveal.getCurrentSlide) return null;
    return stageOf(window.Reveal.getCurrentSlide());
  }

  function captureEnvironment() {
    var memory = performance.memory || null;
    return {
      userAgent: navigator.userAgent,
      platform: navigator.userAgentData && navigator.userAgentData.platform
        ? navigator.userAgentData.platform
        : navigator.platform || 'N/D',
      language: navigator.language,
      logicalProcessors: navigator.hardwareConcurrency || null,
      deviceMemoryGiB: navigator.deviceMemory || null,
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
        devicePixelRatio: window.devicePixelRatio || 1
      },
      screen: {
        width: window.screen.width,
        height: window.screen.height,
        colorDepth: window.screen.colorDepth
      },
      jsHeapLimitBytes: memory ? memory.jsHeapSizeLimit : null,
      initialHeapBytes: memory ? memory.usedJSHeapSize : null,
      online: navigator.onLine,
      documentProtocol: window.location.protocol
    };
  }

  function createHud() {
    var hud = makeElement('div');
    hud.id = 'stress-hud';

    var stage = makeElement('span', 'hud-stage', 'Pronto');
    var time = makeElement('span', 'hud-value', '00:00');
    var fps = makeElement('span', 'hud-value', '— FPS');
    var p95 = makeElement('span', 'hud-value', 'p95 —');
    var stop = makeElement('button', 'hud-stop', '×');
    stop.type = 'button';
    stop.title = 'Interrompi il test (X)';
    stop.setAttribute('aria-label', 'Interrompi il test');
    stop.addEventListener('click', function () {
      abortRun('Interrotto dall’utente', 'user');
    });

    hud.append(stage, time, fps, p95, stop);
    document.body.appendChild(hud);

    var toast = makeElement('div');
    toast.id = 'stress-toast';
    document.body.appendChild(toast);

    state.hud = {
      root: hud,
      stage: stage,
      time: time,
      fps: fps,
      p95: p95,
      stop: stop,
      toast: toast
    };
  }

  function showToast(message) {
    if (!state.hud) return;
    window.clearTimeout(state.toastTimer);
    state.hud.toast.textContent = message;
    state.hud.toast.classList.add('is-visible');
    state.toastTimer = window.setTimeout(function () {
      state.hud.toast.classList.remove('is-visible');
    }, 2600);
  }

  function setHudStatus(node, status) {
    node.classList.remove('hud-warn', 'hud-fail');
    if (status === 'warn') node.classList.add('hud-warn');
    if (status === 'fail') node.classList.add('hud-fail');
  }

  function updateHud(now) {
    if (!state.hud || !state.current) return;
    var elapsed = (now - state.current.startedAt) / 1000;
    var remaining = state.current.durationSec - elapsed;
    var recent = state.current.frames.filter(function (frame) {
      return elapsed * 1000 - frame.at <= 2000;
    }).map(function (frame) {
      return frame.delta;
    });
    var p95 = quantile(recent, 0.95);
    var ratio = state.liveFps / Math.max(1, state.refreshHz);
    var status = ratio < 0.5 ? 'fail' : ratio < 0.75 ? 'warn' : 'pass';

    state.hud.stage.textContent = STAGE_LABELS[state.stage] || state.stage;
    state.hud.time.textContent = formatClock(remaining);
    state.hud.fps.textContent = Math.round(state.liveFps) + ' FPS';
    state.hud.p95.textContent = 'p95 ' + (p95 ? Math.round(p95) + ' ms' : '—');
    setHudStatus(state.hud.fps, status);
    setHudStatus(state.hud.p95, p95 > state.baselineMs * 4 ? 'fail' : p95 > state.baselineMs * 2 ? 'warn' : 'pass');
  }

  function getLiveFps(windowMs) {
    if (!state.current || !state.current.frames.length) return state.refreshHz;
    var elapsed = performance.now() - state.current.startedAt;
    var frames = state.current.frames.filter(function (frame) {
      return elapsed - frame.at <= (windowMs || 2000);
    });
    if (frames.length < 2) return state.refreshHz;
    var deltas = frames.map(function (frame) { return frame.delta; });
    return clamp(1000 / mean(deltas), 0, 1000);
  }

  function canRamp() {
    if (!state.current) return false;
    var elapsed = performance.now() - state.current.startedAt;
    return elapsed > 2500 && state.liveFps >= 30;
  }

  function recordError(kind, message) {
    if (!state.current) return;
    state.current.errors.push({
      atMs: round(performance.now() - state.current.startedAt, 1),
      kind: kind,
      message: String(message || 'Errore sconosciuto').slice(0, 500)
    });
  }

  function createStageApi(name) {
    return {
      name: name,
      profile: state.profile,
      diagnostic: diagnosticMode,
      durationSec: state.current.durationSec,
      canRamp: canRamp,
      getFps: function () { return state.liveFps; },
      setLoad: function (key, value) {
        if (!state.current) return;
        state.current.load[key] = value;
        if (key in state.stableLoads && state.liveFps >= 30) {
          state.stableLoads[key] = value;
        }
      },
      setMeta: function (key, value) {
        if (state.current) state.current.meta[key] = value;
      },
      recordError: recordError,
      registerVideo: function (video) {
        if (!state.current) return;
        var quality = video.getVideoPlaybackQuality ? video.getVideoPlaybackQuality() : null;
        state.current.videos.push({
          element: video,
          initialTotal: quality ? quality.totalVideoFrames : 0,
          initialDropped: quality ? quality.droppedVideoFrames : 0
        });
      },
      contextLost: function () {
        if (!state.current) return;
        state.current.contextLosses += 1;
        recordError('webgl', 'Contesto WebGL perso');
        if (!diagnosticMode) abortRun('Contesto WebGL perso', 'safety');
      }
    };
  }

  function beginStage(name) {
    if (!state.running || state.current || STAGE_ORDER.indexOf(name) < 0) return;
    var section = document.querySelector('[data-stress-stage="' + name + '"]');
    var mount = section ? section.querySelector('.workload-mount') : null;
    var duration = state.durations[name];

    state.stage = name;
    state.lastRaf = 0;
    state.lowFpsSince = 0;
    state.current = {
      name: name,
      startedAt: performance.now(),
      durationSec: duration,
      frames: [],
      longTasks: [],
      errors: [],
      videos: [],
      contextLosses: 0,
      load: {},
      meta: {},
      memoryStart: performance.memory ? performance.memory.usedJSHeapSize : null
    };

    try {
      state.workload = WORKLOADS[name](mount, createStageApi(name)) || null;
    } catch (error) {
      recordError('workload', error && error.stack ? error.stack : error);
      state.workload = null;
    }

    state.hud.root.classList.add('is-running');
    updateHud(performance.now());
  }

  function fpsForTimeWindow(frames, fromMs, toMs) {
    var selected = frames.filter(function (frame) {
      return frame.at >= fromMs && frame.at <= toMs;
    });
    if (!selected.length) return 0;
    return 1000 / mean(selected.map(function (frame) { return frame.delta; }));
  }

  function chooseRefresh(rawHz) {
    var common = [30, 50, 60, 75, 90, 100, 120, 144, 165, 180, 240];
    var best = common[0];
    var distance = Math.abs(rawHz - best);
    common.forEach(function (candidate) {
      var nextDistance = Math.abs(rawHz - candidate);
      if (nextDistance < distance) {
        best = candidate;
        distance = nextDistance;
      }
    });
    return distance / Math.max(1, best) <= 0.1 ? best : Math.round(rawHz);
  }

  function classifyStage(result) {
    if (result.name === 'calibration') return 'info';
    if (result.errors.length || result.contextLosses) return 'fail';

    var refreshRatio = result.fpsMedian / Math.max(1, state.refreshHz);
    var realistic = result.name === 'ab-single' || result.name === 'representative';

    if (realistic) {
      if (
        refreshRatio >= 0.9 &&
        result.missedFrameRatio <= 0.02 &&
        result.videoDropRatio <= 0.01 &&
        result.maxFrameMs <= 500
      ) return 'pass';

      if (
        refreshRatio >= 0.75 &&
        result.missedFrameRatio <= 0.05 &&
        result.videoDropRatio <= 0.05 &&
        result.maxFrameMs <= 1000
      ) return 'warn';

      return 'fail';
    }

    if (refreshRatio >= 0.75 && result.maxFrameMs <= 500) return 'pass';
    if (refreshRatio >= 0.5 && result.maxFrameMs <= 1000) return 'warn';
    return 'fail';
  }

  function summarizeCurrent() {
    var current = state.current;
    if (!current) return null;

    if (state.workload && typeof state.workload.getLoad === 'function') {
      var workloadLoad = state.workload.getLoad();
      if (workloadLoad) Object.assign(current.load, workloadLoad);
    }

    var endedAt = performance.now();
    var elapsedMs = endedAt - current.startedAt;
    var frameValues = current.frames.map(function (frame) { return frame.delta; });

    if (current.name === 'calibration' && frameValues.length) {
      var rawHz = 1000 / median(frameValues);
      state.refreshHz = chooseRefresh(rawHz);
      state.baselineMs = 1000 / state.refreshHz;
      current.meta.rawRefreshHz = round(rawHz, 2);
      current.meta.calibratedRefreshHz = state.refreshHz;
    }

    var expectedFrames = Math.max(1, elapsedMs / state.baselineMs);
    var missedFrames = Math.max(0, expectedFrames - current.frames.length);
    var videoTotal = 0;
    var videoDropped = 0;

    current.videos.forEach(function (sample) {
      if (!sample.element.getVideoPlaybackQuality) return;
      var finalQuality = sample.element.getVideoPlaybackQuality();
      videoTotal += Math.max(0, finalQuality.totalVideoFrames - sample.initialTotal);
      videoDropped += Math.max(0, finalQuality.droppedVideoFrames - sample.initialDropped);
    });

    var soakWindow = Math.min(30000, elapsedMs * 0.2);
    var firstWindowFps = fpsForTimeWindow(current.frames, 0, soakWindow);
    var lastWindowFps = fpsForTimeWindow(current.frames, Math.max(0, elapsedMs - soakWindow), elapsedMs);
    var degradation = firstWindowFps > 0
      ? Math.max(0, (firstWindowFps - lastWindowFps) / firstWindowFps)
      : 0;

    var result = {
      name: current.name,
      label: STAGE_LABELS[current.name],
      durationSec: round(elapsedMs / 1000, 2),
      frameCount: current.frames.length,
      fpsMedian: frameValues.length ? round(1000 / median(frameValues), 2) : 0,
      fpsAverage: frameValues.length ? round(1000 / mean(frameValues), 2) : 0,
      p95FrameMs: round(quantile(frameValues, 0.95), 2),
      p99FrameMs: round(quantile(frameValues, 0.99), 2),
      maxFrameMs: round(frameValues.length ? Math.max.apply(null, frameValues) : 0, 2),
      estimatedMissedFrames: Math.round(missedFrames),
      missedFrameRatio: round(missedFrames / expectedFrames, 4),
      longTaskCount: current.longTasks.length,
      longTaskTotalMs: round(sum(current.longTasks), 2),
      longestTaskMs: round(current.longTasks.length ? Math.max.apply(null, current.longTasks) : 0, 2),
      videoFrames: videoTotal,
      videoDroppedFrames: videoDropped,
      videoDropRatio: round(videoTotal ? videoDropped / videoTotal : 0, 4),
      contextLosses: current.contextLosses,
      errors: current.errors.slice(),
      load: Object.assign({}, current.load),
      meta: Object.assign({}, current.meta),
      memoryStartBytes: current.memoryStart,
      memoryEndBytes: performance.memory ? performance.memory.usedJSHeapSize : null,
      firstWindowFps: round(firstWindowFps, 2),
      lastWindowFps: round(lastWindowFps, 2),
      degradationRatio: round(degradation, 4),
      status: 'info'
    };
    result.status = classifyStage(result);
    return result;
  }

  function finishCurrentStage() {
    if (!state.current) return;
    var result = summarizeCurrent();
    if (result) {
      var existing = state.reports.findIndex(function (item) { return item.name === result.name; });
      if (existing >= 0) state.reports[existing] = result;
      else state.reports.push(result);
    }
  }

  function cleanupCurrentStage() {
    if (state.workload && typeof state.workload.cleanup === 'function') {
      try {
        state.workload.cleanup();
      } catch (error) {
        recordError('cleanup', error);
      }
    }

    var section = state.stage
      ? document.querySelector('[data-stress-stage="' + state.stage + '"]')
      : null;
    var mount = section ? section.querySelector('.workload-mount') : null;
    if (mount) mount.replaceChildren();

    state.workload = null;
    state.current = null;
    state.stage = null;
    state.lastRaf = 0;
    state.lowFpsSince = 0;
  }

  function goToStage(name) {
    if (!window.Reveal) return;
    var section = document.querySelector('[data-stress-stage="' + name + '"]');
    if (!section) return;
    var indices = window.Reveal.getIndices(section);
    window.Reveal.slide(indices.h, indices.v, indices.f);

    window.setTimeout(function () {
      if (state.running && presentStage() === name && !state.current && STAGE_ORDER.indexOf(name) >= 0) {
        beginStage(name);
        state.advancing = false;
      }
    }, 0);
  }

  function advanceStage() {
    if (!state.running || state.advancing || !state.stage) return;
    state.advancing = true;
    var index = STAGE_ORDER.indexOf(state.stage);
    var next = index >= 0 && index < STAGE_ORDER.length - 1
      ? STAGE_ORDER[index + 1]
      : 'results';
    goToStage(next);
  }

  function monitor(now) {
    if (!state.running) {
      state.monitorRaf = 0;
      return;
    }

    if (state.current) {
      if (state.lastRaf) {
        var delta = now - state.lastRaf;
        state.current.frames.push({
          at: now - state.current.startedAt,
          delta: delta
        });
      }
      state.lastRaf = now;
      state.liveFps = getLiveFps(2000);

      var elapsed = now - state.current.startedAt;
      if (!diagnosticMode && elapsed > 3000) {
        var latest = state.current.frames[state.current.frames.length - 1];
        if (latest && latest.delta > 2000) {
          abortRun('Blocco del rendering superiore a 2 secondi', 'safety');
        } else if (state.liveFps < 15) {
          if (!state.lowFpsSince) state.lowFpsSince = now;
          if (now - state.lowFpsSince >= 3000) {
            abortRun('Frame rate sotto 15 FPS per 3 secondi', 'safety');
          }
        } else {
          state.lowFpsSince = 0;
        }
      }

      if (now - state.lastHudUpdate >= 250) {
        updateHud(now);
        state.lastHudUpdate = now;
      }

      if (!state.advancing && elapsed >= state.current.durationSec * 1000) {
        advanceStage();
      }
    }

    if (state.running) state.monitorRaf = window.requestAnimationFrame(monitor);
  }

  function plannedDuration(profile) {
    return sum(Object.keys(DURATIONS[profile]).map(function (key) {
      return DURATIONS[profile][key];
    }));
  }

  function startRun(profile) {
    if (profile !== 'quick' && profile !== 'full') return;

    if (state.running) {
      finishCurrentStage();
      cleanupCurrentStage();
    }

    state.running = true;
    state.profile = profile;
    state.durations = diagnosticMode ? DIAGNOSTIC_DURATIONS : DURATIONS[profile];
    state.reports = [];
    state.report = null;
    state.runStartedAt = performance.now();
    state.refreshHz = 60;
    state.baselineMs = 1000 / 60;
    state.liveFps = 60;
    state.abortReason = null;
    state.abortKind = null;
    state.advancing = true;
    state.environment = captureEnvironment();
    state.stableLoads = {
      domNodes: 240,
      canvasParticles: 20000,
      abCopies: 4,
      gpuIterations: 12,
      cpuWorkers: 1,
      cpuMainMs: 1.5
    };

    delete document.body.dataset.stressRunComplete;
    state.hud.root.classList.add('is-running');

    var fullscreenChoice = document.getElementById('fullscreen-choice');
    if (!diagnosticMode && fullscreenChoice && fullscreenChoice.checked && !document.fullscreenElement) {
      var request = document.documentElement.requestFullscreen;
      if (request) request.call(document.documentElement).catch(function () {
        showToast('Schermo intero non disponibile; il test continua.');
      });
    }

    if (!state.monitorRaf) state.monitorRaf = window.requestAnimationFrame(monitor);
    goToStage('calibration');
  }

  function abortRun(reason, kind) {
    if (!state.running || state.advancing) return;
    state.abortReason = reason;
    state.abortKind = kind || 'safety';
    state.advancing = true;
    showToast(reason);
    goToStage('results');
  }

  function determineOverall(report) {
    if (report.aborted) {
      return {
        status: 'fail',
        title: report.abortKind === 'user' ? 'Test interrotto' : 'Non pronto',
        detail: report.abortReason
      };
    }

    var representative = report.stages.find(function (stage) {
      return stage.name === 'representative';
    });
    var abSingle = report.stages.find(function (stage) {
      return stage.name === 'ab-single';
    });
    var soak = report.stages.find(function (stage) {
      return stage.name === 'soak';
    });

    if (!representative || representative.status === 'fail') {
      return {
        status: 'fail',
        title: 'Non pronto',
        detail: 'Il carico rappresentativo non raggiunge la soglia minima.'
      };
    }

    var warnings = representative.status === 'warn' || !abSingle || abSingle.status !== 'pass';
    warnings = warnings || report.stages.some(function (stage) { return stage.status === 'fail'; });
    if (report.profile === 'full' && soak && soak.degradationRatio > 0.15) warnings = true;

    if (warnings) {
      return {
        status: 'warn',
        title: 'Pronto con cautela',
        detail: 'La talk è riproducibile, ma il margine o la stabilità sostenuta è limitato.'
      };
    }

    return {
      status: 'pass',
      title: 'Pronto',
      detail: 'Carico rappresentativo fluido e margine stabile.'
    };
  }

  function finalizeRun() {
    if (!state.running) return;
    state.running = false;
    if (state.monitorRaf) window.cancelAnimationFrame(state.monitorRaf);
    state.monitorRaf = 0;
    state.hud.root.classList.remove('is-running');

    var endedAt = performance.now();
    var orderedReports = STAGE_ORDER.map(function (name) {
      return state.reports.find(function (stage) { return stage.name === name; });
    }).filter(Boolean);

    var report = {
      schemaVersion: 1,
      generatedAt: new Date().toISOString(),
      profile: state.profile,
      diagnosticMode: diagnosticMode,
      plannedDurationSec: diagnosticMode
        ? sum(Object.keys(DIAGNOSTIC_DURATIONS).map(function (key) { return DIAGNOSTIC_DURATIONS[key]; }))
        : plannedDuration(state.profile),
      actualDurationSec: round((endedAt - state.runStartedAt) / 1000, 2),
      refreshHz: state.refreshHz,
      baselineFrameMs: round(state.baselineMs, 3),
      environment: state.environment,
      stableLoads: Object.assign({}, state.stableLoads),
      thresholds: {
        representativePassRefreshRatio: 0.9,
        representativePassMissedFrameRatio: 0.02,
        representativePassVideoDropRatio: 0.01,
        fullSoakMaximumDegradationRatio: 0.15,
        safetyMinimumFps: 15,
        safetyLowFpsDurationSec: 3,
        safetyMaximumStallMs: 2000
      },
      aborted: Boolean(state.abortReason),
      abortReason: state.abortReason,
      abortKind: state.abortKind,
      stages: orderedReports
    };

    report.overall = determineOverall(report);
    state.report = report;
    renderResults(report);
    document.body.dataset.stressRunComplete = 'true';
    document.body.dataset.stressVerdict = report.overall.status;
  }

  function statusText(status) {
    return status === 'pass' ? 'PASS'
      : status === 'warn' ? 'WARN'
      : status === 'fail' ? 'FAIL'
      : 'INFO';
  }

  function renderResults(report) {
    var verdict = document.getElementById('result-verdict');
    var environment = document.getElementById('environment-summary');
    var body = document.getElementById('result-table-body');
    if (!verdict || !environment || !body) return;

    verdict.dataset.status = report.overall.status;
    verdict.querySelector('strong').textContent = report.overall.title;
    verdict.querySelector('small').textContent = report.overall.detail;

    var env = report.environment;
    environment.textContent = [
      report.profile === 'full' ? 'PROFILO 15 MIN' : 'PROFILO 3 MIN',
      report.refreshHz + ' Hz',
      env.viewport.width + '×' + env.viewport.height + ' @ DPR ' + env.viewport.devicePixelRatio,
      (env.logicalProcessors || 'N/D') + ' thread logici',
      env.deviceMemoryGiB ? env.deviceMemoryGiB + ' GiB RAM dichiarata' : 'RAM N/D',
      report.actualDurationSec + ' s effettivi'
    ].join(' · ');

    body.replaceChildren();
    report.stages.forEach(function (stage) {
      var row = document.createElement('tr');
      var name = makeElement('td', null, stage.label);
      var fps = makeElement('td', null, stage.fpsMedian.toFixed(1));
      var p95 = makeElement('td', null, stage.p95FrameMs.toFixed(1) + ' ms');
      var missed = makeElement('td', null, (stage.missedFrameRatio * 100).toFixed(1) + '%');
      var status = makeElement('td', 'status-' + stage.status, statusText(stage.status));
      row.append(name, fps, p95, missed, status);
      body.appendChild(row);
    });

    document.querySelectorAll('[data-export]').forEach(function (button) {
      button.disabled = false;
    });
  }

  function downloadBlob(filename, type, content) {
    var blob = new Blob([content], { type: type });
    var url = URL.createObjectURL(blob);
    var anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function csvCell(value) {
    var text = value === null || value === undefined ? '' : String(value);
    return '"' + text.replace(/"/g, '""') + '"';
  }

  function exportReport(kind) {
    if (!state.report) return;
    var stamp = state.report.generatedAt.replace(/[:.]/g, '-');
    if (kind === 'json') {
      downloadBlob(
        'stress-test-' + stamp + '.json',
        'application/json;charset=utf-8',
        JSON.stringify(state.report, null, 2)
      );
      return;
    }

    var headings = [
      'stage',
      'duration_s',
      'fps_median',
      'fps_average',
      'p95_ms',
      'p99_ms',
      'max_frame_ms',
      'missed_frame_ratio',
      'long_tasks',
      'video_drop_ratio',
      'degradation_ratio',
      'status'
    ];
    var rows = [headings.map(csvCell).join(',')];
    state.report.stages.forEach(function (stage) {
      rows.push([
        stage.name,
        stage.durationSec,
        stage.fpsMedian,
        stage.fpsAverage,
        stage.p95FrameMs,
        stage.p99FrameMs,
        stage.maxFrameMs,
        stage.missedFrameRatio,
        stage.longTaskCount,
        stage.videoDropRatio,
        stage.degradationRatio,
        stage.status
      ].map(csvCell).join(','));
    });
    downloadBlob('stress-test-' + stamp + '.csv', 'text/csv;charset=utf-8', rows.join('\n'));
  }

  function onSlideChanged(event) {
    var nextStage = stageOf(event.currentSlide);
    if (!state.running) {
      if (nextStage === 'results' && state.report) renderResults(state.report);
      return;
    }

    if (state.current && state.current.name !== nextStage) {
      finishCurrentStage();
      cleanupCurrentStage();
    }

    state.advancing = false;

    if (nextStage === 'results') {
      finalizeRun();
      return;
    }

    if (nextStage === 'start') {
      abortRun('Navigazione manuale alla schermata iniziale', 'user');
      return;
    }

    if (STAGE_ORDER.indexOf(nextStage) >= 0 && !state.current) {
      beginStage(nextStage);
    }
  }

  function installObservers() {
    if (window.PerformanceObserver && PerformanceObserver.supportedEntryTypes &&
        PerformanceObserver.supportedEntryTypes.indexOf('longtask') >= 0) {
      try {
        var observer = new PerformanceObserver(function (list) {
          if (!state.current) return;
          list.getEntries().forEach(function (entry) {
            state.current.longTasks.push(entry.duration);
          });
        });
        observer.observe({ entryTypes: ['longtask'] });
      } catch (error) {
        // Long-task telemetry is optional.
      }
    }

    window.addEventListener('error', function (event) {
      recordError('javascript', event.message || (event.error && event.error.message));
    });
    window.addEventListener('unhandledrejection', function (event) {
      recordError('promise', event.reason && event.reason.message ? event.reason.message : event.reason);
    });
  }

  function init() {
    if (state.initialized) return;
    state.initialized = true;
    createHud();
    installObservers();

    document.addEventListener('click', function (event) {
      var startButton = event.target.closest('[data-start-profile]');
      if (startButton) {
        startRun(startButton.dataset.startProfile);
        return;
      }
      var exportButton = event.target.closest('[data-export]');
      if (exportButton) exportReport(exportButton.dataset.export);
    });

    window.addEventListener('keydown', function (event) {
      if ((event.key === 'x' || event.key === 'X') && state.running) {
        event.preventDefault();
        event.stopImmediatePropagation();
        abortRun('Interrotto dall’utente', 'user');
      }
    }, true);

    window.Reveal.on('slidechanged', onSlideChanged);

    window.__stressDeck = {
      start: startRun,
      stop: function () { abortRun('Interrotto via API diagnostica', 'user'); },
      getReport: function () { return state.report; },
      isRunning: function () { return state.running; }
    };

    if (autoStart) {
      window.setTimeout(function () { startRun(params.get('profile') === 'full' ? 'full' : 'quick'); }, 500);
    }
  }

  function waitForReveal() {
    if (window.Reveal && typeof window.Reveal.on === 'function') {
      if (window.Reveal.isReady && window.Reveal.isReady()) init();
      else window.Reveal.on('ready', init);
    } else {
      window.setTimeout(waitForReveal, 50);
    }
  }

  function startCalibration(mount) {
    var field = makeElement('div', 'calibration-field');
    var orbit = makeElement('div', 'calibration-orbit');
    var readout = makeElement('div', 'calibration-readout');
    var value = makeElement('strong', null, '—');
    var label = makeElement('span', null, 'REFRESH STIMATO');
    readout.append(value, label);
    field.append(orbit, readout);
    mount.appendChild(field);

    var timer = window.setInterval(function () {
      value.textContent = Math.round(getLiveFps(1000));
    }, 250);

    return {
      cleanup: function () { window.clearInterval(timer); },
      getLoad: function () { return { calibrationElements: 4 }; }
    };
  }

  function startDom(mount, api) {
    var storm = makeElement('div', 'dom-storm');
    var badge = makeElement('div', 'load-badge');
    mount.append(storm, badge);
    var count = 0;
    var maximum = diagnosticMode ? 320 : 800;

    function addParticles(amount) {
      var fragment = document.createDocumentFragment();
      for (var i = 0; i < amount && count < maximum; i++, count++) {
        var node = makeElement('i', 'dom-particle');
        var size = 8 + Math.random() * 32;
        node.style.left = (Math.random() * 100).toFixed(2) + '%';
        node.style.top = (Math.random() * 100).toFixed(2) + '%';
        node.style.setProperty('--size', size.toFixed(1) + 'px');
        node.style.setProperty('--hue', String(Math.round(175 + Math.random() * 130)));
        node.style.setProperty('--blur', (8 + Math.random() * 28).toFixed(1) + 'px');
        node.style.setProperty('--duration', (1.6 + Math.random() * 4.2).toFixed(2) + 's');
        node.style.setProperty('--delay', (-Math.random() * 5).toFixed(2) + 's');
        fragment.appendChild(node);
      }
      storm.appendChild(fragment);
      badge.textContent = count.toLocaleString('it-IT') + ' elementi';
      api.setLoad('domNodes', count);
    }

    addParticles(diagnosticMode ? 120 : 240);
    var ramp = window.setInterval(function () {
      if (api.canRamp() && count < maximum) addParticles(80);
    }, 5000);

    return {
      cleanup: function () { window.clearInterval(ramp); },
      getLoad: function () { return { domNodes: count }; }
    };
  }

  function startCanvas(mount, api) {
    var canvas = makeElement('canvas', 'stress-canvas');
    var badge = makeElement('div', 'load-badge');
    mount.append(canvas, badge);
    var context = canvas.getContext('2d', { alpha: false });
    if (!context) {
      api.recordError('canvas', 'Canvas 2D non disponibile');
      return { cleanup: function () {}, getLoad: function () { return {}; } };
    }

    var maximum = diagnosticMode ? 25000 : 80000;
    var x = new Float32Array(maximum);
    var y = new Float32Array(maximum);
    var vx = new Float32Array(maximum);
    var vy = new Float32Array(maximum);
    var size = new Float32Array(maximum);
    var count = 0;
    var width = 1;
    var height = 1;
    var raf = 0;
    var running = true;

    function resize() {
      var dpr = Math.min(2, window.devicePixelRatio || 1);
      var nextWidth = Math.max(1, Math.round(mount.clientWidth * dpr));
      var nextHeight = Math.max(1, Math.round(mount.clientHeight * dpr));
      if (canvas.width !== nextWidth || canvas.height !== nextHeight) {
        canvas.width = nextWidth;
        canvas.height = nextHeight;
        width = nextWidth;
        height = nextHeight;
      }
    }

    function addParticles(amount) {
      var end = Math.min(maximum, count + amount);
      for (var i = count; i < end; i++) {
        x[i] = Math.random() * width;
        y[i] = Math.random() * height;
        vx[i] = (Math.random() - 0.5) * 2.6;
        vy[i] = (Math.random() - 0.5) * 2.6;
        size[i] = 0.7 + Math.random() * 2.4;
      }
      count = end;
      badge.textContent = count.toLocaleString('it-IT') + ' particelle';
      api.setLoad('canvasParticles', count);
    }

    function draw() {
      if (!running) return;
      resize();
      context.globalCompositeOperation = 'source-over';
      context.fillStyle = '#030710';
      context.fillRect(0, 0, width, height);
      context.globalCompositeOperation = 'lighter';
      var colors = ['rgba(66,216,255,0.42)', 'rgba(82,239,169,0.35)', 'rgba(159,124,255,0.38)'];

      for (var group = 0; group < 3; group++) {
        context.fillStyle = colors[group];
        for (var i = group; i < count; i += 3) {
          x[i] += vx[i];
          y[i] += vy[i];
          if (x[i] < 0) x[i] += width;
          else if (x[i] >= width) x[i] -= width;
          if (y[i] < 0) y[i] += height;
          else if (y[i] >= height) y[i] -= height;
          context.fillRect(x[i], y[i], size[i], size[i]);
        }
      }
      raf = window.requestAnimationFrame(draw);
    }

    resize();
    addParticles(diagnosticMode ? 12000 : 20000);
    draw();
    var ramp = window.setInterval(function () {
      if (api.canRamp() && count < maximum) addParticles(10000);
    }, 5000);

    return {
      cleanup: function () {
        running = false;
        window.cancelAnimationFrame(raf);
        window.clearInterval(ramp);
      },
      getLoad: function () {
        return { canvasParticles: count, canvasWidth: width, canvasHeight: height };
      }
    };
  }

  function fitAbGrid(grid) {
    grid.querySelectorAll('.ab-slot').forEach(function (slot) {
      var scale = Math.min(slot.clientWidth / 1000, slot.clientHeight / 560);
      slot.style.setProperty('--ab-scale', String(Math.max(0.05, scale)));
    });
  }

  function startAbGrid(mount, api, copies) {
    var grid = makeElement('div', 'ab-grid' + (copies === 1 ? ' ab-grid-single' : ''));
    var iframes = [];
    for (var i = 0; i < copies; i++) {
      var slot = makeElement('div', 'ab-slot');
      var iframe = document.createElement('iframe');
      iframe.src = AB_ASSET + '?instance=' + (i + 1);
      iframe.title = 'Animazione Canvas 2D ' + (i + 1);
      iframe.loading = 'eager';
      iframe.setAttribute('scrolling', 'no');
      iframe.addEventListener('error', function () {
        api.recordError('iframe', 'Impossibile caricare l’animazione HTML');
      });
      slot.appendChild(iframe);
      grid.appendChild(slot);
      iframes.push(iframe);
    }
    mount.appendChild(grid);
    api.setLoad('abCopies', copies);

    var observer = window.ResizeObserver
      ? new ResizeObserver(function () { fitAbGrid(grid); })
      : null;
    if (observer) observer.observe(grid);
    window.requestAnimationFrame(function () { fitAbGrid(grid); });

    return {
      cleanup: function () {
        if (observer) observer.disconnect();
        iframes.forEach(function (iframe) {
          iframe.src = 'about:blank';
          iframe.remove();
        });
      },
      getLoad: function () { return { abCopies: copies }; }
    };
  }

  function createVideo(container, api, index) {
    var video = makeElement('video', 'stress-video');
    var label = makeElement('span', 'video-state', 'CARICAMENTO');
    video.src = VIDEO_ASSET;
    video.muted = true;
    video.loop = true;
    video.autoplay = true;
    video.playsInline = true;
    video.preload = 'auto';
    video.disablePictureInPicture = true;

    video.addEventListener('loadedmetadata', function () {
      if (Number.isFinite(video.duration) && video.duration > 0) {
        video.currentTime = (index * 7.25) % video.duration;
      }
    }, { once: true });
    video.addEventListener('playing', function () {
      label.textContent = '1080p · PLAY';
    });
    video.addEventListener('waiting', function () {
      label.textContent = 'BUFFER';
    });
    video.addEventListener('error', function () {
      label.textContent = 'ERRORE';
      api.recordError('video', video.error ? video.error.message || ('MediaError ' + video.error.code) : 'Errore video');
    });

    container.append(video, label);
    api.registerVideo(video);
    var playPromise = video.play();
    if (playPromise && typeof playPromise.catch === 'function') {
      playPromise.catch(function (error) {
        api.recordError('video-play', error && error.message ? error.message : error);
      });
    }
    return video;
  }

  function startRepresentative(mount, api) {
    var grid = makeElement('div', 'representative-grid');
    var abPanel = makeElement('div', 'video-panel');
    var videoPanel = makeElement('div', 'video-panel');
    grid.append(abPanel, videoPanel);
    mount.appendChild(grid);

    var ab = startAbGrid(abPanel, api, 1);
    var video = createVideo(videoPanel, api, 0);

    return {
      cleanup: function () {
        ab.cleanup();
        video.pause();
        video.removeAttribute('src');
        video.load();
      },
      getLoad: function () { return { abCopies: 1, videos1080p: 1 }; }
    };
  }

  function compileShader(gl, type, source) {
    var shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      var message = gl.getShaderInfoLog(shader);
      gl.deleteShader(shader);
      throw new Error(message || 'Compilazione shader fallita');
    }
    return shader;
  }

  function startGpu(mount, api, options) {
    options = options || {};
    var canvas = makeElement('canvas', 'gpu-canvas');
    var badge = makeElement('div', 'load-badge');
    mount.append(canvas, badge);

    var gl = canvas.getContext('webgl2', {
      antialias: false,
      alpha: false,
      powerPreference: 'high-performance'
    });
    var webgl2 = Boolean(gl);
    if (!gl) {
      gl = canvas.getContext('webgl', {
        antialias: false,
        alpha: false,
        powerPreference: 'high-performance'
      });
    }
    if (!gl) {
      mount.appendChild(makeElement('div', 'calibration-field', 'WebGL non disponibile'));
      api.recordError('webgl', 'WebGL non disponibile');
      return { cleanup: function () {}, getLoad: function () { return { gpuIterations: 0 }; } };
    }

    canvas.addEventListener('webglcontextlost', function (event) {
      event.preventDefault();
      api.contextLost();
    });

    var vertexSource = webgl2
      ? [
          '#version 300 es',
          'in vec2 a_position;',
          'void main(){ gl_Position = vec4(a_position, 0.0, 1.0); }'
        ].join('\n')
      : [
          'attribute vec2 a_position;',
          'void main(){ gl_Position = vec4(a_position, 0.0, 1.0); }'
        ].join('\n');

    var fragmentLines = [
      'precision highp float;',
      'uniform vec2 u_resolution;',
      'uniform float u_time;',
      'uniform float u_iterations;',
      'void main(){',
      '  vec2 p = (2.0 * gl_FragCoord.xy - u_resolution) / min(u_resolution.x, u_resolution.y);',
      '  p += vec2(sin(u_time * 0.17), cos(u_time * 0.13)) * 0.11;',
      '  float acc = 0.0;',
      '  float energy = 0.0;',
      '  for (int i = 0; i < 60; i++){',
      '    if (float(i) >= u_iterations) break;',
      '    float a = 0.31 + float(i) * 0.071 + u_time * 0.025;',
      '    mat2 r = mat2(cos(a), -sin(a), sin(a), cos(a));',
      '    p = r * (abs(p) / clamp(dot(p,p), 0.16, 2.2) - 0.68);',
      '    float d = abs(length(p) - 0.58);',
      '    acc += exp(-d * (8.0 + mod(float(i), 7.0)));',
      '    energy += dot(sin(p * (2.0 + float(i) * 0.03)), cos(p.yx * 2.7));',
      '  }',
      '  float wave = 0.5 + 0.5 * sin(acc * 0.19 + energy * 0.035 + u_time);',
      '  vec3 color = mix(vec3(0.02,0.08,0.17), vec3(0.20,0.88,0.98), wave);',
      '  color += vec3(0.46,0.15,0.92) * pow(abs(sin(acc * 0.08)), 5.0);'
    ];
    if (webgl2) {
      fragmentLines.unshift('#version 300 es');
      fragmentLines.splice(2, 0, 'out vec4 outColor;');
      fragmentLines.push('  outColor = vec4(color, 1.0);', '}');
    } else {
      fragmentLines.push('  gl_FragColor = vec4(color, 1.0);', '}');
    }

    var program;
    var vertex;
    var fragment;
    try {
      vertex = compileShader(gl, gl.VERTEX_SHADER, vertexSource);
      fragment = compileShader(gl, gl.FRAGMENT_SHADER, fragmentLines.join('\n'));
      program = gl.createProgram();
      gl.attachShader(program, vertex);
      gl.attachShader(program, fragment);
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        throw new Error(gl.getProgramInfoLog(program) || 'Link shader fallito');
      }
    } catch (error) {
      api.recordError('webgl-shader', error.message || error);
      mount.appendChild(makeElement('div', 'calibration-field', 'Shader non disponibile'));
      return { cleanup: function () {}, getLoad: function () { return { gpuIterations: 0 }; } };
    }

    gl.useProgram(program);
    var buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    var position = gl.getAttribLocation(program, 'a_position');
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);

    var resolution = gl.getUniformLocation(program, 'u_resolution');
    var time = gl.getUniformLocation(program, 'u_time');
    var iterationUniform = gl.getUniformLocation(program, 'u_iterations');
    var iterations = options.fixedIterations || 12;
    var maximum = diagnosticMode ? iterations : 60;
    var running = true;
    var raf = 0;
    var started = performance.now();

    var debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
    var renderer = debugInfo
      ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL)
      : gl.getParameter(gl.RENDERER);
    api.setMeta('webglVersion', webgl2 ? 2 : 1);
    api.setMeta('webglRenderer', renderer);

    function resize() {
      var dpr = Math.min(1.5, window.devicePixelRatio || 1);
      var width = Math.max(1, Math.round(mount.clientWidth * dpr));
      var height = Math.max(1, Math.round(mount.clientHeight * dpr));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
        gl.viewport(0, 0, width, height);
      }
    }

    function draw(now) {
      if (!running) return;
      resize();
      gl.uniform2f(resolution, canvas.width, canvas.height);
      gl.uniform1f(time, (now - started) / 1000);
      gl.uniform1f(iterationUniform, iterations);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      badge.textContent = iterations + ' iterazioni · WebGL ' + (webgl2 ? '2' : '1');
      raf = window.requestAnimationFrame(draw);
    }

    api.setLoad('gpuIterations', iterations);
    draw(performance.now());
    var ramp = options.fixedIterations ? 0 : window.setInterval(function () {
      if (api.canRamp() && iterations < maximum) {
        iterations = Math.min(maximum, iterations + 8);
        api.setLoad('gpuIterations', iterations);
      }
    }, 5000);

    return {
      cleanup: function () {
        running = false;
        window.cancelAnimationFrame(raf);
        if (ramp) window.clearInterval(ramp);
        gl.deleteBuffer(buffer);
        gl.deleteProgram(program);
        gl.deleteShader(vertex);
        gl.deleteShader(fragment);
      },
      getLoad: function () {
        return {
          gpuIterations: iterations,
          gpuWidth: canvas.width,
          gpuHeight: canvas.height
        };
      }
    };
  }

  function workerSource() {
    return [
      "'use strict';",
      'var running = true;',
      'var duty = 0.82;',
      'var cycles = 0;',
      'var value = 0.1234567;',
      'function burn(){',
      '  if (!running) return;',
      '  var slice = 18 * duty;',
      '  var started = performance.now();',
      '  var ops = 0;',
      '  while (performance.now() - started < slice){',
      '    for (var i = 0; i < 650; i++){',
      '      value = Math.sin(value * 1.000001 + i) * Math.cos(value - i * 0.001) + Math.sqrt(Math.abs(value) + 1.0);',
      '      ops++;',
      '    }',
      '  }',
      '  cycles++;',
      '  if (cycles % 6 === 0) postMessage({ ops: ops, value: value });',
      '  setTimeout(burn, Math.max(1, 18 - slice));',
      '}',
      'onmessage = function(event){',
      "  if (event.data === 'stop') running = false;",
      "  else if (event.data && event.data.duty) duty = event.data.duty;",
      '};',
      'burn();'
    ].join('\n');
  }

  function startCpu(mount, api, options) {
    options = options || {};
    var visual = options.visual !== false;
    var dashboard = visual ? makeElement('div', 'cpu-dashboard') : null;
    var summary = visual ? makeElement('div', 'cpu-summary') : null;
    var value = visual ? makeElement('strong', null, '0') : null;
    var label = visual ? makeElement('span', null, 'worker attivi') : null;
    var list = visual ? makeElement('div', 'worker-list') : null;
    if (visual) {
      summary.append(value, label);
      dashboard.append(summary, list);
      mount.appendChild(dashboard);
    }

    var logical = navigator.hardwareConcurrency || 4;
    var maximum = options.fixedWorkers ||
      (diagnosticMode ? 2 : Math.max(1, Math.min(8, logical - 2)));
    var workers = [];
    var rows = [];
    var blob = new Blob([workerSource()], { type: 'text/javascript' });
    var workerUrl = URL.createObjectURL(blob);
    var running = true;
    var raf = 0;
    var mainMs = options.fixedMainMs || 1.5;

    function addWorker() {
      if (workers.length >= maximum) return;
      var index = workers.length;
      var worker = new Worker(workerUrl);
      var fill = null;
      if (visual) {
        var row = makeElement('div', 'worker-row');
        var rowLabel = makeElement('span', null, 'worker ' + String(index + 1).padStart(2, '0'));
        var bar = makeElement('div', 'worker-bar');
        fill = makeElement('i');
        bar.appendChild(fill);
        row.append(rowLabel, bar);
        list.appendChild(row);
        rows.push(row);
      }
      worker.onmessage = function () {
        if (fill) fill.style.width = (72 + Math.random() * 25).toFixed(0) + '%';
      };
      worker.onerror = function (event) {
        api.recordError('worker', event.message || 'Errore worker');
      };
      workers.push(worker);
      if (value) value.textContent = workers.length;
      api.setLoad('cpuWorkers', workers.length);
    }

    function burnMainThread() {
      if (!running) return;
      var started = performance.now();
      var sink = 0;
      while (performance.now() - started < mainMs) {
        for (var i = 0; i < 180; i++) sink += Math.sqrt(i + sink % 11);
      }
      if (sink === Number.MIN_VALUE) recordError('cpu', 'Valore impossibile');
      raf = window.requestAnimationFrame(burnMainThread);
    }

    addWorker();
    if (options.fixedWorkers) {
      while (workers.length < maximum) addWorker();
    }
    burnMainThread();
    api.setLoad('cpuMainMs', mainMs);

    var ramp = options.fixedWorkers ? 0 : window.setInterval(function () {
      if (api.canRamp()) {
        if (workers.length < maximum) addWorker();
        mainMs = Math.min(5.5, mainMs + 1);
        api.setLoad('cpuMainMs', mainMs);
      }
    }, 5000);

    return {
      cleanup: function () {
        running = false;
        window.cancelAnimationFrame(raf);
        if (ramp) window.clearInterval(ramp);
        workers.forEach(function (worker) {
          worker.postMessage('stop');
          worker.terminate();
        });
        workers.length = 0;
        URL.revokeObjectURL(workerUrl);
      },
      getLoad: function () {
        return { cpuWorkers: workers.length, cpuMainMs: round(mainMs, 1) };
      }
    };
  }

  function startSoak(mount, api) {
    var grid = makeElement('div', 'soak-grid');
    var abPanel = makeElement('div', 'video-panel soak-ab');
    var videoPanel = makeElement('div', 'video-panel');
    var gpuPanel = makeElement('div', 'gpu-panel');
    var hiddenCpuMount = makeElement('div');
    hiddenCpuMount.hidden = true;
    grid.append(abPanel, videoPanel, gpuPanel, hiddenCpuMount);
    mount.appendChild(grid);

    var abCount = clamp(Math.round((state.stableLoads.abCopies || 4) * 0.75), 2, 3);
    var gpuIterations = clamp(Math.round((state.stableLoads.gpuIterations || 12) * 0.75), 8, 45);
    var cpuWorkers = clamp(
      Math.round((state.stableLoads.cpuWorkers || 1) * 0.75),
      1,
      Math.max(1, Math.min(6, (navigator.hardwareConcurrency || 4) - 2))
    );
    var cpuMainMs = clamp((state.stableLoads.cpuMainMs || 1.5) * 0.75, 1, 4);

    var ab = startAbGrid(abPanel, api, abCount);
    setStyles(videoPanel, {
      display: 'grid',
      gridTemplateRows: '1fr 1fr',
      gap: '4px'
    });
    var videoA = createVideo(videoPanel, api, 0);
    var videoB = createVideo(videoPanel, api, 1);
    var gpu = startGpu(gpuPanel, api, { fixedIterations: gpuIterations });
    var cpu = startCpu(hiddenCpuMount, api, {
      fixedWorkers: cpuWorkers,
      fixedMainMs: cpuMainMs,
      visual: false
    });

    api.setLoad('soakAbCopies', abCount);
    api.setLoad('soakVideos1080p', 2);
    api.setLoad('soakGpuIterations', gpuIterations);
    api.setLoad('soakCpuWorkers', cpuWorkers);

    return {
      cleanup: function () {
        ab.cleanup();
        [videoA, videoB].forEach(function (video) {
          video.pause();
          video.removeAttribute('src');
          video.load();
        });
        gpu.cleanup();
        cpu.cleanup();
      },
      getLoad: function () {
        return {
          soakAbCopies: abCount,
          soakVideos1080p: 2,
          soakGpuIterations: gpuIterations,
          soakCpuWorkers: cpuWorkers,
          soakCpuMainMs: round(cpuMainMs, 1)
        };
      }
    };
  }

  var WORKLOADS = {
    calibration: function (mount) {
      return startCalibration(mount);
    },
    dom: function (mount, api) {
      return startDom(mount, api);
    },
    canvas: function (mount, api) {
      return startCanvas(mount, api);
    },
    'ab-single': function (mount, api) {
      return startAbGrid(mount, api, 1);
    },
    representative: function (mount, api) {
      return startRepresentative(mount, api);
    },
    'ab-multi': function (mount, api) {
      return startAbGrid(mount, api, 4);
    },
    gpu: function (mount, api) {
      return startGpu(mount, api);
    },
    cpu: function (mount, api) {
      return startCpu(mount, api);
    },
    soak: function (mount, api) {
      return startSoak(mount, api);
    }
  };

  waitForReveal();
})();
