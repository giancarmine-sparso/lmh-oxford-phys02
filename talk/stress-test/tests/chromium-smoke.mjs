import { spawn } from 'node:child_process';
import { writeFile } from 'node:fs/promises';
import process from 'node:process';

const baseUrl = process.argv[2] ?? 'http://127.0.0.1:8765/index.html';
const targetUrl = new URL(baseUrl);
targetUrl.searchParams.set('diagnostic', '1');
targetUrl.searchParams.set('autostart', '1');

const chrome = spawn('chromium-browser', [
  '--headless',
  '--no-sandbox',
  '--disable-dev-shm-usage',
  '--enable-unsafe-swiftshader',
  '--hide-scrollbars',
  '--autoplay-policy=no-user-gesture-required',
  '--window-size=1600,900',
  '--remote-debugging-pipe',
  targetUrl.href
], {
  stdio: ['ignore', 'pipe', 'pipe', 'pipe', 'pipe']
});

let nextId = 1;
let buffer = Buffer.alloc(0);
const pending = new Map();
const browserEvents = [];
const pageEvents = [];

function failPending(error) {
  for (const { reject } of pending.values()) reject(error);
  pending.clear();
}

function send(method, params = {}, sessionId) {
  const id = nextId++;
  const message = { id, method, params };
  if (sessionId) message.sessionId = sessionId;
  const payload = Buffer.from(JSON.stringify(message) + '\0');
  chrome.stdio[3].write(payload);
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject, method });
  });
}

chrome.stdio[4].on('data', (chunk) => {
  buffer = Buffer.concat([buffer, chunk]);
  let delimiter;
  while ((delimiter = buffer.indexOf(0)) >= 0) {
    const raw = buffer.subarray(0, delimiter).toString('utf8');
    buffer = buffer.subarray(delimiter + 1);
    if (!raw) continue;
    const message = JSON.parse(raw);
    if (message.id) {
      const waiting = pending.get(message.id);
      if (!waiting) continue;
      pending.delete(message.id);
      if (message.error) {
        waiting.reject(new Error(waiting.method + ': ' + message.error.message));
      } else {
        waiting.resolve(message.result ?? {});
      }
    } else if (message.sessionId) {
      pageEvents.push(message);
    } else {
      browserEvents.push(message);
    }
  }
});

chrome.on('error', failPending);
chrome.on('exit', (code) => {
  if (code && pending.size) failPending(new Error('Chromium terminato con codice ' + code));
});

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function findPageTarget() {
  for (let attempt = 0; attempt < 80; attempt++) {
    const { targetInfos = [] } = await send('Target.getTargets');
    const page = targetInfos.find((target) => target.type === 'page' && target.url.includes('index.html'));
    if (page) return page;
    await delay(100);
  }
  throw new Error('Target Chromium non trovato');
}

async function evaluate(sessionId, expression) {
  const result = await send('Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise: true
  }, sessionId);
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text || 'Runtime.evaluate fallita');
  }
  return result.result?.value;
}

async function main() {
  const page = await findPageTarget();
  const { sessionId } = await send('Target.attachToTarget', {
    targetId: page.targetId,
    flatten: true
  });

  await Promise.all([
    send('Runtime.enable', {}, sessionId),
    send('Page.enable', {}, sessionId),
    send('Log.enable', {}, sessionId)
  ]);

  const timeoutMs = Number(process.env.SMOKE_TIMEOUT_MS || 50_000);
  const deadline = Date.now() + timeoutMs;
  let complete = false;
  while (Date.now() < deadline) {
    complete = await evaluate(
      sessionId,
      'document.body && document.body.dataset.stressRunComplete === "true"'
    );
    if (complete) break;
    await delay(500);
  }

  if (!complete) {
    const snapshot = await evaluate(sessionId, [
      'JSON.stringify({',
      '  ready: document.body && document.body.dataset.stressRunComplete,',
      '  running: window.__stressDeck && window.__stressDeck.isRunning(),',
      '  slide: window.Reveal && window.Reveal.getCurrentSlide() && window.Reveal.getCurrentSlide().dataset.stressStage,',
      '  hud: document.querySelector("#stress-hud .hud-stage") && document.querySelector("#stress-hud .hud-stage").textContent',
      '})'
    ].join(''));
    const recentErrors = pageEvents.filter((event) =>
      event.method === 'Runtime.exceptionThrown' || event.method === 'Log.entryAdded'
    ).slice(-5);
    throw new Error('Il ciclo diagnostico non è terminato entro ' + timeoutMs + ' ms: ' + snapshot + ' ' + JSON.stringify(recentErrors));
  }

  const serializedReport = await evaluate(
    sessionId,
    'JSON.stringify(window.__stressDeck && window.__stressDeck.getReport())'
  );
  const report = JSON.parse(serializedReport);
  if (!report || report.stages.length !== 9) {
    throw new Error('Rapporto incompleto: attesi 9 stadi');
  }

  const teardownState = JSON.parse(await evaluate(sessionId, [
    'JSON.stringify({',
    '  activeResources: document.querySelectorAll(".workload-mount iframe, .workload-mount video, .workload-mount canvas").length,',
    '  exportsEnabled: Array.from(document.querySelectorAll("[data-export]")).every(function(button){ return !button.disabled; })',
    '})'
  ].join('')));
  if (teardownState.activeResources !== 0 || !teardownState.exportsEnabled) {
    throw new Error('Teardown o azioni finali non validi: ' + JSON.stringify(teardownState));
  }

  const screenshot = await send('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: false
  }, sessionId);
  await writeFile('/tmp/stress-test-results.png', Buffer.from(screenshot.data, 'base64'));

  const exceptions = pageEvents.filter((event) =>
    event.method === 'Runtime.exceptionThrown' ||
    (event.method === 'Log.entryAdded' && event.params?.entry?.level === 'error')
  );
  if (exceptions.length) {
    throw new Error('Eccezioni browser rilevate: ' + JSON.stringify(exceptions.slice(0, 3)));
  }

  process.stdout.write(JSON.stringify({
    complete: true,
    stages: report.stages.length,
    verdict: report.overall.status,
    refreshHz: report.refreshHz,
    activeResourcesAfterRun: teardownState.activeResources,
    failedStages: report.stages
      .filter((stage) => stage.status === 'fail')
      .map((stage) => ({ name: stage.name, errors: stage.errors, meta: stage.meta })),
    screenshot: '/tmp/stress-test-results.png'
  }) + '\n');

  await send('Browser.close');
}

const watchdog = setTimeout(() => {
  chrome.kill('SIGKILL');
}, 55_000);

try {
  await main();
  clearTimeout(watchdog);
} catch (error) {
  clearTimeout(watchdog);
  chrome.kill('SIGKILL');
  process.stderr.write((error?.stack ?? String(error)) + '\n');
  process.exitCode = 1;
}
