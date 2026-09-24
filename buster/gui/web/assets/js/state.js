/* Buster GUI — frontend state store (presentation state only; the Buster
   runtime remains the single source of truth). */

export class Store {
  constructor(seed = {}) {
    this._data = { ...seed };
    this._listeners = new Map();
  }

  get(key, fallback) {
    const chains = key.split(".");
    let node = this._data;
    for (const part of chains) {
      if (node == null || !(part in Object(node))) return fallback;
      node = node[part];
    }
    return node;
  }

  set(key, value) {
    const chains = key.split(".");
    let node = this._data;
    for (let i = 0; i < chains.length - 1; i++) {
      if (node[chains[i]] == null || typeof node[chains[i]] !== "object") node[chains[i]] = {};
      node = node[chains[i]];
    }
    const leaf = chains[chains.length - 1];
    node[leaf] = value;
    this.emit(key, value);
    return value;
  }

  subscribe(key, fn) {
    if (!this._listeners.has(key)) this._listeners.set(key, []);
    this._listeners.get(key).push(fn);
    return () => {
      const list = this._listeners.get(key) || [];
      const idx = list.indexOf(fn);
      if (idx >= 0) list.splice(idx, 1);
    };
  }

  emit(key, value) {
    const list = this._listeners.get(key) || [];
    for (const fn of list.slice()) fn(value, key);
  }
}

export const runtimeSummary = (status) => {
  if (!status) return { online: false, state: "offline" };
  return {
    online: true,
    state: status.state || "unknown",
    providers: status.ai_providers || [],
    capabilities: status.capabilities || [],
  };
};

export const orbStateFor = (summary, busy = null) => {
  if (busy) return busy;
  if (!summary || !summary.online) return "offline";
  if (summary.state === "running") return "idle";
  return "attention";
};