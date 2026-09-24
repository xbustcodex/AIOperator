import test from "node:test";
import assert from "node:assert/strict";
import { NAV_AREAS, routesFor, resolveRoute, href, routeFromScreen } from "../js/nav.js";

test("nav defines all consumer areas plus a separate advanced one", () => {
  const ids = NAV_AREAS.map((a) => a.id);
  for (const id of ["home", "talk", "files", "tasks", "memory", "device",
                     "activity", "permissions", "settings"]) {
    assert.ok(ids.includes(id), id);
  }
  assert.ok(ids.includes("advanced"));
  const adv = NAV_AREAS.find((a) => a.id === "advanced");
  assert.ok(adv.advanced === true);
});

test("advanced hidden unless explicitly enabled in boot", () => {
  const normal = routesFor({});
  assert.ok(!normal.some((a) => a.id === "advanced"));
  const withAdvanced = routesFor({ advanced: { enabled: true } });
  assert.ok(withAdvanced.some((a) => a.id === "advanced"));
});

test("resolveRoute falls back to home for unknown ids", () => {
  const route = resolveRoute("#/nonsense", {});
  assert.equal(route.id, "home");
  const known = resolveRoute("#/files", {});
  assert.equal(known.id, "files");
});

test("href produces a hash route", () => {
  assert.equal(href("talk"), "#/talk");
});

test("screen maps back to a route", () => {
  assert.equal(routeFromScreen("chat", {}).id, "talk");
  assert.equal(routeFromScreen("settings", {}).id, "settings");
});