"""Checks every external service live mode depends on, without placing a call.

    python scripts/preflight.py

Each check makes one harmless request (a places search, an auth ping, a tiny model list) and says exactly what
to fix when it fails.

Author: Saamarth Attray
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from .config import Settings


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    warn: bool = False  # passed, but something to be aware of


async def _places(s: Settings, http: httpx.AsyncClient) -> Check:
    if not s.places_enabled:
        return Check("Google Places", False, "Set GOOGLE_PLACES_API_KEY (enable 'Places API (New)' in Google Cloud).")
    resp = await http.post(
        "https://places.googleapis.com/v1/places:searchText",
        json={"textQuery": "pharmacy", "maxResultCount": 5,
              "locationBias": {"circle": {"center": {"latitude": s.default_lat, "longitude": s.default_lng}, "radius": 5000.0}}},
        headers={"X-Goog-Api-Key": s.google_places_api_key or "",
                 "X-Goog-FieldMask": "places.displayName,places.nationalPhoneNumber,places.currentOpeningHours.openNow"},
    )
    if resp.status_code != 200:
        return Check("Google Places", False, f"HTTP {resp.status_code}: {resp.text[:160]}. Is 'Places API (New)' enabled and billing on?")
    places = resp.json().get("places", [])
    with_phone = sum(1 for p in places if p.get("nationalPhoneNumber"))
    return Check("Google Places", bool(places), f"{len(places)} pharmacies found near the default location, {with_phone} with phone numbers")


async def _deepgram(s: Settings, http: httpx.AsyncClient) -> Check:
    if not s.deepgram_enabled:
        return Check("Deepgram", False, "Set DEEPGRAM_API_KEY.")
    resp = await http.get("https://api.deepgram.com/v1/projects", headers={"Authorization": f"Token {s.deepgram_api_key}"})
    return Check("Deepgram", resp.status_code == 200, "API key accepted" if resp.status_code == 200 else f"HTTP {resp.status_code}: key rejected")


async def _llm(s: Settings, http: httpx.AsyncClient) -> Check:
    if not s.llm_enabled:
        return Check("LLM", False, "Set GROQ_API_KEY or OPENAI_API_KEY.")
    resp = await http.get(f"{s.resolved_llm_base_url}/models", headers={"Authorization": f"Bearer {s.llm_api_key}"})
    if resp.status_code != 200:
        return Check("LLM", False, f"HTTP {resp.status_code}: key rejected by {s.llm_provider}")
    ids = {m.get("id") for m in resp.json().get("data", [])}
    model = s.resolved_llm_model
    if ids and model not in ids:
        return Check("LLM", False, f"Key works but model '{model}' isn't available. Set LLM_MODEL to one of: {', '.join(sorted(map(str, ids))[:6])}")
    return Check("LLM", True, f"{s.llm_provider} key accepted, model {model} available")


async def _twilio(s: Settings, http: httpx.AsyncClient) -> Check:
    if not s.twilio_enabled:
        return Check("Twilio", False, "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER.")
    auth = (s.twilio_account_sid or "", s.twilio_auth_token or "")
    base = f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_account_sid}"
    resp = await http.get(f"{base}.json", auth=auth)
    if resp.status_code != 200:
        return Check("Twilio", False, f"HTTP {resp.status_code}: account SID or auth token rejected")
    account = resp.json()
    owned = await http.get(f"{base}/IncomingPhoneNumbers.json", params={"PhoneNumber": s.twilio_from_number}, auth=auth)
    numbers = owned.json().get("incoming_phone_numbers", []) if owned.status_code == 200 else []
    if not numbers:
        return Check("Twilio", False, f"{s.twilio_from_number} isn't a number on this account. Buy one or fix TWILIO_FROM_NUMBER.")
    if account.get("type") == "Trial":
        return Check("Twilio", True, "Trial account: can only call numbers you've verified in the Twilio console, and every call plays a trial message first. Upgrade for real businesses.", warn=True)
    return Check("Twilio", True, "Full account, From number verified")


async def _public_url(s: Settings, http: httpx.AsyncClient) -> Check:
    if not s.public_base_url:
        return Check("Public URL", False, "Set PUBLIC_BASE_URL to your tunnel (ngrok http 8000) so Twilio can reach the webhooks.")
    if not s.public_base_url.startswith("https://"):
        return Check("Public URL", False, "PUBLIC_BASE_URL must be https:// (Twilio refuses plain http webhooks and ws://).")
    try:
        resp = await http.get(f"{s.public_base_url}/api/health")
    except httpx.HTTPError as exc:
        return Check("Public URL", False, f"Can't reach {s.public_base_url}: {exc.__class__.__name__}. Is the tunnel up and the backend running?")
    return Check("Public URL", resp.status_code == 200, "Tunnel reaches this backend" if resp.status_code == 200 else f"HTTP {resp.status_code}: tunnel is up but not pointing at this backend")


def _targets(s: Settings) -> Check:
    if s.allow_real_business_calls:
        return Check("Who gets called", s.places_enabled, f"Real businesses near the user via Google Places (up to {s.max_targets} primary + {s.backup_targets} backup, {s.max_concurrent_calls} calls at once)" if s.places_enabled else "ALLOW_REAL_BUSINESS_CALLS is on but there is no GOOGLE_PLACES_API_KEY", warn=s.places_enabled)
    if s.demo_targets:
        return Check("Who gets called", True, f"TEST MODE: only your {len(s.demo_targets)} DEMO_TARGETS phone(s). Remove ALLOW_REAL_BUSINESS_CALLS=false to dial real businesses.")
    return Check("Who gets called", False, "Set DEMO_TARGETS (teammates' phones) for a safe test, or ALLOW_REAL_BUSINESS_CALLS=true.")


async def run_preflight(settings: Settings, http: httpx.AsyncClient | None = None) -> list[Check]:
    client = http or httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0))
    checks: list[Check] = []
    try:
        for fn in (_places, _deepgram, _llm, _twilio, _public_url):
            try:
                checks.append(await fn(settings, client))
            except httpx.HTTPError as exc:
                checks.append(Check(fn.__name__.strip("_").title(), False, f"Network error: {exc.__class__.__name__}"))
        checks.append(_targets(settings))
    finally:
        if http is None:
            await client.aclose()
    return checks
