"""Rule-based understanding of what a business says, and the scripted agent built on it. Author: Saamarth Attray"""
import pytest

from app.agent import nlu
from app.agent.brain import ScriptedBrain
from app.agent.types import BrainContext
from app.contract import Intent, Target
from app.intent import heuristic_intent


@pytest.mark.parametrize(
    "text,kind",
    [
        ("Yeah, hang on, let me check the shelf.", "wait"),
        ("Okay yeah, we do have amoxicillin. We've got 4 left.", "has"),
        ("Let me check... no, we're out of it right now, sorry about that.", "no"),
        ("Sorry, we're closed right now. We open again tomorrow at 8.", "closed"),
        ("We don't have that, but we do have the generic version for $9.", "partial"),
        ("Hmm, no, we're out. You could try Summit Pharmacy on Main Street, they usually have it.", "no"),
        ("Sorry, I don't talk to robots. Bye.", "refused"),
        ("You've reached us. Please leave a message after the tone.", "voicemail"),
        ("Are you a robot?", "are_you_bot"),
        ("We're fully booked tonight, nothing until tomorrow.", "no"),
        ("Hmm?", "unclear"),
    ],
)
def test_classify(text, kind):
    assert nlu.classify(text).kind == kind


def test_extract_facts():
    f = nlu.extract_facts("It's $12.50, we've got 3 left, and yes, we can hold one for you. About 45 minutes.")
    assert f.price == 12.5 and f.quantity == 3 and f.can_hold is True and f.wait_minutes == 45
    assert nlu.extract_facts("We can't hold items, first come first served.").can_hold is False
    assert nlu.extract_facts("We can be there in about an hour").wait_minutes == 60


def test_extract_referral_with_phone():
    f = nlu.extract_facts("No, but you could try Summit Pharmacy, their number is 202-555-0147.")
    assert f.referral_name == "Summit Pharmacy"
    assert f.referral_phone and "555-0147" in f.referral_phone


def _ctx(query="Find amoxicillin", role="inquiry"):
    intent = heuristic_intent(query, 10, None)
    return BrainContext(intent=intent, target=Target(id="t1", name="CVS", lat=0, lng=0, distance_miles=1), role=role)


async def _collect(brain, text):
    return [e async for e in brain.respond([{"role": "user", "content": text}])]


async def test_scripted_brain_asks_for_details_then_reports():
    brain = ScriptedBrain(_ctx())
    first = await _collect(brain, "Yes, we do have it, 3 left.")
    assert first[0].kind == "text" and "price" in first[0].text.lower()
    second = await _collect(brain, "It's $14 and yes, we can hold one for you.")
    call = second[0].tool_call
    assert call and call.name == "report_availability"
    assert call.arguments["available"] == "yes" and call.arguments["price"] == 14.0
    assert call.arguments["can_hold"] is True and call.arguments["quantity"] == 3


async def test_scripted_brain_refusal_and_voicemail_end_the_call():
    refused = await _collect(ScriptedBrain(_ctx()), "I don't talk to robots.")
    assert refused[-1].tool_call.name == "end_call" and refused[-1].tool_call.arguments["reason"] == "refused"
    vm = await _collect(ScriptedBrain(_ctx()), "Leave a message after the beep.")
    assert vm[0].tool_call.arguments["reason"] == "voicemail"


async def test_scripted_brain_is_honest_about_being_an_ai():
    out = await _collect(ScriptedBrain(_ctx()), "Wait, are you a real person?")
    assert "AI assistant" in out[0].text


async def test_scripted_reserve_role():
    brain = ScriptedBrain(_ctx(role="reserve"))
    ok = await _collect(brain, "Sure, I've set one aside at the counter. Your confirmation code is AB1234.")
    assert ok[0].tool_call.name == "report_hold" and ok[0].tool_call.arguments["success"] is True
    assert ok[0].tool_call.arguments["confirmation"] == "AB1234"
    no = await _collect(ScriptedBrain(_ctx(role="reserve")), "Sorry, we can't hold items over the phone.")
    assert no[0].tool_call.arguments["success"] is False
