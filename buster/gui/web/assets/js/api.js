/* Buster GUI — RPC client wrapper (talks to the buster-gui JSON API,
   which is itself a client of the Buster daemon). */

export class NetworkError extends Error {}

export class ApiClient {
  constructor(base = "/") {
    this.base = base;
    this.fetchImpl = typeof fetch === "function" ? fetch.bind(globalThis) : null;
  }

  async _request(method, path, body) {
    if (!this.fetchImpl) throw new NetworkError("network unavailable");
    const opts = { method, headers: { "Accept": "application/json" } };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    let res;
    try {
      res = await this.fetchImpl(path, opts);
    } catch (err) {
      throw new NetworkError(`cannot reach Buster UI: ${err.message}`);
    }
    let data = null;
    try { data = await res.json(); } catch (_) { /* non-json */ }
    if (res.status === 503 && data && data.offline) {
      return { offline: true, error: data.error ?? "runtime offline", data };
    }
    if (!res.ok) {
      throw new NetworkError(`${res.status} ${res.statusText}`);
    }
    return data ?? {};
  }

  get(path, params) {
    let url = this.base.replace(/\/$/, "") + path;
    if (params) {
      const qs = new URLSearchParams();
      for (const [k, v] of Object.entries(params)) if (v !== undefined) qs.set(k, v);
      const q = qs.toString();
      if (q) url += "?" + q;
    }
    return this._request("GET", url);
  }

  post(path, body = {}) { return this._request("POST", this.base.replace(/\/$/, "") + path, body); }
  del(path, params) {
    let url = this.base.replace(/\/$/, "") + path;
    if (params) url += "?" + new URLSearchParams(params).toString();
    return this._request("DELETE", url);
  }
}

export const api = new ApiClient();