/* Buster GUI — small DOM helpers + consumer copy. */

export function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export function clear(node) {
  node.innerHTML = "";
  return node;
}

export function messageFor(template, values) {
  let out = template;
  for (const [key, value] of Object.entries(values || {})) {
    out = out.replaceAll(`{${key}}`, String(value ?? ""));
  }
  return out;
}

export function friendlyState(status) {
  if (!status) return "Buster isn't reachable right now.";
  if (status.state === "running") return "Buster is available.";
  return "Buster is warming up.";
}

export function friendlyStatusForGoal(goal) {
  const map = {
    active: "Waiting",
    completed: "Done",
    failed: "Needs attention",
    cancelled: "Cancelled",
    paused: "Paused",
  };
  return map[goal?.status] || "Waiting";
}

export function activityWords(item) {
  if (!item) return "something happened";
  const value = String(item.text || item.summary || item.target || item.message || item.type || "");
  if (!value) return "activity";
  return value.length > 96 ? value.slice(0, 96) + "…" : value;
}

export function formatTime(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  return d.toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
}

export function statusBadge(label, kind) {
  const b = el("span", "badge " + kind, label);
  return b;
}