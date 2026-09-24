/* Buster GUI — Onboarding (first run). */

import { el, clear } from "../ui.js";

export async function render(root, ctx) {
  const { api, store, go } = ctx;
  clear(root);
  root.appendChild(el("h1", null, "Welcome to Buster"));

  const intro = el("p", "muted",
    "Buster is your local assistant. It runs on this device, keeps your stuff " +
    "private, and asks before it does anything sensitive.");
  root.appendChild(intro);

  const card = el("div", "card");
  card.appendChild(el("h2", null, "A few preferences"));

  const label = (text) => {
    const l = el("label", "small", text);
    l.style.display = "block";
    return l;
  };

  const name = el("input"); name.placeholder = "What should I call you?";
  const files = el("input"); files.placeholder = "Where should I keep files? (e.g. ~/Buster)";
  card.appendChild(label("Your name"));
  card.appendChild(name);
  card.appendChild(label("Default files location"));
  card.appendChild(files);
  root.appendChild(card);

  const privacy = el("div", "card");
  privacy.appendChild(el("h2", null, "Privacy"));
  privacy.appendChild(el("p", "small faint",
    "Buster works offline by default. It only does what you permit, and it " +
    "never shares your memory with anyone else unless you ask it to."));
  root.appendChild(privacy);

  const start = el("button", "action primary", "Get started");
  start.addEventListener("click", async () => {
    if (name.value.trim()) await api.post("/api/prefs", { key: "name", value: name.value.trim() });
    if (files.value.trim()) await api.post("/api/prefs", { key: "files_path", value: files.value.trim() });
    await api.post("/api/prefs", { key: "onboarded", value: "1" });
    store.set("onboarded", true);
    go("home");
  });
  root.appendChild(start);
}