import type { CallState, ExtractedResult } from "./types";

export const STATE_META: Record<CallState, { label: string; emoji: string; color: string; step: number }> = {
  queued: { label: "Queued", emoji: "⏳", color: "queued", step: 0 },
  dialing: { label: "Dialing", emoji: "📞", color: "dialing", step: 1 },
  talking: { label: "Talking", emoji: "🗣️", color: "talking", step: 2 },
  extracting: { label: "Extracting", emoji: "🧠", color: "extracting", step: 3 },
  completed: { label: "Completed", emoji: "✅", color: "done", step: 4 },
  failed: { label: "Failed", emoji: "❌", color: "failed", step: 4 },
  cancelled: { label: "Cancelled", emoji: "⛔", color: "queued", step: 0 },
};

/** Hex values mirror tailwind.config.ts; needed where SVG attributes can't use classes. */
export const STATE_HEX: Record<CallState, string> = {
  queued: "#8A93A3",
  dialing: "#D98E04",
  talking: "#2557E6",
  extracting: "#7C4DDB",
  completed: "#17895F",
  failed: "#C93B3B",
  cancelled: "#8A93A3",
};

export const money = (n: number | null | undefined) => (n == null ? "—" : `$${Number.isInteger(n) ? n : n.toFixed(2)}`);

export function waitLabel(min: number | null | undefined): string {
  if (min == null) return "—";
  if (min < 60) return `${min} min`;
  const h = min / 60;
  return `${Number.isInteger(h) ? h : h.toFixed(1)} hr`;
}

export const miles = (n: number) => `${n.toFixed(1)} mi`;

export function availabilityLabel(r: ExtractedResult, kind?: string): string {
  if (r.closed) return "Closed";
  if (kind === "donation") {
    if (r.available === "yes") return "Can pick up";
    if (r.available === "partial") return r.can_pickup === false ? "Drop-off only" : "Takes some of it";
    return r.available === "no" ? "Can't take it" : "Unclear";
  }
  return { yes: "Has it", partial: "Partial match", no: "Doesn't have it", unknown: "Unclear" }[r.available];
}

export function resultLine(r: ExtractedResult, kind: string): string {
  if (r.closed) return kind === "donation" ? "Closed for the night" : "Closed right now";
  if (kind === "donation") {
    if (r.available === "no") return r.referral_name ? `At capacity. Suggests ${r.referral_name}` : "Can't take it tonight";
    if (r.can_pickup === false) return "Drop-off only, can't pick up";
    if (r.available === "partial") return r.perishables_ok === false ? "Shelf-stable only, no fresh food" : "Takes only some of it";
    const bits = [
      r.wait_minutes != null ? `Pickup in ~${r.wait_minutes} min` : "Can pick up",
      r.perishables_ok === true ? "takes fresh food" : r.perishables_ok === false ? "no fresh food" : null,
    ];
    return bits.filter(Boolean).join(" · ");
  }
  if (r.available === "no") return r.referral_name ? `Out. Suggests ${r.referral_name}` : "Doesn't have it";
  if (r.available === "unknown") return r.notes ? `Couldn't confirm. ${r.notes}` : "Couldn't confirm";
  const bits = [
    r.available === "partial" ? "Partial" : "In stock",
    r.price != null ? money(r.price) : null,
    kind === "product" && r.quantity != null ? `${r.quantity} left` : null,
    kind !== "product" && r.wait_minutes != null ? waitLabel(r.wait_minutes) : null,
    r.can_hold ? "can hold" : null,
  ];
  return bits.filter(Boolean).join(" · ");
}

export function elapsed(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}