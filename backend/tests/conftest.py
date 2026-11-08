"""Shared fixtures. Author: Saamarth Attray"""
from __future__ import annotations

import dataclasses

import pytest

from app.agent.factory import default_brain_factory
from app.commander import SwarmCommander
from app.config import Settings
from app.db import Database
from app.events import EventBus
from app.places import MockPlaces
from app.repo import Repo
from app.telephony.twilio_client import LiveCallRegistry, NullTelephony


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db", sim_speed=0.0, dial_stagger_s=0.0)


@pytest.fixture
async def stack(settings):
    """A full commander stack on a temp database (simulated mode, scripted agents, mock places)."""
    db = Database(settings.database_url)
    await db.create_all()
    repo = Repo(db)
    bus = EventBus(repo)

    def build(places=None, **overrides) -> SwarmCommander:
        cfg = dataclasses.replace(settings, **overrides) if overrides else settings
        return SwarmCommander(
            settings=cfg,
            repo=repo,
            bus=bus,
            places=places or MockPlaces(),
            brain_factory=default_brain_factory(cfg, None),
            llm=None,
            telephony=NullTelephony(),
            registry=LiveCallRegistry(),
        )

    class Stack:
        pass

    s = Stack()
    s.db, s.repo, s.bus, s.build = db, repo, bus, build
    yield s
    await db.dispose()
