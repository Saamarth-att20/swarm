"""Picks the brain for a call. Author: Saamarth Attray"""
from __future__ import annotations

from typing import Callable

from ..config import Settings
from ..llm import LLMClient
from .brain import LLMBrain, ResilientBrain, ScriptedBrain
from .types import Brain, BrainContext

BrainFactory = Callable[[BrainContext], Brain]


def default_brain_factory(settings: Settings, llm: LLMClient | None) -> BrainFactory:
    def factory(ctx: BrainContext) -> Brain:
        if llm is not None and settings.llm_enabled and not settings.force_scripted_agents:
            return ResilientBrain(LLMBrain(llm, ctx), ScriptedBrain(ctx))
        return ScriptedBrain(ctx)

    return factory