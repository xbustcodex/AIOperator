/* Buster GUI — Activity. */

import { el, clear } from "../ui.js";
import { friendlyState } from "../ui.js";

export async function render(root, ctx) {
  const { api } = ctx;
  clear(root);
  root.appendChild(el("h1", null, "Activity"));

  const data = await api.get("/api/activity");
  if (data.offline) {
    root.appendChild(el("p", "muted", "Reconnecting…"));
    return;
  }

  const goals = data.goals || [];
  if (goals.length) {
    root.appendChild(el("h2", null, "In progress"));
    const list = el("ul", "list");
    for (const goal of goals.filter((g) => g.status === "active").slice(-5)) {
      const li = el("li");
      li.appendChild(el("span", null, goal.title || "Task"));
      li.appendChild(el("span", "spacer"));
      li.appendChild(el("span", "small faint", Math.round((goal.progress || 0) * 100) + "%"));
      list.appendChild(li);
    }
    root.appendChild(list);
  }

  const events = (data.events || []).slice(-10);
  if (events.length) {
    root.appendChild(el("h2", null, "Recent"));
    const list = el("ul", "list");
    for (const event of events) {
      const li = el("li");
      li.appendChild(el("span", null, translateEvent(event.type)));
      list.appendChild(li);
    }
    root.appendChild(list);
  }

  const experiences = data.experiences || [];
  if (experiences.length) {
    root.appendChild(el("h2", null, "Things Buster has worked on"));
    const list = el("ul", "list");
    for (const exp of experiences.slice(-5).reverse()) {
      const li = el("li");
      li.appendChild(el("span", null, exp.target || "task"));
      li.appendChild(el("span", "spacer"));
      li.appendChild(el("span", "badge " + (exp.status === "done" ? "done" : "active"),
                        exp.status || "done"));
      list.appendChild(li);
    }
    root.appendChild(list);
  }

  if (!experiences.length && !events.length && !goals.length) {
    root.appendChild(el("p", "muted", friendlyState({ state: "running" })));
  }
}

function translateEvent(type) {
  const map = {
    "goal.processed": "Finished a task",
    "capability.succeeded": "Completed an action",
    "capability.failed": "An action needed attention",
    "kernel.started": "Buster started",
  };
  return map[type] || String(type || "activity").replace(/[._]/g, " ");
}