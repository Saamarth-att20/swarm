"""REST + WebSocket API through FastAPI's TestClient, fully offline. Author: Saamarth Attray"""
import pytest
from fastapi.testclient import TestClient

from app.contract import EVENT_ADAPTER
from app.main import create_app


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


def read_until_done(ws):
    events = []
    while True:
        ev = ws.receive_json()
        events.append(ev)
        if ev["type"] == "swarm.completed":
            return events


def create(client, **body):
    body.setdefault("query", "Find a pharmacy within 5 miles that has children's amoxicillin in stock right now")
    r = client.post("/api/swarms", json=body)
    assert r.status_code == 201, r.text
    return r.json()["swarm_id"]


def test_health_and_capabilities(client):
    assert client.get("/api/health").json()["ok"] is True
    caps = client.get("/api/capabilities").json()
    assert caps["live_available"] is False and caps["live_missing"] and caps["places_provider"] == "mock"
    assert caps["llm_provider"] == "scripted"


def test_validation_errors(client):
    assert client.post("/api/swarms", json={"query": "x"}).status_code == 422
    assert client.post("/api/swarms", json={"query": "valid query here", "radius_miles": 500}).status_code == 422
    assert client.get("/api/swarms/does_not_exist").status_code == 404


def test_live_mode_is_refused_without_configuration(client):
    r = client.post("/api/swarms", json={"query": "find a plumber tonight", "mode": "live"})
    assert r.status_code == 400
    assert r.json()["detail"]["missing"]


def test_stream_whole_swarm_over_websocket(client):
    sid = create(client, lat=38.9, lng=-77.0)
    with client.websocket_connect(f"/ws/swarms/{sid}") as ws:
        events = read_until_done(ws)
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    for e in events:
        EVENT_ADAPTER.validate_python(e)
    types = {e["type"] for e in events}
    assert {"swarm.created", "call.state", "call.transcript", "call.extracted", "swarm.ranked", "swarm.completed"} <= types


def test_reconnect_replays_only_missed_events(client):
    sid = create(client)
    with client.websocket_connect(f"/ws/swarms/{sid}") as ws:
        everything = read_until_done(ws)
    cut = len(everything) // 2
    seq = everything[cut]["seq"]
    with client.websocket_connect(f"/ws/swarms/{sid}?after={seq}") as ws:
        replay = read_until_done(ws)
    assert replay[0]["seq"] == seq + 1 and replay[-1]["type"] == "swarm.completed"
    assert len(replay) == len(everything) - cut - 1


def test_rest_detail_snapshot_and_listing(client):
    sid = create(client)
    with client.websocket_connect(f"/ws/swarms/{sid}") as ws:
        read_until_done(ws)
    detail = client.get(f"/api/swarms/{sid}").json()
    assert detail["swarm"]["id"] == sid and detail["swarm"]["status"] in ("running", "completed")
    assert detail["events"][0]["type"] == "swarm.created" and detail["last_seq"] == detail["events"][-1]["seq"]
    listing = client.get("/api/swarms").json()
    assert listing[0]["id"] == sid


def test_websocket_for_unknown_swarm_is_rejected(client):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/swarms/nope") as ws:
            ws.receive_json()


def test_reserve_flow(client):
    sid = create(client)
    with client.websocket_connect(f"/ws/swarms/{sid}") as ws:
        events = read_until_done(ws)
        ranked = next(e for e in events if e["type"] == "swarm.ranked")["data"]
        assert ranked["best_call_id"], "simulated pharmacy search should always find a match"
        r = client.post(f"/api/swarms/{sid}/reserve/{ranked['best_call_id']}")
        assert r.status_code == 200 and r.json()["ok"]
        while True:
            ev = ws.receive_json()
            if ev["type"] == "swarm.reserved":
                break
    assert ev["data"]["reserve_call_id"] == r.json()["reserve_call_id"]
    assert ev["data"]["message"]
    assert client.post(f"/api/swarms/{sid}/reserve/not_a_call").status_code in (404, 409)
    assert client.post("/api/swarms/missing/reserve/x").status_code == 404


def test_cancel_endpoint(client):
    sid = create(client)
    r = client.post(f"/api/swarms/{sid}/cancel")
    assert r.status_code == 200
    with client.websocket_connect(f"/ws/swarms/{sid}") as ws:
        events = read_until_done(ws)
    assert events[-1]["data"]["status"] in ("cancelled", "completed")


def test_listen_endpoint_rejects_unknown_calls_and_foreign_websites(client):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as gone:
        with client.websocket_connect("/ws/listen/not-a-call"):
            pass
    assert gone.value.code == 4404
    with pytest.raises(WebSocketDisconnect) as blocked:
        with client.websocket_connect("/ws/listen/not-a-call", headers={"origin": "https://evil.example"}):
            pass
    assert blocked.value.code == 1008