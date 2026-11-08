"""Phone-menu / hold handling: rules answer machines, the model is never needed for them. Author: Saamarth Attray"""
import httpx

from app.agent.brain import LLMBrain, ResilientBrain, ScriptedBrain
from app.agent.ivr import IvrNavigator
from app.agent.session import CallSession
from tests.test_session_llm import Recorder, ctx, make_client


def nav():
    return IvrNavigator(ctx())


def test_kroger_style_announcement_is_waited_out_not_answered():
    n = nav()
    m = n.decide("Thank you for calling Kroger Pharmacy. Your call may be recorded for quality purposes.")
    assert m and m.kind == "wait"


def test_numbered_menu_presses_the_person_option():
    n = nav()
    m = n.decide("For store hours press 1. To speak with a pharmacy team member, press 3. For refills, press 2.")
    assert m and m.kind == "keys" and m.text == "3"


def test_voicemail_ends_without_leaving_a_message():
    m = nav().decide("Please leave a message after the tone.")
    assert m and m.kind == "end"


def test_hold_then_person_gets_a_fresh_introduction():
    n = nav()
    assert n.decide("Please hold while I transfer you.").kind == "wait"
    m = n.decide("Pharmacy, this is Dana.")
    assert m and m.kind == "intro"


def test_screening_question_is_answered_not_treated_as_refusal():
    m = nav().decide("Are you a health care provider calling about a patient? Say yes or no.")
    assert m and m.kind == "say"


def test_a_plain_person_question_is_left_to_the_model():
    assert nav().decide("Yeah, we have that, it is about nine dollars. Anything else?") is None


async def test_resilient_brain_falls_back_when_the_model_is_down(monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr("app.llm.asyncio.sleep", no_sleep)
    c = ctx()
    brain = ResilientBrain(LLMBrain(make_client(lambda r: httpx.Response(500, text="boom")), c), ScriptedBrain(c))
    session = CallSession(c, brain, Recorder())
    await session.start()
    spoken = [s async for s in session.respond("Hi, how can I help you?")]
    assert spoken and session.llm_failures == 0 and not session.finished


async def test_refused_is_not_accepted_without_a_refusal():
    c = ctx()
    session = CallSession(c, ScriptedBrain(c), Recorder())
    await session.start()
    [s async for s in session.respond("Please hold.")]
    assert not session.finished and session.holding