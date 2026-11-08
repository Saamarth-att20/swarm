"""LLM tool definitions + argument coercion (models are sloppy with types; the contract is not).

Author: Saamarth Attray
"""
from __future__ import annotations

import re
from typing import Any

from ..contract import ExtractedResult
from .types import HoldResult

REPORT_AVAILABILITY = {
    "type": "function",
    "function": {
        "name": "report_availability",
        "description": (
            "Call this exactly once, as soon as the business has clearly told you whether they have what the "
            "customer needs (product in stock / service or appointment available). Include every detail you "
            "learned. Do not call it before they have actually answered."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "available": {
                    "type": "string",
                    "enum": ["yes", "no", "partial", "unknown"],
                    "description": "yes = they have it; partial = they have something close but not exactly it; "
                    "no = they do not; unknown = could not find out.",
                },
                "item_matched": {"type": "string", "description": "What they actually have / can offer."},
                "price": {"type": "number", "description": "Price in dollars, if quoted."},
                "quantity": {"type": "integer", "description": "How many they have, if said."},
                "can_hold": {"type": "boolean", "description": "Whether they can hold/reserve one for the customer."},
                "wait_minutes": {"type": "integer", "description": "Wait time / time until service, in minutes."},
                "alternatives": {"type": "array", "items": {"type": "string"}, "description": "Substitutes offered."},
                "referral_name": {"type": "string", "description": "Another business they recommended."},
                "referral_phone": {"type": "string"},
                "closed": {"type": "boolean", "description": "True if the business is closed / not taking requests."},
                "notes": {"type": "string", "description": "One short sentence of anything else useful."},
                "confidence": {"type": "number", "description": "0 to 1: how sure you are about this report."},
                "hours": {"type": "string", "description": "Food pantries: today's distribution hours (seekers) or drop-off hours (donors), e.g. '10am to 2pm'."},
                "requirements": {"type": "string", "description": "Food pantries: what someone must bring or who qualifies (ID, proof of address, appointment, zip codes)."},
                "needs": {"type": "array", "items": {"type": "string"}, "description": "Donors: items the pantry needs most right now."},
                "perishables_ok": {"type": "boolean", "description": "Donors: whether they can take fresh or refrigerated food."},
                "can_pickup": {"type": "boolean", "description": "Food rescue: true if they can send someone to pick the food up; false if it must be dropped off. Put the pickup ETA in wait_minutes."},
            },
            "required": ["available"],
        },
    },
}

END_CALL = {
    "type": "function",
    "function": {
        "name": "end_call",
        "description": "Hang up. Use when finished, or when the call cannot continue.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "enum": [
                        "completed",
                        "closed",
                        "voicemail",
                        "refused",
                        "ivr_unresolved",
                        "no_response",
                        "other",
                    ],
                },
                "notes": {"type": "string"},
            },
            "required": ["reason"],
        },
    },
}

REPORT_HOLD = {
    "type": "function",
    "function": {
        "name": "report_hold",
        "description": "Call once the business has confirmed (or refused) holding the item / slot for the customer.",
        "parameters": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "confirmation": {"type": "string", "description": "Name it is held under, code, or pickup details."},
                "notes": {"type": "string"},
            },
            "required": ["success"],
        },
    },
}


WAIT_FOR_PERSON = {
    "type": "function",
    "function": {
        "name": "wait_for_person",
        "description": (
            "Stay silent and keep the line open. Use it when a recording or automated assistant says to hold, that it "
            "is transferring you, or when hold music is playing. Do not use it when a real person is talking to you."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}


PRESS_KEYS = {
    "type": "function",
    "function": {
        "name": "press_keys",
        "description": (
            "Press keys on the phone keypad, like 'press 3 to speak with the pharmacy'. Use it when an automated menu "
            "offers a numbered option that leads to a person or to the department you need (pharmacy staff, "
            "representative, operator). Send only the digits, for example \"3\" or \"0\". Do not say anything else in the "
            "same turn."
        ),
        "parameters": {
            "type": "object",
            "properties": {"digits": {"type": "string", "description": "Keys to press: digits 0-9, * or #."}},
            "required": ["digits"],
        },
    },
}


_FOOD_ONLY_FIELDS = ("hours", "requirements", "needs", "perishables_ok", "can_pickup")


def _slim_report() -> dict:
    """The same tool without the food-pantry fields: a product or service call never needs them, and every token of the
    request counts against the model's per-minute limit."""
    function = dict(REPORT_AVAILABILITY["function"])
    parameters = dict(function["parameters"])
    parameters["properties"] = {k: v for k, v in parameters["properties"].items() if k not in _FOOD_ONLY_FIELDS}
    function["parameters"] = parameters
    return {"type": "function", "function": function}


REPORT_AVAILABILITY_SLIM = _slim_report()


def tools_for(role: str, kind: str | None = None) -> list[dict]:
    if role == "reserve":
        return [REPORT_HOLD, WAIT_FOR_PERSON, PRESS_KEYS, END_CALL]
    report = REPORT_AVAILABILITY if kind in ("food", "donation") else REPORT_AVAILABILITY_SLIM
    return [report, WAIT_FOR_PERSON, PRESS_KEYS, END_CALL]


# ----------------------------------------------------------------------------- coercion
def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group()) if match else None


def _to_int(value: Any) -> int | None:
    number = _to_float(value)
    return int(round(number)) if number is not None else None


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in ("true", "yes", "y", "1"):
        return True
    if text in ("false", "no", "n", "0"):
        return False
    return None


def _to_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        value = re.split(r",| and ", value)
    return [str(v).strip() for v in value if str(v).strip()]


def coerce_result(args: dict[str, Any], default_item: str | None = None) -> ExtractedResult:
    available = str(args.get("available", "unknown")).strip().lower()
    if available not in ("yes", "no", "partial", "unknown"):
        available = "unknown"
    alternatives = args.get("alternatives") or []
    if isinstance(alternatives, str):
        alternatives = [alternatives]
    confidence = _to_float(args.get("confidence"))
    return ExtractedResult(
        available=available,  # type: ignore[arg-type]
        item=_to_str(args.get("item_matched") or args.get("item")) or default_item,
        price=_to_float(args.get("price")),
        quantity=_to_int(args.get("quantity")),
        can_hold=_to_bool(args.get("can_hold")),
        wait_minutes=_to_int(args.get("wait_minutes")),
        alternatives=[str(a) for a in alternatives if str(a).strip()],
        referral_name=_to_str(args.get("referral_name")),
        referral_phone=_to_str(args.get("referral_phone")),
        closed=_to_bool(args.get("closed")),
        notes=_to_str(args.get("notes")),
        confidence=min(1.0, max(0.0, confidence if confidence is not None else 0.8)),
        hours=_to_str(args.get("hours")),
        requirements=_to_str(args.get("requirements")),
        needs=_to_list(args.get("needs")),
        perishables_ok=_to_bool(args.get("perishables_ok")),
        can_pickup=_to_bool(args.get("can_pickup")),
    )


def coerce_hold(args: dict[str, Any]) -> HoldResult:
    return HoldResult(
        success=bool(_to_bool(args.get("success"))),
        confirmation=_to_str(args.get("confirmation")),
        notes=_to_str(args.get("notes")),
    )