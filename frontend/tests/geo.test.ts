// Author: Saamarth Attray
import { afterEach, describe, expect, it, vi } from "vitest";
import { GeoError, geoMessage, getMyLocation } from "../lib/geo";

afterEach(() => vi.unstubAllGlobals());

describe("Use my location", () => {
  it("explains a blocked permission in plain words", () => {
    expect(geoMessage(1)).toMatch(/blocked/i);
    expect(geoMessage(3)).toMatch(/too long/i);
    expect(geoMessage(2)).toMatch(/turned on/i);
  });

  it("returns the coordinates the browser gives", async () => {
    vi.stubGlobal("navigator", {
      geolocation: { getCurrentPosition: (ok: (p: unknown) => void) => ok({ coords: { latitude: 37.2, longitude: -80.4 } }) },
    });
    expect(await getMyLocation()).toEqual({ lat: 37.2, lng: -80.4 });
  });

  it("rejects with a readable message when the user says no", async () => {
    vi.stubGlobal("navigator", {
      geolocation: { getCurrentPosition: (_ok: unknown, bad: (e: { code: number }) => void) => bad({ code: 1 }) },
    });
    await expect(getMyLocation()).rejects.toBeInstanceOf(GeoError);
    await expect(getMyLocation()).rejects.toThrow(/blocked/i);
  });

  it("rejects when the browser has no geolocation at all", async () => {
    vi.stubGlobal("navigator", {});
    await expect(getMyLocation()).rejects.toThrow(/can't share/i);
  });
});