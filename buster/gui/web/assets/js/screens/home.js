/* Buster GUI — Home: is Buster available, what is it doing, anything
   waiting, what can I ask, what have we worked on recently. */

import { el, clear } from "../ui.js";
import { formatTime, activityWords, statusBadge } from "../ui.js";

export const QUICK_ASKS = [
  "Where are my files?",
  "Check my device",
  "What are we working on?",
  "Help me organise a project",
];

export async function render(root, ctx) {
  const { api, store, orb, go } = ctx;
  const { renderOrb } = await import("../orb.js");
  clear(root);
  const summary = store.get("runtime") || {};
  orb.set(store.get("busy") || (summary.online ? "idle" : "offline"), { force: true });

  const hero = el("section", "hero");
  const orbHost = el("div", null);
  hero.appendChild(orbHost);
  renderOrb(orbHost, orb, { size: "large" });
  const greeting = el("h1", null, summary.online ? "Hey, I'm here." : "I'm here — in local mode.");
  hero.appendChild(greeting);
  const sub = el("p", "muted");
  sub.textContent = summary.online
    ? "Ask me anything, or pick up where we left off."
    : "I can still work with the things on this device.";
  hero.appendChild(sub);
  const liveBtn = el("button", "action primary", "Talk live");
  liveBtn.addEventListener("click", () => go("live"));
  hero.appendChild(liveBtn);
  root.appendChild(hero);

  const card = el("div", "card stack");
  const quickRow = el("div", "row gap-sm");
  for (const ask of QUICK_ASKS) {
    const btn = el("button", "action soft", ask);
    btn.addEventListener("click", () => go("chat", ask));
    quickRow.appendChild(btn);
  }
  card.appendChild(quickRow);
  root.appendChild(card);

  // waiting-for-you
  const attentionCard = el("div", "card");
  const title = el("h2", null, "Anything waiting for you?");
  attentionCard.appendChild(title);
  const attention = await api.get("/api/attention");
  if (attention.offline) {
    attentionCard.appendChild(el("p", "muted", "Buster is offline — this will update when it reconnects."));
  } else {
    const waiting = attention.active_goals || [];
    if (waiting.length === 0) {
      attentionCard.appendChild(el("p", "muted", "Nothing is waiting. You're all caught up."));
    } else {
      const list = el("ul", "list");
      for (const goal of waiting.slice(0, 6)) {
        const li = el("li", null);
        const label = el("span", null, goal.title);
        const badge = statusBadge("waiting", "waiting");
        li.append(label, el("span", "spacer"), badge);
        list.appendChild(li);
      }
      attentionCard.appendChild(list);
    }
  }
  root.appendChild(attentionCard);

  // recent activity
  const recentCard = el("div", "card");
  const recentTitle = el("h2", null, "What we've been working on");
  recentCard.appendChild(recentTitle);
  const activity = await api.get("/api/activity");
  if (activity.offline) {
    recentCard.appendChild(el("p", "muted", "Recent activity isn't available until Buster reconnects."));
  } else {
    const items = [
      ...(activity.goals || []).map((g) => ({
        text: (g.title || "") + " — " + (g.status || ""), ts: g.updated || g.created,
      })),
      ...(activity.experiences || []).map((e) => ({ text: e.target, ts: e.ts })),
      ...(activity.events || []).map((e) => ({ text: e.type, ts: e.ts })),
    ].filter((i) => i.text).slice(-7).reverse();
    const list = el("ul", "list");
    for (const item of items) {
      const li = el("li", null);
      li.appendChild(el("span", null, activityWords(item)));
      const ts = formatTime(item.ts);
      if (ts) li.appendChild(el("span", "small faint", ts));
      list.appendChild(li);
    }
    recentCard.appendChild(list);
  }
  root.appendChild(recentCard);
}