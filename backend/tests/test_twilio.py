"""Twilio webhooks, signature validation, and the Media Streams voice bridge (with fake STT/TTS/Twilio).
Author: Saamarth Attray"""
import asyncio
import base64
import json

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.agent.brain import ScriptedBrain
from app.agent.session import CallSession
from app.agent.types import BrainContext
from app.contract import Target
from app.intent import heuristic_intent
from app.main import create_app
from app.telephony.media_bridge import TwilioMediaBridge
from app.telephony.speech import FakeSTT, FakeTTS, SttEvent
from app.telephony.twilio_client import (
    LiveCallContext,
    LiveCallRegistry,
    compute_signature,
    twiml_connect_stream,
    twiml_hangup,
    validate_signature,
)


# ----------------------------------------------------------------------------- signatures / TwiML
def test_signature_roundtrip_and_tamper_detection():
    url, params, token = "https://x.example/twilio/voice/c1", {"CallSid": "CA1", "AnsweredBy": "human", "A": "1"}, "secret"
    sig = compute_signature(url, params, token)
    assert validate_signature(url, params, sig, token)
    assert not validate_signature(url, {**params, "CallSid": "CA2"}, sig, token)
    assert not validate_signature(url, params, sig, "other-token")
    assert not validate_signature(url, params, None, token)


def test_twiml_is_well_formed_and_escaped():
    xml = twiml_connect_stream("wss://h.example/twilio/stream/c1", 'c"1', "tok&en")
    assert "<Connect>" in xml and "<Stream" in xml and "&amp;" in xml
    from xml.dom import minidom

    minidom.parseString(xml)
    minidom.parseString(twiml_hangup("Bye <now>"))


# ----------------------------------------------------------------------------- webhooks
@pytest.fixture
def client(settings):
    import dataclasses

    cfg = dataclasses.replace(settings, public_base_url="https://demo.example", validate_twilio_signature=False)
    with TestClient(create_app(cfg)) as c:
        yield c


def test_voice_webhook_for_unknown_call_hangs_up(client):
    r = client.post("/twilio/voice/nope", data={"CallSid": "CA1"})
    assert r.status_code == 200 and "<Hangup/>" in r.text


def test_voice_webhook_returns_stream_for_registered_call(client):
    class Dummy:
        finished = False

    loop = asyncio.new_event_loop()
    live = LiveCallContext(call_id="c1", swarm_id="s1", session=Dummy(), reporter=None, future=loop.create_future(), token="tok123")
    client.app.state.registry.register(live)
    r = client.post("/twilio/voice/c1", data={"CallSid": "CA1"})
    assert "wss://demo.example/twilio/stream/c1" in r.text and "tok123" in r.text
    loop.close()


def test_signature_enforced_when_enabled(settings):
    import dataclasses

    cfg = dataclasses.replace(settings, public_base_url="https://demo.example", twilio_auth_token="tok", validate_twilio_signature=True)
    with TestClient(create_app(cfg)) as c:
        assert c.post("/twilio/voice/c1", data={"CallSid": "CA1"}).status_code == 403
        sig = compute_signature("https://demo.example/twilio/voice/c1", {"CallSid": "CA1"}, "tok")
        ok = c.post("/twilio/voice/c1", data={"CallSid": "CA1"}, headers={"X-Twilio-Signature": sig})
        assert ok.status_code == 200


def test_media_stream_rejects_bad_token(settings):
    import dataclasses

    cfg = dataclasses.replace(settings, deepgram_api_key="dg")
    with TestClient(create_app(cfg, stt_factory=FakeSTT, tts=FakeTTS())) as c:
        with c.websocket_connect("/twilio/stream/c1") as ws:
            ws.send_text(json.dumps({"event": "start", "streamSid": "MZ1", "start": {
                "streamSid": "MZ1", "callSid": "CA1", "customParameters": {"call_id": "c1", "token": "wrong"}}}))
            with pytest.raises(WebSocketDisconnect):
                ws.receive_text()


