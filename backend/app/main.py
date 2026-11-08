"""FastAPI application: REST + WebSocket API for the dashboard, Twilio webhooks + media stream for live calls.

Run:  uvicorn app.main:app --reload --port 8000

Author: Saamarth Attray
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect

from .agent.factory import BrainFactory, default_brain_factory
from .agent.types import CallOutcome
from .commander import LiveModeUnavailable, SwarmCommander
from .config import Settings, load_settings
from .contract import (
    CONTRACT_VERSION,
    Capabilities,
    CreateSwarmRequest,
    CreateSwarmResponse,
    ReserveResponse,
    SwarmDetail,
    SwarmSummary,
)
from .db import Database, Swarm
from .events import EventBus
from .llm import LLMClient
from .places import Places, build_places
from .repo import Repo
from .telephony.audio_tap import AudioTap
from .telephony.media_bridge import TwilioMediaBridge
from .telephony.speech import DeepgramSTT, DeepgramTTS, SpeechToText, TextToSpeech
from .telephony.twilio_client import (
    LiveCallRegistry,
    NullTelephony,
    Telephony,
    TwilioTelephony,
    twiml_connect_stream,
    twiml_hangup,
    validate_signature,
)

log = logging.getLogger("swarmdial.api")


def _summary(row: Swarm) -> SwarmSummary:
    return SwarmSummary(
        id=row.id, query=row.query, mode=row.mode, status=row.status, created_at=row.created_at  # type: ignore[arg-type]
    )


def create_app(
    settings: Settings | None = None,
    *,
    brain_factory: BrainFactory | None = None,
    telephony: Telephony | None = None,
    places: Places | None = None,
    stt_factory=None,
    tts: TextToSpeech | None = None,
) -> FastAPI:
    """Application factory. Every external dependency can be injected, which is how the tests run offline."""
    settings = settings or load_settings()
    db = Database(settings.database_url)
    repo = Repo(db)
    bus = EventBus(repo, settings.redis_url)
    llm = LLMClient(settings) if settings.llm_enabled else None
    registry = LiveCallRegistry()
    telephony = telephony or (TwilioTelephony(settings) if settings.twilio_enabled else NullTelephony())
    commander = SwarmCommander(
        settings=settings,
        repo=repo,
        bus=bus,
        places=places or build_places(settings),
        brain_factory=brain_factory or default_brain_factory(settings, llm),
        llm=llm,
        telephony=telephony,
        registry=registry,
    )

    if tts is None and settings.deepgram_enabled:
        tts = DeepgramTTS(settings.deepgram_api_key or "", settings.deepgram_tts_voice)
    if stt_factory is None and settings.deepgram_enabled:
        stt_factory = lambda: DeepgramSTT(settings.deepgram_api_key or "", settings.deepgram_stt_model)  # noqa: E731
    tap = AudioTap()
    bridge = TwilioMediaBridge(registry, stt_factory, tts, telephony, tap=tap) if (tts and stt_factory) else None

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await db.create_all()
        await bus.start()
        yield
        await commander.shutdown()
        await bus.stop()
        await db.dispose()

    app = FastAPI(title="Swarm Dial", version=CONTRACT_VERSION, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.commander = commander
    app.state.bus = bus
    app.state.repo = repo
    app.state.registry = registry

    # ------------------------------------------------------------------ REST
    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True, "version": CONTRACT_VERSION}

    @app.get("/api/capabilities", response_model=Capabilities)
    async def capabilities() -> Capabilities:
        return commander.capabilities()

    @app.post("/api/swarms", response_model=CreateSwarmResponse, status_code=201)
    async def create_swarm(req: CreateSwarmRequest) -> CreateSwarmResponse:
        try:
            swarm_id = await commander.create_swarm(req)
        except LiveModeUnavailable as exc:
            raise HTTPException(status_code=400, detail={"message": str(exc), "missing": exc.missing}) from exc
        return CreateSwarmResponse(swarm_id=swarm_id)

    @app.get("/api/swarms", response_model=list[SwarmSummary])
    async def list_swarms(limit: int = 20) -> list[SwarmSummary]:
        return [_summary(row) for row in await repo.list_swarms(min(max(limit, 1), 100))]

    @app.get("/api/swarms/{swarm_id}", response_model=SwarmDetail)
    async def get_swarm(swarm_id: str) -> SwarmDetail:
        row = await repo.get_swarm(swarm_id)
        if row is None:
            raise HTTPException(status_code=404, detail="swarm not found")
        events = await bus.backlog(swarm_id, 0)
        return SwarmDetail.model_validate(
            {"swarm": _summary(row).model_dump(), "events": events, "last_seq": events[-1]["seq"] if events else 0}
        )

    @app.post("/api/swarms/{swarm_id}/cancel")
    async def cancel_swarm(swarm_id: str) -> dict:
        return {"ok": await commander.cancel(swarm_id)}

    @app.post("/api/swarms/{swarm_id}/reserve/{call_id}", response_model=ReserveResponse)
    async def reserve(swarm_id: str, call_id: str) -> ReserveResponse:
        try:
            reserve_call_id = await commander.reserve(swarm_id, call_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return ReserveResponse(ok=True, reserve_call_id=reserve_call_id)

    # ------------------------------------------------------------------ live dashboard stream
    @app.websocket("/ws/swarms/{swarm_id}")
    async def swarm_stream(ws: WebSocket, swarm_id: str, after: int = 0) -> None:
        """Replays every event after `after` (so reconnects are lossless), then streams live."""
        if await repo.get_swarm(swarm_id) is None:
            await ws.close(code=4404)
            return
        await ws.accept()
        pending_get: asyncio.Task | None = None
        recv: asyncio.Task | None = None
        try:
            async with bus.subscribe(swarm_id) as sub:
                last = after
                for event in await bus.backlog(swarm_id, after):
                    await ws.send_json(event)
                    last = event["seq"]
                recv = asyncio.create_task(ws.receive_text())
                while True:
                    if pending_get is None:
                        pending_get = asyncio.create_task(sub.queue.get())
                    done, _ = await asyncio.wait({pending_get, recv}, return_when=asyncio.FIRST_COMPLETED)
                    if pending_get in done:
                        event = pending_get.result()
                        pending_get = None
                        if event["seq"] > last:
                            await ws.send_json(event)
                            last = event["seq"]
                    if recv in done:
                        try:
                            recv.result()  # raises when the client disconnects; otherwise ignore client pings
                        except Exception:
                            return
                        recv = asyncio.create_task(ws.receive_text())
        except WebSocketDisconnect:
            return
        finally:
            for task in (pending_get, recv):
                if task is not None and not task.done():
                    task.cancel()

    # ------------------------------------------------------------------ Twilio
    async def _verified_form(request: Request) -> dict[str, str]:
        form = await request.form()
        params = {key: str(value) for key, value in form.items()}
        if settings.validate_twilio_signature and settings.twilio_auth_token:
            url = settings.public_base_url + request.url.path
            if not validate_signature(url, params, request.headers.get("X-Twilio-Signature"), settings.twilio_auth_token):
                raise HTTPException(status_code=403, detail="invalid Twilio signature")
        return params

    @app.post("/twilio/voice/{call_id}")
    async def twilio_voice(call_id: str, request: Request) -> Response:
        await _verified_form(request)
        live = registry.get(call_id)
        if live is None:
            return Response(twiml_hangup(), media_type="application/xml")
        ws_url = f"{settings.ws_base_url}/twilio/stream/{call_id}"
        return Response(twiml_connect_stream(ws_url, call_id, live.token), media_type="application/xml")

    @app.post("/twilio/status/{call_id}")
    async def twilio_status(call_id: str, request: Request) -> Response:
        params = await _verified_form(request)
        status = params.get("CallStatus", "")
        live = registry.get(call_id)
        if live is not None and not live.future.done():
            failures = {"busy": "Line busy", "no-answer": "No answer", "failed": "Call failed", "canceled": "Call canceled"}
            if status in failures:
                live.resolve(CallOutcome("failed", reason=failures[status]))
            elif status == "completed":
                live.resolve(
                    live.session.outcome()
                    if live.session.finished
                    else CallOutcome("failed", reason="The business hung up")
                )
        return Response(status_code=204)

    @app.websocket("/twilio/stream/{call_id}")
    async def twilio_stream(ws: WebSocket, call_id: str) -> None:
        await ws.accept()
        if bridge is None:
            await ws.close(code=1011)
            return
        await bridge.run(ws)

    @app.websocket("/ws/listen/{call_id}")
    async def listen(ws: WebSocket, call_id: str) -> None:
        """Live audio of one call for the dashboard's Listen button (business on one side, agent on the other)."""
        origin = ws.headers.get("origin")
        if origin and origin not in settings.cors_origins:
            await ws.close(code=1008)  # another website must not be able to eavesdrop on a call
            return
        if registry.get(call_id) is None:
            await ws.close(code=4404)  # not a live call
            return
        await ws.accept()
        queue = tap.subscribe(call_id)
        incoming = asyncio.create_task(ws.receive_text())  # only used to notice the browser leaving
        try:
            while True:
                outgoing = asyncio.create_task(queue.get())
                done, _ = await asyncio.wait({outgoing, incoming}, return_when=asyncio.FIRST_COMPLETED)
                if incoming in done:
                    outgoing.cancel()
                    with contextlib.suppress(BaseException):
                        incoming.result()  # the browser left (or sent something): just stop
                    break
                message = outgoing.result()
                await ws.send_text(message)
                if '"t": "end"' in message:
                    break
        except WebSocketDisconnect:
            pass
        finally:
            incoming.cancel()
            tap.unsubscribe(call_id, queue)
            with contextlib.suppress(Exception):
                await ws.close()

    @app.get("/")
    async def root() -> dict:
        return {"name": "Swarm Dial API", "docs": "/docs", "version": CONTRACT_VERSION}

    return app


def _default_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    return create_app()


app = _default_app()