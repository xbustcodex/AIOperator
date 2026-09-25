/* Buster GUI — Terminal (Prime Tech Terminal surface).

A Buster-side terminal. Commands are executed by the single Buster runtime's
shell capability, i.e. in Buster's own userspace (Buster OS), never in the
TerminalP host shell, and never by this GUI process. Management commands
such as ``buster status`` therefore reach the same runtime the GUI uses.
*/

import { el, clear } from "../ui.js";

export const SUGGESTED = [
  "buster status",
  "buster doctor",
  "buster caps",
  "buster jobs",
];

export async function render(root, ctx) {
  const { api } = ctx;
  clear(root);
  root.appendChild(el("h1", null, "Terminal"));

  const intro = el("p", "muted",
    "This runs inside Buster OS, in your own Linux environment. " +
    "Try \"buster status\" to see what Buster is doing right now.");
  root.appendChild(intro);

  const card = el("div", "card");
  const form = el("form", "row");
  const input = el("input");
  input.type = "text";
  input.placeholder = "type a command, e.g. buster status";
  input.setAttribute("aria-label", "Buster terminal command");
  const run = el("button", "action primary", "Run");
  form.append(input, run);
  card.appendChild(form);

  const chips = el("div", "row gap-sm");
  for (const suggestion of SUGGESTED) {
    const chip = el("button", "action soft", suggestion);
    chip.addEventListener("click", () => { input.value = suggestion; input.focus(); });
    chips.appendChild(chip);
  }
  card.appendChild(chips);

  const output = el("pre", "term-output", "");
  output.setAttribute("role", "log");
  output.setAttribute("aria-live", "polite");
  card.appendChild(output);
  root.appendChild(card);

  const note = el("p", "small faint",
    "Commands here run through Buster's permission system. If Buster asks, " +
    "you can allow the terminal to run commands from this screen.");
  root.appendChild(note);

  let granted = false;
  const promptLine = () => (granted ? "buster$ " : "… ");

  const announce = (text, cls) => {
    const line = el("div", cls || "");
    line.textContent = text;
    output.appendChild(line);
  };

  const execute = async (command) => {
    if (!command.trim()) return;
    input.value = "";
    announce(promptLine() + command);
    let res;
    try {
      res = await api.post("/api/term", { command, timeout: 90 });
    } catch (err) {
      announce("Couldn't reach Buster: " + err.message, "term-error");
      return;
    }
    if (res.offline) {
      announce("Buster's runtime isn't running. Launch Buster to start it.", "term-error");
      return;
    }
    if (res.permission) {
      announce(res.error || "Permission needed.", "term-error");
      const allow = el("button", "action soft", "Allow commands in Terminal");
      allow.addEventListener("click", async () => {
        try {
          await api.post("/api/permissions/grant", { action: "shell.run" });
          granted = true;
          announce("Allowed. Run your command again.", "");
        } catch (err) {
          announce("Couldn't update permissions: " + err.message, "term-error");
        }
      });
      output.appendChild(allow);
      return;
    }
    if (!res.ok) {
      announce(res.error || "Command failed.", "term-error");
      return;
    }
    const data = res.data || {};
    if (data.stdout) announce(String(data.stdout).replace(/\n$/, ""), "");
    if (data.stderr) announce(String(data.stderr).replace(/\n$/, ""), "term-error");
    if (data.exit_code != null) {
      announce("exit " + data.exit_code, data.exit_code === 0 ? "term-ok" : "term-error");
    }
  };

  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    execute(input.value);
  });

  if (await probePermission()) {
    granted = true;
    announce("Terminal ready — commands run inside Buster OS.", "");
  } else {
    announce("Buster will ask before the terminal can run commands.", "");
  }

  async function probePermission() {
    try {
      const res = await api.post("/api/term", { command: "true", timeout: 5 });
      return Boolean(res.ok || res.offline === false && res.data);
    } catch (_) {
      return false;
    }
  }
}