# ----------------------------------------------------------------------------- the voice bridge
class FakeWS:
    def __init__(self):
        self.incoming: asyncio.Queue = asyncio.Queue()
        self.sent: list[dict] = []
        self.closed = False

    async def receive_text(self):
        item = await self.incoming.get()
        if item is None:
            raise WebSocketDisconnect()
        return item

    async def send_text(self, text):
        self.sent.append(json.loads(text))

    async def close(self, code=1000):
        self.closed = True

    def push(self, message: dict):
        self.incoming.put_nowait(json.dumps(message))

    def kinds(self):
        return [m["event"] for m in self.sent]


class Recorder:
    def __init__(self):
        self.states, self.transcripts, self.results = [], [], []

    async def state(self, state, reason=None):
        self.states.append(state)

    async def transcript(self, speaker, text, utterance_id, is_final):
        self.transcripts.append((speaker, text, is_final))

    async def extracted(self, result):
        self.results.append(result)


class FakeTelephony:
    def __init__(self):
        self.hung_up = []

    async def place_call(self, *, call_id, to):
        return "CA123"

    async def hangup(self, call_sid):
        self.hung_up.append(call_sid)


def build_bridge(**kw):
    registry, stt, tts, tel = LiveCallRegistry(), FakeSTT(), FakeTTS(), FakeTelephony()
    intent = heuristic_intent("Find a pharmacy that has children's amoxicillin", 10, None)
    ctx = BrainContext(intent=intent, target=Target(id="t1", name="Corner Pharmacy", lat=0, lng=0, distance_miles=1))
    rec = Recorder()
    session = CallSession(ctx, ScriptedBrain(ctx), rec)
    live = LiveCallContext(call_id="c1", swarm_id="s1", session=session, reporter=rec,
                           future=asyncio.get_running_loop().create_future(), token="tok")
    live.call_sid = None
    registry.register(live)
    kw.setdefault("greet_wait_s", 0.05)   # these tests are not about the wait for "hello": a silent line is opened quickly
    bridge = TwilioMediaBridge(registry, lambda: stt, tts, tel, drain_timeout_s=0.2, poll_s=0.05, **kw)
    ws = FakeWS()
    ws.push({"event": "connected"})
    ws.push({"event": "start", "streamSid": "MZ1", "start": {
        "streamSid": "MZ1", "callSid": "CA123", "customParameters": {"call_id": "c1", "token": "tok"}}})
    return bridge, ws, stt, tts, tel, live, rec


async def wait_for(predicate, timeout=3.0):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while not predicate():
        assert loop.time() < end, "timed out waiting for condition"
        await asyncio.sleep(0.01)


async def test_bridge_full_conversation_extracts_data_and_hangs_up():
    bridge, ws, stt, tts, tel, live, rec = build_bridge()
    task = asyncio.create_task(bridge.run(ws))

    await wait_for(lambda: tts.spoken)                      # canned opening is spoken immediately
    assert "AI assistant" in tts.spoken[0]
    ws.push({"event": "media", "media": {"payload": base64.b64encode(b"\xff" * 160).decode()}})
    await wait_for(lambda: stt.audio_chunks == 1)           # caller audio reaches STT
    assert "talking" in rec.states

    stt.say("Yeah, hang on, let me check the shelf.")
    await wait_for(lambda: len(tts.spoken) == 2)            # agent waits politely
    stt.say("Okay yeah, we do have it. We've got 4 left.")
    await wait_for(lambda: len(tts.spoken) == 4 and "price" in tts.spoken[3].lower())
    stt.say("It's $14, and yes, we can hold one for you.")  # -> structured extraction fires
    await wait_for(lambda: len(rec.results) == 1)

    outcome = await asyncio.wait_for(live.future, 3)
    await asyncio.wait_for(task, 3)
    assert outcome.state == "completed"
    r = outcome.result
    assert (r.available, r.price, r.quantity, r.can_hold) == ("yes", 14.0, 4, True)
    assert "extracting" in rec.states
    assert any(m["event"] == "media" for m in ws.sent) and "mark" in ws.kinds()
    assert tts.spoken[-1].lower().startswith(("perfect", "great", "okay"))   # closing line was spoken
    assert tel.hung_up == ["CA123"] and stt.closed and ws.closed
    assert any(t[0] == "business" and t[2] is False for t in rec.transcripts)  # partials streamed for the UI


