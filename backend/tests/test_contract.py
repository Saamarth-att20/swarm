"""The wire contract: every event shape validates, and the JSON schema exports. Author: Saamarth Attray"""
import json

import pytest
from pydantic import ValidationError

from app.contract import (
    EVENT_ADAPTER,
    CallStateData,
    CallTranscriptData,
    ContractBundle,
    ExtractedResult,
    Intent,
    LatLng,
    SwarmCompletedData,
    SwarmCreatedData,
    Target,
    make_event,
)


def _intent() -> Intent:
    return Intent(raw_query="q", item="amoxicillin", category="pharmacy", kind="product", place_query="pharmacy",
                  radius_miles=5, summary="Find amoxicillin")


def test_every_event_type_roundtrips():
    target = Target(id="t1", name="CVS", lat=1, lng=2, distance_miles=1.2)
    payloads = [
        SwarmCreatedData(query="q", mode="simulated", intent=_intent(), origin=LatLng(lat=1, lng=2), targets=[target]),
        CallStateData(call_id="c1", target_id="t1", state="talking"),
        CallTranscriptData(call_id="c1", target_id="t1", utterance_id="u1", speaker="agent", text="hi", is_final=False),
        SwarmCompletedData(status="completed", calls_made=1, calls_completed=1, calls_failed=0, positives=1, elapsed_s=2.0),
    ]
    for i, data in enumerate(payloads, start=1):
        event = make_event("s1", i, data)
        parsed = EVENT_ADAPTER.validate_python(event)
        assert parsed.type == data.event_type
        assert parsed.seq == i


def test_unknown_event_type_is_rejected():
    with pytest.raises(ValidationError):
        EVENT_ADAPTER.validate_python({"seq": 1, "swarm_id": "s", "ts": 0, "type": "nope", "data": {}})


def test_extracted_result_bounds():
    with pytest.raises(ValidationError):
        ExtractedResult(available="yes", confidence=1.5)
    with pytest.raises(ValidationError):
        ExtractedResult(available="maybe")  # type: ignore[arg-type]


def test_schema_exports_and_names_all_events():
    schema = ContractBundle.model_json_schema(mode="serialization")
    text = json.dumps(schema)
    for name in ["SwarmCreatedEvent", "CallStateEvent", "CallTranscriptEvent", "CallExtractedEvent",
                 "SwarmRerouteEvent", "SwarmKnowledgeEvent", "SwarmRankedEvent", "SwarmReservedEvent",
                 "SwarmCompletedEvent", "CreateSwarmRequest", "Capabilities"]:
        assert name in text
