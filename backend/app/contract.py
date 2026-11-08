"""Swarm Dial wire contract: the single source of truth shared with the frontend.

Everything the browser ever receives (REST bodies and WebSocket events) is defined here.
`scripts/export_contract.py` turns this file into `contract/schema.json` and the frontend's
generated `types.ts`, so the two sides can never drift apart.

Author: Saamarth Attray
"""
from __future__ import annotations

import time
from typing import Annotated, ClassVar, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter

CONTRACT_VERSION = "1.0.0"

CallState = Literal["queued", "dialing", "talking", "extracting", "completed", "failed", "cancelled"]
Availability = Literal["yes", "no", "partial", "unknown"]
Speaker = Literal["agent", "business"]
Mode = Literal["live", "simulated"]
Priority = Literal["balanced", "price", "distance", "speed"]
CallRole = Literal["inquiry", "reserve"]


# --------------------------------------------------------------------------- shared models
class LatLng(BaseModel):
    lat: float
    lng: float


class Target(BaseModel):
    id: str
    name: str
    address: str | None = None
    phone: str | None = None
    lat: float
    lng: float
    distance_miles: float
    open_now: bool | None = None
    rating: float | None = None
    tier: Literal["primary", "backup"] = "primary"
    source: Literal["places", "mock", "demo", "referral"] = "mock"


class Intent(BaseModel):
    raw_query: str
    item: str
    category: str
    kind: Literal["product", "service", "appointment", "food", "donation"]
    place_query: str
    urgency: Literal["now", "today", "flexible"] = "now"
    priority: Priority = "balanced"
    radius_miles: float
    summary: str


class ExtractedResult(BaseModel):
    available: Availability
    item: str | None = None
    price: float | None = None
    currency: str = "USD"
    quantity: int | None = None
    can_hold: bool | None = None
    wait_minutes: int | None = None
    alternatives: list[str] = Field(default_factory=list)
    referral_name: str | None = None
    referral_phone: str | None = None
    closed: bool | None = None
    notes: str | None = None
    confidence: float = Field(default=0.8, ge=0, le=1)
    # Food access: distribution hours (seekers) or drop-off hours (donors), what to bring / who qualifies,
    # what the pantry needs most right now, and whether it can take fresh food.
    hours: str | None = None
    requirements: str | None = None
    needs: list[str] = Field(default_factory=list)
    perishables_ok: bool | None = None
    # Food rescue (donation): True when the organization can send someone to pick the food up.
    # `wait_minutes` then means "pickup ETA".
    can_pickup: bool | None = None


class RankedItem(BaseModel):
    call_id: str
    target_id: str
    rank: int
    score: float
    reasons: list[str]


# --------------------------------------------------------------------------- event payloads
class _Data(BaseModel):
    event_type: ClassVar[str]


class SwarmCreatedData(_Data):
    event_type: ClassVar[str] = "swarm.created"
    query: str
    mode: Mode
    intent: Intent
    origin: LatLng
    targets: list[Target]


class CallStateData(_Data):
    event_type: ClassVar[str] = "call.state"
    call_id: str
    target_id: str
    state: CallState
    role: CallRole = "inquiry"
    reason: str | None = None


class CallTranscriptData(_Data):
    event_type: ClassVar[str] = "call.transcript"
    call_id: str
    target_id: str
    utterance_id: str
    speaker: Speaker
    text: str
    is_final: bool


class CallExtractedData(_Data):
    event_type: ClassVar[str] = "call.extracted"
    call_id: str
    target_id: str
    result: ExtractedResult


class SwarmRerouteData(_Data):
    event_type: ClassVar[str] = "swarm.reroute"
    from_call_id: str | None = None
    from_target_id: str | None = None
    to_target_id: str
    to_call_id: str
    kind: Literal["closed", "no_stock", "failed", "referral", "backup"]
    reason: str
    new_target: Target | None = None  # set when the destination is a brand-new (referral) target


class SwarmKnowledgeData(_Data):
    event_type: ClassVar[str] = "swarm.knowledge"
    note: str
    source_call_id: str | None = None


class SwarmRankedData(_Data):
    event_type: ClassVar[str] = "swarm.ranked"
    rankings: list[RankedItem]
    best_call_id: str | None = None
    criteria: str


class SwarmReservedData(_Data):
    event_type: ClassVar[str] = "swarm.reserved"
    call_id: str
    target_id: str
    reserve_call_id: str
    success: bool
    confirmation: str | None = None
    message: str


