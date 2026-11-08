"""Persistent schema: Users, Swarms, Tasks, Calls, ExtractedData (+ an append-only event log).

SQLite by default for zero-setup local dev; point DATABASE_URL at Postgres for production.

Author: Saamarth Attray
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class Swarm(Base):
    __tablename__ = "swarms"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    query: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="running")
    intent: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    origin_lat: Mapped[float] = mapped_column(Float)
    origin_lng: Mapped[float] = mapped_column(Float)
    radius_miles: Mapped[float] = mapped_column(Float)
    best_call_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, default=time.time, index=True)
    completed_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class Task(Base):
    """One unit of work: 'find out what this business has'. A swarm has many; reroutes add more."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    swarm_id: Mapped[str] = mapped_column(ForeignKey("swarms.id"), index=True)
    target_id: Mapped[str] = mapped_column(String(32))
    target: Mapped[dict] = mapped_column(JSON)
    tier: Mapped[str] = mapped_column(String(16), default="primary")
    role: Mapped[str] = mapped_column(String(16), default="inquiry")
    status: Mapped[str] = mapped_column(String(16), default="queued")
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    swarm_id: Mapped[str] = mapped_column(ForeignKey("swarms.id"), index=True)
    target_id: Mapped[str] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(16), default="inquiry")
    provider_sid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    state: Mapped[str] = mapped_column(String(16), default="queued")
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    started_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ended_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    duration_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class ExtractedData(Base):
    __tablename__ = "extracted_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id"), unique=True)
    swarm_id: Mapped[str] = mapped_column(ForeignKey("swarms.id"), index=True)
    available: Mapped[str] = mapped_column(String(16))
    item: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    can_hold: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    wait_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    alternatives: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    referral_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    referral_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    closed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    raw: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class SwarmEventRow(Base):
    """Append-only log of every wire event; lets clients reconnect and replay from any seq."""

    __tablename__ = "swarm_events"
    __table_args__ = (UniqueConstraint("swarm_id", "seq", name="uq_swarm_events_swarm_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    swarm_id: Mapped[str] = mapped_column(ForeignKey("swarms.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(32))
    data: Mapped[dict] = mapped_column(JSON)
    ts: Mapped[float] = mapped_column(Float)


def normalize_database_url(url: str) -> str:
    """Accept the address a hosted provider gives you (Neon, Supabase, Render...) and make it work with our driver.

    Providers hand out `postgresql://...?sslmode=require`. The async driver (asyncpg) spells that `ssl=require` and
    rejects `sslmode` / `channel_binding`, so those are rewritten or dropped here.
    """
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    elif url.startswith("sqlite://") and "+aiosqlite" not in url:
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    if url.startswith("postgresql+asyncpg://") and "?" in url:
        base, query = url.split("?", 1)
        kept: list[str] = []
        for part in query.split("&"):
            key, _, value = part.partition("=")
            if key == "sslmode":
                kept.append("ssl=" + value)
            elif key in ("channel_binding", "options"):
                continue
            elif part:
                kept.append(part)
        url = base + ("?" + "&".join(kept) if kept else "")
    return url


class Database:
    def __init__(self, url: str):
        self.url = normalize_database_url(url)
        kwargs: dict = {}
        if self.url.startswith("sqlite"):
            kwargs["connect_args"] = {"timeout": 30}
        else:
            kwargs["pool_pre_ping"] = True
        self.engine = create_async_engine(self.url, **kwargs)
        if self.url.startswith("sqlite"):

            @event.listens_for(self.engine.sync_engine, "connect")
            def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - trivial
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        self._sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_all(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self._sessionmaker() as session:
            yield session

    async def dispose(self) -> None:
        await self.engine.dispose()
