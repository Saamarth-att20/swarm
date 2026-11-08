"""Thin persistence layer. All writes go through one lock so SQLite never sees concurrent writers.

Author: Saamarth Attray
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from sqlalchemy import func, select, update

from .contract import ExtractedResult, Intent, Target
from .db import Call, Database, ExtractedData, Swarm, SwarmEventRow, Task, User
from .ids import new_id

TERMINAL_CALL_STATES = {"completed", "failed", "cancelled"}


class Repo:
    def __init__(self, db: Database):
        self.db = db
        self._lock = asyncio.Lock()

    # ----------------------------------------------------------------- users / swarms
    async def ensure_user(self, user_id: str) -> None:
        async with self._lock, self.db.session() as s:
            if await s.get(User, user_id) is None:
                s.add(User(id=user_id))
                await s.commit()

    async def create_swarm(
        self,
        *,
        swarm_id: str,
        user_id: str,
        query: str,
        mode: str,
        origin_lat: float,
        origin_lng: float,
        radius_miles: float,
    ) -> None:
        async with self._lock, self.db.session() as s:
            if await s.get(User, user_id) is None:
                s.add(User(id=user_id))
                await s.flush()  # the swarm row has a FK to the user row
            s.add(
                Swarm(
                    id=swarm_id,
                    user_id=user_id,
                    query=query,
                    mode=mode,
                    origin_lat=origin_lat,
                    origin_lng=origin_lng,
                    radius_miles=radius_miles,
                )
            )
            await s.commit()

    async def update_swarm(self, swarm_id: str, **fields: Any) -> None:
        async with self._lock, self.db.session() as s:
            await s.execute(update(Swarm).where(Swarm.id == swarm_id).values(**fields))
            await s.commit()

    async def get_swarm(self, swarm_id: str) -> Swarm | None:
        async with self.db.session() as s:
            return await s.get(Swarm, swarm_id)

    async def list_swarms(self, limit: int = 20) -> list[Swarm]:
        async with self.db.session() as s:
            rows = await s.execute(select(Swarm).order_by(Swarm.created_at.desc()).limit(limit))
            return list(rows.scalars())

    async def save_intent(self, swarm_id: str, intent: Intent) -> None:
        await self.update_swarm(swarm_id, intent=intent.model_dump(mode="json"))

    # ----------------------------------------------------------------- tasks / calls
    async def create_task_and_call(
        self, *, swarm_id: str, call_id: str, target: Target, role: str = "inquiry"
    ) -> str:
        task_id = new_id("task")
        async with self._lock, self.db.session() as s:
            s.add(
                Task(
                    id=task_id,
                    swarm_id=swarm_id,
                    target_id=target.id,
                    target=target.model_dump(mode="json"),
                    tier=target.tier,
                    role=role,
                )
            )
            await s.flush()
            s.add(Call(id=call_id, task_id=task_id, swarm_id=swarm_id, target_id=target.id, role=role))
            await s.commit()
        return task_id

    async def update_call_state(self, call_id: str, state: str, reason: str | None = None) -> None:
        now = time.time()
        async with self._lock, self.db.session() as s:
            call = await s.get(Call, call_id)
            if call is None:
                return
            call.state = state
            if reason:
                call.failure_reason = reason
            if state in ("dialing", "talking") and call.started_at is None:
                call.started_at = now
            if state in TERMINAL_CALL_STATES:
                call.ended_at = now
                if call.started_at:
                    call.duration_s = round(now - call.started_at, 2)
                task = await s.get(Task, call.task_id)
                if task:
                    task.status = state
            await s.commit()

    async def set_call_provider_sid(self, call_id: str, sid: str) -> None:
        async with self._lock, self.db.session() as s:
            await s.execute(update(Call).where(Call.id == call_id).values(provider_sid=sid))
            await s.commit()

    async def save_transcript(self, call_id: str, transcript: list[dict]) -> None:
        async with self._lock, self.db.session() as s:
            await s.execute(update(Call).where(Call.id == call_id).values(transcript=transcript))
            await s.commit()

    async def save_extracted(self, call_id: str, swarm_id: str, result: ExtractedResult) -> None:
        async with self._lock, self.db.session() as s:
            existing = (
                await s.execute(select(ExtractedData).where(ExtractedData.call_id == call_id))
            ).scalar_one_or_none()
            values = dict(
                available=result.available,
                item=result.item,
                price=result.price,
                quantity=result.quantity,
                can_hold=result.can_hold,
                wait_minutes=result.wait_minutes,
                alternatives=result.alternatives,
                referral_name=result.referral_name,
                referral_phone=result.referral_phone,
                closed=result.closed,
                notes=result.notes,
                confidence=result.confidence,
                raw=result.model_dump(mode="json"),
            )
            if existing:
                for key, value in values.items():
                    setattr(existing, key, value)
            else:
                s.add(ExtractedData(call_id=call_id, swarm_id=swarm_id, **values))
            await s.commit()

    # ----------------------------------------------------------------- event log
    async def append_event(self, event: dict) -> None:
        async with self._lock, self.db.session() as s:
            s.add(
                SwarmEventRow(
                    swarm_id=event["swarm_id"],
                    seq=event["seq"],
                    type=event["type"],
                    data=event["data"],
                    ts=event["ts"],
                )
            )
            await s.commit()

    async def list_events(self, swarm_id: str, after: int = 0) -> list[dict]:
        async with self.db.session() as s:
            rows = await s.execute(
                select(SwarmEventRow)
                .where(SwarmEventRow.swarm_id == swarm_id, SwarmEventRow.seq > after)
                .order_by(SwarmEventRow.seq)
            )
            return [
                {"seq": r.seq, "swarm_id": r.swarm_id, "ts": r.ts, "type": r.type, "data": r.data}
                for r in rows.scalars()
            ]

    async def max_seq(self, swarm_id: str) -> int:
        async with self.db.session() as s:
            value = await s.scalar(select(func.max(SwarmEventRow.seq)).where(SwarmEventRow.swarm_id == swarm_id))
            return int(value or 0)

    # ----------------------------------------------------------------- reads for tests / debugging
    async def count(self, model: type) -> int:
        async with self.db.session() as s:
            return int(await s.scalar(select(func.count()).select_from(model)) or 0)
