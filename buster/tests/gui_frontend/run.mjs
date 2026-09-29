/* Buster GUI frontend regression tests.
 *
 * These run the *real* shipped modules (buster/gui/web/assets/js) against a
 * minimal DOM harness that reproduces the one browser behaviour the fresh-
 * install bug turned on: assigning `location.hash` a value the document
 * already has emits NO `hashchange` event.
 *
 * That fidelity matters. A harness that fired `hashchange` on every
 * assignment would pass the old, broken app.js, because the redirect would
 * appear to work. The regression is only observable when the no-op assignment
 * is modelled honestly.
 *
 * Run:  node buster/tests/gui_frontend/run.mjs
 */

import { installDom } from "./dom.mjs";
import assert from "node:assert/strict";

const JS = new URL("../../gui/web/assets/js/", import.meta.url);

let passed = 0;
const failures = [];

async function test(name, fn) {
  try {
    await fn();
    passed += 1;
    console.log(`ok   - ${name}`);
  } catch (err) {
    failures.push({ name, err });
    console.log(`FAIL - ${name}`);
    console.log(`       ${err && err.message}`);
  }
}

/* -- pure navigation model ------------------------------------------- */

await test("resolveRoute('#/onboarding') resolves the onboarding route", async () => {
  const nav = await import(JS + "nav.js");
  const route = nav.resolveRoute("#/onboarding", {});
  assert.equal(route.id, "onboarding");
  assert.equal(route.screen, "onboarding");
});

await test("routeFromScreen('onboarding') resolves the onboarding route", async () => {
  const nav = await import(JS + "nav.js");
  const route = nav.routeFromScreen("onboarding", {});
  assert.equal(route.id, "onboarding");
  assert.equal(route.screen, "onboarding");
});

await test("onboarding is resolvable but is NOT a visible nav destination", async () => {
  const nav = await import(JS + "nav.js");
  assert.ok(nav.NAV_AREAS.some((a) => a.id === "onboarding"),
    "onboarding must exist in route metadata so it can resolve");
  for (const boot of [{}, { advanced: { enabled: true } }]) {
    const visible = nav.routesFor(boot).map((a) => a.id);
    assert.ok(!visible.includes("onboarding"),
      `onboarding must stay out of the nav track (boot=${JSON.stringify(boot)})`);
  }
});

await test("established nav behaviour is preserved", async () => {
  const nav = await import(JS + "nav.js");
  assert.equal(nav.resolveRoute("", {}).id, "home");
  assert.equal(nav.resolveRoute("#/files", {}).id, "files");
  assert.equal(nav.resolveRoute("#/advanced", {}).id, "advanced");
  // Advanced stays gated behind the flag, exactly as before.
  assert.ok(!nav.routesFor({}).some((a) => a.id === "advanced"));
  assert.ok(nav.routesFor({ advanced: { enabled: true } }).some((a) => a.id === "advanced"));
  const plain = nav.routesFor({}).map((a) => a.id);
  assert.deepEqual(plain,
    ["home", "talk", "live", "terminal", "files", "tasks", "memory",
      "device", "activity", "permissions", "updates", "settings"],
    "the visible nav track must be unchanged by the onboarding repair");
});

/* -- full application boot against the DOM harness -------------------- */

/**
 * Boot the real app.js with stubbed API responses and return the settled DOM.
 *
 * `prefs` drives the `/api/memory` payload that decides `onboarded`.
 */
async function bootApp({ prefs, hash = "" }) {
  const dom = installDom({ hash });
  dom.serve({
    "/api/bootstrap": {
      buster_version: "0.4.2", install_path: "/var/lib/buster",
      runtime_state: "running", online: true, host: "terminalp",
    },
    "/api/memory": { stats: {}, preferences: prefs || {} },
  });
  // A unique query string defeats the ES module cache so app.js re-runs its
  // top-level boot() for every case in this file.
  await import(JS + "app.js?boot=" + Math.random());
  await dom.settle();
  return dom.snapshot();
}

await test("preferences:{} leaves the loading state and renders onboarding", async () => {
  const snap = await bootApp({ prefs: {} });

  assert.equal(snap.errors.length, 0, `unexpected page errors: ${snap.errors.join("; ")}`);
  assert.ok(!snap.mainText.includes("Waking Buster"),
    "the app must not be left in its loading markup");
  assert.ok(!snap.statusText.includes("Starting"),
    "the header must not still read Starting…");
  assert.ok(snap.mainText.includes("Welcome to Buster"),
    `onboarding must render, got: ${JSON.stringify(snap.mainText)}`);
  assert.equal(snap.hash, "#/onboarding",
    "the URL must reflect the onboarding destination");
});

await test('an already-current "#/onboarding" hash still renders (the 0.4.2 defect)', async () => {
  // This is the exact live-Pixel failure: the document already carries the
  // onboarding hash, so the old guard's assignment was a no-op that emitted no
  // hashchange and the loading markup stayed forever.
  const snap = await bootApp({ prefs: {}, hash: "#/onboarding" });

  assert.equal(snap.errors.length, 0, `unexpected page errors: ${snap.errors.join("; ")}`);
  assert.ok(!snap.mainText.includes("Waking Buster"),
    "an unchanged hash must not strand the app in its loading markup");
  assert.ok(snap.mainText.includes("Welcome to Buster"),
    `onboarding must render, got: ${JSON.stringify(snap.mainText)}`);
  assert.equal(snap.hashChanges, 0,
    "assigning the already-current hash must not be relied on to re-enter");
});

await test('onboarded:"1" continues to render the established normal destination', async () => {
  const snap = await bootApp({ prefs: { onboarded: "1" } });

  assert.equal(snap.errors.length, 0, `unexpected page errors: ${snap.errors.join("; ")}`);
  assert.ok(!snap.mainText.includes("Welcome to Buster"),
    "an onboarded install must not be sent back to onboarding");
  assert.ok(snap.mainText.includes("Hey, I'm here."),
    `Home must render as before, got: ${JSON.stringify(snap.mainText)}`);
  assert.equal(snap.statusText, "Buster is available");
});

/* -- report ----------------------------------------------------------- */

console.log("");
console.log(`${passed} passed, ${failures.length} failed`);
if (failures.length) {
  for (const f of failures) console.error(`\n${f.name}\n${f.err && f.err.stack}`);
  process.exit(1);
}
