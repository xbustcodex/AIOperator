/* Buster GUI — Advanced (technical). Intentionally separate. */

import { el, clear } from "../ui.js";

const SECTIONS = ["health", "status", "providers", "memory", "goals", "world", "capabilities", "jobs"];

export async function render(root, ctx) {
  const { api } = ctx;
  clear(root);
  root.appendChild(el("h1", null, "Advanced"));

  const intro = el("p", "muted", "Technical view — the everyday Buster surfaces stay simple on purpose.");
  root.appendChild(intro);

  const tabs = el("div", "row gap-sm");
  for (const id of SECTIONS) {
    const b = el("button", "action soft", id);
    b.addEventListener("click", () => load(id));
    tabs.appendChild(b);
  }
  root.appendChild(tabs);

  const frame = el("div", "card");
  root.appendChild(frame);

  async function load(id) {
    clear(frame);
    frame.appendChild(el("p", "muted", "Loading…"));
    let data = null;
    try {
      data = await api.get("/api/advanced/" + id);
    } catch (_) {
      clear(frame);
      frame.appendChild(el("p", "muted", "Unavailable right now."));
      return;
    }
    clear(frame);
    if (data && data.offline) {
      frame.appendChild(el("p", "muted", "Reconnecting…"));
      return;
    }
    const pre = el("pre", "small", JSON.stringify(data, null, 2));
    frame.appendChild(pre);
  }

  load("health");
}