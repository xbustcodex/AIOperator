import test from "node:test";
import assert from "node:assert/strict";
import { Store, runtimeSummary, orbStateFor } from "../js/state.js";

test("store get/set round trip", () => {
  const s = new Store();
  s.set("boot.version", "0.4.0");
  s.set("route", "home");
  assert.equal(s.get("boot.version"), "0.4.0");
  assert.equal(s.get("route"), "home");
  assert.equal(s.get("missing", "fallback"), "fallback");
});

test("store subscribes and notifies", () => {
  const s = new Store();
  const got = [];
  const unsub = s.subscribe("route", (v) => got.push(v));
  s.set("route", "files");
  s.set("route", "home");
  unsub();
  s.set("route", "settings");
  assert.deepEqual(got, ["files", "home"]);
});

test("runtimeSummary folds offline", () => {
  assert.equal(runtimeSummary(null).online, false);
  const running = runtimeSummary({ state: "running", ai_providers: ["local"], capabilities: ["fs"] });
  assert.ok(running.online);
  assert.equal(running.state, "running");
});

test("orbStateFor maps runtime to orb state", () => {
  assert.equal(orbStateFor(null), "offline");
  assert.equal(orbStateFor(runtimeSummary(null)), "offline");
  assert.equal(orbStateFor({ online: true, state: "running" }), "idle");
  assert.equal(orbStateFor({ online: true, state: "starting" }), "attention");
  assert.equal(orbStateFor({ offline: true }, "working"), "working");
});