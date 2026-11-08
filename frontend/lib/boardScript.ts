/**
 * The scripted sample run shown on the home page and beside the sign-in forms: a swarm calling eight (made-up)
 * pharmacies, one closing, one not answering so a backup dials, and one clear winner at the end.
 * Plain data so the timeline can be tested. Author: Saamarth Attray
 */
export type BoardState = "queued" | "dialing" | "talking" | "extracting" | "done" | "failed";

export interface BoardRow {
  name: string;
  miles: number;
}

export interface BoardEvent {
  at: number; // ms after the run starts
  row: number;
  state: BoardState;
  text: string;
}

export const BOARD_QUERY = "Pharmacy that has children's amoxicillin in stock right now";

export const BOARD_ROWS: BoardRow[] = [
  { name: "Maple Health Pharmacy", miles: 0.6 },
  { name: "Corner Apothecary", miles: 0.8 },
  { name: "Harbor Drug", miles: 1.1 },
  { name: "Sunrise Pharmacy", miles: 1.4 },
  { name: "Greenway Pharmacy", miles: 1.9 },
  { name: "Family Care Pharmacy", miles: 2.3 },
  { name: "Bluebird Pharmacy", miles: 2.8 },
  { name: "Northside Drugs", miles: 3.4 },
];

export const WINNER_ROW = 1;
export const WINNER_LINE = "Best match: Corner Apothecary, 0.8 mi, $14, can hold one";
export const WINNER_AT = 9600;
export const LOOP_MS = 15500;

export const BOARD_EVENTS: BoardEvent[] = [
  // everyone except the last (a backup) starts ringing, a fraction of a second apart
  ...BOARD_ROWS.slice(0, 7).map((_, i): BoardEvent => ({ at: 300 + i * 240, row: i, state: "dialing", text: "Ringing" })),

  { at: 2300, row: 0, state: "talking", text: "“Let me check the shelf.”" },
  { at: 2700, row: 1, state: "talking", text: "“Yes, we have the 125 mg.”" },
  { at: 3100, row: 2, state: "talking", text: "“We closed at 8.”" },
  { at: 3500, row: 3, state: "talking", text: "“One second, checking.”" },
  { at: 4000, row: 5, state: "talking", text: "“Hmm, let me look.”" },
  { at: 4400, row: 6, state: "talking", text: "“Which strength?”" },

  { at: 4300, row: 0, state: "failed", text: "Out of stock" },
  { at: 4700, row: 1, state: "extracting", text: "Noting price and quantity" },
  { at: 4900, row: 2, state: "failed", text: "Closed, sending a backup" },
  { at: 5800, row: 1, state: "done", text: "In stock · $14 · can hold" },
  { at: 6200, row: 3, state: "done", text: "In stock · $17" },
  { at: 6600, row: 4, state: "failed", text: "No answer, sending a backup" },

  // the two backups
  { at: 5100, row: 7, state: "dialing", text: "Backup ringing" },
  { at: 6000, row: 5, state: "failed", text: "Out of stock" },
  { at: 6900, row: 7, state: "talking", text: "“Give me a moment.”" },
  { at: 7600, row: 6, state: "done", text: "In stock · $22" },
  { at: 8600, row: 7, state: "failed", text: "Out of stock" },
];

/** Row states after `ms` of the run (events are applied in time order). */
export function boardAt(ms: number): { state: BoardState; text: string }[] {
  const rows = BOARD_ROWS.map((_, i) => ({ state: (i === 7 ? "queued" : "queued") as BoardState, text: i === 7 ? "On standby" : "Waiting" }));
  for (const e of [...BOARD_EVENTS].sort((a, b) => a.at - b.at)) {
    if (e.at <= ms) rows[e.row] = { state: e.state, text: e.text };
  }
  return rows;
}