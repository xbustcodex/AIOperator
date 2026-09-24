/* Buster GUI — Memory / Preferences.

Exposes Buster's existing memory stores in readable form and lets the user
edit preferences. No second memory authority — everything goes through
Buster's own store. Raw episodic/procedural databases are not shown here.
*/

import { el, clear } from "../ui.js";

export async function render(root, ctx) {
  const { api } = ctx;
  clear(root);
  root.appendChild(el("h1", null, "Memory & Preferences"));

  let mem;
  try {
    mem = await api.get("/api/memory");
  } catch {
    root.appendChild(el("p", "muted", "Memory unavailable right now."));
    return;
  }
  if (mem.offline) {
    root.appendChild(el("p", "muted", "Reconnecting…"));
    return;
  }

  const stats = mem.stats || {};
  const keys = stats.knowledge_keys || [];

  const intro = el("p", "muted",
    "Buster keeps useful things it has learned and the preferences you set. " +
    "It works even when it's offline, and it's stored on this device.");
  root.appendChild(intro);

  const learned = el("div", "card");
  learned.appendChild(el("h2", null, "Things Buster is learning"));
  if (keys.length) {
    const grid = el("div", "row gap-sm");
    for (const key of keys.slice(0, 16)) {
      const chip = el("span", "badge done", friendlyKey(key));
      grid.appendChild(chip);
    }
    learned.appendChild(grid);
  } else {
    learned.appendChild(el("p", "muted", "Buster is still getting familiar with things."));
  }
  root.appendChild(learned);

  const prefCard = el("div", "card");
  prefCard.appendChild(el("h2", null, "Your preferences"));
  const prefs = mem.preferences || {};
  if (Object.keys(prefs).length) {
    const list = el("ul", "list");
    for (const [k, v] of Object.entries(prefs)) {
      const li = el("li", null);
      const row = el("div", "row");
      row.appendChild(el("span", "small", friendlyKey(k)));
      const input = el("input");
      input.type = "text";
      input.value = String(v);
      input.addEventListener("change", async () => {
        await api.post("/api/prefs", { key: k, value: input.value });
      });
      row.append(input);
      li.append(row);
      list.appendChild(li);
    }
    prefCard.appendChild(list);
  } else {
    prefCard.appendChild(el("p", "muted", "No preferences set yet."));
  }
  root.appendChild(prefCard);

  const note = el("p", "small faint",
    "Internal experience and procedural records stay inside Buster and are " +
    "managed in Advanced. This page shows the useful, understandable parts.");
  root.appendChild(note);
}

function friendlyKey(key) {
  const clean = String(key || "").replace(/^(lesson|goal_seen|pattern|agent_working|avoid_repeat):/, "");
  return clean.split("_").join(" ").slice(0, 40);
}