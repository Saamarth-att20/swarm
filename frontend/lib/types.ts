// Friendly aliases over the generated contract (lib/contract.ts is copied from ../contract/types.ts).
import type {
  CallExtractedData,
  CallStateData,
  CallTranscriptData,
  Capabilities,
  CreateSwarmRequest,
  Event as WireEvent,
  ExtractedResult,
  Intent,
  RankedItem,
  SwarmCompletedData,
  SwarmDetail,
  SwarmReservedData,
  Target,
} from "./contract";

export type { Capabilities, CreateSwarmRequest, ExtractedResult, Intent, RankedItem, SwarmDetail, Target };
export type SwarmEvent = WireEvent;
export type CallState = CallStateData["state"];
export type SwarmStatus = "connecting" | "running" | "completed" | "cancelled" | "error";

export interface Utterance {
  id: string;
  speaker: CallTranscriptData["speaker"];
  text: string;
  final: boolean;
}

export interface CallView {
  callId: string;
  targetId: string;
  role: CallStateData["role"];
  state: CallState;
  reason: string | null;
  result: ExtractedResult | null;
  transcript: Utterance[];
}

export type LogItem =
  | { kind: "reroute"; seq: number; message: string; tone: "closed" | "no_stock" | "failed" | "referral" | "backup"; toTargetId: string; fromTargetId: string | null }
  | { kind: "knowledge"; seq: number; message: string };

export interface SwarmView {
  swarmId: string;
  lastSeq: number;
  created: boolean;
  query: string;
  mode: "live" | "simulated";
  intent: Intent | null;
  targets: Record<string, Target>;
  targetOrder: string[];
  calls: Record<string, CallView>;
  inquiryByTarget: Record<string, string>; // target id -> inquiry call id
  log: LogItem[];
  ranked: { rankings: RankedItem[]; bestCallId: string | null; criteria: string } | null;
  reserved: SwarmReservedData | null;
  reserving: string | null; // call id currently being reserved
  completed: SwarmCompletedData | null;
  startedAt: number | null; // epoch seconds of the first event
  finishedAt: number | null;
}

export type { CallExtractedData };
