import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { applyAll, applyEvent, counts, initialSwarm, inquiryCalls } from "../lib/reducer";
import type { SwarmEvent } from "../lib/types";

const load = (name: string) => JSON.parse(readFileSync(`../contract/fixtures/${name}.json`, "utf8")) as SwarmEvent[];

describe("reducer over recorded swarms", () => {
  for (const name of ["pharmacy", "plumber", "rescue"]) {
    const events = load(name);
    const final = applyAll(initialSwarm("s"), events);

    it(`${name}: ends completed with a ranked best option`, () => {
      expect(final.completed?.status).toBe("completed");
      expect(final.ranked?.bestCallId).toBeTruthy();
      expect(final.lastSeq).toBe(events[events.length - 1].seq);
    });

    it(`${name}: every call finishes in a terminal state and partial lines are all resolved`, () => {
      for (const c of inquiryCalls(final)) {
        expect(["completed", "failed", "cancelled"]).toContain(c.state);
        expect(c.transcript.every((u) => u.final)).toBe(true);
      }
      const k = counts(final);
      expect(k.matches).toBeGreaterThan(0);
      expect(k.active).toBe(0);
    });

    it(`${name}: replaying the same events twice, or from the middle, gives the same state`, () => {
      const twice = events.reduce(applyEvent, final);
      expect(twice).toBe(final);
      const mid = Math.floor(events.length / 2);
      const resumed = events.slice(mid).reduce(applyEvent, applyAll(initialSwarm("s"), events.slice(0, mid)));
      expect(JSON.stringify(resumed)).toBe(JSON.stringify(final));
    });
  }

  it("rescue: drop-off-only organizations are not counted as pickups", () => {
    const final = applyAll(initialSwarm("s"), load("rescue"));
    const calls = inquiryCalls(final);
    expect(calls.some((c) => c.result?.can_pickup === false)).toBe(true);
    const pickups = calls.filter((c) => c.result && c.result.available !== "no" && c.result.available !== "unknown" && c.result.can_pickup !== false);
    expect(counts(final).matches).toBe(pickups.length);
    expect(final.intent?.kind).toBe("donation");
  });

  it("a late partial never overwrites a final utterance", () => {
    const base = load("pharmacy");
    const t = base.find((e) => e.type === "call.transcript" && e.data.is_final)!;
    const s0 = applyAll(initialSwarm("s"), base.slice(0, base.indexOf(t) + 1));
    if (t.type !== "call.transcript") throw new Error();
    const late: SwarmEvent = { ...t, seq: t.seq + 1000, data: { ...t.data, text: "partial…", is_final: false } };
    const s1 = applyEvent(s0, late);
    const u = s1.calls[t.data.call_id].transcript.find((x) => x.id === t.data.utterance_id)!;
    expect(u.final).toBe(true);
    expect(u.text).toBe(t.data.text);
  });
});
