"""Agent brains: the LLM-driven production brain and the offline scripted brain.

Both implement `respond(messages) -> AsyncIterator[BrainEvent]`, so the call session, the Twilio media
bridge and the simulator never care which one is plugged in.

Author: Saamarth Attray
"""
from __future__ import annotations

import asyncio
import logging
import random
import uuid
from typing import AsyncIterator

from ..llm import LLMClient
from . import nlu
from .personas import build_system_prompt
from .tools import tools_for
from .types import Brain, BrainContext, BrainEvent, ToolCall

log = logging.getLogger("swarmdial.brain")

WAIT_LINES = ["Sure, no rush.", "Mm-hm, take your time.", "Yep, no problem.", "Okay, I'll hold."]
CLARIFY_LINES = [
    "Sorry, I didn't quite catch that. Could you say it one more time?",
    "Just to make sure I've got it right, is that a yes or a no?",
]


def _tool(name: str, **arguments) -> BrainEvent:
    clean = {k: v for k, v in arguments.items() if v is not None}
    return BrainEvent(kind="tool_call", tool_call=ToolCall(id=f"call_{uuid.uuid4().hex[:8]}", name=name, arguments=clean))


def _text(text: str) -> BrainEvent:
    return BrainEvent(kind="text", text=text)


class LLMBrain:
    """Streams a reply (and tool calls) from an OpenAI-compatible model such as Groq's Llama 3 70B."""

    def __init__(self, llm: LLMClient, ctx: BrainContext):
        self.llm = llm
        self.ctx = ctx
        self.system = build_system_prompt(ctx)
        self.tools = tools_for(ctx.role, ctx.intent.kind)

    async def respond(self, messages: list[dict]) -> AsyncIterator[BrainEvent]:
        full = [{"role": "system", "content": self.system}, *messages]
        # One quick retry on the backup model: on a live call a long wait is worse than a simpler answer.
        async for event in self.llm.stream_chat(full, self.tools, retries=1):
            yield event


class ResilientBrain:
    """Language model first; if it fails (rate limit, outage) before saying anything, the built-in scripted brain takes
    that turn so the call carries on instead of going quiet or hanging up."""

    def __init__(self, primary: Brain, backup: Brain) -> None:
        self.primary = primary
        self.backup = backup

    async def respond(self, messages: list[dict]) -> AsyncIterator[BrainEvent]:
        emitted = False
        try:
            async for event in self.primary.respond(messages):
                emitted = True
                yield event
            return
        except (asyncio.CancelledError, GeneratorExit):
            raise
        except Exception as exc:
            log.warning("language model failed (%s); %s", exc, "turn cut short" if emitted else "using the built-in script for this turn")
            if emitted:
                return
        async for event in self.backup.respond(messages):
            yield event


