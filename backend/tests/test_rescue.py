"""Food rescue: a restaurant describes surplus food, the swarm finds who can pick it up.
Author: Saamarth Attray"""
import pytest
from fastapi.testclient import TestClient

from app.agent.brain import ScriptedBrain
from app.agent.personas import opening_line
from app.agent.session import CallSession
from app.agent.types import BrainContext
from app.contract import EVENT_ADAPTER, CreateSwarmRequest, ExtractedResult, Target
from app.intent import heuristic_intent
from app.main import create_app
from app.ranking import Candidate, rank

FOOD = "12 trays of pasta primavera, 40 turkey sandwiches and 3 gallons of tomato soup, all made today"


def intent():
    return heuristic_intent(FOOD, 8, None, "donate")


def ctx(**kw):
    t = Target(id="t1", name="Harvest Hope Pantry", lat=0, lng=0, distance_miles=1.2)
    return BrainContext(intent=intent(), target=t, contact_name="Luigi's Trattoria", donor_address="412 Main St",
                        pickup_by="before 10 pm", **kw)


class Rec:
    def __init__(self):
        self.results, self.states = [], []

    async def state(self, state, reason=None):
        self.states.append(state)

    async def transcript(self, *a):
        pass

    async def extracted(self, result):
        self.results.append(result)


async def converse(*lines):
    c, rec = ctx(), Rec()
    session = CallSession(c, ScriptedBrain(c), rec)
    spoken = [await session.start()]
    for line in lines:
        async for sentence in session.respond(line):
            spoken.append(sentence)
        if session.finished:
            break
    return session, rec, spoken


# ----------------------------------------------------------------------------- intent and wording
def test_donor_description_is_kept_verbatim_and_prioritises_speed():
    i = intent()
    assert i.kind == "donation" and i.category == "food_donation" and i.priority == "speed"
    assert i.item == FOOD and i.urgency == "now"
    assert "pick up" in i.summary


def test_opening_line_discloses_ai_names_the_donor_and_asks_for_pickup():
    line = opening_line(ctx())
    assert "AI assistant" in line and "Luigi's Trattoria" in line
    assert "pasta primavera" in line and "before 10 pm" in line
    assert "pick it up?" in line and line.rstrip().endswith("on behalf of Luigi's Trattoria.")


def test_long_food_lists_are_shortened_when_spoken():
    long_item = ", ".join(f"{n} trays of dish number {n}" for n in range(1, 30))
    c = ctx()
    c.intent = c.intent.model_copy(update={"item": long_item})
    spoken = opening_line(c)
    assert len(spoken) < 500 and ", and more" in spoken


# ----------------------------------------------------------------------------- the agent
async def test_pickup_conversation_extracts_eta_and_fresh_food():
    session, rec, spoken = await converse(
        "Oh that's wonderful, let me check with our driver.",
        "Yes, we can send a volunteer to pick it up, about 25 minutes from now.",
        "And yes, we have a walk-in cooler so fresh food is no problem.",
    )
    assert any("fresh or refrigerated" in s for s in spoken)  # it asked what it still needed
    r = rec.results[0]
    assert (r.available, r.can_pickup, r.wait_minutes, r.perishables_ok) == ("yes", True, 25, True)
    assert session.finished and session.outcome().state == "completed"


async def test_drop_off_only_is_partial_with_no_pickup():
    _, rec, _ = await converse("We can't send anyone to pick up tonight, but you can drop it off here until 8 pm.")
    r = rec.results[0]
    assert r.available == "partial" and r.can_pickup is False


async def test_at_capacity_is_a_no():
    _, rec, _ = await converse("I'm sorry, we're at capacity tonight, our fridges are completely full.")
    assert rec.results[0].available == "no"


async def test_shelf_stable_only_is_partial_and_says_why():
    _, rec, _ = await converse("Thank you for thinking of us. We don't take fresh food, only shelf-stable items, sorry.")
    r = rec.results[0]
    assert r.available == "partial" and r.perishables_ok is False and "shelf-stable" in (r.notes or "")


async def test_pickup_confirmation_call_succeeds_with_a_code():
    c = ctx(role="reserve", prior_result=ExtractedResult(available="yes", can_pickup=True, wait_minutes=25))
    rec = Rec()
    session = CallSession(c, ScriptedBrain(c), rec)
    opening = await session.start()
    assert "AI assistant" in opening and "412 Main St" in opening
    _ = [s async for s in session.respond("Sure, let me confirm that.")]
    assert not session.finished  # waited politely
    _ = [s async for s in session.respond("Okay, confirmed. Priya will come by in about 25 minutes. The confirmation code is AB1234.")]
    hold = session.outcome().hold
    assert hold and hold.success and hold.confirmation == "AB1234"


