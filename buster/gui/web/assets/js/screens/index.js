/* Buster GUI — screens index / router. */

import { render as home } from "./home.js";
import { render as chat } from "./chat.js";
import { render as live } from "./live.js";
import { render as files } from "./files.js";
import { render as tasks } from "./tasks.js";
import { render as memory } from "./memory.js";
import { render as permissions } from "./permissions.js";
import { render as device } from "./device.js";
import { render as activity } from "./activity.js";
import { render as settings } from "./settings.js";
import { render as advanced } from "./advanced.js";
import { render as updates } from "./updates.js";
import { render as onboarding } from "./onboarding.js";
import { render as terminal } from "./terminal.js";

export const SCREENS = {
  home, chat, live, files, tasks, memory, permissions,
  device, activity, settings, advanced, updates, onboarding, terminal,
};

export async function renderScreen(id, root, ctx) {
  const renderer = SCREENS[id] || SCREENS.home;
  await renderer(root, ctx);
  return id;
}