"""Twilio Media Streams bridge: pipes a live phone call through STT -> LLM -> TTS with barge-in.

    Twilio  --(mu-law frames, base64 JSON over WebSocket)-->  bridge  --> Deepgram STT
    Deepgram STT --(final transcript)--> CallSession.respond() --(sentences as the LLM streams)--> Deepgram TTS
    Deepgram TTS --(mu-law)--> bridge --(media + mark events)--> Twilio

Latency tricks: the opening line is canned (no LLM round trip), sentences are synthesised and sent as soon as
the LLM emits them (not after the full reply), and Twilio's own playback buffer lets us pipeline the next
sentence while the previous one is still playing. When the business starts talking over the agent we
send Twilio a `clear` event, which flushes buffered audio instantly, and cancel the in-flight turn.

Author: Saamarth Attray
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import hmac
import json
import logging
import time
from typing import Callable

from .audio_tap import AudioTap
from .dtmf import dtmf_mulaw
from .speech import SpeechToText, SttEvent, TextToSpeech
from .twilio_client import LiveCallContext, LiveCallRegistry, Telephony

log = logging.getLogger("swarmdial.bridge")

CHUNK_BYTES = 640  # 80 ms of 8 kHz mu-law
_FILLERS = {"uh", "um", "hm", "hmm", "mm", "mhm", "mmm", "ah", "oh", "eh", "huh"}


def _is_real_speech(text: str) -> bool:
    """False for line-noise transcripts like "uh" or "mm", which must not cut the agent off mid-sentence."""
    letters = [w.strip(".,!?").lower() for w in text.split()]
    return any(len(w) >= 2 and w not in _FILLERS for w in letters)


class _State:
    def __init__(self) -> None:
        self.stream_sid: str = ""
        self.call_id: str = ""
        self.speaking = False
        self.pending_marks: set[str] = set()
        self.protected_until = 0.0  # keypad tones must not be cut off by the menu talking over them
        self.mark_n = 0
        self.heard_first = asyncio.Event()  # someone has said something real on the line
        self.pending_text: list[str] = []
        self.utterance_id: str | None = None
        self.turn_task: asyncio.Task | None = None
        self.hung_up = False
        self.started = time.monotonic()
        self.last_activity = time.monotonic()
        self.done = asyncio.Event()

    def touch(self) -> None:
        self.last_activity = time.monotonic()


class TwilioMediaBridge:
    def __init__(
        self,
        registry: LiveCallRegistry,
        stt_factory: Callable[[], SpeechToText],
        tts: TextToSpeech,
        telephony: Telephony,
        *,
        greet_wait_s: float = 3.5,
        idle_timeout_s: float = 25.0,
        hold_timeout_s: float = 240.0,
        max_call_s: float = 420.0,
        drain_timeout_s: float = 8.0,
        poll_s: float = 0.5,
        tap: AudioTap | None = None,
    ):
        self.registry = registry
        self.stt_factory = stt_factory
        self.tts = tts
        self.telephony = telephony
        self.greet_wait_s = greet_wait_s
        self.idle_timeout_s = idle_timeout_s
        self.hold_timeout_s = hold_timeout_s
        self.max_call_s = max_call_s
        self.drain_timeout_s = drain_timeout_s
        self.poll_s = poll_s
        self.tap = tap or AudioTap()  # copies audio to dashboard listeners; costs nothing when nobody listens

    # ===================================================================== entry point
    async def run(self, ws) -> None:
        """`ws` needs receive_text(), send_text(str) and close(); FastAPI's WebSocket qualifies."""
        start = await self._wait_for_start(ws)
        ctx = self._authorize(start)
        if ctx is None:
            with contextlib.suppress(Exception):
                await ws.close()
            return

        state = _State()
        state.stream_sid = start["streamSid"]
        state.call_id = ctx.call_id
        ctx.stream_sid = state.stream_sid
        ctx.call_sid = ctx.call_sid or start.get("callSid")
        session = ctx.session

        stt = self.stt_factory()
        tasks: list[asyncio.Task] = []
        try:
            await ctx.reporter.state("talking")
            await stt.connect()
            tasks = [
                asyncio.create_task(self._twilio_reader(ws, stt, state), name="twilio-reader"),
                asyncio.create_task(self._stt_consumer(ws, stt, state, ctx), name="stt-consumer"),
                asyncio.create_task(self._watchdog(state, ctx), name="watchdog"),
            ]
            # We are the one calling, so we let them say hello first and answer that (see CallSession.respond). If the
            # line stays silent, say why we are calling after a few seconds.
            try:
                await asyncio.wait_for(state.heard_first.wait(), self.greet_wait_s)
            except asyncio.TimeoutError:
                if not session.opened and not session.finished:
                    length = await self._speak(ws, state, await session.open())
                    # The opening line ends with the AI disclosure: do not let the first words from the business cut it off.
                    state.protected_until = time.monotonic() + length / 8000 + 0.3
                    session.just_opened = False
            await state.done.wait()
        except Exception:
            log.exception("media bridge failed for %s", ctx.call_id)
            session.force_end("error")
            state.done.set()
        finally:
            for task in tasks:
                task.cancel()
            if state.turn_task and not state.turn_task.done():
                state.turn_task.cancel()
            for task in [*tasks, *([state.turn_task] if state.turn_task else [])]:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
            with contextlib.suppress(Exception):
                await session.abort_turn()
            with contextlib.suppress(Exception):
                await stt.close()

            if not session.finished:
                session.force_end("business_hung_up" if state.hung_up else "no_response")
            outcome = session.outcome()
            log.info(
                "[%s %s] call finished: %s (%s), business hung up first: %s, seconds: %.0f",
                ctx.call_id, session.ctx.target.name, outcome.state, outcome.reason or session.end_reason or "ok",
                state.hung_up, time.monotonic() - state.started,
            )
            self.tap.end(ctx.call_id)
            ctx.resolve(outcome)
            if ctx.call_sid and not state.hung_up:
                with contextlib.suppress(Exception):
                    await self.telephony.hangup(ctx.call_sid)
            with contextlib.suppress(Exception):
                await ws.close()

    # ===================================================================== handshake
    async def _wait_for_start(self, ws) -> dict | None:
        try:
            for _ in range(10):
                message = json.loads(await ws.receive_text())
                if message.get("event") == "start":
                    start = message["start"]
                    start.setdefault("streamSid", message.get("streamSid", ""))
                    return start
        except Exception:
            return None
        return None

    def _authorize(self, start: dict | None) -> LiveCallContext | None:
        if not start:
            return None
        params = start.get("customParameters") or {}
        ctx = self.registry.get(params.get("call_id", ""))
        if ctx is None or not hmac.compare_digest(ctx.token, params.get("token", "")):
            log.warning("rejected media stream with bad call id / token")
            return None
        return ctx

    # ===================================================================== inbound audio
    async def _twilio_reader(self, ws, stt: SpeechToText, state: _State) -> None:
        try:
            while True:
                message = json.loads(await ws.receive_text())
                event = message.get("event")
                if event == "media":
                    raw = base64.b64decode(message["media"]["payload"])
                    self.tap.audio(state.call_id, "business", raw)
                    await stt.send_audio(raw)
                elif event == "mark":
                    state.pending_marks.discard(message.get("mark", {}).get("name", ""))
                    if not state.pending_marks:
                        state.speaking = False
                elif event == "stop":
                    break
        except asyncio.CancelledError:
            raise  # we are shutting down ourselves: that is not the business hanging up
        except Exception:
            pass  # socket closed
        state.hung_up = True
        state.done.set()

    # ===================================================================== what the business says
    async def _stt_consumer(self, ws, stt: SpeechToText, state: _State, ctx: LiveCallContext) -> None:
        session = ctx.session
        async for event in stt.events():
            if event.kind == "speech_started":
                # Voice-activity alone also fires on line noise and breathing, so it never interrupts the agent;
                # only recognised words do (below).
                state.touch()
            elif event.kind in ("interim", "final"):
                if event.text:
                    state.touch()
                    if _is_real_speech(event.text):
                        state.heard_first.set()
                    if state.speaking and time.monotonic() >= state.protected_until and _is_real_speech(event.text):
                        await self._barge_in(ws, state, ctx)
                    if state.utterance_id is None:
                        state.utterance_id = session.new_utterance_id()
                    shown = " ".join([*state.pending_text, event.text]) if event.kind == "interim" else None
                    if event.kind == "final":
                        state.pending_text.append(event.text)
                        shown = " ".join(state.pending_text)
                    await session.business_partial(shown or event.text, state.utterance_id)
                if event.kind == "final" and event.speech_final:
                    await self._flush(ws, state, ctx)
            elif event.kind == "utterance_end":
                await self._flush(ws, state, ctx)

    async def _flush(self, ws, state: _State, ctx: LiveCallContext) -> None:
        if not state.pending_text or ctx.session.finished:
            return
        text = " ".join(state.pending_text)
        utterance_id = state.utterance_id
        state.pending_text, state.utterance_id = [], None
        log.info("[%s %s] business said: %r", ctx.call_id, ctx.session.ctx.target.name, text)
        if state.turn_task and not state.turn_task.done():
            state.turn_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await state.turn_task
            await ctx.session.abort_turn()
        state.turn_task = asyncio.create_task(self._take_turn(ws, state, ctx, text, utterance_id), name="agent-turn")

    async def _barge_in(self, ws, state: _State, ctx: LiveCallContext) -> None:
        """The business started talking while we were: stop playback immediately and drop the rest of our turn."""
        log.info("[%s %s] barge-in: business spoke over the agent", ctx.call_id, ctx.session.ctx.target.name)
        state.speaking = False
        state.pending_marks.clear()
        self.tap.clear(state.call_id)
        with contextlib.suppress(Exception):
            await ws.send_text(json.dumps({"event": "clear", "streamSid": state.stream_sid}))
        task = state.turn_task
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
            await ctx.session.abort_turn()

    # ===================================================================== what the agent says
    async def _take_turn(self, ws, state: _State, ctx: LiveCallContext, text: str, utterance_id: str | None) -> None:
        session = ctx.session
        agen = session.respond(text, utterance_id)
        sent = 0
        try:
            async for sentence in agen:
                sent += await self._speak(ws, state, sentence)
            if session.just_opened:  # we just said why we are calling, disclosure included: do not let them cut it off
                session.just_opened = False
                state.protected_until = time.monotonic() + sent / 8000 + 0.3
            if session.pending_keys:
                keys, session.pending_keys = session.pending_keys, ""
                log.info("[%s %s] pressing keypad: %s", ctx.call_id, session.ctx.target.name, keys)
                tones = dtmf_mulaw(keys)
                state.protected_until = time.monotonic() + len(tones) / 8000 + 0.6
                await self._play(ws, state, tones)
            if session.finished:
                await self._drain(state)
                state.done.set()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("agent turn failed")
            session.force_end("error")
            state.done.set()
        finally:
            with contextlib.suppress(Exception):
                await agen.aclose()

    async def _speak(self, ws, state: _State, text: str) -> int:
        return await self._play(ws, state, await self.tts.synthesize(text))

    async def _play(self, ws, state: _State, audio: bytes) -> int:
        """Send audio to the call; returns how many bytes (1 byte = 1/8000 s) were sent."""
        if not audio:
            return 0
        state.touch()
        state.speaking = True
        for offset in range(0, len(audio), CHUNK_BYTES):
            frame = audio[offset : offset + CHUNK_BYTES]
            self.tap.audio(state.call_id, "agent", frame)
            payload = base64.b64encode(frame).decode()
            await ws.send_text(json.dumps({"event": "media", "streamSid": state.stream_sid, "media": {"payload": payload}}))
        state.mark_n += 1
        name = f"m{state.mark_n}"
        state.pending_marks.add(name)
        await ws.send_text(json.dumps({"event": "mark", "streamSid": state.stream_sid, "mark": {"name": name}}))
        return len(audio)

    async def _drain(self, state: _State) -> None:
        """Wait for Twilio to finish playing buffered audio so the goodbye is not cut off by the hang-up."""
        deadline = time.monotonic() + self.drain_timeout_s
        while state.pending_marks and time.monotonic() < deadline and not state.hung_up:
            await asyncio.sleep(0.05)

    # ===================================================================== silence / runaway protection
    async def _watchdog(self, state: _State, ctx: LiveCallContext) -> None:
        while not state.done.is_set():
            await asyncio.sleep(self.poll_s)
            now = time.monotonic()
            turn_running = bool(state.turn_task and not state.turn_task.done())
            if now - state.started > self.max_call_s:
                ctx.session.force_end("no_response")
                state.done.set()
            elif not state.speaking and not turn_running and now - state.last_activity > (
                self.hold_timeout_s if ctx.session.holding else self.idle_timeout_s  # patient while on hold / transferring
            ):
                ctx.session.force_end("no_response")
                state.done.set()