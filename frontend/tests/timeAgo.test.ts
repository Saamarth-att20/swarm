import { describe, expect, it } from "vitest";
import { timeAgo } from "../lib/timeAgo";

const NOW = 1_700_000_000_000; // ms

describe("timeAgo", () => {
  it("says just now for the last minute", () => {
    expect(timeAgo(NOW / 1000 - 20, NOW)).toBe("Just now");
  });
  it("counts minutes, then hours", () => {
    expect(timeAgo(NOW / 1000 - 5 * 60, NOW)).toBe("5 min ago");
    expect(timeAgo(NOW / 1000 - 3600, NOW)).toBe("1 hour ago");
    expect(timeAgo(NOW / 1000 - 2 * 3600, NOW)).toBe("2 hours ago");
  });
  it("says yesterday, then days", () => {
    expect(timeAgo(NOW / 1000 - 26 * 3600, NOW)).toBe("Yesterday");
    expect(timeAgo(NOW / 1000 - 3 * 86400, NOW)).toBe("3 days ago");
  });
  it("never goes negative if the clocks disagree", () => {
    expect(timeAgo(NOW / 1000 + 500, NOW)).toBe("Just now");
  });
});