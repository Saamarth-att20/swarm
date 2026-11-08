# One Makefile for Windows, Mac and Linux. Author: Saamarth Attray
ifeq ($(OS),Windows_NT)
SHELL := cmd.exe
BOOT := python
PY := .venv\Scripts\python
SIM_ENV := set SIM_SPEED=0.3&&
else
BOOT := python3
PY := .venv/bin/python
SIM_ENV := SIM_SPEED=0.3
endif

.PHONY: preflight setup dev local backend frontend ngrok mock test contract fixtures sim up

setup:
	cd backend && $(BOOT) -m venv .venv && $(PY) -m pip install -r requirements.txt
	cd frontend && npm install

dev:        ## backend + frontend + ngrok together in this one window (Ctrl+C stops all)
	$(MAKE) -j3 backend frontend ngrok

local:      ## backend + frontend only, for practice runs (no ngrok needed)
	$(MAKE) -j2 backend frontend

backend:    ## API on :8000 (practice mode needs no keys)
	cd backend && $(PY) -m uvicorn app.main:app --reload --port 8000

frontend:   ## UI on :3000
	cd frontend && npm run dev

ngrok:      ## public address so Twilio can reach the backend (real calls only)
	ngrok http 8000

mock:       ## frontend-only: replays recorded swarms on :8000, no Python
	cd frontend && npm run mock

test:
	cd backend && $(PY) -m pytest -q
	cd frontend && npm test && npm run typecheck

contract:   ## regenerate schema.json + TS types after editing backend/app/contract.py
	cd backend && $(PY) scripts/export_contract.py
	cd frontend && npx --yes json-schema-to-typescript@15 -i ../contract/schema.json -o ../contract/types.ts --unreachableDefinitions --bannerComment "/* Generated from contract/schema.json. DO NOT EDIT. Regenerate: make contract */"
	cd frontend && npm run contract

fixtures:
	cd backend && $(PY) scripts/record_fixtures.py

preflight:  ## check every key/URL live mode needs, without placing a call
	cd backend && $(PY) scripts/preflight.py

sim:        ## watch a full swarm in the terminal
	cd backend && $(SIM_ENV) $(PY) scripts/simulate.py

up:
	docker compose up --build