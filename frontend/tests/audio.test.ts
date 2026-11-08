import { describe, expect, it } from "vitest";
import { base64ToBytes, decodeMulaw, parseListenMessage } from "../lib/audio";

describe("live listening audio helpers", () => {
  it("decodes mu-law silence and full-scale values", () => {
    const [silence, loud, loudNegative] = decodeMulaw(new Uint8Array([0xff, 0x80, 0x00]));
    expect(silence).toBeCloseTo(0, 3);
    expect(loud).toBeGreaterThan(0.95);
    expect(loudNegative).toBeLessThan(-0.95);
  });

  it("round-trips base64 and parses only well-formed messages", () => {
    expect(Array.from(base64ToBytes(btoa(String.fromCharCode(1, 2, 255))))).toEqual([1, 2, 255]);
    expect(parseListenMessage('{"t":"audio","src":"agent","d":"AQI="}')).toEqual({ t: "audio", src: "agent", d: "AQI=" });
    expect(parseListenMessage('{"t":"clear"}')).toEqual({ t: "clear" });
    expect(parseListenMessage('{"t":"end"}')).toEqual({ t: "end" });
    expect(parseListenMessage('{"t":"audio","src":"hacker","d":"x"}')).toBeNull();
    expect(parseListenMessage("not json")).toBeNull();
  });
});