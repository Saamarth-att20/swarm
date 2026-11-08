"""Event bus: ordered per-swarm event log + live fan-out.

Redis pub/sub topology
----------------------
    channel  swarm:{swarm_id}      one JSON wire-event per message
    publish  the process running the Swarm Commander for that swarm (single writer, so `seq`
             is strictly increasing with no coordination)
    listen   every API process psubscribes to `swarm:*` and hands events to its local
             WebSocket subscribers; late joiners / reconnects replay from the `swarm_events` table

Without REDIS_URL the same interface works in-process, which is all a hackathon demo needs.

Author: Saamarth Attray
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from pydantic import BaseModel

from .contract import EVENT_ADAPTER, make_event
from .repo import Repo

log = logging.getLogger("swarmdial.events")


class Subscription:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[dict] = asyncio.Queue()


class EventBus:
    def __init__(self, repo: Repo, redis_url: str | None = None, redis_client: Any | None = None):
        self.repo = repo
        self.redis_url = redis_url
        self._redis = redis_client
        self._pubsub: Any | None = None
        self._listener: asyncio.Task | None = None
        self._subs: dict[str, set[Subscription]] = {}
        self._logs: dict[str, list[dict]] = {}
        self._seq: dict[str, int] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._load_locks: dict[str, asyncio.Lock] = {}

    # ----------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        if self._redis is None and self.redis_url:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(self.redis_url, decode_responses=True)
        if self._redis is not None:
            self._pubsub = self._redis.pubsub()
            await self._pubsub.psubscribe("swarm:*")
            self._listener = asyncio.create_task(self._listen(), name="redis-listener")
            log.info("event bus using Redis pub/sub")

    async def stop(self) -> None:
        if self._listener:
            self._listener.cancel()
            try:
                await self._listener
            except (asyncio.CancelledError, Exception):
                pass
        if self._pubsub is not None:
            try:
                await self._pubsub.aclose()
            except Exception:
                pass
        if self._redis is not None and self.redis_url:
            try:
                await self._redis.aclose()
            except Exception:
                pass

    # ----------------------------------------------------------------- publish
    async def publish(self, swarm_id: str, data: BaseModel, *, persist: bool = True) -> dict:
        """Assign the next seq, validate against the contract, log, persist and fan out.

        `persist=False` is for high-volume ephemeral events (partial transcripts): they still stream live
        and stay in the in-memory log for reconnects, but skip the database.
        """
        lock = self._locks.setdefault(swarm_id, asyncio.Lock())
        async with lock:
            await self._ensure_loaded(swarm_id)
            seq = self._seq[swarm_id] + 1
            self._seq[swarm_id] = seq
            event = make_event(swarm_id, seq, data)  # type: ignore[arg-type]
            EVENT_ADAPTER.validate_python(event)  # contract guard: never emit something the UI can't parse
            self._logs[swarm_id].append(event)
            if persist:
                try:
                    await self.repo.append_event(event)
                except Exception:  # persistence must never kill a live call
                    log.exception("failed to persist event %s/%s", swarm_id, seq)
            await self._fanout(swarm_id, event)
        return event

    async def _fanout(self, swarm_id: str, event: dict) -> None:
        if self._redis is not None:
            try:
                await self._redis.publish(f"swarm:{swarm_id}", json.dumps(event))
                return
            except Exception:
                log.exception("redis publish failed; falling back to local fan-out")
        self._dispatch_local(swarm_id, event)

    def _dispatch_local(self, swarm_id: str, event: dict) -> None:
        for sub in list(self._subs.get(swarm_id, ())):
            sub.queue.put_nowait(event)

    async def _listen(self) -> None:
        assert self._pubsub is not None
        async for message in self._pubsub.listen():
            if message.get("type") != "pmessage":
                continue
            try:
                channel = message["channel"]
                swarm_id = channel.split(":", 1)[1]
                self._dispatch_local(swarm_id, json.loads(message["data"]))
            except Exception:
                log.exception("bad redis message")

    # ----------------------------------------------------------------- subscribe / replay
    @asynccontextmanager
    async def subscribe(self, swarm_id: str) -> AsyncIterator[Subscription]:
        sub = Subscription()
        self._subs.setdefault(swarm_id, set()).add(sub)
        try:
            yield sub
        finally:
            self._subs.get(swarm_id, set()).discard(sub)

    async def backlog(self, swarm_id: str, after: int = 0) -> list[dict]:
        await self._ensure_loaded(swarm_id)
        return [e for e in self._logs[swarm_id] if e["seq"] > after]

    async def last_seq(self, swarm_id: str) -> int:
        await self._ensure_loaded(swarm_id)
        return self._seq[swarm_id]

    async def _ensure_loaded(self, swarm_id: str) -> None:
        if swarm_id in self._logs:
            return
        async with self._load_locks.setdefault(swarm_id, asyncio.Lock()):
            if swarm_id in self._logs:  # another coroutine finished loading while we waited
                return
            events = await self.repo.list_events(swarm_id, 0)
            self._seq[swarm_id] = events[-1]["seq"] if events else 0
            self._logs[swarm_id] = events
