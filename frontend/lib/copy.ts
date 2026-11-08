import type { Intent } from "./types";

/** Wording that changes when the swarm is rescuing surplus food (kind "donation") instead of finding something. */
export interface Copy {
  matches: string;
  bestTitle: string;
  reserve: string;
  reserving: string;
  reservedOk: string;
  reservedFail: string;
  whenColumn: string;
  whenValue: (minutes: number | null | undefined) => string;
  noWinnerTitle: string;
  noWinnerBody: (calls: number) => string;
}

const FIND: Copy = {
  matches: "matches found",
  bestTitle: "Best match",
  reserve: "Reserve this one",
  reserving: "Calling to reserve",
  reservedOk: "Held for you",
  reservedFail: "Couldn't hold it",
  whenColumn: "Arrives in",
  whenValue: (m) => (m == null ? "—" : m < 60 ? `${m} min` : `${(m / 60).toFixed(1)} hr`),
  noWinnerTitle: "No one had it",
  noWinnerBody: (n) => `${n} calls and none confirmed. Try a wider radius or a more general item.`,
};

const RESCUE: Copy = {
  matches: "pickups found",
  bestTitle: "Best pickup",
  reserve: "Confirm this pickup",
  reserving: "Calling to confirm",
  reservedOk: "Pickup confirmed",
  reservedFail: "Couldn't confirm",
  whenColumn: "Pickup in",
  whenValue: (m) => (m == null ? "—" : m < 60 ? `~${m} min` : `~${(m / 60).toFixed(1)} hr`),
  noWinnerTitle: "No one can collect it yet",
  noWinnerBody: (n) => `${n} organizations called and none could pick up. Widen the radius, or extend the pickup time and try again.`,
};

export const isRescue = (intent: Intent | null | undefined) => intent?.kind === "donation";
export const copyFor = (intent: Intent | null | undefined): Copy => (isRescue(intent) ? RESCUE : FIND);
