/* Buster GUI — visual review driver (Playwright).
 *
 * Brings up the REAL Buster stack using the project's own entry points and
 * configuration, then inspects the rendered UI in a real browser:
 *
 *   1. buster bootstrap  (offline install/init — creates install layout)
 *   2. buster start      (the one daemon / one Kernel runtime)
 *   3. python -m buster.gui.server   (the GUI server, a pure RPC client)
 *   4. Playwright/Chromium: Home + Live first, then the remaining consumer
 *      screens, at desktop and mobile viewports.
 *
 * The GUI host/port come from buster.gui (DEFAULT_PORT), never a guess, and
 * the GUI is only started if it is not already answering.
 *
 * Preconditions verified before any screenshot:
 *   - the Buster daemon/runtime is online (single runtime lock held)
 *   - the GUI server is listening and /api/ping answers
 *   - Playwright can load the absolute GUI URL
 *
 * Usage:
 *   node ui_review.mjs                    # full sweep, screenshots + report
 *   node ui_review.mjs --only home,live   # focus screens
 *   node ui_review.mjs --keep-running     # leave daemon + GUI up
 */

import { chromium } from "file:///C:/Users/xkali/new_ai/webApp/frontend/node_modules/playwright/index.mjs";
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const REPO = path.resolve(import.meta.dirname, "../../../..");
const PYTHON = process.env.BUSTER_PYTHON
  || "C:/Users/xkali/AppData/Local/Microsoft/WindowsApps/python.exe";
const HOST = "127.0.0.1";

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  mobile: { width: 390, height: 844 },
};

// Home and Live first: they carry the primary visual identity.
const SCREENS = [
  "home", "live", "chat", "tasks", "files", "memory",
  "permissions", "device", "activity", "settings", "updates", "advanced",
];

const CHROMIUM = process.env.BUSTER_CHROMIUM
  || "C:/Users/xkali/AppData/Local/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-win64/chrome-headless-shell.exe";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function run(args, opts = {}) {
  return spawnSync(PYTHON, args, { cwd: REPO, encoding: "utf-8", ...opts });
}

function guiConfig() {
  // Authoritative GUI host/port straight from the project source.
  const res = run(["-c",
    "from buster.gui.server import DEFAULT_PORT; import buster.gui as g;"
    + "print(DEFAULT_PORT, g.GUI_VERSION)"]);
  if (res.status !== 0) {
    throw new Error("could not read GUI config: " + (res.stderr || ""));
  }
  const [port, version] = res.stdout.trim().split(/\s+/);
  return { port: Number(port), version };
}

async function httpJson(url, init) {
  const res = await fetch(url, init);
  const text = await res.text();
  let body = null;
  try { body = JSON.parse(text); } catch { body = { raw: text.slice(0, 200) }; }
  return { status: res.status, body };
}

async function waitFor(fn, { timeoutMs = 30000, intervalMs = 250, label }) {
  const deadline = Date.now() + timeoutMs;
  let lastError = null;
  while (Date.now() < deadline) {
    try {
      const value = await fn();
      if (value) return value;
    } catch (err) { lastError = err; }
    await sleep(intervalMs);
  }
  throw new Error(`timed out waiting for ${label}`
    + (lastError ? `: ${lastError.message}` : ""));
}

async function runtimeOnline(install) {
  const res = run(["-c",
    "import sys; from buster.runtime import RuntimeLock;"
    + `print('yes' if RuntimeLock(${JSON.stringify(install)}).is_online() else 'no')`]);
  return res.status === 0 && res.stdout.trim() === "yes";
}

async function ensureRuntime(install) {
  if (await runtimeOnline(install)) {
    console.log(`[preflight] daemon already online (${install})`);
    return false;
  }
  console.log(`[preflight] bootstrapping + starting daemon (${install})`);
  run(["-m", "buster.cli", "bootstrap", "--install-path", install]);
  const started = run(["-m", "buster.cli", "start", "--install-path", install]);
  if (started.status !== 0) {
    throw new Error("buster start failed: " + (started.stderr || started.stdout));
  }
  await waitFor(() => runtimeOnline(install), { label: "daemon runtime lock" });
  console.log("[preflight] daemon online");
  return true;
}

async function ensureGui(install, port) {
  const base = `http://${HOST}:${port}`;
  try {
    const ping = await httpJson(`${base}/api/ping`);
    if (ping.status === 200) {
      console.log(`[preflight] GUI already listening at ${base}`);
      return { base, child: null };
    }
  } catch { /* not running yet */ }

  console.log(`[preflight] starting GUI server on ${base}`);
  const child = spawn(PYTHON,
    ["-u", "-m", "buster.gui.server", "--install-path", install, "--port", String(port)],
    { cwd: REPO, stdio: ["ignore", "pipe", "pipe"] });
  child.stdout.on("data", (d) => {
    const m = String(d).match(/listening on (http:\/\/[^\s]+)/);
    if (m) console.log("[gui] " + m[1]);
  });
  child.stderr.on("data", (d) => process.stderr.write("[gui] " + d));

  await waitFor(async () => {
    const ping = await httpJson(`${base}/api/ping`);
    return ping.status === 200 ? ping.body : null;
  }, { label: `GUI /api/ping on ${base}` });

  return { base, child };
}

