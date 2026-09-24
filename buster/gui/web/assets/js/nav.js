/* Buster GUI — navigation model (DOM-free, testable). */

export const NAV_AREAS = [
  { id: "home", label: "Home", screen: "home", icon: "home" },
  { id: "talk", label: "Talk", screen: "chat", icon: "chat" },
  { id: "live", label: "Live", screen: "live", icon: "mic" },
  { id: "files", label: "Files", screen: "files", icon: "folder" },
  { id: "tasks", label: "Tasks", screen: "tasks", icon: "check" },
  { id: "memory", label: "Memory", screen: "memory", icon: "brain" },
  { id: "device", label: "Device", screen: "device", icon: "phone" },
  { id: "activity", label: "Activity", screen: "activity", icon: "pulse" },
  { id: "permissions", label: "Permissions", screen: "permissions", icon: "shield" },
  { id: "settings", label: "Settings", screen: "settings", icon: "gear" },
  { id: "advanced", label: "Advanced", screen: "advanced", icon: "code", advanced: true },
];

export function routesFor(boot) {
  const showAdvanced = !!(boot && boot.advanced && boot.advanced.enabled);
  return NAV_AREAS.filter((area) => !area.advanced || showAdvanced);
}

export function resolveRoute(hash, boot) {
  const id = (hash || "").replace(/^#\//, "").split("/")[0].trim();
  const routes = routesFor(boot || {});
  return routes.find((r) => r.id === id) || routes.find((r) => r.id === "home");
}

export function href(route) {
  return `#/${route}`;
}

export function routeFromScreen(scheme, boot) {
  const routes = routesFor(boot || {});
  return routes.find((r) => r.screen === scheme) || routes[0];
}