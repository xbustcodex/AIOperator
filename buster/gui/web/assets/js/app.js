/* Buster GUI — application entry point. */

import { api } from "./api.js";
import { Store, orbStateFor } from "./state.js";
import { OrbController, renderOrb } from "./orb.js";
import { routesFor, resolveRoute, routeFromScreen } from "./nav.js";
import { renderScreen } from "./screens/index.js";

const store = new Store();
const orb = new OrbController();

const els = {
  orb: () => document.getElementById("app-orb"),
  nav: () => document.getElementById("nav-track"),
  status: () => document.getElementById("app-status"),
  main: () => document.getElementById("app-main"),
  offline: () => document.getElementById("offline-notch"),
  error: () => document.getElementById("error-toast"),
};

function go(screen, param) {
  const route = routeFromScreen(screen, store.get("boot"));
  window.location.hash = "/" + route.id;
  if (param) store.set("routeParam", param);
}

async function boot() {
  // 1. Paint the shell first so the user always sees Buster, then hydrate.
  renderNav({});
  await renderHeaderOrb();
  els.status().textContent = "Starting…";
  showLoading("Waking Buster…");
  setOrb("thinking");

  let payload = { online: false };
  try {
    payload = await api.get("/api/bootstrap");
  } catch (_) {
    payload = { online: false };
  }
  store.set("boot", payload);
  store.set("runtime", {
    online: !!payload.online && payload.runtime_state === "running",
    state: payload.runtime_state,
  });
  renderNav(payload);
  setOrb(orbStateFor(store.get("runtime")));

  // 2. Onboarding state, best-effort (must never block the first paint).
  let onboarded = false;
  try {
    const mem = await api.get("/api/memory");
    onboarded = mem && mem.preferences && (mem.preferences.onboarded === "1"
      || mem.preferences.onboarded === true);
  } catch (_) {
    onboarded = false;
  }
  store.set("onboarded", onboarded);
  route();
}

function showLoading(text) {
  const main = els.main();
  main.innerHTML = "";
  const note = document.createElement("div");
  note.className = "state-note";
  const spinner = document.createElement("div");
  spinner.className = "spinner";
  const label = document.createElement("p");
  label.textContent = text;
  note.append(spinner, label);
  main.appendChild(note);
}

function renderNav(boot) {
  const container = els.nav();
  container.innerHTML = "";
  for (const area of routesFor(boot)) {
    const b = document.createElement("button");
    b.className = "nav-item";
    b.dataset.route = area.id;
    b.textContent = area.label;
    b.setAttribute("aria-label", area.label);
    b.addEventListener("click", () => { window.location.hash = "/" + area.id; });
    container.appendChild(b);
  }
}

async function renderHeaderOrb() {
  const host = els.orb();
  if (!host) return;
  host.innerHTML = "";
  renderOrb(host, orb, { size: "small" });
  host.setAttribute("aria-hidden", "true");
}

function setOrb(state) {
  orb.set(state, { force: true });
  const host = els.orb();
  if (host) {
    // Re-render its data-state in place without rebuilding every nav change.
    const inner = host.querySelector(".buster-orb");
    if (inner) inner.setAttribute("data-state", orb.state);
  }
}

window.setOrb = setOrb;
window.store = store;
window.orb = orb;

async function route() {
  const boot = store.get("boot") || {};
  const route = resolveRoute(window.location.hash, boot);
  const target = routeFromScreen(route.screen, boot);

  if (!store.get("onboarded") && target.screen !== "onboarding" && target.screen !== "advanced") {
    window.location.hash = "/onboarding";
    return;
  }

  for (const b of els.nav().querySelectorAll(".nav-item")) {
    b.setAttribute("aria-current", String(b.dataset.route === target.id));
  }
  setOrb(orbStateFor(store.get("runtime")));

  const runtime = store.get("runtime") || {};
  els.status().textContent = runtime.online
    ? "Buster is available"
    : (runtime.state === "starting" ? "Starting…" : "Buster is in local mode");

  const ctx = { api, store, orb, go, routeParam: store.get("routeParam") };
  els.main().innerHTML = "";
  try {
    await renderScreen(target.screen, els.main(), ctx);
  } catch (err) {
    showError("Something went wrong loading this screen. Buster is still running.");
    console.error(err);
  }
}

function showError(text) {
  const e = els.error();
  e.textContent = text;
  e.hidden = false;
  setTimeout(() => { e.hidden = true; }, 5000);
}

window.addEventListener("hashchange", route);
window.addEventListener("online", () => { els.offline().hidden = true; route(); });
window.addEventListener("offline", () => {
  showError("You're offline. Buster is still available in local mode.");
  els.offline().hidden = false;
});

export { store, orb, go, route, boot };

boot();