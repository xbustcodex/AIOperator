/* Buster GUI — Tasks & Projects (goals/plans in ordinary language). */

import { el, clear } from "../ui.js";
import { friendlyStatusForGoal, statusBadge } from "../ui.js";

export async function render(root, ctx) {
  const { api } = ctx;
  clear(root);
  root.appendChild(el("h1", null, "Tasks & Projects"));
  const intro = el("p", "muted",
    "Here's what Buster is working on, what's waiting, what got done and what needs your attention.");
  root.appendChild(intro);

  const run = el("form", "row");
  const input = el("input");
  input.type = "text";
  input.placeholder = "What should Buster take on?";
  const submit = el("button", "action primary", "Add & run");
  run.append(input, submit);
  root.appendChild(run);

  submit.addEventListener("click", async (ev) => {
    ev.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    run.style.opacity = "0.5";
    try {
      await api.post("/api/goals/run", { text, kind: "task", tentative: false });
    } finally {
      run.style.opacity = "1";
      input.value = "";
    }
    await render(root, ctx);
  });

  const data = await api.get("/api/goals");
  const listBox = el("div", "card");
  if (data && data.goals && data.goals.length) {
    const list = el("ul", "list");
    const sorted = [...data.goals].sort((a, b) => (b.priority || 0) - (a.priority || 0));
    for (const goal of sorted) {
      const li = el("li", null);
      const inner = el("div", null);
      inner.appendChild(el("div", null, goal.title || "Untitled"));
      inner.appendChild(el("div", "small faint", `${goal.kind || "task"} · ${Math.round((goal.progress || 0) * 100)}%`));
      li.appendChild(inner);
      const kind = goal.status === "completed" ? "done"
        : goal.status === "failed" ? "failed"
          : goal.status === "active" ? "active" : "waiting";
      li.appendChild(el("span", "spacer"));
      li.appendChild(statusBadge(friendlyStatusForGoal(goal), kind));
      list.appendChild(li);
    }
    listBox.appendChild(list);
  } else {
    listBox.appendChild(el("p", "muted", "Nothing on your list yet. Give Buster a task to get started."));
  }
  root.appendChild(listBox);
}