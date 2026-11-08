"""Redis pub/sub fan-out (fakeredis) and event-log persistence/replay. Author: Saamarth Attray"""
import asyncio

import fakeredis

from app.contract import CallStateData, SwarmKnowledgeData
from app.db import Database
from app.events import EventBus
from app.repo import Repo


async def test_redis_fanout_delivers_events_in_order(settings):
    db = Database(settings.database_url)
    await db.create_all()
    repo = Repo(db)
    await repo.create_swarm(swarm_id="s1", user_id="u", query="q", mode="simulated", origin_lat=0, origin_lng=0, radius_miles=5)
    bus = EventBus(repo, redis_client=fakeredis.FakeAsyncRedis(decode_responses=True))
    await bus.start()
    try:
        async with bus.subscribe("s1") as sub:
            await bus.publish("s1", CallStateData(call_id="c1", target_id="t1", state="queued"))
            await bus.publish("s1", SwarmKnowledgeData(note="hello"))
            got = [await asyncio.wait_for(sub.queue.get(), 3) for _ in range(2)]
        assert [e["type"] for e in got] == ["call.state", "swarm.knowledge"]
        assert [e["seq"] for e in got] == [1, 2]
    finally:
        await bus.stop()
        await db.dispose()


async def test_events_survive_restart_and_resume_sequence(settings):
    db = Database(settings.database_url)
    await db.create_all()
    repo = Repo(db)
    await repo.create_swarm(swarm_id="s1", user_id="u", query="q", mode="simulated", origin_lat=0, origin_lng=0, radius_miles=5)
    bus = EventBus(repo)
    for i in range(3):
        await bus.publish("s1", SwarmKnowledgeData(note=f"n{i}"))
    fresh = EventBus(repo)  # a new process: empty memory, same database
    assert [e["seq"] for e in await fresh.backlog("s1")] == [1, 2, 3]
    assert (await fresh.publish("s1", SwarmKnowledgeData(note="after restart")))["seq"] == 4
    assert [e["seq"] for e in await fresh.backlog("s1", after=2)] == [3, 4]
    await db.dispose()


async def test_partial_events_are_streamed_but_not_persisted(settings):
    from app.contract import CallTranscriptData

    db = Database(settings.database_url)
    await db.create_all()
    repo = Repo(db)
    await repo.create_swarm(swarm_id="s1", user_id="u", query="q", mode="simulated", origin_lat=0, origin_lng=0, radius_miles=5)
    bus = EventBus(repo)
    t = dict(call_id="c1", target_id="t1", utterance_id="u1", speaker="agent")
    await bus.publish("s1", CallTranscriptData(text="Hel", is_final=False, **t), persist=False)
    await bus.publish("s1", CallTranscriptData(text="Hello", is_final=True, **t))
    assert len(await bus.backlog("s1")) == 2
    assert len(await repo.list_events("s1")) == 1
    await db.dispose()
