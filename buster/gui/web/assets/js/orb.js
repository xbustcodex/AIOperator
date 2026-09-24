/* Buster GUI — the purple orb: a persistent, stateful presence.

The state machine is DOM-free so it can be unit-tested under Node. Rendering
is a thin layer that turns state into CSS-driven presence and honours
prefers-reduced-motion.
*/

export const ORB_STATES = [
  "idle",
  "listening",
  "thinking",
  "working",
  "speaking",
  "attention",
  "offline",
  "error",
];

// Allowed transitions (state -> states). Anything not listed is disallowed
// unless forced (e.g. teleporting straight to offline on disconnect).
export const ORB_TRANSITIONS = {
  idle: ["listening", "thinking", "working", "speaking", "attention", "offline", "error"],
  listening: ["thinking", "working", "speaking", "idle", "offline", "attention"],
  thinking: ["working", "speaking", "idle", "attention", "offline", "error"],
  working: ["thinking", "speaking", "idle", "attention", "offline", "error"],
  speaking: ["listening", "thinking", "working", "idle", "offline", "attention"],
  attention: ["listening", "thinking", "working", "idle", "offline", "error"],
  offline: ["idle", "error", "attention"],
  error: ["idle", "attention", "offline", "working"],
};

export const ORB_LABELS = {
  idle: "Buster is ready",
  listening: "Buster is listening",
  thinking: "Buster is thinking",
  working: "Buster is working",
  speaking: "Buster is speaking",
  attention: "Buster needs attention",
  offline: "Buster is in local mode",
  error: "Buster hit a snag",
};

export class OrbController {
  constructor() {
    this.state = "idle";
    this._onchange = null;
    this.history = [];
  }

  set(state, opts = {}) {
    const next = String(state).toLowerCase();
    if (!ORB_STATES.includes(next)) return false;
    const allowed = (ORB_TRANSITIONS[this.state] || []).includes(next);
    if (!allowed && !opts.force) return false;
    if (this.state === next && !opts.force) return false;
    this.history.push({ from: this.state, to: next, at: Date.now() });
    this.state = next;
    if (this._onchange) this._onchange(next);
    return true;
  }

  reset() {
    this.state = "idle";
    this.history = [];
  }

  label() { return ORB_LABELS[this.state] || this.state; }
}

/* Rendering (guarded so Node tests can import this module). */
export function renderOrb(container, controller, opts = {}) {
  if (typeof document === "undefined") return null;
  const size = opts.size || "normal"; // small | normal | large | hero
  const reduced = (opts.reducedMotion != null)
    ? opts.reducedMotion
    : (globalThis.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);

  const wrap = document.createElement("div");
  wrap.className = "orb-wrap orb-" + size;
  const orb = document.createElement("div");
  orb.className = "buster-orb";
  orb.setAttribute("data-state", controller.state);
  orb.setAttribute("role", "img");
  orb.setAttribute("aria-label", controller.label());
  const halo = document.createElement("span");
  halo.className = "orb-halo";
  orb.appendChild(halo);
  wrap.appendChild(orb);

  if (reduced) wrap.classList.add("reduced-motion");

  controller._onchange = (state) => {
    orb.setAttribute("data-state", state);
    orb.setAttribute("aria-label", controller.label());
  };
  container.innerHTML = "";
  container.appendChild(wrap);
  return { wrap, orb };
}