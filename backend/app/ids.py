"""Short, URL-safe ids. Author: Saamarth Attray"""
from __future__ import annotations

import uuid


def new_id(prefix: str, length: int = 8) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:length]}"
