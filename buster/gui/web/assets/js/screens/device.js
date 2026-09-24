/* Buster GUI — Device. */

import { el, clear } from "../ui.js";

export async function render(root, ctx) {
  const { api } = ctx;
  clear(root);
  root.appendChild(el("h1", null, "This Device"));

  const data = await api.get("/api/device");
  if (data.offline) {
    root.appendChild(el("p", "muted", "Reconnecting…"));
    return;
  }

  const device = data.device || {};
  const cell = (label, value) => {
    const row = el("li", null);
    row.appendChild(el("span", null, label));
    row.appendChild(el("span", "spacer"));
    row.appendChild(el("span", "small faint", String(value || "?")));
    return row;
  };

  const list = el("ul", "list");
  list.appendChild(cell("Host", device.host || "this device"));
  list.appendChild(cell("Platform", device.platform));
  list.appendChild(cell("Machine", device.machine));
  list.appendChild(cell("Python", device.python_version));
  list.appendChild(cell("CPUs", data.resources?.cpus ?? device.cpus));
  list.appendChild(cell("Storage free", bytes(data.environment?.disk?.free_bytes)));
  list.appendChild(cell("Battery", battery(data.battery)));
  root.appendChild(list);
}

function bytes(n) {
  if (n == null) return "?";
  const mb = n / 1024 / 1024;
  return mb > 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb.toFixed(0)} MB`;
}

function battery(b) {
  if (!b || b.percentage == null) return "?";
  return `${b.percentage}%${b.charging ? " (charging)" : ""}`;
}