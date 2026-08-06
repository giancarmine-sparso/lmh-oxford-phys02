#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [chromiumBin, pageUrl, outputPath, expectedPagesArg] = process.argv.slice(2);
const expectedPages = Number(expectedPagesArg);

if (!chromiumBin || !pageUrl || !outputPath || !Number.isInteger(expectedPages)) {
  console.error(
    "Usage: print_reveal_pdf.mjs CHROMIUM URL OUTPUT_PDF EXPECTED_PAGES",
  );
  process.exit(2);
}

const profileDir = mkdtempSync(join(tmpdir(), "lmh-talk-chromium-"));
let browser;
let socket;

const delay = (milliseconds) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds));

async function waitForDebuggerUrl(process) {
  return new Promise((resolve, reject) => {
    let stderr = "";
    const timeout = setTimeout(
      () => reject(new Error(`Chromium did not expose DevTools.\n${stderr}`)),
      15_000,
    );

    process.stderr.setEncoding("utf8");
    process.stderr.on("data", (chunk) => {
      stderr += chunk;
      const match = stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (match) {
        clearTimeout(timeout);
        resolve(match[1]);
      }
    });

    process.once("exit", (code) => {
      clearTimeout(timeout);
      reject(new Error(`Chromium exited with status ${code}.\n${stderr}`));
    });
  });
}

async function waitForPage(port) {
  const deadline = Date.now() + 15_000;

  while (Date.now() < deadline) {
    try {
      const targets = await fetch(`http://127.0.0.1:${port}/json/list`).then(
        (response) => response.json(),
      );
      const page = targets.find(
        (target) => target.type === "page" && target.url.startsWith("file:"),
      );
      if (page?.webSocketDebuggerUrl) return page;
    } catch {
      // The debugging endpoint can lag slightly behind Chromium's log line.
    }
    await delay(100);
  }

  throw new Error("Chromium did not open the presentation page.");
}

async function connect(webSocketUrl) {
  const ws = new WebSocket(webSocketUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve, { once: true });
    ws.addEventListener("error", reject, { once: true });
  });

  let commandId = 0;
  const pending = new Map();

  ws.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;

    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(message.error.message));
    else resolve(message.result);
  });

  return {
    ws,
    command(method, params = {}) {
      const id = ++commandId;
      ws.send(JSON.stringify({ id, method, params }));
      return new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject });
      });
    },
  };
}

try {
  browser = spawn(
    chromiumBin,
    [
      "--headless",
      "--disable-gpu",
      "--disable-dev-shm-usage",
      "--no-sandbox",
      "--remote-allow-origins=*",
      "--remote-debugging-port=0",
      `--user-data-dir=${profileDir}`,
      pageUrl,
    ],
    { stdio: ["ignore", "ignore", "pipe"] },
  );

  const debuggerUrl = await waitForDebuggerUrl(browser);
  const port = new URL(debuggerUrl).port;
  const page = await waitForPage(port);
  const connection = await connect(page.webSocketDebuggerUrl);
  socket = connection.ws;

  await connection.command("Page.enable");
  const readiness = await connection.command("Runtime.evaluate", {
    expression: `(async () => {
      const deadline = Date.now() + 20000;
      while (Date.now() < deadline) {
        const pages = document.querySelectorAll('.pdf-page').length;
        const imagesReady = [...document.images].every(
          (image) => image.complete && image.naturalWidth > 0,
        );
        if (
          document.documentElement.classList.contains('print-pdf') &&
          pages === ${expectedPages} &&
          imagesReady
        ) {
          await document.fonts.ready;
          await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
          return { pages, title: document.title };
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
      throw new Error('Timed out waiting for the Reveal print layout');
    })()`,
    awaitPromise: true,
    returnByValue: true,
  });

  if (readiness.exceptionDetails) {
    throw new Error(readiness.exceptionDetails.exception?.description ?? "Page error");
  }

  const pdf = await connection.command("Page.printToPDF", {
    displayHeaderFooter: false,
    printBackground: true,
    preferCSSPageSize: true,
  });
  writeFileSync(outputPath, Buffer.from(pdf.data, "base64"));
  console.log(
    `Printed ${readiness.result.value.pages} Reveal pages to ${outputPath}.`,
  );
} finally {
  socket?.close();
  if (browser && browser.exitCode === null) {
    const exited = new Promise((resolve) => browser.once("exit", resolve));
    browser.kill("SIGTERM");
    await Promise.race([exited, delay(3_000)]);
    if (browser.exitCode === null) {
      browser.kill("SIGKILL");
      await exited;
    }
  }
  rmSync(profileDir, { recursive: true, force: true });
}
