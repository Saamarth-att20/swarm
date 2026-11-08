"""Turns a free-text request into a structured Intent (what to ask, who to call).

Heuristics always run first so the app works with zero keys; if an LLM is configured it refines the
result (better item names, odd categories). Any LLM failure silently falls back to the heuristics.

Author: Saamarth Attray
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from .contract import Intent
from .llm import LLMClient

log = logging.getLogger("swarmdial.intent")


@dataclass(frozen=True)
class CategorySpec:
    key: str
    kind: str  # product | service | appointment
    place_query: str
    keywords: tuple[str, ...]


CATEGORIES: tuple[CategorySpec, ...] = (
    CategorySpec("pharmacy", "product", "pharmacy", (
        "amoxicillin", "ibuprofen", "prescription", "pharmacy", "antibiotic", "insulin", "inhaler", "medicine",
        "medication", "tylenol", "benadryl", "epipen", "pills", "tablets", "cough syrup", "albuterol", "zofran",
        "children's", "infant's", "liquid")),
    CategorySpec("urgent_care", "appointment", "urgent care", (
        "urgent care", "walk-in clinic", "walk in clinic", "stitches", "x-ray", "xray", "clinic")),
    CategorySpec("emergency_vet", "appointment", "emergency veterinarian", (
        "vet", "veterinar", "my dog", "my cat", "pet emergency")),
    CategorySpec("plumber", "service", "plumber", (
        "plumb", "leak", "water heater", "burst pipe", "clogged", "drain", "toilet", "sewer")),
    CategorySpec("electrician", "service", "electrician", (
        "electrician", "outlet", "breaker", "power out", "wiring", "panel")),
    CategorySpec("locksmith", "service", "locksmith", (
        "locksmith", "locked out", "lockout", "lost key", "car key", "rekey")),
    CategorySpec("hvac", "service", "hvac repair", (
        "hvac", "furnace", "heating", "ac repair", "air conditioner", "heat pump", "no heat")),
    CategorySpec("dmv", "appointment", "dmv", (
        "dmv", "driver's license", "drivers license", "license renewal", "real id", "vehicle registration")),
    CategorySpec("tire_shop", "service", "tire shop", ("tire", "flat tire", "tyre")),
    CategorySpec("auto_parts", "product", "auto parts store", (
        "car battery", "brake pad", "alternator", "oil filter", "wiper", "auto parts", "spark plug")),
    CategorySpec("electronics", "product", "electronics store", (
        "ps5", "playstation", "xbox", "nintendo", "switch 2", "iphone", "laptop", "gpu", "rtx", "headphones",
        "airpods", "charger", "console", "tv ")),
    CategorySpec("baby_supplies", "product", "grocery store", (
        "baby formula", "formula", "diapers", "pull-ups", "wipes")),
    CategorySpec("grocery", "product", "grocery store", (
        "groceries", "milk", "eggs", "bread", "ice", "produce")),
    CategorySpec("hardware", "product", "hardware store", (
        "drill", "ladder", "lumber", "hardware", "generator", "sump pump", "space heater", "propane", "plywood")),
)

FOOD_CATEGORY = CategorySpec("food_pantry", "food", "food pantry", (
    "food pantry", "food bank", "soup kitchen", "free food", "free meal", "hungry", "need food", "food assistance",
    "food box", "groceries", "meal", "feed my", "snap", "diapers", "baby formula", "halal", "kosher"))
DONATION_CATEGORY = CategorySpec("food_donation", "donation", "food pantry", (
    "donate", "donation", "drop off", "drop-off", "give food", "contribute"))
_DONATION_INTENT = re.compile(r"\b(donat\w*|drop[- ]?off|give (?:away|food)|contribute)\b", re.I)
_DONATION_ITEM = re.compile(
    r"\bdonat(?:e|ing|ion of)\s+(?:some\s+|my\s+|about\s+|a\s+few\s+)?(.+?)"
    r"(?:\s+(?:to|at|near|nearby|today|tonight|this|within|that|who|with)\b|[?.!,]|$)", re.I)
_DONATION_ITEM_NOUN = re.compile(r"\b(?:drop off|give)\s+(?:some\s+|my\s+)?(.+?)(?:\s+(?:to|at|near)\b|[?.!,]|$)", re.I)

DEFAULT_CATEGORY = CategorySpec("general", "product", "store", ())

_HAS_PATTERN = re.compile(
    r"(?:has|have|carr(?:y|ies)|sell(?:s|ing)?|stock(?:s|ing)?)\s+(?:any\s+|some\s+)?(.+?)"
    r"(?:\s+in\s+stock|\s+right now|\s+today|\s+tonight|\s+available|\s+near\b|\s+within\b|[?.!,]|$)", re.I)
_NEED_PATTERN = re.compile(
    r"(?:need|want|looking for)\s+(?:an?\s+|the\s+|some\s+)?(.+?)"
    r"(?:\s+(?:within|near|nearby|in stock|tonight|today|right now|asap|that|who|with)\b|[?.!,]|$)", re.I)
_FIND_PATTERN = re.compile(
    r"(?:find me|find|get)\s+(?:an?\s+|the\s+|some\s+)?(.+?)"
    r"(?:\s+(?:within|near|nearby|in stock|tonight|today|right now|asap|that|who|with)\b|[?.!,]|$)", re.I)
_WITH_PATTERN = re.compile(
    r"\bwith\s+(?:any\s+|some\s+)?(.+?)"
    r"(?:\s+in\s+stock|\s+right now|\s+today|\s+tonight|\s+available|[?.!,]|$)", re.I)
_PRONOUNS = {"it", "them", "that", "one", "some", "any", "this", "those", "these"}
_PLACE_WORDS = {"pharmacy", "store", "shop", "place", "business", "stores", "pharmacies", "plumber", "clinic",
                "vet", "dmv", "locksmith", "electrician", "somewhere"}
_LEADING_FILLER = re.compile(
    r"^(?:please\s+|i\s+(?:need|want)\s+(?:to\s+)?|can you\s+|find\s+(?:me\s+)?|a\s+|an\s+|the\s+|some\s+)+", re.I
)
_RADIUS = re.compile(r"within\s+(\d+(?:\.\d+)?)\s*(?:mi|miles?)\b", re.I)

# A place named in the request ("in Los Angeles", "near Austin, TX", "in 90001") overrides the user's own location.
_PLACE_ALIASES = {
    "la": "Los Angeles, CA", "l.a.": "Los Angeles, CA", "nyc": "New York, NY", "sf": "San Francisco, CA",
    "dc": "Washington, DC", "d.c.": "Washington, DC", "philly": "Philadelphia, PA", "vegas": "Las Vegas, NV",
    "atl": "Atlanta, GA", "chi": "Chicago, IL",
}
_PLACE_RE = re.compile(r"\b(?:in|near|around|close to)\s+(?:the\s+)?([A-Za-z][A-Za-z.'\- ]*(?:,\s*[A-Za-z]{2}\b)?(?:\s+\d{5})?)", re.I)
_ZIP_RE = re.compile(r"\b(?:in|near|around)\s+(\d{5})\b", re.I)
_PLACE_STOP = re.compile(
    r"\b(?:that|which|with|who|has|have|for|right|now|within|today|tonight|open|and|or|please|stock|available|in|at|on|"
    r"before|after|under|asap|from|so|if|is|are|can|could|whose|next|this|tomorrow|tonight|week|weekend|month|then|when|"
    r"while|where|until|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.I)
_NOT_PLACES = {"stock", "the", "a", "an", "my", "your", "this", "that", "time", "case", "need", "person", "store",
               "advance", "general", "particular", "bulk", "cash", "full", "total", "few", "about", "less", "under",
               "half", "one", "two", "three", "ten", "fifteen", "twenty", "thirty", "some", "any", "every",
               # "near me", "around here", "close to us": the user's own location, not a place to look up
               "me", "here", "us", "you", "there", "myself", "home", "anywhere", "nearby"}


# Trips and moves: "I'm going to LA next week", "visiting Austin", "flying to Denver on Friday".
_TRIP_RE = re.compile(
    r"\b(?:going to|travel(?:l)?ing to|trip to|visiting|flying to|driving to|heading to|moving to|arriving in|staying in|"
    r"landing in|be in|will be in)\s+(?:the\s+)?([A-Za-z][A-Za-z.'\- ]*(?:,\s*[A-Za-z]{2}\b)?)"
)
_BARE_ALIAS_RE = re.compile(r"\b(LA|L\.A\.|NYC|SF|DC|D\.C\.|ATL)\b")  # capitals only: "la" is a word in other languages


def extract_place(query: str) -> str | None:
    """A city, state or zip named in the request, or None ("Find CVS in LA that has insulin" -> "Los Angeles, CA")."""
    zipcode = _ZIP_RE.search(query)
    if zipcode:
        return zipcode.group(1)
    trip = _TRIP_RE.search(query)
    if trip:
        raw = trip.group(1)
        cut = _PLACE_STOP.search(raw)
        place = (raw[: cut.start()] if cut else raw).strip(" ,.-")
        if place and place.lower().split()[0] not in _NOT_PLACES and len(place) >= 2:
            return _PLACE_ALIASES.get(place.lower(), place)
    pos = 0
    while True:
        match = _PLACE_RE.search(query, pos)
        if not match:
            alias = _BARE_ALIAS_RE.search(query)  # "LA CVS pharmacy with amoxicillin"
            return _PLACE_ALIASES.get(alias.group(1).lower()) if alias else None
        pos = match.start() + 1
        raw = match.group(1)
        cut = _PLACE_STOP.search(raw)
        place = (raw[: cut.start()] if cut else raw).strip(" ,.-")
        if not place or place.lower().split()[0] in _NOT_PLACES or len(place) < 2:
            continue
        return _PLACE_ALIASES.get(place.lower(), place)


def _score(spec: CategorySpec, text: str) -> int:
    return sum(1 for kw in spec.keywords if kw in text)


def classify_category(query: str) -> CategorySpec:
    text = f" {query.lower()} "
    if _DONATION_INTENT.search(text) and any(w in text for w in ("food", "pantry", "bank", "can", "meal", "grocer", "produce")):
        return DONATION_CATEGORY
    if _score(FOOD_CATEGORY, text) and not _score_other_than_food(text):
        return FOOD_CATEGORY
    best, best_score = DEFAULT_CATEGORY, 0
    for spec in CATEGORIES:
        score = _score(spec, text)
        if score > best_score:
            best, best_score = spec, score
    return best


def _score_other_than_food(text: str) -> int:
    """Real products/services that happen to share a word with food ('baby formula' alone is food-adjacent)."""
    return max((_score(spec, text) for spec in CATEGORIES if spec.key not in ("grocery", "baby_supplies")), default=0)


def extract_donation_item(query: str) -> str:
    text = query.strip().rstrip("?.! ")
    for pattern in (_DONATION_ITEM, _DONATION_ITEM_NOUN):
        match = pattern.search(text)
        if match:
            item = match.group(1).strip()
            if item and item.lower() not in _PRONOUNS | {"food", "money"} | _PLACE_WORDS:
                return item
    return "food"


_DIETARY = re.compile(r"\b(halal|kosher|vegetarian|vegan|gluten[- ]free|baby formula|diapers|fresh produce|fresh fruit)\b", re.I)


def extract_item(query: str) -> str:
    text = query.strip().rstrip("?.! ")
    for pattern in (_HAS_PATTERN, _NEED_PATTERN, _WITH_PATTERN, _FIND_PATTERN):
        for match in pattern.finditer(text):
            item = _LEADING_FILLER.sub("", match.group(1).strip())
            if item and item.lower() not in _PRONOUNS | _PLACE_WORDS:
                return item
    return _LEADING_FILLER.sub("", text) or text


def summarize(kind: str, item: str, radius: float) -> str:
    if kind == "food":
        what = "free food" if item == "food" else f"free {item}"
        return f"Find {what} available today within {radius:g} miles"
    if kind == "donation":
        short = item if len(item) <= 90 else item[:87].rstrip(" ,;") + "…"
        return f"Find a food bank or pantry that can pick up {short if item != 'food' else 'surplus food'} within {radius:g} miles"
    verb = "Find" if kind == "product" else "Book"
    return f"{verb} {item} within {radius:g} miles"


def heuristic_intent(query: str, radius_miles: float, priority: str | None, purpose: str = "find") -> Intent:
    donate = purpose == "donate"
    spec = DONATION_CATEGORY if donate else classify_category(query)
    lowered = query.lower()

    radius = radius_miles
    match = _RADIUS.search(lowered)
    if match:
        radius = min(50.0, max(0.5, float(match.group(1))))

    if donate or re.search(r"\b(now|tonight|asap|urgent|emergency|right now|immediately)\b", lowered):
        urgency = "now"
    elif "today" in lowered:
        urgency = "today"
    else:
        urgency = "today" if spec.kind in ("product", "food", "donation") else "now"

    inferred_priority = "speed" if spec.kind == "donation" else "balanced"  # perishable food: soonest pickup wins
    if re.search(r"\b(cheapest|lowest price|best price|under \$)", lowered):
        inferred_priority = "price"
    elif re.search(r"\b(closest|nearest)\b", lowered):
        inferred_priority = "distance"
    elif re.search(r"\b(earliest|soonest|fastest|quickest)\b", lowered):
        inferred_priority = "speed"

    noun = spec.place_query.replace(" repair", "")
    if spec.kind == "product":
        item = extract_item(query)
    elif spec.kind == "food":
        diet = _DIETARY.search(query)
        term = diet.group(1).lower() if diet else ""
        item = f"{term} food" if term in ("halal", "kosher", "vegetarian", "vegan", "gluten-free", "gluten free") else (term or "food")
    elif spec.kind == "donation":
        # a donor describing their surplus gives us the exact food list: keep it verbatim
        item = " ".join(query.split())[:240] if donate else extract_donation_item(query)
    elif spec.kind == "service":
        item = f"an urgent {noun} visit" if urgency == "now" else f"a {noun} visit"
    else:
        item = "a same-day appointment" if urgency != "flexible" else "an appointment"
    summary = summarize(spec.kind, item, radius)
    return Intent(
        raw_query=query,
        item=item,
        category=spec.key,
        kind=spec.kind,  # type: ignore[arg-type]
        place_query=spec.place_query,
        urgency=urgency,  # type: ignore[arg-type]
        priority=(priority or inferred_priority),  # type: ignore[arg-type]
        radius_miles=radius,
        summary=summary,
    )


_LLM_SYSTEM = (
    "You extract structured intent from a request to find something available nearby by phoning businesses. "
    "Reply with a JSON object with keys: item (short noun phrase of exactly what is needed), category (one of: "
    + ", ".join(c.key for c in CATEGORIES)
    + ", food_pantry, food_donation, general), kind (product, service, appointment, food or donation), place_query (what to search for on a maps site, e.g. "
    "'pharmacy'; use food_pantry/food for someone needing free food and food_donation/donation for someone who wants to give food), urgency (now, today or flexible), priority (balanced, price, distance or speed)."
)


async def parse_intent(
    query: str, radius_miles: float, priority: str | None, llm: LLMClient | None, purpose: str = "find"
) -> Intent:
    intent = heuristic_intent(query, radius_miles, priority, purpose)
    if llm is None or purpose == "donate":  # a donor's food description is used exactly as written
        return intent
    try:
        data = await llm.complete_json(_LLM_SYSTEM, query)
        update: dict = {}
        if isinstance(data.get("item"), str) and data["item"].strip():
            update["item"] = data["item"].strip()[:120]
        if isinstance(data.get("place_query"), str) and data["place_query"].strip():
            update["place_query"] = data["place_query"].strip()[:80]
        if data.get("category") in {c.key for c in CATEGORIES} | {"general", "food_pantry", "food_donation"}:
            update["category"] = data["category"]
        if data.get("kind") in ("product", "service", "appointment", "food", "donation"):
            update["kind"] = data["kind"]
        if data.get("urgency") in ("now", "today", "flexible"):
            update["urgency"] = data["urgency"]
        if priority is None and data.get("priority") in ("balanced", "price", "distance", "speed"):
            update["priority"] = data["priority"]
        merged = intent.model_copy(update=update)
        return merged.model_copy(update={"summary": summarize(merged.kind, merged.item, merged.radius_miles)})
    except Exception as exc:
        log.warning("LLM intent parsing failed (%s); using heuristics", exc)
        return intent