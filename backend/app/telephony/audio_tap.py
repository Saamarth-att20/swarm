"""Live audio tap: lets the dashboard listen in on a call while it happens.

The media bridge already holds both sides of every call (the business's audio coming in from Twilio and the agent's
audio going out). When someone is listening, it copies each 8 kHz mu-law frame here, and a WebSocket route fans the
frames out to the browser. Nothing is stored: audio is only copied while a listener is connected, and each listener
has a small queue that drops the oldest frames if the browser falls behind.

Messages (JSON text):
    {"t": "audio", "src": "business" | "agent", "d": "<base64 mu-law>"}
    {"t": "clear"}   # the agent was interrupted: drop any agent audio that has not played yet
    {"t": "end"}     # the call is over

Author: Saamarth Attray
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import json
from collections import defaultdict


class AudioTap:
    def __init__(self, max_queue: int = 600) -> None:
        self._listeners: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._max_queue = max_queue

    def subscribe(self, call_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue)
        self._listeners[call_id].add(queue)
        return queue

    def unsubscribe(self, call_id: str, queue: asyncio.Queue) -> None:
        self._listeners[call_id].discard(queue)
        if not self._listeners[call_id]:
            self._listeners.pop(call_id, None)

    def has_listeners(self, call_id: str) -> bool:
        return bool(self._listeners.get(call_id))

    def _put(self, call_id: str, message: dict) -> None:
        text = json.dumps(message)
        for queue in list(self._listeners.get(call_id, ())):
            if queue.full():  # a slow browser loses the oldest audio rather than growing memory
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(text)

    def audio(self, call_id: str, src: str, mulaw: bytes) -> None:
        if self.has_listeners(call_id) and mulaw:
            self._put(call_id, {"t": "audio", "src": src, "d": base64.b64encode(mulaw).decode()})

    def clear(self, call_id: str) -> None:
        if self.has_listeners(call_id):
            self._put(call_id, {"t": "clear"})

    def end(self, call_id: str) -> None:
        if self.has_listeners(call_id):
            self._put(call_id, {"t": "end"})