"""Verify every key and URL live mode needs, without placing a call. Run from backend/:  python scripts/preflight.py

Author: Saamarth Attray
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import load_settings  # noqa: E402
from app.preflight import run_preflight  # noqa: E402


async def main() -> int:
    checks = await run_preflight(load_settings())
    for c in checks:
        mark = "✓" if c.ok and not c.warn else "!" if c.ok else "✗"
        print(f"{mark} {c.name:<16} {c.detail}")
    failed = [c for c in checks if not c.ok]
    print("\nReady for live calls." if not failed else f"\n{len(failed)} thing(s) to fix before live calls will work.")
    return 1 if failed else 0


sys.exit(asyncio.run(main()))
