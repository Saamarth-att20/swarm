"""CallSession: the transport-agnostic heart of one phone call.

The Twilio media bridge, the offline simulator and the tests all drive the same object:

    opening = await session.start()                 # speak this first
    async for sentence in session.respond(heard):   # speak each sentence as it streams in
        ...
    session.finished / session.outcome()

The session runs the LLM tool-use loop, fires the structured-data-extraction tool
(`report_availability`) when the business gives a clear answer, and keeps the conversation history
consistent even when the business barges in halfway through a sentence.

Author: Saamarth Attray
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import AsyncIterator

from ..contract import ExtractedResult
from ..telephony.dtmf import clean_digits
from .ivr import IvrNavigator, Move
from .nlu import REFUSED
from .personas import FALLBACK_LINE, closing_line, opening_line
from .textcalls import TOOL_TEXT, parse_text_tool_call
from .tools import coerce_hold, coerce_result, tools_for
from .types import Brain, BrainContext, CallOutcome, HoldResult, Reporter, ToolCall

log = logging.getLogger("swarmdial.session")

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

END_REASON_LABELS = {
    "closed": "Business is closed",
    "voicemail": "Reached voicemail",
    "refused": "Declined to talk to an AI assistant",
    "ivr_unresolved": "Stuck in an automated phone menu",
    "no_response": "Nobody responded",
    "other": "Call ended without an answer",
    "business_hung_up": "The business hung up",
    "error": "Call failed unexpectedly",
    "llm_error": "The AI model had trouble responding",
    "turn_limit": "The call went on too long without an answer",
}

REPEAT_LINES = ("Sorry, I didn't catch that. Could you say it one more time?", "Sorry, could you repeat that for me?")
MAX_LLM_FAILURES = 3  # consecutive model failures before the agent gives up (each earlier one just asks to repeat)


class CallSession:
    def __init__(self, ctx: BrainContext, brain: Brain, reporter: Reporter, *, max_turns: int = 30):
        self.ctx = ctx
        self.brain = brain
        self.reporter = reporter
        self.max_turns = max_turns
        self.messages: list[dict] = []
        self.finished = False
        self.result: ExtractedResult | None = None
        self.hold: HoldResult | None = None
        self.end_reason: str | None = None
        self.holding = False  # waiting on a recording / hold music / transfer: the bridge is more patient
        self.pending_keys = ""  # keypad digits for the bridge to play after this turn's speech
        self.llm_failures = 0
        self.opened = False  # have we said why we are calling yet? (we wait to hear "hello" first)
        self.just_opened = False  # the bridge reads this after a turn to protect the opening line from interruptions
        self.ivr = IvrNavigator(ctx)  # rules for phone menus, recordings and holds (no model call needed)
        self._last_heard = ""
        self.turns = 0
        self._counter = 0
        self._turn_uid: str | None = None
        self._turn_spoken: list[str] = []

    # --------------------------------------------------------------------- ids
    def new_utterance_id(self) -> str:
        self._counter += 1
        return f"u{self._counter}"

    # --------------------------------------------------------------------- lifecycle
    async def open(self) -> str:
        """Say why we are calling (the first thing a person hears from us)."""
        line = opening_line(self.ctx)
        self.opened = self.just_opened = True
        self.messages.append({"role": "assistant", "content": line})
        await self.reporter.transcript("agent", line, self.new_utterance_id(), True)
        return line

    async def start(self) -> str:
        return await self.open()

    async def business_partial(self, text: str, utterance_id: str) -> None:
        await self.reporter.transcript("business", text, utterance_id, False)

    def force_end(self, reason: str) -> None:
        """Transport-level end (silence timeout, hang-up). No speech, no tool call."""
        if not self.finished:
            self.finished = True
            self.end_reason = self.end_reason or reason

    async def abort_turn(self) -> None:
        """Called by the transport after it cancelled a turn (barge-in): finalise what was actually said."""
        if self._turn_uid and self._turn_spoken:
            await self.reporter.transcript("agent", " ".join(self._turn_spoken), self._turn_uid, True)
        self._turn_uid, self._turn_spoken = None, []

    # --------------------------------------------------------------------- one conversational turn
    async def respond(self, business_text: str, utterance_id: str | None = None) -> AsyncIterator[str]:
        if self.finished:
            return
        self.holding = False
        uid = utterance_id or self.new_utterance_id()
        self._last_heard = business_text
        await self.reporter.transcript("business", business_text, uid, True)

        # Machines first: menus, recordings, holds and transfers are handled by rules, instantly and without the model.
        move = self.ivr.decide(business_text)
        if move is not None:
            async for line in self._apply_move(move):
                yield line
            return

        if not self.opened:
            # We are the ones calling: we let them pick up and say hello (or "how can I help?") first, then say why we called.
            self.messages.append({"role": "user", "content": business_text})
            yield await self.open()
            return

        self.messages.append({"role": "user", "content": business_text})
        self.turns += 1

        if self.turns > self.max_turns:
            async for line in self._give_up("turn_limit", "Conversation exceeded the turn limit", speak=True):
                yield line
            return

        self._turn_uid = self.new_utterance_id()
        self._turn_spoken = []
        tool_calls: list[ToolCall] = []
        buffer = ""
        machine_text = ""  # a tool call the model typed out as text: never spoken to the business
        failed = False

        try:
            async for event in self.brain.respond(list(self.messages)):
                if event.kind == "text":
                    if machine_text:
                        machine_text += event.text
                        continue
                    buffer += event.text
                    cut = TOOL_TEXT.search(buffer)
                    if cut:
                        buffer, machine_text = buffer[: cut.start()], buffer[cut.start():]
                    parts = SENTENCE_END.split(buffer)
                    for sentence in parts[:-1]:
                        sentence = sentence.strip()
                        if sentence:
                            await self._say(sentence)
                            yield sentence
                    buffer = parts[-1]
                elif event.kind == "tool_call" and event.tool_call:
                    tool_calls.append(event.tool_call)
            tail = buffer.strip()
            if tail:
                await self._say(tail)
                yield tail
            if machine_text:
                names = {t["function"]["name"] for t in tools_for(self.ctx.role, self.ctx.intent.kind)}
                typed = parse_text_tool_call(machine_text, names)
                if typed and not any(t.name == typed.name for t in tool_calls):
                    log.warning("[%s] the model typed a tool call as text; running it: %s", self.ctx.target.name, typed.name)
                    tool_calls.append(typed)
                elif typed is None:
                    log.warning("[%s] dropped machine text the model tried to say: %r", self.ctx.target.name, machine_text[:120])
        except (asyncio.CancelledError, GeneratorExit):
            # Barge-in or hang-up. Keep history truthful: only what was actually spoken counts.
            if self._turn_spoken:
                self.messages.append({"role": "assistant", "content": " ".join(self._turn_spoken)})
            raise
        except Exception as exc:  # LLM outage, bad stream...
            log.warning("[%s] brain failed: %s", self.ctx.target.name, exc)
            failed = True

        if failed and not self._turn_spoken and not tool_calls:
            # One bad model response is not a reason to hang up on a person or a phone menu: ask them to repeat and
            # try again on the next turn. Only give up after several failures in a row.
            self.llm_failures += 1
            self._turn_uid, self._turn_spoken = None, []
            if self.llm_failures >= MAX_LLM_FAILURES:
                async for line in self._give_up("llm_error", "The agent could not process the conversation", speak=True):
                    yield line
                return
            if self.ivr.automated or self.ivr.awaiting_human:
                self.holding = True  # never talk back to a recording just because the model hiccuped
                return
            line = REPEAT_LINES[(self.llm_failures - 1) % len(REPEAT_LINES)]
            self.messages.append({"role": "assistant", "content": line})
            await self.reporter.transcript("agent", line, self.new_utterance_id(), True)
            yield line
            return
        if not failed:
            self.llm_failures = 0

        for tc in tool_calls:
            log.info("[%s] agent tool call: %s %s", self.ctx.target.name, tc.name, tc.arguments)
        # A model that asks a question and hangs up in the same breath never lets the business answer it.
        asked_question = bool(self._turn_spoken) and self._turn_spoken[-1].rstrip().endswith("?")
        kept: list[ToolCall] = []
        for tc in tool_calls:
            if tc.name == "end_call" and asked_question and str(tc.arguments.get("reason") or "other") == "other":
                log.warning("[%s] ignored end_call(other) issued together with a question; waiting for the answer", self.ctx.target.name)
                continue
            kept.append(tc)
        tool_calls = kept

        text = " ".join(self._turn_spoken)
        assistant: dict = {"role": "assistant", "content": text or None}
        if tool_calls:
            assistant["tool_calls"] = [
                {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}
                for tc in tool_calls
            ]
        self.messages.append(assistant)
        if self._turn_spoken:
            await self.reporter.transcript("agent", text, self._turn_uid or "", True)
        self._turn_uid, self._turn_spoken = None, []

        if not tool_calls and not text:
            # empty generation: nudge once instead of leaving dead air
            line = "Sorry, could you say that again?"
            self.messages.append({"role": "assistant", "content": line})
            await self.reporter.transcript("agent", line, self.new_utterance_id(), True)
            yield line
            return

        for call in tool_calls:
            async for line in self._handle_tool(call):
                yield line

    async def _apply_move(self, move: Move) -> AsyncIterator[str]:
        """Carry out a rule-based decision for the automated part of a call."""
        name = self.ctx.target.name
        if move.kind == "wait":
            log.info("[%s] automated line: waiting", name)
            self.holding = True
        elif move.kind == "say":
            log.info("[%s] automated line: saying %r", name, move.text)
            await self.reporter.transcript("agent", move.text, self.new_utterance_id(), True)
            yield move.text
        elif move.kind == "keys":
            keys = clean_digits(move.text)
            log.info("[%s] automated line: pressing %s", name, keys)
            self.pending_keys += keys
            self.holding = True
            await self.reporter.transcript("agent", f"[Pressed {keys}]", self.new_utterance_id(), True)
        elif move.kind == "intro":
            # A person just came on after a recording, a hold or a menu: they have not heard who we are yet.
            log.info("[%s] a person came on the line: introducing again", name)
            yield await self.open()
        elif move.kind == "end":
            log.info("[%s] automated line: ending (%s)", name, move.reason)
            async for line in self._handle_tool(ToolCall(id="ivr", name="end_call", arguments={"reason": move.reason})):
                yield line

    async def _say(self, sentence: str) -> None:
        self._turn_spoken.append(sentence)
        await self.reporter.transcript("agent", " ".join(self._turn_spoken), self._turn_uid or "", False)

    # --------------------------------------------------------------------- tool handling
    async def _handle_tool(self, call: ToolCall) -> AsyncIterator[str]:
        if call.name == "report_availability":
            result = coerce_result(call.arguments, default_item=self.ctx.intent.item)
            await self._record_result(result)
            self._tool_result(call, "recorded")
            async for line in self._close(closing_line(result.available in ("yes", "partial"))):
                yield line
            self.end_reason = "completed"
        elif call.name == "report_hold":
            self.hold = coerce_hold(call.arguments)
            self._tool_result(call, "recorded")
            async for line in self._close(closing_line(self.hold.success)):
                yield line
            self.end_reason = "completed"
        elif call.name == "wait_for_person":
            self.holding = True
            self._tool_result(call, "waiting silently")
        elif call.name == "press_keys":
            keys = clean_digits(call.arguments.get("digits"))
            if keys:
                self.pending_keys += keys
                self.holding = True  # the menu needs a moment to answer
                log.info("[%s] pressing keys: %s", self.ctx.target.name, keys)
                self._tool_result(call, f"pressed {keys}; wait for the next prompt")
            else:
                self._tool_result(call, "no valid keys; use digits 0-9, * or #")
        elif call.name == "end_call":
            reason = str(call.arguments.get("reason") or "other")
            if reason == "refused" and not REFUSED.search(self._last_heard):
                # The model hung up as "refused", but nobody refused anything (a phone menu said something unexpected).
                reason = "ivr_unresolved" if self.ivr.automated else "other"
            self._tool_result(call, "call ended")
            self.end_reason = reason
            if reason == "closed" and self.result is None and self.ctx.role == "inquiry":
                await self._record_result(
                    ExtractedResult(
                        available="no",
                        closed=True,
                        notes=str(call.arguments.get("notes") or END_REASON_LABELS["closed"]),
                        confidence=0.8,
                    )
                )
            elif reason == "refused":
                self.finished = True
            self.finished = True
        else:
            self._tool_result(call, f"unknown tool {call.name}")

    async def _record_result(self, result: ExtractedResult) -> None:
        self.result = result
        await self.reporter.state("extracting")
        await self.reporter.extracted(result)

    def _tool_result(self, call: ToolCall, content: str) -> None:
        self.messages.append({"role": "tool", "tool_call_id": call.id, "content": content})

    async def _close(self, line: str) -> AsyncIterator[str]:
        self.messages.append({"role": "assistant", "content": line})
        await self.reporter.transcript("agent", line, self.new_utterance_id(), True)
        self.finished = True
        yield line

    async def _give_up(self, code: str, reason: str, *, speak: bool) -> AsyncIterator[str]:
        # A call we could not carry out is a failed call, not an "unknown" answer: no result is recorded, so the
        # dashboard shows why it ended and the commander can move on to a backup business.
        log.warning("[%s] giving up: %s", self.ctx.target.name, reason)
        self.end_reason = code
        if speak:
            self.messages.append({"role": "assistant", "content": FALLBACK_LINE})
            await self.reporter.transcript("agent", FALLBACK_LINE, self.new_utterance_id(), True)
            yield FALLBACK_LINE
        self.finished = True

    # --------------------------------------------------------------------- result
    def outcome(self) -> CallOutcome:
        if self.ctx.role == "reserve":
            if self.hold is not None:
                return CallOutcome("completed", hold=self.hold)
            return CallOutcome("failed", reason=END_REASON_LABELS.get(self.end_reason or "other", "Call ended"))
        if self.result is not None:
            return CallOutcome("completed", result=self.result)
        reason = self.end_reason or "other"
        return CallOutcome("failed", reason=END_REASON_LABELS.get(reason, reason))