async def test_pickup_confirmation_call_can_fail():
    c = ctx(role="reserve")
    session = CallSession(c, ScriptedBrain(c), Rec())
    await session.start()
    _ = [s async for s in session.respond("Oh no, our driver just got called away, we can't send anyone tonight after all.")]
    hold = session.outcome().hold
    assert hold is not None and hold.success is False


# ----------------------------------------------------------------------------- ranking
def cand(i, wait, dist, **kw):
    t = Target(id=f"t{i}", name=f"Org {i}", lat=0, lng=0, distance_miles=dist)
    return Candidate(f"c{i}", t, ExtractedResult(available="yes", can_pickup=True, wait_minutes=wait, **kw))


def test_soonest_pickup_wins_and_no_fresh_food_is_penalised():
    ranked, best, criteria = rank([cand(1, 45, 1.0), cand(2, 15, 6.0), cand(3, 15, 1.0, perishables_ok=False)], intent())
    assert best == "c2" and "pickup" in criteria.lower()
    assert [r.call_id for r in ranked][-1] == "c3"
    assert "Can pick up" in ranked[0].reasons[0] and any("min away" in x for x in ranked[0].reasons)


def test_drop_off_only_ranks_below_a_real_pickup():
    drop = Candidate("d", Target(id="td", name="Drop", lat=0, lng=0, distance_miles=0.5),
                     ExtractedResult(available="partial", can_pickup=False))
    ranked, best, _ = rank([drop, cand(1, 50, 5.0)], intent())
    assert best == "c1" and ranked[1].reasons[0] == "Drop-off only"


# ----------------------------------------------------------------------------- the whole swarm
async def test_simulated_rescue_swarm_finds_reroutes_ranks_and_confirms_pickup(stack):
    cmd = stack.build()
    sid = await cmd.create_swarm(CreateSwarmRequest(
        query=FOOD, purpose="donate", contact_name="Luigi's Trattoria", donor_address="412 Main St",
        pickup_by="before 10 pm", radius_miles=8))
    await cmd._runs[sid].main_task
    events = await stack.bus.backlog(sid)
    for e in events:
        EVENT_ADAPTER.validate_python(e)

    created = events[0]["data"]
    assert created["intent"]["kind"] == "donation" and created["targets"][0]["name"]
    assert any(t["name"] in ("Community Table Food Bank", "Harvest Hope Pantry", "St. Anne's Soup Kitchen",
                             "Neighbors Helping Neighbors", "Second Helpings Rescue") or "Pantry" in t["name"] or "Kitchen" in t["name"]
               or "Food" in t["name"] or "Shelter" in t["name"] or "Meal" in t["name"] for t in created["targets"])

    extracted = [e["data"]["result"] for e in events if e["type"] == "call.extracted"]
    assert any(r["available"] == "yes" and r["can_pickup"] for r in extracted)
    assert any(e["type"] == "swarm.reroute" for e in events)
    notes = [e["data"]["note"] for e in events if e["type"] == "swarm.knowledge"]
    assert any("pick it up" in n or "capacity" in n or "drop-off" in n for n in notes)

    ranked = next(e["data"] for e in events if e["type"] == "swarm.ranked")
    assert ranked["best_call_id"] and "pickup" in ranked["criteria"].lower()
    best = next(e["data"]["result"] for e in events if e["type"] == "call.extracted" and e["data"]["call_id"] == ranked["best_call_id"])
    assert best["can_pickup"] is True

    await cmd.reserve(sid, ranked["best_call_id"])
    import asyncio

    for _ in range(100):
        events = await stack.bus.backlog(sid)
        done = [e for e in events if e["type"] == "swarm.reserved"]
        if done:
            break
        await asyncio.sleep(0.02)
    assert done and "pickup" in done[0]["data"]["message"].lower()


def test_rest_api_accepts_donor_details(settings):
    with TestClient(create_app(settings)) as c:
        r = c.post("/api/swarms", json={"query": FOOD, "purpose": "donate", "contact_name": "Luigi's",
                                        "donor_address": "412 Main St", "pickup_by": "before 10 pm"})
        assert r.status_code == 201
        assert c.post("/api/swarms", json={"query": FOOD, "purpose": "donate", "donor_address": "x" * 200}).status_code == 422
        assert c.post("/api/swarms", json={"query": FOOD, "purpose": "bogus"}).status_code == 422
