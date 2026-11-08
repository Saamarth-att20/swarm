// Mock of the Swarm Dial backend for frontend work without Python, keys or phones.
// Replays real recorded swarms (contract/fixtures/*.json) over the exact same REST + WebSocket contract.
//   npm run mock   ->  http://localhost:8000
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { randomBytes } from "node:crypto";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { WebSocketServer } from "ws";

const here = dirname(fileURLToPath(import.meta.url));
const FIXTURES = {
  pharmacy: JSON.parse(readFileSync(join(here, "../../contract/fixtures/pharmacy.json"), "utf8")),
  plumber: JSON.parse(readFileSync(join(here, "../../contract/fixtures/plumber.json"), "utf8")),
  rescue: JSON.parse(readFileSync(join(here, "../../contract/fixtures/rescue.json"), "utf8")),
};
const SPEED = Number(process.env.MOCK_SPEED || 1);
const PORT = Number(process.env.PORT || 8000);

/** swarmId -> { query, events: [], listeners: Set, status, timers: [] } */
const swarms = new Map();

const delayFor = (e) => {
  switch (e.type) {
    case "call.transcript": return e.data.is_final ? 700 : 90;
    case "call.state": return e.data.state === "dialing" ? 300 : 450;
    case "swarm.created": return 400;
    case "swarm.ranked": return 600;
    default: return 350;
  }
};

function emit(s, event) {
  event.seq = s.events.length + 1;
  event.swarm_id = s.id;
  event.ts = Date.now() / 1000;
  s.events.push(event);
  for (const send of s.listeners) send(event);
}

function start(query, purpose = "find") {
  const id = "s_" + randomBytes(5).toString("hex");
  const rescue = purpose === "donate";
  const fixture = rescue ? FIXTURES.rescue : /plumb|leak|pipe|electric|locksmith|dmv|appointment/i.test(query) ? FIXTURES.plumber : FIXTURES.pharmacy;
  const s = { id, query, rescue, events: [], listeners: new Set(), status: "running", created_at: Date.now() / 1000, timers: [] };
  swarms.set(id, s);
  let at = 0;
  fixture.forEach((src, i) => {
    at += delayFor(src) / SPEED;
    s.timers.push(setTimeout(() => {
      const e = structuredClone(src);
      if (i === 0) e.data.query = query;
      emit(s, e);
      if (e.type === "swarm.completed") s.status = e.data.status;
    }, at));
  });
  return s;
}

function cancel(s) {
  if (s.status !== "running") return false;
  s.timers.forEach(clearTimeout);
  s.status = "cancelled";
  emit(s, { type: "swarm.completed", data: { status: "cancelled", calls_made: 0, calls_completed: 0, calls_failed: 0, positives: 0, elapsed_s: 0, error: null } });
  return true;
}

function reserve(s, callId) {
  const src2 = s;
  const src = s.events.find((e) => e.type === "call.state" && e.data.call_id === callId);
  if (!src) return null;
  const rid = "r_" + randomBytes(3).toString("hex");
  const base = { call_id: rid, target_id: src.data.target_id, role: "reserve", reason: null };
  emit(s, { type: "call.state", data: { ...base, state: "dialing" } });
  setTimeout(() => emit(s, { type: "call.state", data: { ...base, state: "talking" } }), 800 / SPEED);
  setTimeout(() => {
    emit(s, { type: "call.state", data: { ...base, state: "completed" } });
    emit(s, { type: "swarm.reserved", data: { call_id: callId, target_id: src.data.target_id, reserve_call_id: rid, success: true, confirmation: (src2.rescue ? "PICKUP-" : "HOLD-") + randomBytes(2).toString("hex").toUpperCase(), message: src2.rescue ? "Pickup confirmed. A volunteer is on the way with a van." : "Held under your name for the next two hours." } });
  }, 2600 / SPEED);
  return rid;
}

const json = (res, code, body) => {
  res.writeHead(code, { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "*" });
  res.end(JSON.stringify(body));
};
const summary = (s) => ({ id: s.id, query: s.query, mode: "simulated", status: s.status, created_at: s.created_at });

const server = createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  const p = url.pathname;
  if (req.method === "OPTIONS") return json(res, 204, {});
  let body = "";
  for await (const chunk of req) body += chunk;

  if (p === "/api/health") return json(res, 200, { ok: true, version: "1.0.0", mock: true });
  if (p === "/api/capabilities")
    return json(res, 200, { version: "1.0.0", live_available: false, live_missing: ["This is the mock server; use the real backend for phone calls"], llm_provider: "mock", places_provider: "mock", demo_targets: 0 });
  if (p === "/api/swarms" && req.method === "POST") {
    const { query, purpose } = JSON.parse(body || "{}");
    if (!query || query.length < 3) return json(res, 422, { detail: "query must be at least 3 characters" });
    return json(res, 201, { swarm_id: start(query, purpose).id });
  }
  if (p === "/api/swarms" && req.method === "GET") return json(res, 200, [...swarms.values()].reverse().slice(0, 6).map(summary));

  let m = p.match(/^\/api\/swarms\/([^/]+)$/);
  if (m) {
    const s = swarms.get(m[1]);
    return s ? json(res, 200, { swarm: summary(s), events: s.events, last_seq: s.events.length }) : json(res, 404, { detail: "swarm not found" });
  }
  m = p.match(/^\/api\/swarms\/([^/]+)\/cancel$/);
  if (m) {
    const s = swarms.get(m[1]);
    return s ? json(res, 200, { ok: cancel(s) }) : json(res, 404, { detail: "swarm not found" });
  }
  m = p.match(/^\/api\/swarms\/([^/]+)\/reserve\/([^/]+)$/);
  if (m) {
    const s = swarms.get(m[1]);
    if (!s) return json(res, 404, { detail: "swarm not found" });
    const rid = reserve(s, m[2]);
    return rid ? json(res, 200, { ok: true, reserve_call_id: rid }) : json(res, 404, { detail: "call not found" });
  }
  json(res, 404, { detail: "not found" });
});

const wss = new WebSocketServer({ noServer: true });
server.on("upgrade", (req, socket, head) => {
  const url = new URL(req.url, "http://x");
  const m = url.pathname.match(/^\/ws\/swarms\/([^/]+)$/);
  const s = m && swarms.get(m[1]);
  if (!s) return socket.destroy();
  const after = Number(url.searchParams.get("after") || 0);
  wss.handleUpgrade(req, socket, head, (ws) => {
    const send = (e) => ws.readyState === 1 && ws.send(JSON.stringify(e));
    s.events.filter((e) => e.seq > after).forEach(send);
    s.listeners.add(send);
    ws.on("close", () => s.listeners.delete(send));
  });
});

server.listen(PORT, () => console.log(`Mock Swarm Dial API on http://localhost:${PORT} (MOCK_SPEED=${SPEED})`));
