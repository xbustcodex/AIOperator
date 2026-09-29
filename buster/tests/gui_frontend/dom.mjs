/* Minimal DOM harness for Buster GUI frontend tests.
 *
 * The single behaviour that must be modelled exactly is `location.hash`:
 * a browser emits `hashchange` only when the value actually changes. The
 * fresh-install "Waking Buster…" defect lived precisely in that gap, so a
 * harness that fired the event unconditionally would hide the regression.
 */

class Node {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.attributes = {};
    this.dataset = {};
    this.style = {};
    this.listeners = {};
    this.className = "";
    this._text = "";
    this._html = "";
    this.value = "";
    this.placeholder = "";
    this.hidden = false;
  }

  get textContent() {
    if (this.children.length === 0) return this._text;
    return this.children.map((c) => c.textContent).join("");
  }

  set textContent(v) { this._text = String(v); this.children = []; }

  get innerHTML() { return this._html; }

  set innerHTML(v) {
    this._html = v;
    if (v === "") { this.children = []; this._text = ""; }
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
    if (name.startsWith("data-")) {
      const key = name.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      this.dataset[key] = String(value);
    }
  }

  getAttribute(name) {
    return Object.prototype.hasOwnProperty.call(this.attributes, name)
      ? this.attributes[name] : null;
  }

  appendChild(child) { this.children.push(child); return child; }
  append(...nodes) { for (const n of nodes) this.appendChild(n); }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  removeEventListener() {}
  focus() {}
  click() {}

  querySelectorAll(selector) {
    const cls = String(selector).replace(/^\./, "");
    const out = [];
    const walk = (n) => {
      for (const c of n.children) {
        if (String(c.className).split(/\s+/).includes(cls)) out.push(c);
        walk(c);
      }
    };
    walk(this);
    return out;
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }
}

class ClassList {
  constructor(node) { this.node = node; }
  add(...names) {
    const cur = new Set(String(this.node.className).split(/\s+/).filter(Boolean));
    for (const n of names) cur.add(n);
    this.node.className = [...cur].join(" ");
  }
  remove(...names) {
    const cur = new Set(String(this.node.className).split(/\s+/).filter(Boolean));
    for (const n of names) cur.delete(n);
    this.node.className = [...cur].join(" ");
  }
  contains(n) { return String(this.node.className).split(/\s+/).includes(n); }
}

const ELEMENTS = ["app-orb", "nav-track", "app-status", "app-main",
  "offline-notch", "error-toast"];

/**
 * The JSON bodies the stable `fetch` serves for the current boot.
 *
 * `api.js` binds `fetch` once, when it is first imported, and keeps that
 * bound reference for the life of the module. Reassigning `globalThis.fetch`
 * between cases would be silently ignored, and every case after the first
 * would replay the first one's bodies. So one stable fetch is installed and
 * this table is what changes between boots.
 */
const routesRef = { current: {} };

let fetchInstalled = false;

function installStableFetch() {
  if (fetchInstalled) return;
  fetchInstalled = true;
  globalThis.fetch = async (url) => {
    const key = String(url);
    const body = Object.prototype.hasOwnProperty.call(routesRef.current, key)
      ? routesRef.current[key] : {};
    return { status: 200, ok: true, statusText: "OK", json: async () => body };
  };
}

/**
 * Install a DOM on globalThis and return a handle for inspection.
 */
export function installDom({ hash = "" } = {}) {
  const errors = [];
  const byId = {};
  for (const id of ELEMENTS) {
    const node = new Node("div");
    node.id = id;
    node.classList = new ClassList(node);
    byId[id] = node;
  }

  let currentHash = hash;
  let hashChanges = 0;
  const windowListeners = {};

  const location = {
    get hash() { return currentHash; },
    set hash(value) {
      const next = String(value);
      const normalized = next.startsWith("#") ? next : "#" + next;
      // A real browser fires hashchange ONLY on an actual change. Modelling
      // this faithfully is what makes the regression observable.
      if (normalized === currentHash) return;
      currentHash = normalized;
      hashChanges += 1;
      queueMicrotask(() => {
        for (const fn of (windowListeners.hashchange || []).slice()) {
          fn({ type: "hashchange" });
        }
      });
    },
  };

  const document = {
    createElement: (tag) => {
      const n = new Node(tag);
      n.classList = new ClassList(n);
      return n;
    },
    getElementById: (id) => byId[id] || null,
    querySelectorAll: (sel) => byId["nav-track"].querySelectorAll(sel),
    querySelector: (sel) => byId["nav-track"].querySelector(sel),
    addEventListener() {},
    body: new Node("body"),
  };

  const win = {
    location,
    document,
    addEventListener(type, fn) { (windowListeners[type] ||= []).push(fn); },
    removeEventListener() {},
    matchMedia: () => ({ matches: false }),
    setTimeout: (fn, ms) => setTimeout(fn, ms),
    clearTimeout: (id) => clearTimeout(id),
    SpeechRecognition: undefined,
    webkitSpeechRecognition: undefined,
  };

  globalThis.window = win;
  globalThis.document = document;
  globalThis.location = location;
  globalThis.addEventListener = win.addEventListener;
  globalThis.removeEventListener = win.removeEventListener;
  globalThis.matchMedia = win.matchMedia;
  installStableFetch();

  const realError = console.error;
  console.error = (...args) => { errors.push(args.map(String).join(" ")); };

  return {
    errors,
    get hashChanges() { return hashChanges; },
    /** Install the JSON bodies served for the current boot. */
    serve(routes) { routesRef.current = routes || {}; },
    /**
     * Drain every pending continuation: microtasks, timers and immediates.
     *
     * app.js awaits a chain of promises before rendering, so a shallow drain
     * leaves that render in flight. The next case then installs a fresh DOM
     * and the *previous* boot's late render lands in it, which shows up as a
     * phantom screen from the wrong case. Drain to a fixed point instead.
     */
    async settle() {
      for (let i = 0; i < 8; i += 1) {
        for (let j = 0; j < 40; j += 1) await Promise.resolve();
        await new Promise((r) => setTimeout(r, 0));
        await new Promise((r) => setImmediate(r));
      }
    },
    snapshot() {
      console.error = realError;
      return {
        mainText: byId["app-main"].textContent,
        statusText: byId["app-status"].textContent,
        navText: byId["nav-track"].textContent,
        hash: currentHash,
        hashChanges,
        errors,
      };
    },
  };
}
