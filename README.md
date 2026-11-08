# Swarm Dial

**Food rescue.** A restaurant, bakery or caterer describes the exact food that is about to go to waste. A swarm of real-time voice AI agents phones every nearby food bank, pantry and shelter at once, asks who can send someone to pick it up and how soon, and a Swarm Commander reroutes around full or closed organizations, shares what the agents learn, follows referrals, and ranks who can collect it soonest. One click makes a second call to confirm the pickup. A live dashboard shows every call, transcript and a ranked comparison.

The same engine also finds things nearby (pharmacy stock, plumbers, DMV appointments, free food) from the "I need something" tab.

**Runs with zero API keys** in practice mode (simulated businesses, scripted agents). Real phone calls need Twilio + Deepgram + an LLM key.

## Quick start
```bash
make setup
make backend      # terminal 1  → http://localhost:8000/docs
make frontend     # terminal 2  → http://localhost:3000
```
Frontend only (no Python): `make mock` replays recorded swarms on :8000.
Terminal demo: `make sim`. Tests: `make test`. Everything in Docker: `make up`.

## Real calls
Copy `backend/.env.example` to `backend/.env`, set the Twilio, Deepgram and Groq/OpenAI keys, expose the backend with a tunnel (`ngrok http 8000`) and set `PUBLIC_BASE_URL`, and put teammates' phones in `DEMO_TARGETS`. Live mode only dials those numbers by default.

## Layout
```
backend/    FastAPI, Swarm Commander, agents, Twilio bridge, tests (69)
frontend/   Next.js 14 dashboard, reducer, mock server, tests
contract/   schema.json, generated types.ts, recorded fixtures, EVENTS.md
docs/       ARCHITECTURE.md (schema, Redis topology, flows)
```
The Pydantic models in `backend/app/contract.py` are the single contract; edit them, then `make contract`.