async def test_bridge_barge_in_clears_audio_and_cancels_turn():
    bridge, ws, stt, tts, tel, live, rec = build_bridge()
    task = asyncio.create_task(bridge.run(ws))
    await wait_for(lambda: tts.spoken)                      # opening queued in Twilio's buffer (not yet "played")
    assert "clear" not in ws.kinds()
    await asyncio.sleep(1.0)                                # the opening line (with the AI disclosure) is protected
    stt.emit(SttEvent("interim", "wait, say that again"))    # ...so talking over it does not cut it off
    await asyncio.sleep(0.1)
    assert "clear" not in ws.kinds()
    await asyncio.sleep(1.0)                                # after it has played, barge-in works again
    stt.emit(SttEvent("speech_started"))                    # noise / breathing alone must NOT cut the agent off
    stt.emit(SttEvent("interim", "um"))                     # neither does a filler word
    await asyncio.sleep(0.2)
    assert "clear" not in ws.kinds()
    stt.emit(SttEvent("interim", "wait, say that again"))   # real words from the business do
    await wait_for(lambda: "clear" in ws.kinds())
    assert next(m for m in ws.sent if m["event"] == "clear")["streamSid"] == "MZ1"
    ws.push({"event": "stop"})
    await asyncio.wait_for(task, 3)
    assert live.future.done() and live.future.result().state == "failed"


async def test_bridge_business_hangs_up_mid_call():
    bridge, ws, stt, tts, tel, live, rec = build_bridge()
    task = asyncio.create_task(bridge.run(ws))
    await wait_for(lambda: tts.spoken)
    ws.push({"event": "stop"})
    await asyncio.wait_for(task, 3)
    outcome = live.future.result()
    assert outcome.state == "failed" and "hung up" in outcome.reason.lower()
    assert tel.hung_up == []        # nothing to hang up: they already did


async def test_bridge_silence_watchdog_ends_the_call():
    bridge, ws, stt, tts, tel, live, rec = build_bridge(idle_timeout_s=0.3)
    task = asyncio.create_task(bridge.run(ws))
    await wait_for(lambda: tts.spoken)
    ws.pending = None
    # simulate Twilio playing the opening so the agent is not considered "speaking"
    for _ in range(50):
        mark = next((m for m in ws.sent if m["event"] == "mark"), None)
        if mark:
            ws.push({"event": "mark", "mark": mark["mark"]})
            break
        await asyncio.sleep(0.01)
    await asyncio.wait_for(task, 5)
    outcome = live.future.result()
    assert outcome.state == "failed" and "nobody" in outcome.reason.lower()
    assert tel.hung_up == ["CA123"]


async def test_bridge_is_patient_while_on_hold_but_not_otherwise():
    bridge, ws, stt, tts, tel, live, rec = build_bridge(idle_timeout_s=0.3, hold_timeout_s=30.0)
    task = asyncio.create_task(bridge.run(ws))
    await wait_for(lambda: tts.spoken)
    live.session.holding = True                  # the agent is waiting out a transfer / hold music
    for _ in range(50):
        mark = next((m for m in ws.sent if m["event"] == "mark"), None)
        if mark:
            ws.push({"event": "mark", "mark": mark["mark"]})
            break
        await asyncio.sleep(0.01)
    await asyncio.sleep(1.0)                     # well past the normal 0.3 s silence limit
    assert not task.done() and not live.future.done()
    live.session.holding = False                 # back to normal: the silence limit applies again
    await asyncio.wait_for(task, 5)
    assert live.future.result().state == "failed"


