import test from "node:test";
import assert from "node:assert/strict";
import {
  ORB_STATES, ORB_TRANSITIONS, ORB_LABELS, OrbController,
} from "../js/orb.js";

test("all defined states are valid", () => {
  for (const s of ["idle", "listening", "thinking", "working", "speaking",
                   "attention", "offline", "error"]) {
    assert.ok(ORB_STATES.includes(s), s);
  }
});

test("every state has a transition table and a label", () => {
  for (const s of ORB_STATES) {
    assert.ok(ORB_TRANSITIONS[s], s);
    assert.ok(ORB_LABELS[s], s);
  }
});

test("controller starts idle and transitions normally", () => {
  const orb = new OrbController();
  assert.equal(orb.state, "idle");
  assert.equal(orb.set("listening"), true);
  assert.equal(orb.set("thinking"), true);
  assert.equal(orb.set("working"), true);
  assert.equal(orb.set("idle"), true);
});

test("disallowed transition is rejected, forced transition allowed", () => {
  const orb = new OrbController();
  assert.equal(orb.set("working"), true);
  assert.equal(orb.set("listening"), false); // working -> listening not allowed
  assert.equal(orb.state, "working");
  assert.equal(orb.set("listening", { force: true }), true);
  assert.equal(orb.state, "listening");
});

test("unknown state cannot be set", () => {
  const orb = new OrbController();
  assert.equal(orb.set("bogus"), false);
});

test("offline is reachable from every state via force", () => {
  for (const state of ORB_STATES) {
    const orb = new OrbController();
    orb.state = "idle";
    assert.equal(orb.set(state, { force: true }) || state === "idle", true);
    assert.equal(orb.set("offline", { force: true }), true);
    assert.equal(orb.state, "offline");
  }
});

test("controller notifies listeners on change", () => {
  const orb = new OrbController();
  const seen = [];
  orb._onchange = (s) => seen.push(s);
  orb.set("working");
  assert.deepEqual(seen, ["working"]);
});