class SwarmCompletedData(_Data):
    event_type: ClassVar[str] = "swarm.completed"
    status: Literal["completed", "cancelled", "error"]
    calls_made: int
    calls_completed: int
    calls_failed: int
    positives: int
    elapsed_s: float
    error: str | None = None


# --------------------------------------------------------------------------- events (envelope + payload)
class _EventBase(BaseModel):
    seq: int
    swarm_id: str
    ts: float


class SwarmCreatedEvent(_EventBase):
    type: Literal["swarm.created"] = "swarm.created"
    data: SwarmCreatedData


class CallStateEvent(_EventBase):
    type: Literal["call.state"] = "call.state"
    data: CallStateData


class CallTranscriptEvent(_EventBase):
    type: Literal["call.transcript"] = "call.transcript"
    data: CallTranscriptData


class CallExtractedEvent(_EventBase):
    type: Literal["call.extracted"] = "call.extracted"
    data: CallExtractedData


class SwarmRerouteEvent(_EventBase):
    type: Literal["swarm.reroute"] = "swarm.reroute"
    data: SwarmRerouteData


class SwarmKnowledgeEvent(_EventBase):
    type: Literal["swarm.knowledge"] = "swarm.knowledge"
    data: SwarmKnowledgeData


class SwarmRankedEvent(_EventBase):
    type: Literal["swarm.ranked"] = "swarm.ranked"
    data: SwarmRankedData


class SwarmReservedEvent(_EventBase):
    type: Literal["swarm.reserved"] = "swarm.reserved"
    data: SwarmReservedData


class SwarmCompletedEvent(_EventBase):
    type: Literal["swarm.completed"] = "swarm.completed"
    data: SwarmCompletedData


SwarmEvent = Annotated[
    Union[
        SwarmCreatedEvent,
        CallStateEvent,
        CallTranscriptEvent,
        CallExtractedEvent,
        SwarmRerouteEvent,
        SwarmKnowledgeEvent,
        SwarmRankedEvent,
        SwarmReservedEvent,
        SwarmCompletedEvent,
    ],
    Field(discriminator="type"),
]

EVENT_ADAPTER: TypeAdapter = TypeAdapter(SwarmEvent)


def make_event(swarm_id: str, seq: int, data: _Data) -> dict:
    """Wrap a payload model in the wire envelope."""
    return {
        "seq": seq,
        "swarm_id": swarm_id,
        "ts": time.time(),
        "type": data.event_type,
        "data": data.model_dump(mode="json"),
    }


# --------------------------------------------------------------------------- REST models
class CreateSwarmRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    radius_miles: float = Field(default=10, gt=0, le=50)
    mode: Mode = "simulated"
    priority: Priority | None = None
    max_calls: int | None = Field(default=None, ge=1, le=30)
    stop_after_matches: int | None = Field(default=None, ge=1, le=10)
    contact_name: str | None = Field(default=None, max_length=60)  # for rescues: the donor (restaurant) name
    # Food rescue: `purpose="donate"` means `query` is the exact description of the surplus food and the swarm
    # phones food banks / pantries / shelters to find who can pick it up soonest.
    purpose: Literal["find", "donate"] = "find"
    donor_address: str | None = Field(default=None, max_length=120)  # where the food is picked up
    pickup_by: str | None = Field(default=None, max_length=60)  # e.g. "before 9:30 pm"
    user_id: str | None = Field(default=None, max_length=64)


class CreateSwarmResponse(BaseModel):
    swarm_id: str


class SwarmSummary(BaseModel):
    id: str
    query: str
    mode: Mode
    status: Literal["running", "completed", "cancelled", "error"]
    created_at: float


class SwarmDetail(BaseModel):
    swarm: SwarmSummary
    events: list[SwarmEvent]
    last_seq: int


class ReserveResponse(BaseModel):
    ok: bool
    reserve_call_id: str


class Capabilities(BaseModel):
    version: str
    live_available: bool
    live_missing: list[str]
    llm_provider: str
    places_provider: Literal["google", "mock"]
    demo_targets: int


class ContractBundle(BaseModel):
    """Never sent over the wire; exists so one schema covers every type the frontend needs."""

    version: str = CONTRACT_VERSION
    event: SwarmEvent
    create_swarm_request: CreateSwarmRequest
    create_swarm_response: CreateSwarmResponse
    swarm_detail: SwarmDetail
    reserve_response: ReserveResponse
    capabilities: Capabilities
