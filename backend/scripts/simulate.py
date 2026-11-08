"""Run a full simulated swarm in-process and print the live event stream. No keys, no server needed.

    python scripts/simulate.py "Find a pharmacy within 5 miles with children's amoxicillin in stock"
    SIM_SPEED=0 python scripts/simulate.py "emergency plumber tonight"     # instant

Author: Saamarth Attray
"""
import asyncio
import dataclasses
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import load_settings  # noqa: E402
from app.contract import CreateSwarmRequest  # noqa: E402
from app.main import create_app  # noqa: E402

ICON = {"queued": "…", "dialing": "📞", "talking": "🗣️ ", "extracting": "🧠", "completed": "✅", "failed": "❌", "cancelled": "⛔"}


def render(e: dict) -> str | None:
    d, t = e["data"], e["type"]
    if t == "swarm.created":
        return f"#{e['seq']:>3} SWARM  {len(d['targets'])} targets · intent: {d['intent']['item']}"
    if t == "call.state":
        return f"#{e['seq']:>3} {ICON.get(d['state'], '?')} {d['target_id']:<4} {d['state']} {d.get('reason') or ''}"
    if t == "call.transcript" and d["is_final"]:
        return f"#{e['seq']:>3}    {d['target_id']:<4} {d['speaker']:>8}: {d['text']}"
    if t == "call.extracted":
        r = d["result"]
        return f"#{e['seq']:>3} 🧠 {d['target_id']:<4} available={r['available']} price={r.get('price')} qty={r.get('quantity')}"
    if t in ("swarm.reroute", "swarm.knowledge", "swarm.reserved"):
        return f"#{e['seq']:>3} 🎯 {d.get('message') or d.get('note')}"
    if t == "swarm.ranked":
        return f"#{e['seq']:>3} 🏆 best={d.get('best_call_id')} ({len(d['rankings'])} ranked)"
    if t == "swarm.completed":
        return f"#{e['seq']:>3} DONE   {d['status']}: {d['calls_made']} calls, {d['positives']} matches, {d['elapsed_s']}s"
    return None


async def main(query: str) -> None:
    settings = dataclasses.replace(
        load_settings(),
        database_url=f"sqlite+aiosqlite:///{tempfile.mkdtemp()}/sim.db",
        redis_url=None,
        force_scripted_agents=True,
        sim_speed=float(os.environ.get("SIM_SPEED", "0.3")),
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        commander, bus = app.state.commander, app.state.bus
        swarm_id = await commander.create_swarm(CreateSwarmRequest(query=query, mode="simulated"))
        async with bus.subscribe(swarm_id) as sub:
            last = 0
            for e in await bus.backlog(swarm_id):
                if (line := render(e)):
                    print(line)
                last = e["seq"]
                if e["type"] == "swarm.completed":
                    return
            while True:
                e = await sub.queue.get()
                if e["seq"] <= last:
                    continue
                last = e["seq"]
                if (line := render(e)):
                    print(line)
                if e["type"] == "swarm.completed":
                    return


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "Find a pharmacy within 5 miles that has children's amoxicillin in stock"))
