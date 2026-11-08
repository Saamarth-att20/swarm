# Wire contract v1.0.0

Source of truth: `backend/app/contract.py` → `contract/schema.json` → `contract/types.ts` (`make contract`).

## REST
| Method | Path | Body → Response |
|---|---|---|
| GET | `/api/capabilities` | → `Capabilities` (is live mode possible, what is missing) |
| POST | `/api/swarms` | `CreateSwarmRequest` (food rescue: `purpose: "donate"`, `contact_name`, `donor_address`, `pickup_by`) → `{swarm_id}` (400 `{message, missing[]}` if live mode isn't configured) |
| GET | `/api/swarms?limit=` | → `SwarmSummary[]` |
| GET | `/api/swarms/{id}` | → `SwarmDetail` (all events so far) |
| POST | `/api/swarms/{id}/cancel` | → `{ok}` |
| POST | `/api/swarms/{id}/reserve/{call_id}` | → `{ok, reserve_call_id}` (404 unknown, 409 not reservable) |

## WebSocket `/ws/swarms/{id}?after=<seq>`
Replays every event with `seq > after`, then streams live. Envelope: `{seq, swarm_id, ts, type, data}`.

| type | data | UI effect |
|---|---|---|
| `swarm.created` | query, mode, intent, origin, targets[] | create nodes |
| `call.state` | call_id, target_id, state, role, reason | status grid / canvas colour |
| `call.transcript` | call_id, utterance_id, speaker, text, is_final | transcript; same `utterance_id` replaces the partial |
| `call.extracted` | call_id, result | comparison row |
| `swarm.reroute` | from/to ids, kind, reason, new_target? | commander log, dashed arc |
| `swarm.knowledge` | note | commander log |
| `swarm.ranked` | rankings[], best_call_id, criteria | highlight the winner |
| `swarm.reserved` | call_id, success, confirmation?, message | winner card |
| `swarm.completed` | status, counts, elapsed_s | stop timers |

Call states: `queued → dialing → talking → extracting → completed | failed | cancelled`.
