/* Buster GUI — Permissions & Approvals. */

import { el, clear } from "../ui.js";

export async function render(root, ctx) {
  const { api } = ctx;
  clear(root);
  root.appendChild(el("h1", null, "Permissions & Approvals"));

  const data = await api.get("/api/permissions");
  if (data.offline) {
    root.appendChild(el("p", "muted", "Permissions need Buster online."));
    return;
  }

  const card = el("div", "card");
  card.appendChild(el("h2", null, "Current Rules"));
  const list = el("ul", "list");
  for (const action of Object.keys(data.rules || {}).sort()) {
    const rule = data.rules[action];
    const li = el("li", null);
    const badge = el("span", "badge " + (rule.allow ? "done" : "denied"), rule.allow ? "Allow" : "Deny");
    li.appendChild(el("code", "small", action));
    li.appendChild(el("span", "spacer"));
    li.appendChild(badge);
    list.appendChild(li);
  }
  if (!Object.keys(data.rules || {}).length) {
    list.appendChild(el("li", "muted", "No explicit rules. Default is deny."));
  }
  root.appendChild(list);
  root.appendChild(el("hr"));

  const controls = el("div", "card");
  controls.appendChild(el("h2", null, "Change a Rule"));
  const row = el("div", "row");
  const sel = el("select");
  sel.innerHTML = Object.keys(data.sensitive || {}).map(a => `<option>${a}</option>`).join("");
  const grant = el("button", "action", "Grant");
  const deny = el("button", "action danger", "Deny");
  row.append(sel, grant, deny);
  controls.appendChild(row);
  controls.appendChild(el("p", "small faint", "Changes take effect immediately. Sensitive actions always require explicit grant."));
  root.appendChild(controls);
}