async def test_two_simultaneous_calls_through_one_bridge_do_not_affect_each_other():
    """You and a teammate are called in the same swarm. One answering/finishing must not touch the other."""
    registry, tts, tel = LiveCallRegistry(), FakeTTS(), FakeTelephony()
    stts = {"c1": FakeSTT(), "c2": FakeSTT()}
    order = iter(["c1", "c2"])
    bridge = TwilioMediaBridge(registry, lambda: stts[next(order)], tts, tel, drain_timeout_s=0.2, poll_s=0.05, idle_timeout_s=30, greet_wait_s=0.05)

    def make(call_id, name):
        intent = heuristic_intent("Find a pharmacy that has children's amoxicillin", 10, None)
        ctx = BrainContext(intent=intent, target=Target(id=call_id, name=name, lat=0, lng=0, distance_miles=1))
        rec = Recorder()
        live = LiveCallContext(call_id=call_id, swarm_id="s1", session=CallSession(ctx, ScriptedBrain(ctx), rec), reporter=rec,
                               future=asyncio.get_running_loop().create_future(), token=f"tok-{call_id}")
        registry.register(live)
        ws = FakeWS()
        ws.push({"event": "start", "streamSid": f"MZ-{call_id}", "start": {
            "streamSid": f"MZ-{call_id}", "callSid": f"CA-{call_id}", "customParameters": {"call_id": call_id, "token": f"tok-{call_id}"}}})
        return live, ws, rec

    live1, ws1, rec1 = make("c1", "Saamarth")
    live2, ws2, rec2 = make("c2", "Jaswant")
    t1 = asyncio.create_task(bridge.run(ws1))
    await wait_for(lambda: "media" in ws1.kinds())            # call 1 is answered and the agent has spoken
    t2 = asyncio.create_task(bridge.run(ws2))
    await wait_for(lambda: "media" in ws2.kinds())            # call 2 is answered while call 1 is still open

    # call 2's business gives a full answer and the agent finishes that call
    stts["c2"].emit(SttEvent("final", "Yes we have it, it's $12 and we can hold one.", speech_final=True))
    await asyncio.wait_for(t2, 5)
    assert live2.future.done() and live2.future.result().state == "completed"

    # call 1 must be completely unaffected: still open, nothing said to it, nothing hung up
    await asyncio.sleep(0.3)
    assert not t1.done() and not live1.future.done()
    assert tel.hung_up == ["CA-c2"] and not ws1.closed
    assert [t for t in rec1.transcripts if t[0] == "business"] == []

    # and it still works normally afterwards
    stts["c1"].emit(SttEvent("final", "No, we are out of that.", speech_final=True))
    await asyncio.wait_for(t1, 5)
    assert live1.future.result().result.available == "no"


async def test_bridge_plays_keypad_tones_when_the_agent_presses_a_menu_key():
    from app.agent.types import BrainEvent, ToolCall
    from app.telephony.dtmf import dtmf_mulaw

    class MenuBrain:
        async def respond(self, messages):
            yield BrainEvent(kind="tool_call", tool_call=ToolCall(id="k1", name="press_keys", arguments={"digits": "3"}))

    bridge, ws, stt, tts, tel, live, rec = build_bridge()
    live.session.brain = MenuBrain()
    task = asyncio.create_task(bridge.run(ws))
    await wait_for(lambda: tts.spoken)
    stt.say("To speak with a member of the pharmacy staff, press 3.")

    tones = dtmf_mulaw("3")
    expected = [base64.b64encode(tones[i:i + 640]).decode() for i in range(0, len(tones), 640)]
    await wait_for(lambda: [m["media"]["payload"] for m in ws.sent if m["event"] == "media"][-len(expected):] == expected)
    assert not live.session.finished and live.session.holding and live.session.pending_keys == ""

    ws.push(None)
    await asyncio.wait_for(task, 3)


