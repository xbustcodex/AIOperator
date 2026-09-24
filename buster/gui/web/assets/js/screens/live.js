/* Buster GUI — Live / voice experience.

The purple orb is the centre of attention here. Listening, thinking,
working and speaking map to the orb's real interaction states and, where the
platform supports it, a portable voice backend drives input.
*/

import { el, clear } from "../ui.js";
import { bestBackend } from "../voice.js";

export async function render(root, ctx) {
  const { api, store, orb, go } = ctx;
  const { renderOrb } = await import("../orb.js");
  clear(root);

  const summary = store.get("runtime") || {};
  orb.set(store.get("busy") || (summary.online ? "idle" : "offline"), { force: true });

  const hero = el("section", "hero");
  const orbHost = el("div", null);
  const orbNodes = renderOrb(orbHost, orb, { size: "hero" });
  hero.appendChild(orbHost);
  const statusLine = el("h2", null, orb.label());
  hero.appendChild(statusLine);
  const sub = el("p", "muted", summary.online ? "Talk to me — I'm listening." : "I'm here in local mode.");
  hero.appendChild(sub);

  const controls = el("div", "row gap-sm");
  const mic = el("button", "action primary", "Listen");
  mic.setAttribute("aria-label", "Start voice input");
  const stop = el("button", "action", "Stop");
  controls.append(mic, stop);
  hero.appendChild(controls);
  root.appendChild(hero);

  const transcript = el("div", "card chat-list");
  root.appendChild(transcript);

  const backend = await bestBackend();

  const append = (role, text) => {
    const bubble = el("div", "chat-bubble " + role);
    bubble.textContent = text;
    transcript.appendChild(bubble);
  };

  const onText = async (text) => {
    if (!text || !text.trim()) return;
    append("user", text);
    orb.set("thinking", { force: true });
    statusLine.textContent = orb.label();
    try {
      const res = await api.post("/api/chat", { message: text, session: "live" });
      orb.set(res.offline ? "offline" : "idle", { force: true });
      statusLine.textContent = orb.label();
      append("buster", res.reply || "Done.");
    } catch (err) {
      orb.set("error", { force: true });
      statusLine.textContent = "Hit a snag — Buster is still running.";
      append("buster", "I ran into a problem. Try again in a moment.");
    }
  };

  mic.addEventListener("click", async () => {
    if (!backend) {
      append("user", "(voice not available on this platform)");
      const prompt = el("input");
      prompt.placeholder = "Type instead";
      const send = el("button", "action primary", "Send");
      const row = el("div", "row");
      row.append(prompt, send);
      transcript.appendChild(row);
      send.addEventListener("click", () => onText(prompt.value));
      return;
    }
    orb.set("listening", { force: true });
    statusLine.textContent = orb.label();
    try {
      await backend.listen(({ text }) => {
        orb.set("working", { force: true });
        statusLine.textContent = "Got it — working.";
        onText(text);
      });
    } catch (_) {
      orb.set("idle", { force: true });
      statusLine.textContent = orb.label();
    }
  });

  stop.addEventListener("click", () => {
    if (backend) backend.stop();
    orb.set("idle", { force: true });
    statusLine.textContent = orb.label();
  });

  root.appendChild(el("p", "small faint",
    "The orb reflects what Buster is doing. Voice input follows whatever " +
    "audio backend this device provides — the interface stays the same."));
}