async function preflight(base) {
  const ping = await httpJson(`${base}/api/ping`);
  if (ping.status !== 200) throw new Error(`GUI ping failed: ${ping.status}`);
  console.log(`[preflight] ping ok (${ping.body.gui} ${ping.body.version})`);

  const boot = await httpJson(`${base}/api/bootstrap`);
  if (boot.status !== 200) throw new Error(`bootstrap failed: ${boot.status}`);
  if (boot.body.runtime_state !== "running") {
    throw new Error(`runtime not running: ${boot.body.runtime_state}`);
  }
  console.log(`[preflight] runtime running (buster ${boot.body.buster_version}, host ${boot.body.host})`);

  // mark onboarding complete through the real API so Home/Live are reachable
  await httpJson(`${base}/api/prefs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key: "onboarded", value: "1" }),
  });
  return boot.body;
}

async function measure(page) {
  return page.evaluate(() => {
    const cs = (el) => getComputedStyle(el);
    const heroOrb = document.querySelector(".hero .buster-orb");
    const anyOrb = document.querySelector(".buster-orb");
    const main = document.querySelector(".app-main");
    const box = (el) => (el ? el.getBoundingClientRect() : null);

    const hero = box(heroOrb);
    const mainBox = box(main);
    const viewportArea = innerWidth * innerHeight;

    // largest rendered element inside main (rough prominence check)
    let biggest = null;
    for (const el of main ? main.querySelectorAll("*") : []) {
      const b = el.getBoundingClientRect();
      const area = b.width * b.height;
      if (!biggest || area > biggest.area) {
        biggest = { area, tag: el.tagName.toLowerCase(), cls: el.className?.toString().slice(0, 60) || "" };
      }
    }

    return {
      hash: location.hash,
      heroOrb: hero ? {
        w: Math.round(hero.width), h: Math.round(hero.height),
        state: heroOrb.getAttribute("data-state"),
        pctOfViewportHeight: Math.round((hero.height / innerHeight) * 100),
        pctOfViewportArea: +((hero.width * hero.height) / viewportArea * 100).toFixed(1),
        boxShadow: cs(heroOrb).boxShadow,
        animation: cs(heroOrb).animationName,
      } : null,
      headerOrb: anyOrb ? (() => { const b = box(anyOrb); return { w: Math.round(b.width), h: Math.round(b.height) }; })() : null,
      heroPresent: !!document.querySelector(".hero"),
      h1: document.querySelector("h1")?.textContent?.trim() || null,
      mainHeight: mainBox ? Math.round(mainBox.height) : null,
      cards: document.querySelectorAll(".card").length,
      navItems: document.querySelectorAll(".nav-item").length,
      overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      largestInMain: biggest,
      bodyBG: cs(document.body).backgroundColor,
      textColor: cs(document.body).color,
    };
  });
}

async function sweep(browser, base, outDir, screens) {
  const report = { generated: new Date().toISOString(), base, viewports: {} };
  for (const [name, viewport] of Object.entries(VIEWPORTS)) {
    const ctx = await browser.newContext({ viewport });
    const page = await ctx.newPage();
    page.on("pageerror", (err) => console.log(`[pageerror:${name}] ` + String(err).slice(0, 200)));
    const dir = path.join(outDir, name);
    fs.mkdirSync(dir, { recursive: true });
    const entries = {};
    for (const screen of screens) {
      await page.goto(`${base}/#/${screen}`, { waitUntil: "domcontentloaded" });
      await page.waitForSelector(".app-main h1, .app-main .state-note", { timeout: 30000 }).catch(() => {});
      await sleep(700);
      entries[screen] = await measure(page);
      await page.screenshot({ path: path.join(dir, `${screen}.png`), fullPage: true });
    }
    report.viewports[name] = { viewport, screens: entries };
    await ctx.close();
  }
  return report;
}

function summarise(report) {
  const lines = [];
  for (const [vp, data] of Object.entries(report.viewports)) {
    lines.push(`== ${vp} ${data.viewport.width}x${data.viewport.height}`);
    for (const [screen, m] of Object.entries(data.screens)) {
      const o = m.heroOrb;
      const orb = o ? `${o.w}x${o.h} (${o.pctOfViewportHeight}%vh, ${o.pctOfViewportArea}% area, ${o.state})` : "no hero orb";
      lines.push(`  ${screen.padEnd(12)} ${orb.padEnd(46)} hero=${String(m.heroPresent).padEnd(5)} `
        + `ovfX=${String(m.overflowX).padEnd(5)} nav=${m.navItems} cards=${m.cards} h1="${m.h1 ?? ""}"`);
    }
  }
  return lines.join("\n");
}

async function main() {
  const argv = process.argv.slice(2);
  const onlyIdx = argv.indexOf("--only");
  const screens = onlyIdx >= 0
    ? argv[onlyIdx + 1].split(",")
    : SCREENS;
  const keep = argv.includes("--keep-running");
  const outDir = path.resolve(REPO, "artifacts/ui-review");

  const install = process.env.BUSTER_INSTALL
    || path.join(fs.mkdtempSync(path.join(process.env.TEMP || ".", "buster-review-")), "state");
  const { port, version } = guiConfig();
  console.log(`[config] GUI v${version} default port ${port}; install ${install}`);

  const startedDaemon = await ensureRuntime(install);
  const { base, child: guiChild } = await ensureGui(install, port);
  const boot = await preflight(base);

  const browser = await chromium.launch({ executablePath: CHROMIUM });
  let report;
  try {
    report = await sweep(browser, base, outDir, screens);
  } finally {
    await browser.close();
  }

  report.buster = boot;
  report.install = install;
  fs.mkdirSync(outDir, { recursive: true });
  const reportPath = path.join(outDir, "report.json");
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  console.log("\n" + summarise(report));
  console.log("\nREPORT=" + reportPath);

  if (guiChild && !keep) guiChild.kill();
  if (startedDaemon && !keep) {
    run(["-m", "buster.cli", "stop", "--install-path", install]);
  }
}

await main();