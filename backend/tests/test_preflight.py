"""Preflight checks against a mocked network. Author: Saamarth Attray"""
import dataclasses

import httpx

from app.config import Settings
from app.preflight import run_preflight

FULL = Settings(
    google_places_api_key="g", deepgram_api_key="d", llm_provider="groq", llm_api_key="k",
    twilio_account_sid="AC1", twilio_auth_token="t", twilio_from_number="+12025550100",
    public_base_url="https://x.example", demo_targets=(("Sam", "+12025550101"),),
    allow_real_business_calls=False,
)


def transport(overrides=None, trial=False):
    overrides = overrides or {}

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        for key, resp in overrides.items():
            if key in url:
                return resp
        if "places:searchText" in url:
            return httpx.Response(200, json={"places": [{"nationalPhoneNumber": "(202) 555-0100"}] * 3})
        if "deepgram" in url:
            return httpx.Response(200, json={})
        if "/models" in url:
            return httpx.Response(200, json={"data": [{"id": "llama-3.3-70b-versatile"}]})
        if "IncomingPhoneNumbers" in url:
            return httpx.Response(200, json={"incoming_phone_numbers": [{"sid": "PN1"}]})
        if "api.twilio.com" in url:
            return httpx.Response(200, json={"type": "Trial" if trial else "Full"})
        if "/api/health" in url:
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_everything_configured_passes():
    checks = await run_preflight(FULL, transport())
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]
    assert next(c for c in checks if c.name == "Google Places").detail.startswith("3 pharmacies")


async def test_trial_twilio_is_flagged():
    twilio = next(c for c in await run_preflight(FULL, transport(trial=True)) if c.name == "Twilio")
    assert twilio.ok and twilio.warn and "verified" in twilio.detail


async def test_missing_keys_each_say_what_to_set():
    checks = await run_preflight(Settings(allow_real_business_calls=False), transport())
    assert not any(c.ok for c in checks)
    text = " ".join(c.detail for c in checks)
    for needle in ("GOOGLE_PLACES_API_KEY", "DEEPGRAM_API_KEY", "GROQ_API_KEY", "TWILIO_ACCOUNT_SID", "PUBLIC_BASE_URL", "DEMO_TARGETS"):
        assert needle in text


async def test_bad_places_key_and_wrong_model_are_reported():
    bad = {"places:searchText": httpx.Response(403, text="API key not valid")}
    checks = await run_preflight(FULL, transport(bad))
    assert "403" in next(c for c in checks if c.name == "Google Places").detail
    wrong = dataclasses.replace(FULL, llm_model="nope-model")
    assert "LLM_MODEL" in next(c for c in await run_preflight(wrong, transport()) if c.name == "LLM").detail


async def test_http_public_url_is_rejected():
    c = next(c for c in await run_preflight(dataclasses.replace(FULL, public_base_url="http://x.example"), transport()) if c.name == "Public URL")
    assert not c.ok and "https" in c.detail


async def test_recording_only_for_demo_phones_and_never_with_real_calls():
    import dataclasses
    from app.telephony.twilio_client import TwilioTelephony

    sent = []

    def handler(req: httpx.Request) -> httpx.Response:
        sent.append(dict(x.split("=", 1) for x in req.content.decode().split("&")))
        return httpx.Response(201, json={"sid": "CA1"})

    def telephony(**kw):
        s = dataclasses.replace(FULL, **kw)
        return TwilioTelephony(s, httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    await telephony(record_demo_calls=True).place_call(call_id="c1", to="+12025550101")      # your own phone
    await telephony(record_demo_calls=True).place_call(call_id="c2", to="+19995550000")      # a stranger
    await telephony(record_demo_calls=True, allow_real_business_calls=True).place_call(call_id="c3", to="+12025550101")
    await telephony().place_call(call_id="c4", to="+12025550101")                            # recording off by default
    assert [("Record" in d) for d in sent] == [True, False, False, False]
    assert sent[0]["RecordingChannels"] == "dual"


async def test_places_follows_the_page_token_for_more_results():
    from app.places import GooglePlaces
    from app.contract import LatLng

    bodies = []

    def handler(req: httpx.Request) -> httpx.Response:
        import json as _json
        body = _json.loads(req.content)
        bodies.append(body)
        page = [{"id": f"p{len(bodies)}-{i}", "displayName": {"text": "Pharmacy"}, "nationalPhoneNumber": "(202) 555-01%02d" % i,
                 "location": {"latitude": 38.9, "longitude": -77.0}} for i in range(3)]
        return httpx.Response(200, json={"places": page, **({"nextPageToken": "tok"} if len(bodies) == 1 else {})})

    gp = GooglePlaces("k", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    got = await gp._query("pharmacy", LatLng(lat=38.9, lng=-77.0), 5, 40, pages=2)
    assert len(got) == 6 and bodies[1]["pageToken"] == "tok" and "pageToken" not in bodies[0]


def test_dotenv_last_duplicate_line_wins(tmp_path, monkeypatch):
    from app.config import _load_dotenv, parse_demo_targets

    monkeypatch.delenv("DEMO_TARGETS", raising=False)
    env = tmp_path / ".env"
    env.write_text("DEMO_TARGETS=Old:+12025550100\n# comment\nDEMO_TARGETS = Jaswant: +17033032019; Saamarth: +17039442264\n")
    _load_dotenv(env)
    import os
    assert parse_demo_targets(os.environ["DEMO_TARGETS"]) == [("Jaswant", "+17033032019"), ("Saamarth", "+17039442264")]


def test_real_calls_are_the_default_and_need_a_places_key():
    s = Settings(deepgram_api_key="d", llm_provider="groq", llm_api_key="k", twilio_account_sid="AC1",
                 twilio_auth_token="t", twilio_from_number="+12025550100", public_base_url="https://x.example")
    assert s.allow_real_business_calls
    assert any("GOOGLE_PLACES_API_KEY" in m for m in s.live_missing())
    assert not dataclasses.replace(s, google_places_api_key="g").live_missing()  # no DEMO_TARGETS needed any more


def test_never_dial_emergency_agencies_or_non_business_numbers():
    from app.places import dialable_business

    assert dialable_business("CVS Pharmacy", "+12027654321")
    assert not dialable_business("City Police Department", "+12025550123")
    assert not dialable_business("Fairfax Fire Station 12", "+17035550123")
    assert not dialable_business("Anything", "+911")          # short / emergency
    assert not dialable_business("Anything", "+12115550123")  # 211-style service code
    assert not dialable_business("Anything", "+442071234567") # not US/Canada
    assert not dialable_business("Anything", "+19005550123")  # premium rate


async def test_dial_limits_cooldown_and_daily_cap():
    import time
    from app.commander import SwarmCommander as Commander
    from app.contract import Target

    def t(i):
        return Target(id=f"t{i}", name=f"B{i}", phone=f"+120276543{i}0", lat=0, lng=0, distance_miles=1.0, open_now=True, source="places")

    cmd = Commander.__new__(Commander)
    cmd.settings = dataclasses.replace(FULL, redial_cooldown_min=30, max_calls_per_day=2)
    cmd._last_dialed, cmd._calls_today, cmd._day = {}, 0, time.strftime("%Y-%m-%d")
    got = cmd._apply_dial_limits([t(1), t(2), t(3)])
    assert [x.id for x in got] == ["t1", "t2"]            # daily cap trims the list
    cmd._note_dialed(got[0].phone)
    assert [x.id for x in cmd._apply_dial_limits([t(1), t(2)])] == ["t2"]  # t1 is cooling down
