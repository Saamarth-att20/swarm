.PHONY: preflight setup backend frontend mock test contract fixtures sim up

setup:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd frontend && npm install

backend:    ## API on :8000 (practice mode needs no keys)
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend:   ## UI on :3000
	cd frontend && npm run dev

mock:       ## frontend-only: replays recorded swarms on :8000, no Python
	cd frontend && npm run mock

test:
	cd backend && .venv/bin/python -m pytest -q
	cd frontend && npm test && npm run typecheck

contract:   ## regenerate schema.json + TS types after editing backend/app/contract.py
	cd backend && .venv/bin/python scripts/export_contract.py
	cd frontend && npx --yes json-schema-to-typescript@15 -i ../contract/schema.json -o ../contract/types.ts --unreachableDefinitions --bannerComment "/* Generated from contract/schema.json. DO NOT EDIT. Regenerate: make contract */"
	cd frontend && npm run contract

fixtures:
	cd backend && .venv/bin/python scripts/record_fixtures.py

preflight:  ## check every key/URL live mode needs, without placing a call
	cd backend && .venv/bin/python scripts/preflight.py

sim:        ## watch a full swarm in the terminal
	cd backend && SIM_SPEED=0.3 .venv/bin/python scripts/simulate.py

up:
	docker compose up --build
