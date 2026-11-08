# Swarm Dial: architecture

## System

```
 Browser (Next.js)  ──REST──►  FastAPI  ──►  SwarmCommander ──► CallSession × N ──► Twilio ⇄ Deepgram ⇄ LLM
        ▲                         │              │                                      (live)
        └────── WebSocket ◄───────┴── EventBus ◄─┴── SimulatedCallRunner (practice mode)
                  /ws/swarms/{id}?after=seq        │
                                              Postgres/SQLite (events, calls, results)  +  Redis pub/sub (optional)
```

One contract, two transports. Every state change is an **event** (`seq`, `swarm_id`, `ts`, `type`, `data`). The browser
renders by folding events through one reducer (`frontend/lib/reducer.ts`), whether they come from the first replay,
the live stream or a reconnect.

## Database schema (SQLAlchemy 2, `backend/app/db.py`)

| Table | Purpose | Key columns |
|---|---|---|
| `users` | Owner of swarms | `id`, `email` |
| `swarms` | One user request | `id`, `user_id→users`, `query`, `mode`, `status`, `intent` JSON, `origin_lat/lng`, `radius_miles`, `best_call_id`, `summary` JSON, `created_at`, `completed_at` |
| `tasks` | One business to call (and why) | `id`, `swarm_id→swarms`, `target_id`, `target` JSON, `tier` primary/backup, `role` inquiry/reserve, `status` |
| `calls` | One phone call | `id`, `task_id→tasks`, `swarm_id`, `state`, `failure_reason`, `provider_sid` (Twilio CallSid), `transcript` JSON, `started_at/ended_at/duration_s` |
| `extracted_data` | Structured answer from a call | `call_id→calls` (unique), `available` yes/no/partial/unknown, `item`, `price`, `quantity`, `can_hold`, `wait_minutes`, `alternatives`, `referral_*`, `closed`, `notes`, `confidence`, `raw` |
| `swarm_events` | Append-only event log (replay source) | `swarm_id`, `seq` (unique together), `type`, `data` JSON, `ts` |

SQLite (WAL) by default so it runs with zero setup; Postgres via `DATABASE_URL=postgresql+asyncpg://…`. Partial
(non-final) transcript events are streamed but not persisted.

## Redis pub/sub topology

- Channel per swarm: `swarm:{swarm_id}`; each API process does `PSUBSCRIBE swarm:*`.
- Publisher side (`EventBus.publish`): take the per-swarm lock → assign `seq` → validate against the Pydantic contract → append to the in-memory log → persist to `swarm_events` → `PUBLISH`.
- Every process (including the publisher) delivers to its own WebSocket subscribers from the Redis message, so N API replicas all serve the same stream.
- Without Redis the bus fans out in-process. Everything else is identical.
- Reconnect: `GET /ws/swarms/{id}?after=<last seq>` replays the missed events from the log, then goes live; duplicates are dropped client-side by `seq`.

## Swarm Commander (`backend/app/commander.py`)

1. Parse the request into an `Intent` (item, kind, category, priority), find targets (Google Places or mock), split into primary and backup tiers.
2. Dial primaries in parallel (semaphore `MAX_CONCURRENT_CALLS`, dials spaced by `DIAL_STAGGER_S`). A slot is held until its result is processed, so early-stop is exact.
3. On each result: closed, no stock, failed or referral ⇒ **reroute** to the next backup (a referral creates a brand-new target); `swarm.knowledge` notes are fed into later agents' prompts; after a closure open-now businesses move to the front; a brand that is dry twice is deprioritised.
4. Stop early after `TARGET_YES_COUNT` confirmed matches, cancel queued calls, rank, emit `swarm.ranked`.
5. **Reserve** ("closer"): a second call to the chosen business asks them to hold the item → `swarm.reserved`.

## A call

`CallSession` is transport-agnostic: `start()` → opening line, `respond(heard)` streams sentences while running the LLM tool loop. Tools: `report_availability` (the structured extraction), `report_hold`, `end_call`. Brains: `LLMBrain` (OpenAI-compatible streaming: Groq Llama 3 70B or GPT-4o-mini) and `ScriptedBrain` (offline).

Live path: Twilio REST dials → `/twilio/voice/{call_id}` returns `<Connect><Stream>` (with a per-call token) → `/twilio/stream/{call_id}` WebSocket (µ-law 8 kHz) → Deepgram STT → `CallSession` → Deepgram TTS → back to Twilio. Barge-in sends Twilio `clear`; marks tell us when the goodbye has finished playing before hanging up.

## Safety decisions

- Every call opens with "I'm an AI assistant calling on behalf of a customer". There is deliberately no switch to turn this off.
- Live mode only dials `DEMO_TARGETS` unless `ALLOW_REAL_BUSINESS_CALLS=true` and a Places key is present. Mock businesses use fictional 555 numbers.
- Twilio webhooks verify `X-Twilio-Signature`; media streams require the per-call token.

## Food rescue mode (`purpose: "donate"`)

`CreateSwarmRequest` carries `purpose`, `contact_name` (the donor business), `donor_address` and `pickup_by`. The request's `query` is the donor's exact food description and is kept verbatim as `Intent.item` (kind `donation`, category `food_donation`, priority `speed`).

| Piece | Behaviour |
|---|---|
| Targets | Food banks, pantries, shelters and meal programs (`place_query` "food pantry"). |
| Opening line | "I'm an AI assistant calling on behalf of {donor}. They have surplus food that would otherwise be thrown out tonight: {food}. Could your organization pick it up?" |
| Extraction | `available` yes = can pick up, partial = drop-off only or only some items, no = at capacity / closed. Plus `can_pickup`, `wait_minutes` (pickup ETA), `perishables_ok`, `hours`, `needs`. |
| Commander | Stops after 2 confirmed pickups. Drop-off-only counts as a miss and triggers a backup call. Knowledge notes: "X can pick it up in about 25 min", "Y is at capacity tonight". |
| Ranking | Weights: soonest pickup 0.40, availability 0.30, pickup ability 0.15, distance 0.15; no fresh food multiplies the score by 0.6. |
| Reserve | "Confirm pickup": a second call tells the organization the address and asks who is coming and when; result is `swarm.reserved` with a confirmation. |

Safety: the agent shares the pickup address only after the organization agrees to pick up, and never promises anything on the donor's behalf beyond confirming a pickup the donor chose.