class ScriptedBrain:
    """Deterministic, key-free stand-in. Reads the business's words with `nlu` and follows the same
    workflow the LLM prompt describes. Powers simulated mode and the test-suite."""

    def __init__(self, ctx: BrainContext):
        self.ctx = ctx
        self.stage = "asked_availability"
        self.facts = nlu.Facts()
        self.clarifications = 0
        self.ivr_attempts = 0

    # --------------------------------------------------------------------- helpers
    def _absorb(self, text: str, new: nlu.Facts | None = None) -> None:
        new = new or nlu.extract_facts(text)
        for name in ("price", "quantity", "can_hold", "wait_minutes", "referral_name", "referral_phone",
                     "hours", "requirements", "perishables_ok", "can_pickup"):
            value = getattr(new, name)
            if value is not None:
                setattr(self.facts, name, value)

    @staticmethod
    def _last_business(messages: list[dict]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user":
                return str(message.get("content") or "")
        return ""

    # --------------------------------------------------------------------- main entry
    async def respond(self, messages: list[dict]) -> AsyncIterator[BrainEvent]:
        last = self._last_business(messages)
        if self.ctx.role == "reserve":
            events = self._reserve(last)
        elif self.ctx.intent.kind in ("food", "donation"):
            events = self._inquire_pantry(last)
        else:
            events = self._inquire(last)
        for event in events:
            yield event

    # --------------------------------------------------------------------- inquiry role
    def _inquire(self, last: str) -> list[BrainEvent]:
        intent = self.ctx.intent
        self._absorb(last)
        c = nlu.classify(last)
        f = self.facts

        if c.kind == "refused":
            return [_text("No problem at all, sorry to bother you."), _tool("end_call", reason="refused")]
        if c.kind == "voicemail":
            return [_tool("end_call", reason="voicemail")]
        if c.kind == "ivr":
            if self.ivr_attempts == 0:
                self.ivr_attempts += 1
                return [_text("Representative, please.")]
            return [_tool("end_call", reason="ivr_unresolved")]
        if c.kind == "are_you_bot":
            return [_text("Yes, I'm an AI assistant calling for a customer. Is it okay if I ask a quick question?")]
        if c.kind == "wait":
            return [_text(random.choice(WAIT_LINES))]
        if c.kind == "closed":
            return [
                _tool(
                    "report_availability",
                    available="no",
                    closed=True,
                    notes=_first_sentence(last) or "Closed right now",
                    confidence=0.9,
                )
            ]
        if c.kind == "partial":
            return [
                _tool(
                    "report_availability",
                    available="partial",
                    item_matched=c.alt,
                    alternatives=[c.alt] if c.alt else None,
                    price=f.price,
                    wait_minutes=f.wait_minutes,
                    can_hold=f.can_hold,
                    notes=f"Does not have exactly {intent.item}; offers {c.alt}" if c.alt else None,
                    confidence=0.85,
                )
            ]
        if c.kind == "no":
            return [
                _tool(
                    "report_availability",
                    available="no",
                    referral_name=f.referral_name,
                    referral_phone=f.referral_phone,
                    notes=_first_sentence(last),
                    confidence=0.9,
                )
            ]
        if c.kind == "has" or self.stage == "asked_details":
            if intent.kind == "product":
                need_details = f.price is None or f.can_hold is None
            else:
                need_details = f.price is None or f.wait_minutes is None
            if need_details and self.stage != "asked_details":
                self.stage = "asked_details"
                if intent.kind == "product":
                    return [
                        _text(
                            "Great, thank you. And what's the price on that, "
                            "and is it something you could hold for a couple of hours?"
                        )
                    ]
                return [_text("Great, thank you. What would the call-out fee be, and roughly how soon could someone get here?")]
            if c.kind == "unclear" and f.price is None and f.can_hold is None and f.wait_minutes is None:
                return self._clarify()
            return [
                _tool(
                    "report_availability",
                    available="yes",
                    item_matched=intent.item,
                    price=f.price,
                    quantity=f.quantity,
                    can_hold=f.can_hold,
                    wait_minutes=f.wait_minutes,
                    notes=None,
                    confidence=0.9,
                )
            ]
        return self._clarify()

    # --------------------------------------------------------------------- food pantries (seekers and donors)
    def _inquire_pantry(self, last: str) -> list[BrainEvent]:
        donating = self.ctx.intent.kind == "donation"
        new = nlu.extract_food_facts(last)
        self._absorb(last, new)
        if new.needs:
            self.facts.needs = new.needs
        f = self.facts
        c = nlu.classify_food(last)
        if self.stage == "asked_details" and c.kind in ("partial", "unclear", "has"):
            c = nlu.Classification("has")  # they already said yes; this turn only supplies details

        if c.kind == "refused":
            return [_text("No problem at all, sorry to bother you."), _tool("end_call", reason="refused")]
        if c.kind == "voicemail":
            return [_tool("end_call", reason="voicemail")]
        if c.kind == "ivr":
            if self.ivr_attempts == 0:
                self.ivr_attempts += 1
                return [_text("Food pantry or donations, please.")]
            return [_tool("end_call", reason="ivr_unresolved")]
        if c.kind == "are_you_bot":
            return [_text("Yes, I'm an AI assistant calling for someone in the community. Is it okay if I ask a quick question?")]
        if c.kind == "wait":
            return [_text(random.choice(WAIT_LINES))]

        common = dict(
            hours=f.hours, requirements=f.requirements, needs=f.needs or None, perishables_ok=f.perishables_ok,
            wait_minutes=f.wait_minutes, can_hold=f.can_hold, can_pickup=f.can_pickup, referral_name=f.referral_name,
            referral_phone=f.referral_phone, item_matched=self.ctx.intent.item,
        )
        if c.kind == "no":
            closed = bool(nlu.CLOSED.search(last) or nlu.FOOD_NO.search(last) and "closed" in last.lower())
            return [_tool("report_availability", available="no", closed=closed or None, notes=_first_sentence(last),
                          confidence=0.9, **{k: v for k, v in common.items() if k in ("referral_name", "referral_phone")})]
        if c.kind == "partial":
            note = ("No fresh food, shelf-stable only" if donating and f.perishables_ok is False else _first_sentence(last))
            return [_tool("report_availability", available="partial", notes=note, confidence=0.85, **common)]
        if c.kind == "has" or self.stage == "asked_details":
            if donating:
                # food rescue: we need to know how soon someone can come and whether they take fresh food
                need_details = f.can_pickup is not False and (f.wait_minutes is None or f.perishables_ok is None)
            else:
                need_details = f.hours is None or f.requirements is None
            if need_details and self.stage != "asked_details":
                self.stage = "asked_details"
                if donating:
                    asks = []
                    if f.wait_minutes is None:
                        asks.append("how soon could someone come by")
                    if f.perishables_ok is None:
                        asks.append("can you take fresh or refrigerated food")
                    return [_text("Wonderful, thank you. " + " and ".join(asks).capitalize() + "?")]
                return [_text("Great, thank you. What time do you close today, and does anyone need to bring ID or proof of address?")]
            if c.kind == "unclear" and f.hours is None and f.requirements is None and not f.needs and f.can_pickup is None:
                return self._clarify()
            if donating and f.can_pickup is False:
                # they will take it, but only if the donor brings it: useful, but not a pickup
                return [_tool("report_availability", available="partial", confidence=0.85,
                              notes="Drop-off only, they cannot pick up", **common)]
            return [_tool("report_availability", available="yes", confidence=0.9, **common)]
        return self._clarify()

    def _clarify(self) -> list[BrainEvent]:
        if self.clarifications >= 2:
            return [_tool("end_call", reason="other", notes="Could not get a clear answer")]
        self.clarifications += 1
        if self.clarifications == 1 and self.ctx.intent.kind == "food":
            return [_text("Sorry, just to confirm, are you giving out food today?")]
        if self.clarifications == 1 and self.ctx.intent.kind == "donation":
            return [_text("Sorry, just to confirm, could your organization send someone to pick up the food tonight?")]
        if self.clarifications == 1 and self.ctx.intent.kind == "product":
            return [_text(f"Sorry, just to confirm, do you have {self.ctx.intent.item} in stock right now?")]
        return [_text(CLARIFY_LINES[min(self.clarifications - 1, len(CLARIFY_LINES) - 1)])]

    # --------------------------------------------------------------------- reserve role
    def _reserve(self, last: str) -> list[BrainEvent]:
        c = nlu.classify(last)
        if c.kind == "wait":
            return [_text(random.choice(WAIT_LINES))]
        if c.kind in ("refused", "voicemail", "ivr"):
            return [_tool("end_call", reason={"refused": "refused", "voicemail": "voicemail"}.get(c.kind, "ivr_unresolved"))]
        facts = nlu.extract_facts(last)
        if facts.can_hold is False or c.kind in ("no", "closed"):
            return [_tool("report_hold", success=False, notes=_first_sentence(last) or "They could not hold it")]
        if nlu.HOLD_SUCCESS.search(last) or facts.can_hold:
            confirmation = nlu.extract_confirmation(last) or (
                "Pickup confirmed" if self.ctx.intent.kind == "donation" else
                (f"Held under {self.ctx.contact_name}" if self.ctx.contact_name else "Held at the counter")
            )
            return [_tool("report_hold", success=True, confirmation=confirmation, notes=_first_sentence(last))]
        if self.clarifications >= 2:
            return [_tool("end_call", reason="other")]
        self.clarifications += 1
        if self.ctx.intent.kind == "donation":
            return [_text("Sorry, can you confirm that someone is coming to pick it up?")]
        return [_text("Sorry, were you able to set that aside for the customer?")]


def _first_sentence(text: str) -> str | None:
    text = text.strip()
    if not text:
        return None
    first = nlu.re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    return first[:200]