async def test_listeners_hear_both_sides_and_are_told_when_the_call_ends():
    from app.telephony.audio_tap import AudioTap

    tap = AudioTap()
    bridge, ws, stt, tts, tel, live, rec = build_bridge(tap=tap)
    queue = tap.subscribe("c1")
    task = asyncio.create_task(bridge.run(ws))
    await wait_for(lambda: tts.spoken)
    ws.push({"event": "media", "media": {"payload": base64.b64encode(b"\x7f" * 160).decode()}})
    seen: list[dict] = []

    def collect() -> bool:
        while not queue.empty():
            seen.append(json.loads(queue.get_nowait()))
        return {m.get("src") for m in seen} >= {"agent", "business"}

    await wait_for(collect)
    sources = {m["src"] for m in seen if m["t"] == "audio"}
    assert sources == {"agent", "business"}                      # the opening line and the caller's audio
    assert base64.b64decode(next(m["d"] for m in seen if m.get("src") == "business")) == b"\x7f" * 160

    stt.say("Hang on, let me check, we do have it.")             # real words while the agent is still talking
    ws.push(None)
    await asyncio.wait_for(task, 3)
    tail = [json.loads(queue.get_nowait()) for _ in range(queue.qsize())]
    assert tail[-1] == {"t": "end"}                              # listeners are told the call is over


def test_audio_tap_costs_nothing_without_listeners_and_drops_old_audio_when_slow():
    from app.telephony.audio_tap import AudioTap

    tap = AudioTap(max_queue=3)
    tap.audio("c1", "agent", b"\xff" * 10)                       # nobody listening: nothing is queued or kept
    assert not tap.has_listeners("c1")
    q = tap.subscribe("c1")
    for i in range(5):
        tap.audio("c1", "business", bytes([i]) * 4)
    assert q.qsize() == 3
    first = json.loads(q.get_nowait())
    assert base64.b64decode(first["d"]) == bytes([2]) * 4        # the two oldest frames were dropped
    tap.unsubscribe("c1", q)
    assert not tap.has_listeners("c1")



async def test_the_agent_waits_for_hello_and_then_says_why_it_is_calling():
    """We are the ones calling: the business picks up and speaks first, and the agent answers that."""
    bridge, ws, stt, tts, tel, live, rec = build_bridge(greet_wait_s=5.0)
    task = asyncio.create_task(bridge.run(ws))
    await wait_for(lambda: "talking" in rec.states)
    await asyncio.sleep(0.4)
    assert tts.spoken == []                                   # nothing said into the silence of an answered line
    stt.say("Hello, Corner Pharmacy, how can I help you?")
    await wait_for(lambda: tts.spoken)
    assert "amoxicillin" in tts.spoken[0] and tts.spoken[0].rstrip().endswith("on behalf of a customer.")
    assert [t for t in rec.transcripts if t[0] == "business" and t[2]][0][1].startswith("Hello")
    ws.push(None)
    await asyncio.wait_for(task, 3)


async def test_a_silent_line_gets_the_opening_line_after_a_short_wait():
    bridge, ws, stt, tts, tel, live, rec = build_bridge(greet_wait_s=0.3)
    task = asyncio.create_task(bridge.run(ws))
    await asyncio.sleep(0.15)
    assert tts.spoken == []
    await wait_for(lambda: tts.spoken)
    assert "AI assistant" in tts.spoken[0]
    ws.push(None)
    await asyncio.wait_for(task, 3)


async def test_a_recording_is_listened_to_and_the_opening_waits_for_a_person():
    bridge, ws, stt, tts, tel, live, rec = build_bridge(greet_wait_s=5.0)
    task = asyncio.create_task(bridge.run(ws))
    await wait_for(lambda: "talking" in rec.states)
    stt.say("Thank you for calling Corner Pharmacy. Your call may be recorded.")   # a recording: nothing to answer
    await asyncio.sleep(0.4)
    assert tts.spoken == [] and live.session.holding
    stt.say("Pharmacy, this is Dana.")                                             # a person comes on
    await wait_for(lambda: tts.spoken)
    assert "AI assistant" in tts.spoken[0]
    ws.push(None)
    await asyncio.wait_for(task, 3)