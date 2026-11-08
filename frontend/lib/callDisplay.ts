// Plain-language text and small decisions for the swarm page, kept out of the components so they can be tested.
// Relative imports on purpose: the test runner has no "@/" alias. Author: Saamarth Attray
import { copyFor, isRescue } from "./copy";
import { resultLine } from "./format";
import { counts, inquiryCalls } from "./reducer";
import type { CallState, CallView, ExtractedResult, SwarmView } from "./types";

export type DotStatus = "standby" | "calling" | "talking" | "found" | "closed";
export type Tone = "muted" | "quote" | "good" | "bad";

export const isActiveState = (state: CallState | undefined) => state === "dialing" || state === "talking" || state === "extracting";

/** A real "yes" or "partly": the same rule the comparison table has always used, except a closed business never counts. */
export function isPositive(result: ExtractedResult, kind: string | undefined): boolean {
  if (result.closed) return false;
  const rescue = kind === "donation";
  return result.available === "yes" || (result.available === "partial" && !(rescue && result.can_pickup === false));
}

/** The coloured dot on a caller card. */
export function dotFor(call: CallView | null | undefined, kind: string | undefined): DotStatus {
  if (!call) return "standby";
  switch (call.state) {
    case "dialing":
      return "calling";
    case "talking":
    case "extracting":
      return "talking";
    case "failed":
      return "closed";
    case "completed":
      return call.result ? (isPositive(call.result, kind) ? "found" : "closed") : "standby";
    default:
      return "standby";
  }
}

const STATUS_LABEL: Record<CallState, string> = {
  queued: "Standing by",
  dialing: "Ringing",
  talking: "Talking",
  extracting: "Wrapping up",
  completed: "Done",
  failed: "Didn't connect",
  cancelled: "Stopped",
};
export const statusLabel = (call: CallView | null | undefined) => (call ? STATUS_LABEL[call.state] : "Standing by");

/** The one line a caller card shows: what is happening on that call right now. */
export function snippetFor(call: CallView | null | undefined, kind: string | undefined): { text: string; tone: Tone } {
  if (!call || call.state === "queued") return { text: "Waiting for an available caller…", tone: "muted" };
  switch (call.state) {
    case "dialing":
      return { text: "Calling now…", tone: "muted" };
    case "talking": {
      const last = call.transcript[call.transcript.length - 1];
      return last ? { text: `“${last.text}”`, tone: "quote" } : { text: "Connected. Waiting for them to speak…", tone: "muted" };
    }
    case "extracting":
      return { text: "Noting down what they said…", tone: "muted" };
    case "completed":
      return call.result
        ? { text: resultLine(call.result, kind ?? "product"), tone: isPositive(call.result, kind) ? "good" : "muted" }
        : { text: "Call finished", tone: "muted" };
    case "failed":
      return { text: call.reason ?? "The call didn't connect", tone: "bad" };
    default:
      return { text: "Stopped", tone: "muted" };
  }
}

/** While calls are still running: the strongest answer so far (a clear "yes" first, then the closest). The final ranking replaces it. */
export function bestSoFar(swarm: SwarmView): CallView | null {
  const kind = swarm.intent?.kind;
  const options = inquiryCalls(swarm).filter((c) => c.result && isPositive(c.result, kind));
  if (options.length === 0) return null;
  const distance = (c: CallView) => swarm.targets[c.targetId]?.distance_miles ?? 1e9;
  const yesFirst = (c: CallView) => (c.result?.available === "yes" ? 0 : 1);
  return [...options].sort((a, b) => yesFirst(a) - yesFirst(b) || distance(a) - distance(b))[0];
}

const WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
const countWord = (n: number) => (n < WORDS.length ? WORDS[n] : String(n));

/** The big title: what the swarm is doing while it runs, what it found once it is done. */
export function headline(swarm: SwarmView): string {
  if (!swarm.query) return "Connecting to the swarm…";
  const rescue = isRescue(swarm.intent);
  if (swarm.completed) {
    if (swarm.completed.status === "cancelled") return "Swarm stopped.";
    if (swarm.completed.status === "error") return "The swarm hit a problem.";
    const n = counts(swarm).matches;
    if (n === 0) return `${copyFor(swarm.intent).noWinnerTitle}.`;
    const noun = rescue ? (n === 1 ? "pickup" : "pickups") : n === 1 ? "good option" : "good options";
    return `We found ${countWord(n)} ${noun}.`;
  }
  if (rescue) return "Finding someone to collect your surplus food";
  const text = swarm.intent?.summary?.replace(/\s+within\s+[\d.]+\s+miles?\s*$/i, "").trim();
  if (text && /^find\b/i.test(text)) return text.replace(/^find\b/i, "Finding");
  if (text && /^book\b/i.test(text)) return text.replace(/^book\b/i, "Booking");
  return swarm.query;
}

/** The line under the title: what was asked, how far, and a note when the calls are made-up. */
export function subtitle(swarm: SwarmView): string {
  if (!swarm.query) return "";
  const asked = swarm.query.length > 140 ? `${swarm.query.slice(0, 137).trimEnd()}…` : swarm.query;
  const parts = [asked];
  if (swarm.intent && !/within\s+[\d.]+\s*(mi|miles?)\b/i.test(swarm.query)) parts.push(`within ${Number(swarm.intent.radius_miles)} miles`);
  if (swarm.mode === "simulated") parts.push(`Practice run with made-up ${isRescue(swarm.intent) ? "organizations" : "businesses"}`);
  return parts.join(" · ");
}

export function durationLabel(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} second${s === 1 ? "" : "s"}`;
  return `${Math.floor(s / 60)} min ${s % 60} sec`;
}

/** "Search complete in 24 seconds", shown next to the back link once the swarm has finished. */
export function completionNote(swarm: SwarmView): string | null {
  const done = swarm.completed;
  if (!done) return null;
  if (done.status === "cancelled") return `Stopped after ${durationLabel(done.elapsed_s)}`;
  if (done.status === "error") return "Ended with an error";
  return `Search complete in ${durationLabel(done.elapsed_s)}`;
}

/** 0:04 as 00:04, the way the stats bar shows it. */
export function clock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export const telHref = (phone: string) => `tel:${phone.replace(/[^\d+]/g, "")}`;
export const directionsHref = (lat: number, lng: number) => `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`;