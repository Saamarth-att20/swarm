"""Shared agent types. Author: Saamarth Attray"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal, Protocol

from ..contract import CallState, ExtractedResult, Intent, Target


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class BrainEvent:
    kind: Literal["text", "tool_call"]
    text: str = ""
    tool_call: ToolCall | None = None


@dataclass
class BrainContext:
    intent: Intent
    target: Target
    knowledge: list[str] = field(default_factory=list)
    role: Literal["inquiry", "reserve"] = "inquiry"
    contact_name: str | None = None  # the customer, or for food rescues the donor (restaurant)
    donor_address: str | None = None
    pickup_by: str | None = None
    # for role == "reserve": what we learned on the earlier inquiry call
    prior_result: ExtractedResult | None = None


@dataclass
class HoldResult:
    success: bool
    confirmation: str | None = None
    notes: str | None = None


@dataclass
class CallOutcome:
    state: Literal["completed", "failed", "cancelled"]
    reason: str | None = None
    result: ExtractedResult | None = None
    hold: HoldResult | None = None


class Brain(Protocol):
    """Decides what the agent says next. Streams text chunks and/or tool calls."""

    def respond(self, messages: list[dict]) -> AsyncIterator[BrainEvent]: ...


class Reporter(Protocol):
    """Where a call session reports what is happening (the commander persists + broadcasts it)."""

    async def state(self, state: CallState, reason: str | None = None) -> None: ...

    async def transcript(self, speaker: str, text: str, utterance_id: str, is_final: bool) -> None: ...

    async def extracted(self, result: ExtractedResult) -> None: ...
