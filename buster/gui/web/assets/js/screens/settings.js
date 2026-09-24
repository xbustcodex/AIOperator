/* Buster GUI — Settings (consumer). */

import { el, clear } from "../ui.js";

export async function render(root, ctx) {
  const { api, go } = ctx;
  clear(root);
  root.appendChild(el("h1", null, "Settings"));

  const data = await api.get("/api/settings");
  if (data.offline) {
    root.appendChild(el("p", "muted", "Reconnecting…"));
    return;
  }

  const status = data.status || {};
  const card = el("div", "card");
  card.appendChild(el("h2", null, "Buster"));
  const table = el("table", "meta");
  const rows = [
    ["Status", status.state === "running" ? "Available" : "Starting"],
    ["AI providers", (status.ai_providers || []).join(", ") || "local"],
    ["Capabilities", String((status.capabilities || []).length)],
    ["Version", (data.updates && data.updates.buster_version) || "?"],
  ];
  for (const [k, v] of rows) {
    const tr = el("tr");
    tr.append(el("td", null, k), el("td", null, v));
    table.appendChild(tr);
  }
  card.appendChild(table);
  root.appendChild(card);

  const pref = el("div", "card");
  pref.appendChild(el("h2", null, "Preferences"));
  const addRow = el("div", "row");
  const key = el("input"); key.placeholder = "name";
  const value = el("input"); value.placeholder = "value";
  const save = el("button", "action primary", "Save");
  save.addEventListener("click", async () => {
    if (key.value.trim()) {
      await api.post("/api/prefs", { key: key.value.trim(), value: value.value });
      key.value = ""; value.value = "";
    }
  });
  addRow.append(key, value, save);
  pref.appendChild(addRow);
  root.appendChild(pref);

  const links = el("div", "card");
  links.appendChild(el("h2", null, "Related"));
  const row = el("div", "row gap-sm");
  for (const [label, screen] of [["Permissions", "permissions"], ["Memory", "memory"], ["Updates", "updates"]]) {
    const b = el("button", "action soft", label);
    b.addEventListener("click", () => go(screen));
    row.appendChild(b);
  }
  links.appendChild(row);
  root.appendChild(links);
}