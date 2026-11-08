import type { CallView, LogItem, SwarmEvent, SwarmView } from "./types";

export function initialSwarm(swarmId: string): SwarmView {
  return {
    swarmId,
    lastSeq: 0,
    created: false,
    query: "",
    mode: "simulated",
    intent: null,
    targets: {},
    targetOrder: [],
    calls: {},
    inquiryByTarget: {},
    log: [],
    ranked: null,
    reserved: null,
    reserving: null,
    completed: null,
    startedAt: null,
    finishedAt: null,
  };
}

function ensureCall(state: SwarmView, callId: string, targetId: string, role: CallView["role"] = "inquiry"): CallView {
  const existing = state.calls[callId];
  if (existing) return existing;
  const call: CallView = { callId, targetId, role, state: "queued", reason: null, result: null, transcript: [] };
  state.calls[callId] = call;
  if (role === "inquiry") state.inquiryByTarget[targetId] = callId;
  return call;
}

/**
 * The single place where server events become UI state. Used for the initial replay, live streaming and
 * reconnects alike. Idempotent: events at or below `lastSeq` are ignored, so duplicates are harmless.
 */
export function applyEvent(prev: SwarmView, ev: SwarmEvent): SwarmView {
  if (ev.seq <= prev.lastSeq) return prev;
  const s: SwarmView = {
    ...prev,
    calls: { ...prev.calls },
    targets: { ...prev.targets },
    inquiryByTarget: { ...prev.inquiryByTarget },
    lastSeq: ev.seq,
    startedAt: prev.startedAt ?? ev.ts,
  };

  switch (ev.type) {
    case "swarm.created": {
      const d = ev.data;
      s.created = true;
      s.query = d.query;
      s.mode = d.mode;
      s.intent = d.intent;
      s.targets = {};
      d.targets.forEach((t) => (s.targets[t.id] = t));
      s.targetOrder = d.targets.map((t) => t.id);
      break;
    }
    case "call.state": {
      const d = ev.data;
      const call = { ...ensureCall(s, d.call_id, d.target_id, d.role) };
      call.state = d.state;
      call.reason = d.reason ?? call.reason;
      s.calls[d.call_id] = call;
      s.reserving = d.role === "reserve" && (d.state === "completed" || d.state === "failed") ? null : s.reserving;
      break;
    }
    case "call.transcript": {
      const d = ev.data;
      const call = { ...ensureCall(s, d.call_id, d.target_id) };
      const list = call.transcript.slice();
      const at = list.findIndex((u) => u.id === d.utterance_id);
      const next = { id: d.utterance_id, speaker: d.speaker, text: d.text, final: d.is_final };
      if (at === -1) list.push(next);
      else if (!list[at].final || d.is_final) list[at] = next; // a final line is never replaced by a late partial
      call.transcript = list;
      s.calls[d.call_id] = call;
      break;
    }
    case "call.extracted": {
      const d = ev.data;
      const call = { ...ensureCall(s, d.call_id, d.target_id) };
      call.result = d.result;
      s.calls[d.call_id] = call;
      break;
    }
    case "swarm.reroute": {
      const d = ev.data;
      if (d.new_target) {
        s.targets[d.new_target.id] = d.new_target;
        if (!s.targetOrder.includes(d.new_target.id)) s.targetOrder = [...s.targetOrder, d.new_target.id];
      }
      ensureCall(s, d.to_call_id, d.to_target_id);
      s.calls[d.to_call_id] = { ...s.calls[d.to_call_id] };
      s.log = [...s.log, rerouteItem(ev.seq, d)];
      break;
    }
    case "swarm.knowledge":
      s.log = [...s.log, { kind: "knowledge", seq: ev.seq, message: ev.data.note }];
      break;
    case "swarm.ranked":
      s.ranked = { rankings: ev.data.rankings, bestCallId: ev.data.best_call_id ?? null, criteria: ev.data.criteria };
      break;
    case "swarm.reserved":
      s.reserved = ev.data;
      s.reserving = null;
      break;
    case "swarm.completed":
      s.completed = ev.data;
      s.finishedAt = ev.ts;
      break;
  }
  return s;
}

function rerouteItem(seq: number, d: Extract<SwarmEvent, { type: "swarm.reroute" }>["data"]): LogItem {
  return { kind: "reroute", seq, message: d.reason, tone: d.kind, toTargetId: d.to_target_id, fromTargetId: d.from_target_id ?? null };
}

export function applyAll(initial: SwarmView, events: SwarmEvent[]): SwarmView {
  return events.reduce(applyEvent, initial);
}

// ------------------------------------------------------------------ selectors
export const ACTIVE_STATES = ["dialing", "talking", "extracting"] as const;

export function inquiryCalls(s: SwarmView): CallView[] {
  return s.targetOrder.map((tid) => s.calls[s.inquiryByTarget[tid]]).filter((c): c is CallView => Boolean(c));
}

export function counts(s: SwarmView) {
  const calls = inquiryCalls(s);
  return {
    total: calls.length,
    active: calls.filter((c) => (ACTIVE_STATES as readonly string[]).includes(c.state)).length,
    done: calls.filter((c) => c.state === "completed").length,
    failed: calls.filter((c) => c.state === "failed").length,
    // drop-off-only organizations (can_pickup === false) are not a pickup, so they don't count as a match
    matches: calls.filter((c) => c.result && (c.result.available === "yes" || c.result.available === "partial") && c.result.can_pickup !== false).length,
  };
}

export function swarmStatus(s: SwarmView): "running" | "completed" | "cancelled" | "error" {
  return s.completed ? s.completed.status : "running";
}
