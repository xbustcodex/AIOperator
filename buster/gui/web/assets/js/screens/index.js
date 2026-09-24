/* Buster GUI — screens index / router. */

import { render as home } from "./screens/home.js";
import { render as chat } from "./screens/chat.js";
import { render as live } from "./screens/live.js";
import { render as files } from "./screens/files.js";
import { render as tasks } from "./screens/tasks.js";
import { render as memory } from "./screens/memory.js";
import { render as permissions } from "./screens/permissions.js";
import { render as device } from "./screens/device.js";
import { render as activity } from "./screens/activity.js";
import { render as settings } from "./screens/settings.js";
import { render as advanced } from "./screens/advanced.js";
import { render as updates } from "./screens/updates.js";
import { render as onboarding } from "./screens/onboarding.js";

export const SCREENS = {
  home, chat, live, files, tasks, memory, permissions,
  device, activity, settings, advanced, updates, onboarding,
};

export async function renderScreen(id, root, ctx) {
  const renderer = SCREENS[id] || SCREENS.home;
  await renderer(root, ctx);
  return id;
}