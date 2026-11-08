"""Tool calls a model wrote as plain text.

Smaller models (and sometimes bigger ones under load) occasionally print a tool call instead of making one:

    {"reason": "ivr_unresolved", "notes": "Automated message"}
    <function=end_call>{"reason": "voicemail"}</function>

Spoken aloud that is gibberish. The session hides anything that looks like this from the business and, when it can,
runs it as the tool call the model meant.

Author: Saamarth Attray
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

from .types import ToolCall

# Real speech never contains these, so the first sign of one means "from here on this is machine text".
TOOL_TEXT = re.compile(r"<\s*function|<\s*\|?\s*tool|\{|\[\s*\{|```")
_FUNCTION = re.compile(r"<\s*function\s*[=:]?\s*([A-Za-z_]+)")

# A bare JSON object is matched to a tool by a field only that tool has.
_SHAPES = (("available", "report_availability"), ("digits", "press_keys"), ("success", "report_hold"), ("reason", "end_call"))


def _loads(text: str) -> Any:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def parse_text_tool_call(text: str, allowed: set[str]) -> ToolCall | None:
    """The tool call hidden in `text`, or None when it is just noise."""
    text = text.strip()
    name: str | None = None
    args: Any = None

    fn = _FUNCTION.match(text)
    if fn and fn.group(1) in allowed:
        name, args = fn.group(1), _loads(text[fn.end(1) :]) or {}
    else:
        data = _loads(text)
        if isinstance(data, dict):
            if isinstance(data.get("name"), str) and data["name"] in allowed:
                name = data["name"]
                args = data.get("arguments") or data.get("parameters") or {}
                if isinstance(args, str):
                    args = _loads(args) or {}
            else:
                for key, tool in _SHAPES:
                    if key in data and tool in allowed:
                        name, args = tool, data
                        break
    if name is None or not isinstance(args, dict):
        return None
    return ToolCall(id=f"call_{uuid.uuid4().hex[:8]}", name=name, arguments=args)