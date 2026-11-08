"""Speech services for the live phone bridge: streaming STT and TTS over Deepgram (mu-law 8 kHz end to
end, which is exactly what Twilio Media Streams speaks, so no transcoding is needed anywhere).

Also contains fake implementations used by the tests.

Author: Saamarth Attray
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import AsyncIterator, Protocol
from urllib.parse import urlencode

import httpx

log = logging.getLogger("swarmdial.speech")


@dataclass
class SttEvent:
    kind: str  # speech_started | interim | final | utterance_end
    text: str = ""
    speech_final: bool = False


class SpeechToText(Protocol):
    async def connect(self) -> None: ...

    async def send_audio(self, chunk: bytes) -> None: ...

    def events(self) -> AsyncIterator[SttEvent]: ...

    async def close(self) -> None: ...


class TextToSpeech(Protocol):
    async def synthesize(self, text: str) -> bytes:
        """Return raw mu-law, 8 kHz, mono audio (no container)."""
        ...


class DeepgramSTT:
    URL = "wss://api.deepgram.com/v1/listen"

    def __init__(self, api_key: str, model: str = "nova-2-phonecall"):
        self.api_key = api_key
        self.model = model
        self._ws = None
        self._reader: asyncio.Task | None = None
        self._queue: asyncio.Queue[SttEvent | None] = asyncio.Queue()

    async def connect(self) -> None:
        from websockets.asyncio.client import connect

        params = {
            "model": self.model,
            "encoding": "mulaw",
            "sample_rate": 8000,
            "channels": 1,
            "interim_results": "true",
            "endpointing": 300,
            "utterance_end_ms": 1000,
            "vad_events": "true",
            "smart_format": "true",
            "punctuate": "true",
        }
        self._ws = await connect(
            f"{self.URL}?{urlencode(params)}",
            additional_headers={"Authorization": f"Token {self.api_key}"},
            open_timeout=8,
            max_size=None,
        )
        self._reader = asyncio.create_task(self._read(), name="deepgram-stt-reader")

    async def _read(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                if isinstance(raw, bytes):
                    continue
                msg = json.loads(raw)
                kind = msg.get("type")
                if kind == "Results":
                    alternatives = (msg.get("channel") or {}).get("alternatives") or [{}]
                    text = (alternatives[0].get("transcript") or "").strip()
                    speech_final = bool(msg.get("speech_final"))
                    if not text and not speech_final:
                        continue
                    await self._queue.put(
                        SttEvent("final" if msg.get("is_final") else "interim", text, speech_final=speech_final)
                    )
                elif kind == "SpeechStarted":
                    await self._queue.put(SttEvent("speech_started"))
                elif kind == "UtteranceEnd":
                    await self._queue.put(SttEvent("utterance_end"))
        except Exception as exc:  # connection dropped
            log.info("deepgram stt reader ended: %s", exc)
        finally:
            await self._queue.put(None)

    async def send_audio(self, chunk: bytes) -> None:
        if self._ws is not None:
            await self._ws.send(chunk)

    async def events(self) -> AsyncIterator[SttEvent]:
        while True:
            event = await self._queue.get()
            if event is None:
                return
            yield event

    async def close(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.send(json.dumps({"type": "CloseStream"}))
                await self._ws.close()
            except Exception:
                pass
        if self._reader is not None:
            self._reader.cancel()
            try:
                await self._reader
            except (asyncio.CancelledError, Exception):
                pass


class DeepgramTTS:
    URL = "https://api.deepgram.com/v1/speak"

    def __init__(self, api_key: str, voice: str = "aura-asteria-en", http: httpx.AsyncClient | None = None):
        self.api_key = api_key
        self.voice = voice
        self._http = http or httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=4.0))

    async def synthesize(self, text: str) -> bytes:
        resp = await self._http.post(
            self.URL,
            params={"model": self.voice, "encoding": "mulaw", "sample_rate": 8000, "container": "none"},
            headers={"Authorization": f"Token {self.api_key}", "Content-Type": "application/json"},
            json={"text": text},
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Deepgram TTS error {resp.status_code}: {resp.text[:200]}")
        return resp.content


# ----------------------------------------------------------------------------- test doubles
class FakeSTT:
    """Scripted speech-to-text: tests push events with `emit(...)`."""

    def __init__(self) -> None:
        self.audio_chunks = 0
        self.connected = False
        self.closed = False
        self._queue: asyncio.Queue[SttEvent | None] = asyncio.Queue()

    async def connect(self) -> None:
        self.connected = True

    async def send_audio(self, chunk: bytes) -> None:
        self.audio_chunks += 1

    def emit(self, event: SttEvent) -> None:
        self._queue.put_nowait(event)

    def say(self, text: str) -> None:
        """A business utterance, as the final transcript Deepgram would produce."""
        self.emit(SttEvent("speech_started"))
        self.emit(SttEvent("final", text, speech_final=True))

    async def events(self) -> AsyncIterator[SttEvent]:
        while True:
            event = await self._queue.get()
            if event is None:
                return
            yield event

    async def close(self) -> None:
        self.closed = True
        self._queue.put_nowait(None)


class FakeTTS:
    def __init__(self, bytes_per_char: int = 40) -> None:
        self.bytes_per_char = bytes_per_char
        self.spoken: list[str] = []

    async def synthesize(self, text: str) -> bytes:
        self.spoken.append(text)
        return b"\x7f" * (len(text) * self.bytes_per_char)
