/* Visual review capture driver — uses the ALREADY-RUNNING Buster GUI at
   127.0.0.1:8468 (no daemon/GUI spawning). Captures each screen at desktop
   and mobile viewports, both in default (OS) and forced-dark color schemes,
   writes screenshots + a measurements report.
*/

import { chromium } from "file:///C:/Users/xkali/new_ai/webApp/frontend/node_modules/playwright/index.mjs";
import fs from "node:fs";
import path from "node:path";

const REPO = path.resolve(import.meta.dirname, "../../../..");
const BASE = "http://127.0.0.1:8468";
const CHROMIUM = process.env.BUSTER_CHROMIUM
  || "C:/Users/xkali/AppData/Local/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-win64/chrome-headless-shell.exe";

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  mobile: { width: 390, height: 844 },
};

const SCREENS = [
  ["home", "Hey, I'm here."],
  ["live", "Buster Live"],
  ["talk", "Talk to Buster"],
  ["tasks", "Tasks & Projects"],
  ["files", "My Files"],
  ["memory", "Memory & Preferences"],
  ["permissions", "Permissions & Approvals"],
  ["device", "This Device"],
  ["activity", "Activity"],
  ["settings", "Settings"],
  ["updates", "Updates"],
  ["advanced", "Advanced"],
];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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

    let biggest = null;
    for (const el of main ? main.querySelectorAll("*") : []) {
      const b = el.getBoundingClientRect();
      const area = b.width * b.height;
      if (!biggest || area > biggest.area) {
        biggest = { area: Math.round(area), tag: el.tagName.toLowerCase(), cls: String(el.className).slice(0, 60) };
      }
    }
    let fontSize = null;
    const h1 = document.querySelector("h1");
    if (h1) fontSize = cs(h1).fontSize;

    const halo = document.querySelector(".orb-halo");
    return {
      hash: location.hash,
      heroOrb: hero ? {
        w: Math.round(hero.width), h: Math.round(hero.height),
        state: heroOrb.getAttribute("data-state"),
        pctVh: Math.round((hero.height / innerHeight) * 100),
        pctArea: +((hero.width * hero.height) / viewportArea * 100).toFixed(1),
        glow: cs(heroOrb).boxShadow.slice(0, 120),
        anim: cs(heroOrb).animationName.split(",")[0],
        haloOpacity: halo ? cs(halo).opacity : "n/a",
      } : null,
      headerOrb: anyOrb ? null : null,
      heroPresent: !!document.querySelector(".hero"),
      h1: h1?.textContent?.trim() || null,
      h1Size: fontSize,
      bodyBG: cs(document.body).backgroundColor,
      textColor: cs(document.body).color,
      mainMaxW: mainBox ? Math.round(mainBox.width) : null,
      overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      scrollW: document.documentElement.scrollWidth,
      clientW: document.documentElement.clientWidth,
    };
  });
}

async function main() {
  const tag = process.argv[2] || "pass0";
  const schema = process.argv[3] || "default"; // default | dark
  const outDir = path.join(REPO, "artifacts", "ui-review", tag);
  const browser = await chromium.launch({ executablePath: CHROMIUM });
  const report = { tag, schema, base: BASE, viewports: {} };
  try {
    for (const [name, viewport] of Object.entries(VIEWPORTS)) {
      const contextOptions = { viewport };
      if (schema === "dark") contextOptions.colorScheme = "dark";
      if (schema === "light") contextOptions.colorScheme = "light";
      const ctx = await browser.newContext(contextOptions);
      const page = await ctx.newPage();
      page.on("pageerror", (err) => console.log(`[pageerror:${name}] ` + String(err).slice(0, 160)));
      const dir = path.join(outDir, name);
      fs.mkdirSync(dir, { recursive: true });
      const entries = {};
      for (const [screen, heading] of SCREENS) {
        await page.goto(`${BASE}/#/${screen}`, { waitUntil: "domcontentloaded" });
        // wait for the screen's own heading (boot + route complete; also
        // guards against a stale previous screen / route fallback to Home)
        await page.waitForFunction(
          (h) => {
            const el = document.querySelector(".app-main h1");
            return el && el.textContent.trim() === h;
          },
          heading,
          { timeout: 30000 },
        ).catch(() => { console.log(`!! ${name}/${screen}: heading not reached (fallback?)`); });
        await sleep(700);
        entries[screen] = await measure(page);
        await page.screenshot({ path: path.join(dir, screen + ".png"), fullPage: true });
      }
      report.viewports[name] = { viewport, screens: entries };
      await ctx.close();
    }
  } finally {
    await browser.close();
  }
  fs.mkdirSync(outDir, { recursive: true });
  const reportPath = path.join(outDir, "report.json");
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  console.log("REPORT=" + reportPath);
  for (const [vp, data] of Object.entries(report.viewports)) {
    for (const [screen, m] of Object.entries(data.screens)) {
      const o = m.heroOrb;
      const orb = o ? `${o.w}x${o.h} ${o.pctVh}%vh ${o.pctArea}%area ${o.state}` : "no-orb";
      console.log(`${vp.padEnd(7)} ${screen.padEnd(12)} ${orb.padEnd(34)} bg=${m.bodyBG} h1="${m.h1}"`);
    }
  }
}

await main();