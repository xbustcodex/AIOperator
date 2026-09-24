/* Buster GUI — Conversation (Talk).

Real Buster runtime round-trip: user message -> /api/chat -> the daemon's
process_goal over RPC. History is stored in Buster's own memory store; the
frontend keeps no second conversation authority.
*/

import { el, clear } from "../ui.js";
import { formatTime } from "../ui.js";
import { bestBackend } from "../voice.js";

export const SESSION = "gui";

export async function render(root, ctx) {
  const { api, orb, store } = ctx;
  clear(root);
  const pending = store.get("chat.pendingMsg");

  const title = el("h1", null, "Talk to Buster");
  root.appendChild(title);

  const chatList = el("div", "chat-list");
  root.appendChild(chatList);

  const composer = el("form", "chat-composer");
  const input = el("input");
  input.type = "text";
  input.placeholder = "What can I do for you?";
  input.setAttribute("aria-label", "Message Buster");
  const micBtn = el("button", "action", "🎙");
  micBtn.setAttribute("aria-label", "Use voice");
  const send = el("button", "action primary", "Send");
  send.setAttribute("aria-label", "Send message");
  composer.append(input, micBtn, send);
  root.appendChild(composer);

  const say = (role, text, meta) => {
    const bubble = el("div", "chat-bubble " + role);
    bubble.appendChild(el("span", "who", role === "user" ? "You" : "Buster"));
    bubble.appendChild(el("div", null, text));
    if (meta) bubble.appendChild(el("div", "small faint", formatTime(meta.ts)));
    chatList.appendChild(bubble);
  };

  const renderHistory = (history) => {
    clear(chatList);
    if (!history || history.length === 0) {
      chatList.appendChild(el("p", "muted", "Say hello and I'll jump in."));
      return;
    }
    for (const item of history) {
      if (!item || typeof item.text !== "string") continue;
      say(item.role, item.text, item);
    }
  };

  const onBust = async (msg) => {
    if (!msg.trim()) return;
    orb.set("thinking", { force: true });
    say("user", msg);
    input.value = "";
    const bubble = el("div", "chat-bubble buster");
    bubble.appendChild(el("span", "who", "Buster"));
    bubble.appendChild(el("div", "muted", "working…"));
    chatList.appendChild(bubble);
    try {
      const res = await api.post("/api/chat", { message: msg, session: SESSION });
      if (res.offline) orb.set("offline", { force: true });
      else orb.set("idle");
      bubble.innerHTML = "";
      bubble.appendChild(el("span", "who", "Buster"));
      bubble.appendChild(el("div", null, String(res.reply || "Done.")));
      const note = el("div", "small faint", metaSummary(res.result));
      bubble.appendChild(note);
    } catch (err) {
      orb.set("error", { force: true });
      bubble.innerHTML = "";
      bubble.appendChild(el("span", "who", "Buster"));
      bubble.appendChild(el("div", "muted", `I hit a snag: ${err.message}`));
    }
  };

  composer.addEventListener("submit", (ev) => {
    ev.preventDefault();
    onBust(input.value);
  });

  const backend = await bestBackend();
  if (backend) {
    micBtn.disabled = false;
    micBtn.addEventListener("click", async () => {
      orb.set("listening", { force: true });
      try {
        await backend.listen(({ text }) => {
          input.value = text;
          orb.set("listening", { force: true });
          onBust(text);
        });
      } catch {
        orb.set("idle", { force: true });
        micBtn.disabled = true;
      }
    });
  } else {
    micBtn.disabled = true;
    micBtn.title = "Voice not available on this platform";
  }

  try {
    const history = await api.get("/api/chat", { session: SESSION });
    renderHistory(history.history);
  } catch (_) {
    chatList.appendChild(el("p", "muted", "Conversation history is unavailable until Buster reconnects."));
  }

  if (pending) {
    store.set("chat.pendingMsg", null);
    onBust(pending);
  }
}

function metaSummary(result) {
  if (!result) return "";
  const status = result.status || "unknown";
  const steps = result.steps ?? "";
  if (status === "done") return `Done · ${steps} step(s)`;
  if (status === "failed") return `Needs attention · ${result.error || "it hit a problem"}`;
  return `Status ${status}`;
}