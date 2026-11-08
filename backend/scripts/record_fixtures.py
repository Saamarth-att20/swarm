"""Record real simulated swarms into contract/fixtures/*.json for the frontend mock server.

    python scripts/record_fixtures.py

Author: Saamarth Attray
"""
import asyncio
import dataclasses
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import load_settings  # noqa: E402
from app.contract import CreateSwarmRequest  # noqa: E402
from app.main import create_app  # noqa: E402

SCENARIOS = {
    "pharmacy": {"query": "Find a pharmacy within 5 miles that has children's amoxicillin in stock right now"},
    "plumber": {"query": "I need an emergency plumber who can come tonight for a burst pipe"},
    "rescue": {
        "query": "12 trays of pasta primavera, 40 turkey sandwiches and 3 gallons of tomato soup, all made today",
        "purpose": "donate", "contact_name": "Luigi's Trattoria", "donor_address": "412 Main St",
        "pickup_by": "before 10 pm", "radius_miles": 8,
    },
}


async def record(name: str, request: dict, out: Path) -> None:
    settings = dataclasses.replace(
        load_settings(), database_url=f"sqlite+aiosqlite:///{tempfile.mkdtemp()}/f.db", redis_url=None,
        force_scripted_agents=True, sim_speed=0,
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        bus = app.state.bus
        sid = await app.state.commander.create_swarm(CreateSwarmRequest(mode="simulated", **request))
        async with bus.subscribe(sid) as sub:
            events = list(await bus.backlog(sid))
            while not events or events[-1]["type"] != "swarm.completed":
                e = await sub.queue.get()
                if e["seq"] > (events[-1]["seq"] if events else 0):
                    events.append(e)
    (out / f"{name}.json").write_text(json.dumps(events, indent=1))
    print(f"{name}: {len(events)} events")


async def main() -> None:
    out = Path(__file__).resolve().parents[2] / "contract" / "fixtures"
    out.mkdir(parents=True, exist_ok=True)
    for name, request in SCENARIOS.items():
        await record(name, request, out)


asyncio.run(main())
