/* Buster GUI — Updates. */

import { el, clear } from "../ui.js";

export async function render(root, ctx) {
  const { api } = ctx;
  clear(root);
  root.appendChild(el("h1", null, "Updates"));

  const data = await api.get("/api/updates");
  if (data.offline) {
    root.appendChild(el("p", "muted", "Reconnecting…"));
    return;
  }

  const card = el("div", "card");
  card.appendChild(el("h2", null, "Buster version"));
  const table = el("table", "meta");
  const rows = [
    ["Installed", data.buster_version || "?"],
    ["Runtime", data.runtime_state || "?"],
    ["State dir", data.install_path || "?"],
  ];
  for (const [k, v] of rows) {
    const tr = el("tr");
    tr.append(el("td", null, k), el("td", null, v));
    table.appendChild(tr);
  }
  card.appendChild(table);
  root.appendChild(card);

  const note = el("p", "small faint",
    data.updater_note || "Updates are managed by Buster's bootstrap and update system.");
  root.appendChild(note);
}