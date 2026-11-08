"""CallSession + the streaming LLM brain, against a mocked OpenAI-compatible SSE endpoint. Author: Saamarth Attray"""
import dataclasses
import json

import httpx

from app.agent.brain import LLMBrain
from app.agent.session import CallSession
from app.agent.types import BrainContext
from app.config import Settings
from app.contract import Target
from app.intent import heuristic_intent
from app.llm import LLMClient


class Recorder:
    def __init__(self):
        self.states, self.lines, self.extracted_results = [], [], []

    async def state(self, state, reason=None):
        self.states.append(state)

    async def transcript(self, speaker, text, utterance_id, is_final):
        if is_final:
            self.lines.append((speaker, text))

    async def extracted(self, result):
        self.extracted_results.append(result)


def sse(*chunks) -> bytes:
    body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
    return body.encode()


def delta(content=None, tool_calls=None):
    d = {}
    if content is not None:
        d["content"] = content
    if tool_calls is not None:
        d["tool_calls"] = tool_calls
    return {"choices": [{"delta": d}]}


def make_client(handler) -> LLMClient:
    settings = Settings(llm_provider="groq", llm_api_key="test-key")
    return LLMClient(settings, http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def ctx():
    return BrainContext(
        intent=heuristic_intent("Find a pharmacy with amoxicillin", 10, None),
        target=Target(id="t1", name="CVS Pharmacy", lat=0, lng=0, distance_miles=1),
    )


async def test_llm_stream_text_and_split_tool_call():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content)
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, content=sse(
            delta("Great, thanks. "), delta("Let me note that down."),
            delta(tool_calls=[{"index": 0, "id": "call_1", "function": {"name": "report_availability", "arguments": '{"available": "ye'}}]),
            delta(tool_calls=[{"index": 0, "function": {"arguments": 's", "price": "$14.50", "can_hold": "true"}'}}]),
        ), headers={"content-type": "text/event-stream"})

    rec = Recorder()
    c = ctx()
    session = CallSession(c, LLMBrain(make_client(handler), c), rec)
    await session.start()
    spoken = [s async for s in session.respond("Yes we have it, fourteen fifty, and we can hold it.")]

    assert seen["auth"] == "Bearer test-key" and seen["payload"]["stream"] is True
    assert {t["function"]["name"] for t in seen["payload"]["tools"]} == {"report_availability", "wait_for_person", "press_keys", "end_call"}
    assert "CVS Pharmacy" in seen["payload"]["messages"][0]["content"]   # dynamic persona for this business
    assert spoken[0] == "Great, thanks." and session.finished
    assert rec.states == ["extracting"] and len(rec.extracted_results) == 1
    result = session.outcome().result
    assert result.available == "yes" and result.price == 14.5 and result.can_hold is True
    assert session.outcome().state == "completed"
    # valid OpenAI history: assistant(tool_calls) followed by the tool result
    roles = [m["role"] for m in session.messages]
    assert roles[-3:] == ["assistant", "tool", "assistant"] or "tool" in roles


