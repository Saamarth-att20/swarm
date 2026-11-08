"""Ranks the businesses that said yes (or offered a close substitute).

Author: Saamarth Attray
"""
from __future__ import annotations

from dataclasses import dataclass

from .contract import ExtractedResult, Intent, RankedItem, Target

WEIGHTS: dict[str, dict[str, float]] = {
    "balanced": {"avail": 0.40, "price": 0.20, "distance": 0.20, "speed": 0.10, "hold": 0.10},
    "price": {"avail": 0.30, "price": 0.40, "distance": 0.10, "speed": 0.10, "hold": 0.10},
    "distance": {"avail": 0.30, "price": 0.10, "distance": 0.40, "speed": 0.10, "hold": 0.10},
    "speed": {"avail": 0.30, "price": 0.10, "distance": 0.15, "speed": 0.35, "hold": 0.10},
}
# Food rescue: the food is perishable, so soonest pickup matters most; there is no price.
DONATION_WEIGHTS = {"avail": 0.30, "price": 0.0, "distance": 0.15, "speed": 0.40, "hold": 0.15}
CRITERIA = {
    "balanced": "Balanced: availability, price, distance, wait time and hold-ability",
    "price": "Weighted toward lowest price",
    "distance": "Weighted toward closest location",
    "speed": "Weighted toward shortest wait",
}
DONATION_CRITERIA = "Soonest pickup first, then distance and whether they take fresh food"


@dataclass
class Candidate:
    call_id: str
    target: Target
    result: ExtractedResult


def _norm_low_is_good(value: float | None, values: list[float]) -> float:
    if value is None or not values:
        return 0.5
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return 1.0
    return 1.0 - (value - lo) / (hi - lo)


def rank(candidates: list[Candidate], intent: Intent) -> tuple[list[RankedItem], str | None, str]:
    live = [c for c in candidates if c.result.available in ("yes", "partial")]
    donation = intent.kind == "donation"
    criteria = DONATION_CRITERIA if donation else CRITERIA.get(intent.priority, CRITERIA["balanced"])
    if not live:
        return [], None, criteria

    weights = DONATION_WEIGHTS if donation else WEIGHTS.get(intent.priority, WEIGHTS["balanced"])
    prices = [c.result.price for c in live if c.result.price is not None]
    distances = [c.target.distance_miles for c in live]
    waits = [float(c.result.wait_minutes) for c in live if c.result.wait_minutes is not None]
    best_price = min(prices) if prices else None

    scored: list[tuple[float, Candidate, list[str]]] = []
    for c in live:
        r, t = c.result, c.target
        avail = 1.0 if r.available == "yes" else 0.5
        price = _norm_low_is_good(r.price, prices)
        distance = _norm_low_is_good(t.distance_miles, distances)
        speed = _norm_low_is_good(float(r.wait_minutes), waits) if r.wait_minutes is not None else 0.5
        hold_flag = r.can_pickup if donation else r.can_hold
        hold = 1.0 if hold_flag else (0.3 if hold_flag is None else 0.0)
        score = (
            weights["avail"] * avail
            + weights["price"] * price
            + weights["distance"] * distance
            + weights["speed"] * speed
            + weights["hold"] * hold
        )
        score *= 0.8 + 0.2 * r.confidence
        if donation and r.perishables_ok is False:
            score *= 0.6  # can't take fresh or refrigerated food

        if donation:
            reasons = ["Can pick up" if r.can_pickup is not False else "Drop-off only"]
            if r.wait_minutes is not None:
                reasons.append(f"~{r.wait_minutes} min away" if r.wait_minutes < 60 else f"~{r.wait_minutes / 60:g} hr away")
            reasons.append(f"{t.distance_miles:g} mi")
            if r.perishables_ok:
                reasons.append("Takes fresh food")
            elif r.perishables_ok is False:
                reasons.append("No fresh food")
            scored.append((score, c, reasons))
            continue

        reasons = ["In stock" if r.available == "yes" and intent.kind == "product" else
                   ("Available" if r.available == "yes" else "Close substitute available")]
        if r.price is not None:
            tag = " (lowest price)" if best_price is not None and abs(r.price - best_price) < 1e-9 and len(prices) > 1 else ""
            reasons.append(f"${r.price:,.2f}{tag}")
        reasons.append(f"{t.distance_miles:g} mi away")
        if r.wait_minutes is not None:
            reasons.append(f"~{r.wait_minutes} min")
        if r.can_hold:
            reasons.append("Can hold for you")
        if r.quantity is not None:
            reasons.append(f"{r.quantity} left")
        scored.append((score, c, reasons))

    scored.sort(key=lambda item: item[0], reverse=True)
    ranked = [
        RankedItem(call_id=c.call_id, target_id=c.target.id, rank=i + 1, score=round(score, 3), reasons=reasons)
        for i, (score, c, reasons) in enumerate(scored)
    ]
    return ranked, ranked[0].call_id, criteria
