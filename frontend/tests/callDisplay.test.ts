// Author: Saamarth Attray
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { bestSoFar, clock, completionNote, directionsHref, dotFor, durationLabel, headline, isPositive, snippetFor, statusLabel, subtitle, telHref } from "../lib/callDisplay";
import { applyAll, initialSwarm, inquiryCalls } from "../lib/reducer";
import type { CallView, SwarmEvent } from "../lib/types";

const load = (name: string) => JSON.parse(readFileSync(`../contract/fixtures/${name}.json`, "utf8")) as SwarmEvent[];
const events = load("pharmacy");
const final = applyAll(initialSwarm("s"), events);
const at = (type: string, nth = 1) => events.findIndex((e, i) => e.type === type && events.slice(0, i + 1).filter((x) => x.type === type).length === nth);

const call = (over: Partial<CallView>): CallView => ({ callId: "c", targetId: "t", role: "inquiry", state: "queued", reason: null, result: null, transcript: [], ...over });
const yes = { available: "yes" as const };

describe("what a caller card shows", () => {
  it("a closed business is never counted as a match", () => {
    expect(isPositive({ available: "yes", closed: true }, "product")).toBe(false);
    expect(isPositive({ available: "partial" }, "product")).toBe(true);
    expect(isPositive({ available: "partial", can_pickup: false }, "donation")).toBe(false);
  });

  it("maps each call state to a dot", () => {
    expect(dotFor(undefined, "product")).toBe("standby");
    expect(dotFor(call({ state: "dialing" }), "product")).toBe("calling");
    expect(dotFor(call({ state: "talking" }), "product")).toBe("talking");
    expect(dotFor(call({ state: "failed" }), "product")).toBe("closed");
    expect(dotFor(call({ state: "completed", result: yes }), "product")).toBe("found");
    expect(dotFor(call({ state: "completed", result: { available: "no" } }), "product")).toBe("closed");
  });

  it("says what is happening on the call", () => {
    expect(snippetFor(undefined, "product").text).toMatch(/waiting/i);
    expect(snippetFor(call({ state: "dialing" }), "product").text).toBe("Calling now…");
    expect(snippetFor(call({ state: "talking" }), "product").text).toMatch(/waiting for them/i);
    const talking = call({ state: "talking", transcript: [{ id: "1", speaker: "business", text: "Let me check the shelf.", final: true }] });
    expect(snippetFor(talking, "product")).toEqual({ text: "“Let me check the shelf.”", tone: "quote" });
    expect(snippetFor(call({ state: "failed", reason: "No answer" }), "product")).toEqual({ text: "No answer", tone: "bad" });
    expect(snippetFor(call({ state: "completed", result: yes }), "product").tone).toBe("good");
  });

  it("has a friendly status label, including for a business with no call yet", () => {
    expect(statusLabel(undefined)).toBe("Standing by");
    expect(statusLabel(call({ state: "dialing" }))).toBe("Ringing");
  });
});

describe("the page text over a recorded swarm", () => {
  it("while calling, the title says what it is doing and the subtitle says what was asked", () => {
    const running = applyAll(initialSwarm("s"), events.slice(0, at("call.state", 3) + 1));
    expect(running.completed).toBeNull();
    expect(headline(running)).toMatch(/^Finding /);
    expect(headline(running)).not.toMatch(/within/i);
    expect(subtitle(running).match(/within 5 miles/g)).toHaveLength(1); // the fixture's request already says it
    expect(subtitle({ ...running, query: "a plumber tonight" })).toBe("a plumber tonight · within 5 miles · Practice run with made-up businesses");
    expect(subtitle(running)).toMatch(/Practice run with made-up businesses/);
    expect(completionNote(running)).toBeNull();
  });

  it("before anything arrives it says it is connecting", () => {
    expect(headline(initialSwarm("s"))).toBe("Connecting to the swarm…");
    expect(subtitle(initialSwarm("s"))).toBe("");
  });

  it("when done, the title counts the good options and the note says how long it took", () => {
    expect(headline(final)).toMatch(/^We found (one|two|three|four|five|six|seven|eight|nine|ten|\d+) good options?\.$/);
    expect(completionNote(final)).toMatch(/^Search complete in /);
  });

  it("stopped and failed swarms say so", () => {
    const stopped = { ...final, completed: { ...final.completed!, status: "cancelled" as const, elapsed_s: 12 } };
    expect(headline(stopped)).toBe("Swarm stopped.");
    expect(completionNote(stopped)).toBe("Stopped after 12 seconds");
    expect(headline({ ...final, completed: { ...final.completed!, status: "error" as const } })).toBe("The swarm hit a problem.");
  });

  it("with no match the title is the app's own 'no one had it' wording", () => {
    const none = { ...final, calls: Object.fromEntries(Object.entries(final.calls).map(([k, c]) => [k, { ...c, result: null }])) };
    expect(headline(none)).toBe("No one had it.");
  });

  it("once a call has a yes it becomes the best so far, and it is a real positive result", () => {
    const upTo = events.findIndex((e) => e.type === "call.extracted" && e.data.result.available === "yes");
    expect(upTo).toBeGreaterThan(-1);
    const partway = applyAll(initialSwarm("s"), events.slice(0, upTo + 1));
    const best = bestSoFar(partway);
    expect(best?.result?.available).toBe("yes");
    expect(bestSoFar(initialSwarm("s"))).toBeNull();
    expect(inquiryCalls(partway).length).toBeGreaterThan(0);
  });
});

describe("small formatters", () => {
  it("formats durations and the stats clock", () => {
    expect(durationLabel(1)).toBe("1 second");
    expect(durationLabel(24.4)).toBe("24 seconds");
    expect(durationLabel(72)).toBe("1 min 12 sec");
    expect(clock(4)).toBe("00:04");
    expect(clock(75)).toBe("01:15");
    expect(clock(-3)).toBe("00:00");
  });

  it("builds a tel: link without spaces or dashes and a directions link from coordinates", () => {
    expect(telHref("+1 (202) 555-0107")).toBe("tel:+12025550107");
    expect(directionsHref(37.7, -122.4)).toBe("https://www.google.com/maps/dir/?api=1&destination=37.7,-122.4");
  });
});