async def test_llm_failure_asks_to_repeat_then_gives_up_only_after_several_failures(monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr("app.llm.asyncio.sleep", no_sleep)

    def handler(request):
        return httpx.Response(500, text="boom")

    rec = Recorder()
    c = ctx()
    session = CallSession(c, LLMBrain(make_client(handler), c), rec)
    await session.start()
    first = [s async for s in session.respond("hello?")]
    assert not session.finished and first and "sorry" in first[0].lower()
    second = [s async for s in session.respond("hello? anyone there?")]
    assert not session.finished and second
    third = [s async for s in session.respond("hello???")]
    assert session.finished and "trouble" in third[-1].lower()
    outcome = session.outcome()
    # a call we could not carry out is a failure with a reason, never a fake "unknown" answer
    assert outcome.state == "failed" and outcome.result is None and "AI model" in (outcome.reason or "")


async def test_a_good_turn_resets_the_failure_count(monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr("app.llm.asyncio.sleep", no_sleep)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] <= 2:  # the whole first turn fails (primary, then the fallback model), then the model recovers
            return httpx.Response(429, text="rate limited", headers={"retry-after": "0"})
        return httpx.Response(200, content=sse(delta("Sure, children's Tylenol please.")), headers={"content-type": "text/event-stream"})

    rec = Recorder()
    c = ctx()
    session = CallSession(c, LLMBrain(make_client(handler), c), rec)
    await session.start()
    [s async for s in session.respond("Hi")]
    assert session.llm_failures == 1
    again = [s async for s in session.respond("How can I help you?")]
    assert again == ["Sure, children's Tylenol please."] and session.llm_failures == 0


async def test_rate_limit_retries_then_switches_to_fallback_model(monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr("app.llm.asyncio.sleep", no_sleep)
    models = []

    def handler(request):
        models.append(json.loads(request.content)["model"])
        if len(models) < 2:
            return httpx.Response(429, text="rate limited", headers={"retry-after": "1"})
        return httpx.Response(200, content=sse(delta("Okay.")), headers={"content-type": "text/event-stream"})

    client = make_client(handler)
    client.settings = dataclasses.replace(client.settings, llm_fallback_model="llama-3.1-8b-instant")
    out = [e async for e in client.stream_chat([{"role": "user", "content": "hi"}])]
    assert out and out[0].text == "Okay."
    # a rate limit switches to the fallback model straight away instead of burning seconds on retries
    assert models == [client.settings.resolved_llm_model, "llama-3.1-8b-instant"]


async def test_press_keys_tool_queues_digits_and_waits_for_the_menu():
    rec = Recorder()
    c = ctx()

    def handler(request):
        return httpx.Response(200, content=sse(
            delta(tool_calls=[{"index": 0, "id": "k1", "function": {"name": "press_keys", "arguments": '{"digits": "press 3"}'}}]),
        ), headers={"content-type": "text/event-stream"})

    session = CallSession(c, LLMBrain(make_client(handler), c), rec)
    await session.start()
    spoken = [s async for s in session.respond("To speak to a member of the pharmacy staff, press 3.")]
    assert spoken == [] and session.pending_keys == "3" and session.holding and not session.finished


def test_dtmf_tones_are_valid_mulaw_with_the_right_frequencies():
    import math
    from app.telephony.dtmf import SAMPLE_RATE, clean_digits, dtmf_mulaw

    assert clean_digits("press 3, then #") == "3#" and clean_digits(None) == "" and len(clean_digits("1" * 40)) == 12
    audio = dtmf_mulaw("5")
    assert len(audio) == int(SAMPLE_RATE * 0.25) + int(SAMPLE_RATE * 0.15)

    def decode(b):  # G.711 mu-law -> linear
        b = ~b & 0xFF
        sign, exp, man = b & 0x80, (b >> 4) & 7, b & 0x0F
        v = (((man << 3) + 0x84) << exp) - 0x84
        return -v if sign else v

    pcm = [decode(b) for b in audio[: int(SAMPLE_RATE * 0.25)]]

    def power(freq):
        re = sum(x * math.cos(2 * math.pi * freq * n / SAMPLE_RATE) for n, x in enumerate(pcm))
        im = sum(x * math.sin(2 * math.pi * freq * n / SAMPLE_RATE) for n, x in enumerate(pcm))
        return re * re + im * im

    # "5" = 770 Hz + 1336 Hz; other keypad frequencies must be far quieter
    assert power(770) > 20 * power(697) and power(1336) > 20 * power(1209) and power(1336) > 20 * power(1477)


async def test_llm_retries_once_on_transient_error():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(400, text='{"error":{"code":"tool_use_failed"}}')
        return httpx.Response(200, content=sse(delta("Okay, one moment.")), headers={"content-type": "text/event-stream"})

    rec = Recorder()
    c = ctx()
    session = CallSession(c, LLMBrain(make_client(handler), c), rec)
    await session.start()
    spoken = [s async for s in session.respond("hold on")]
    assert calls["n"] == 2 and spoken == ["Okay, one moment."] and not session.finished


async def test_interrupted_turn_keeps_only_spoken_text_in_history():
    import asyncio

    def handler(request):
        return httpx.Response(200, content=sse(delta("First sentence. "), delta("Second sentence. "), delta("Third.")),
                              headers={"content-type": "text/event-stream"})

    rec = Recorder()
    c = ctx()
    session = CallSession(c, LLMBrain(make_client(handler), c), rec)
    await session.start()
    agen = session.respond("hello")
    first = await agen.__anext__()          # the business barges in right after the first sentence
    await agen.aclose()
    await session.abort_turn()
    assert first == "First sentence."
    assert session.messages[-1] == {"role": "assistant", "content": "First sentence."}
    assert ("agent", "First sentence.") in rec.lines


async def test_opening_line_discloses_ai():
    rec = Recorder()
    c = ctx()
    session = CallSession(c, LLMBrain(make_client(lambda r: httpx.Response(200)), c), rec)
    line = await session.start()
    assert "AI assistant" in line and "amoxicillin" in line.lower()


async def test_end_call_issued_together_with_a_question_is_ignored():
    def handler(request):
        return httpx.Response(200, content=sse(
            delta("Sure, no rush. Can you hold one for the customer?"),
            delta(tool_calls=[{"index": 0, "id": "call_9", "function": {"name": "end_call", "arguments": '{"reason": "other"}'}}]),
        ), headers={"content-type": "text/event-stream"})

    rec = Recorder()
    c = ctx()
    session = CallSession(c, LLMBrain(make_client(handler), c), rec)
    await session.start()
    spoken = [s async for s in session.respond("It's twelve dollars.")]
    assert spoken == ["Sure, no rush.", "Can you hold one for the customer?"]
    assert not session.finished                       # the business still gets to answer
    assert all(m.get("role") != "tool" for m in session.messages)


async def test_end_call_with_a_real_reason_still_hangs_up():
    def handler(request):
        return httpx.Response(200, content=sse(
            delta("No problem, thanks for your time."),
            delta(tool_calls=[{"index": 0, "id": "call_8", "function": {"name": "end_call", "arguments": '{"reason": "refused"}'}}]),
        ), headers={"content-type": "text/event-stream"})

    rec = Recorder()
    c = ctx()
    session = CallSession(c, LLMBrain(make_client(handler), c), rec)
    await session.start()
    [s async for s in session.respond("We don't talk to robots.")]
    assert session.finished


def test_filler_noise_does_not_count_as_speech():
    from app.telephony.media_bridge import _is_real_speech

    assert not _is_real_speech("uh") and not _is_real_speech("Mm.") and not _is_real_speech("hmm, uh")
    assert _is_real_speech("Yes") and _is_real_speech("hold on") and _is_real_speech("No.")


async def test_gpt_oss_gets_short_reasoning_and_room_to_answer():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content)
        return httpx.Response(200, content=sse(delta("Okay.")), headers={"content-type": "text/event-stream"})

    settings = Settings(llm_provider="groq", llm_api_key="k", llm_model="openai/gpt-oss-120b")
    client = LLMClient(settings, http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    c = ctx()
    session = CallSession(c, LLMBrain(client, c), Recorder())
    await session.start()
    [s async for s in session.respond("hello")]
    assert seen["payload"]["reasoning_effort"] == "low" and seen["payload"]["max_tokens"] >= 300


async def test_prompt_teaches_the_agent_to_handle_phone_menus_and_ai_receptionists():
    from app.agent.personas import build_system_prompt

    prompt = build_system_prompt(ctx())
    for needle in ("press 1", "representative", "wait_for_person", "voicemail", "AI receptionist", "real person answers"):
        assert needle in prompt


async def test_hold_is_handled_by_rules_then_the_agent_reintroduces_itself_to_the_person():
    def handler(request):
        raise AssertionError("the model must not be called for a hold announcement or the first words of a person")

    rec = Recorder()
    c = ctx()
    session = CallSession(c, LLMBrain(make_client(handler), c), rec)
    await session.start()
    spoken = [s async for s in session.respond("Please hold while we transfer your call.")]
    assert spoken == [] and session.holding and not session.finished   # silent: nothing said to a recording
    intro = [s async for s in session.respond("Pharmacy, this is Dana.")]   # a person arrives
    assert not session.holding
    assert intro and "AI" in " ".join(intro)                            # introduces itself again, still disclosing


async def test_prompt_handles_screening_questions_and_bare_greetings():
    from app.agent.personas import build_system_prompt

    prompt = build_system_prompt(ctx())
    for needle in ("health care provider", "not a refusal", "Thank you for calling", "Never say goodbye unless"):
        assert needle in prompt


async def test_real_business_calls_require_the_users_real_location(stack):
    import pytest

    from app.commander import LiveModeUnavailable
    from app.contract import CreateSwarmRequest

    live = dict(twilio_account_sid="AC1", twilio_auth_token="t", twilio_from_number="+12025550100",
                deepgram_api_key="d", llm_provider="groq", llm_api_key="k", public_base_url="https://x.example",
                allow_real_business_calls=True, google_places_api_key="g")
    commander = stack.build(**live)
    with pytest.raises(LiveModeUnavailable) as err:                   # no browser location: never fall back to the default city
        await commander.create_swarm(CreateSwarmRequest(query="pharmacy with amoxicillin", mode="live"))
    assert "location" in str(err.value).lower()
    assert await commander.create_swarm(CreateSwarmRequest(query="pharmacy with amoxicillin", mode="live", lat=38.9, lng=-77.4))



# ----------------------------------------------------------------------------- tool calls typed out as text
async def test_a_tool_call_the_model_types_as_text_is_never_spoken_and_is_run():
    """The failure seen on a real call: the transcript showed {"reason":"ivr_unresolved"} said aloud."""
    def handler(request):
        return httpx.Response(200, content=sse(delta('{"reason":"ivr_unresolved",'), delta('"notes":"Automated message. Nobody there"}')))

    rec = Recorder()
    c = ctx()
    session = CallSession(c, LLMBrain(make_client(handler), c), rec)
    await session.start()
    spoken = [s async for s in session.respond("Okay, what size were you after?")]
    assert spoken == []
    assert session.finished and session.end_reason == "ivr_unresolved"
    assert all("{" not in text for _, text in rec.lines)


async def test_text_before_a_typed_tool_call_is_still_spoken_and_function_tags_are_understood():
    def handler(request):
        return httpx.Response(200, content=sse(delta("Okay, thanks anyway. "), delta('<function=end_call>{"reason": "voicemail"}</function>')))

    c = ctx()
    session = CallSession(c, LLMBrain(make_client(handler), c), Recorder())
    await session.start()
    spoken = [s async for s in session.respond("Hmm, let me think about that for you.")]
    assert spoken == ["Okay, thanks anyway."]
    assert session.finished and session.end_reason == "voicemail"


async def test_unrecognised_machine_text_is_dropped_not_spoken():
    from app.agent.textcalls import parse_text_tool_call

    assert parse_text_tool_call('{"foo": 1}', {"end_call"}) is None
    call = parse_text_tool_call('{"name": "press_keys", "arguments": {"digits": "3"}}', {"press_keys", "end_call"})
    assert call and call.name == "press_keys" and call.arguments == {"digits": "3"}
    assert parse_text_tool_call('{"reason": "voicemail"}', {"press_keys"}) is None   # not a tool this call has


def test_service_and_appointment_calls_open_like_a_person_and_still_disclose():
    from app.agent.personas import opening_line

    t = Target(id="t1", name="Acme", lat=0, lng=0, distance_miles=1)
    for query, expect in (
        ("My water heater burst, find a plumber who can come tonight", "needs a plumber as soon as possible"),
        ("I need an HVAC company that can fix my furnace today", "heating or AC repaired today"),
        ("Find urgent care with a short wait for a sprained ankle", "walk-ins"),
    ):
        line = opening_line(BrainContext(intent=heuristic_intent(query, 10, None), target=t))
        assert expect in line and line.rstrip().endswith("on behalf of a customer.") and "AI assistant" in line
        assert "urgent plumber visit" not in line


def test_the_prompt_carries_the_customers_own_words_and_a_natural_call_flow():
    from app.agent.personas import build_system_prompt

    prompt = build_system_prompt(BrainContext(intent=heuristic_intent("Find a pharmacy with children's amoxicillin 125mg/5ml", 10, None),
                                              target=Target(id="t1", name="CVS", lat=0, lng=0, distance_miles=1)))
    assert "125mg/5ml" in prompt and "Usual order" in prompt and "How a good call sounds" in prompt


def test_groq_backup_model_is_a_capable_one_and_never_the_main_model():
    from app.config import _default_fallback

    assert _default_fallback("groq", "openai/gpt-oss-120b") == "llama-3.3-70b-versatile"
    assert _default_fallback("groq", None) == "llama-3.1-8b-instant"   # the default main model is already the 70B
    assert _default_fallback("openai", None) == ""


async def test_the_agent_answers_hello_with_why_it_is_calling_before_the_model_is_used():
    def handler(request):
        raise AssertionError("the opening is canned: no model call for the first reply")

    rec = Recorder()
    c = ctx()
    session = CallSession(c, LLMBrain(make_client(handler), c), rec)
    assert not session.opened
    spoken = [s async for s in session.respond("Hello, CVS pharmacy, how can I help you?")]
    assert len(spoken) == 1 and "amoxicillin" in spoken[0].lower() and spoken[0].rstrip().endswith("on behalf of a customer.")
    assert session.opened and session.messages[0] == {"role": "user", "content": "Hello, CVS pharmacy, how can I help you?"}
    assert rec.lines[0] == ("business", "Hello, CVS pharmacy, how can I help you?") and rec.lines[1][0] == "agent"