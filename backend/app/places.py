"""Finding businesses to call: Google Places (New) when a key is configured, otherwise a deterministic
mock directory so the whole system runs offline. Both return Targets sorted by distance.

Author: Saamarth Attray
"""
from __future__ import annotations

import hashlib
import logging
import math
import random
import re
from typing import Protocol

import httpx

from .config import Settings
from .contract import Intent, LatLng, Target

log = logging.getLogger("swarmdial.places")

EARTH_RADIUS_MILES = 3958.8


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def offset_point(lat: float, lng: float, miles: float, bearing_deg: float) -> tuple[float, float]:
    ang = miles / EARTH_RADIUS_MILES
    brg = math.radians(bearing_deg)
    p1, l1 = math.radians(lat), math.radians(lng)
    p2 = math.asin(math.sin(p1) * math.cos(ang) + math.cos(p1) * math.sin(ang) * math.cos(brg))
    l2 = l1 + math.atan2(math.sin(brg) * math.sin(ang) * math.cos(p1), math.cos(ang) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), math.degrees(l2)


def brand_key(name: str) -> str:
    """'CVS Pharmacy #12' -> 'cvs'. Used so the swarm can learn 'this whole chain is out'."""
    words = re.sub(r"[#()\d]", " ", name.lower()).split()
    words = [w for w in words if w not in {"the"}]
    if not words:
        return name.lower()
    if words[0] in {"main", "family", "city", "new", "local", "corner", "sunrise", "greenway", "maple"} and len(words) > 1:
        return f"{words[0]} {words[1]}"
    return words[0]


class Places(Protocol):
    async def search(self, intent: Intent, origin: LatLng, radius_miles: float, limit: int) -> list[Target]: ...

    async def resolve_referral(
        self, name: str, phone: str | None, origin: LatLng, target_id: str, intent: Intent
    ) -> Target | None: ...


# --------------------------------------------------------------------------- mock directory
_CHAINS = {
    "pharmacy": ["CVS Pharmacy", "Walgreens", "Rite Aid", "Kroger Pharmacy", "Walmart Pharmacy", "Costco Pharmacy",
                 "Safeway Pharmacy", "Target Pharmacy", "Harris Teeter Pharmacy", "Main Street Drugs",
                 "Family Care Pharmacy", "Greenway Pharmacy", "Corner Apothecary", "Sunrise Pharmacy",
                 "Bluebird Pharmacy", "Maple Health Pharmacy", "CarePlus Drugs", "Walgreens", "CVS Pharmacy",
                 "Giant Pharmacy"],
    "electronics": ["Best Buy", "GameStop", "Micro Center", "Target", "Walmart", "Costco", "Staples", "Best Buy",
                    "GameStop", "Fry's Electronics", "Newegg Store", "Apple Store", "Target", "Walmart",
                    "Office Depot", "Metro Computers", "Circuit Hub", "GameStop", "Radio Shack", "Best Buy"],
    "grocery": ["Kroger", "Safeway", "Whole Foods", "Trader Joe's", "Walmart Supercenter", "Target", "Costco",
                "Aldi", "Giant", "Harris Teeter", "Publix", "Sprouts", "Food Lion", "Meijer", "Wegmans",
                "Corner Market", "Fresh Basket", "Kroger", "Safeway", "Aldi"],
    "hardware": ["Home Depot", "Lowe's", "Ace Hardware", "Menards", "True Value", "Harbor Freight", "Home Depot",
                 "Lowe's", "Ace Hardware", "Northside Hardware", "City Lumber & Supply", "Tractor Supply",
                 "Do it Best", "Main Street Hardware", "Home Depot", "Lowe's", "Ace Hardware", "Mills Hardware",
                 "Menards", "True Value"],
    "auto_parts": ["AutoZone", "O'Reilly Auto Parts", "Advance Auto Parts", "NAPA Auto Parts", "Pep Boys",
                   "AutoZone", "O'Reilly Auto Parts", "Advance Auto Parts", "NAPA Auto Parts", "Carquest",
                   "Summit Auto Supply", "AutoZone", "Metro Auto Parts", "O'Reilly Auto Parts", "Pep Boys",
                   "Advance Auto Parts", "NAPA Auto Parts", "Ace Auto Supply", "Parts Plus", "AutoZone"],
    "pantry": ["Community Table Food Bank", "Harvest Hope Pantry", "St. Anne's Soup Kitchen", "Neighbors Helping Neighbors",
               "Second Helpings Rescue", "Grace Church Food Pantry", "Hope Shelter Kitchen", "Open Hands Pantry",
               "Capital Area Food Bank", "Mercy Meals", "Rise Up Community Fridge", "Salvation Army Meal Program",
               "Loaves & Fishes Kitchen", "Mosque Community Pantry", "Family Promise Shelter", "Eastside Food Co-op Pantry",
               "Gurdwara Langar Hall", "Sunrise Youth Shelter", "Fresh Start Food Rescue", "Table of Plenty"],
}
_ADJECTIVES = ["Rapid", "Reliable", "Premier", "Metro", "Capital", "Summit", "Evergreen", "Liberty", "Ace", "Pioneer",
               "Harbor", "Northside", "Southgate", "Westview", "Eastbrook", "Cornerstone", "Allied", "Precision",
               "Trusted", "Sunrise", "Blue Ridge", "Keystone", "Lakeside", "Redwood"]
_STREETS = ["Main St", "Oak Ave", "Maple Dr", "Cedar Ln", "Elm St", "Park Blvd", "Washington Ave", "Lakeview Rd",
            "Highland Ave", "Sunset Blvd", "Mill Rd", "Church St", "River Rd", "Broadway", "2nd Ave", "5th St"]
_CATEGORY_TO_CHAIN_KEY = {
    "pharmacy": "pharmacy", "electronics store": "electronics", "grocery store": "grocery",
    "hardware store": "hardware", "auto parts store": "auto_parts", "food pantry": "pantry",
}


_NANP = re.compile(r"^\+1[2-9]\d{2}[2-9]\d{6}$")
_NEVER_CALL_NAMES = re.compile(
    r"\b(police|sheriff|fire (department|dept|station)|911|emergency (management|dispatch)|"
    r"crisis|suicide|hotline|poison control|courthouse|jail|prison|detention)\b",
    re.I,
)


def dialable_business(name: str, phone: str) -> bool:
    """Only ordinary US/Canada business lines: no emergency/public-safety agencies, no premium or short numbers."""
    if not _NANP.match(phone):
        return False
    area = phone[2:5]
    if area[1:] == "11" or area in ("900", "976"):  # 211/311/411/911-style and premium-rate
        return False
    if phone[5:8] == "555" and phone[8:10] == "01":  # fictional 555-01xx
        return False
    return not _NEVER_CALL_NAMES.search(name)


def _seed(*parts: object) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


def _title(text: str) -> str:
    return " ".join(w.capitalize() for w in text.split())


class MockPlaces:
    """Deterministic fictional businesses (555-01xx numbers are reserved for fiction)."""

    def _names(self, intent: Intent, n: int, rng: random.Random) -> list[str]:
        chain_key = _CATEGORY_TO_CHAIN_KEY.get(intent.place_query)
        if chain_key:
            names = list(_CHAINS[chain_key])
            rng.shuffle(names)
            return (names * 2)[:n]
        noun = _title(intent.place_query.replace(" repair", ""))
        adjectives = _ADJECTIVES[:]
        rng.shuffle(adjectives)
        return [f"{adjectives[i % len(adjectives)]} {noun}" for i in range(n)]

    async def search(self, intent: Intent, origin: LatLng, radius_miles: float, limit: int) -> list[Target]:
        rng = random.Random(_seed(intent.place_query, round(origin.lat, 2), round(origin.lng, 2)))
        n = max(limit, 8)
        names = self._names(intent, n, rng)
        raw: list[Target] = []
        for i, name in enumerate(names):
            miles = round(rng.uniform(0.4, radius_miles * 0.95), 1)
            lat, lng = offset_point(origin.lat, origin.lng, miles, rng.uniform(0, 360))
            raw.append(
                Target(
                    id=f"t{i + 1}",
                    name=name,
                    address=f"{rng.randint(100, 9899)} {rng.choice(_STREETS)}",
                    phone=f"+1202555{(100 + i):04d}",
                    lat=round(lat, 5),
                    lng=round(lng, 5),
                    distance_miles=miles,
                    open_now=True,
                    rating=round(rng.uniform(3.6, 4.9), 1),
                    source="mock",
                )
            )
        raw.sort(key=lambda t: t.distance_miles)
        out = []
        for i, t in enumerate(raw[:limit]):
            # Make sure a couple of nearby places are closed so the "reroute" story always has material.
            out.append(t.model_copy(update={"id": f"t{i + 1}", "open_now": False if i in (3, 10) else True}))
        return out

    async def resolve_referral(
        self, name: str, phone: str | None, origin: LatLng, target_id: str, intent: Intent
    ) -> Target | None:
        rng = random.Random(_seed("ref", name, origin.lat, origin.lng))
        miles = round(rng.uniform(0.8, 6.0), 1)
        lat, lng = offset_point(origin.lat, origin.lng, miles, rng.uniform(0, 360))
        return Target(
            id=target_id,
            name=name,
            address=f"{rng.randint(100, 9899)} {rng.choice(_STREETS)}",
            phone=phone or f"+1202555{rng.randint(200, 999):04d}",
            lat=round(lat, 5),
            lng=round(lng, 5),
            distance_miles=miles,
            open_now=True,
            rating=round(rng.uniform(3.8, 4.8), 1),
            tier="backup",
            source="referral",
        )


# --------------------------------------------------------------------------- Google Places (New)
class GooglePlaces:
    URL = "https://places.googleapis.com/v1/places:searchText"
    FIELDS = ",".join(
        [
            "places.id", "places.displayName", "places.formattedAddress", "places.location",
            "places.nationalPhoneNumber", "places.internationalPhoneNumber", "places.rating",
            "places.currentOpeningHours.openNow", "places.businessStatus", "nextPageToken",
        ]
    )

    def __init__(self, api_key: str, http: httpx.AsyncClient | None = None):
        self.api_key = api_key
        self._http = http or httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0))

    async def _query(self, text: str, origin: LatLng, radius_miles: float, count: int, pages: int = 1) -> list[dict]:
        body: dict = {
            "textQuery": text,
            "maxResultCount": min(20, max(1, count)),
            "locationBias": {
                "circle": {
                    "center": {"latitude": origin.lat, "longitude": origin.lng},
                    "radius": min(50000.0, radius_miles * 1609.34),
                }
            },
        }
        places: list[dict] = []
        for _ in range(max(1, pages)):  # Google returns at most 20 per page; follow the page token for more
            resp = await self._http.post(
                self.URL, json=body, headers={"X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": self.FIELDS}
            )
            resp.raise_for_status()
            data = resp.json()
            places.extend(data.get("places", []))
            token = data.get("nextPageToken")
            if not token or len(places) >= count:
                break
            body = {**body, "pageToken": token}
        return places[:count]

    @staticmethod
    def _to_target(place: dict, origin: LatLng, target_id: str, source: str = "places") -> Target | None:
        phone = place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber")
        loc = place.get("location") or {}
        if not phone or "latitude" not in loc or place.get("businessStatus") in ("CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY"):
            return None
        phone = re.sub(r"[^\d+]", "", phone)
        if not phone.startswith("+"):
            phone = "+1" + phone
        name_text = (place.get("displayName") or {}).get("text", "")
        if not dialable_business(name_text, phone):
            return None
        return Target(
            id=target_id,
            name=(place.get("displayName") or {}).get("text", "Unknown business"),
            address=place.get("formattedAddress"),
            phone=phone,
            lat=loc["latitude"],
            lng=loc["longitude"],
            distance_miles=round(haversine_miles(origin.lat, origin.lng, loc["latitude"], loc["longitude"]), 1),
            open_now=(place.get("currentOpeningHours") or {}).get("openNow"),
            rating=place.get("rating"),
            source=source,  # type: ignore[arg-type]
        )

    _AREA_TYPES = {"locality", "sublocality", "neighborhood", "postal_code", "administrative_area_level_1",
                   "administrative_area_level_2", "administrative_area_level_3", "postal_town", "political"}

    async def geocode(self, text: str) -> tuple[LatLng, str] | None:
        """Turn a city / state / zip typed in the request into coordinates. None if it is not a place."""
        resp = await self._http.post(
            self.URL,
            json={"textQuery": text, "maxResultCount": 1},
            headers={"X-Goog-Api-Key": self.api_key,
                     "X-Goog-FieldMask": "places.location,places.types,places.formattedAddress,places.displayName"},
        )
        resp.raise_for_status()
        places = resp.json().get("places") or []
        if not places:
            return None
        place = places[0]
        loc = place.get("location") or {}
        if "latitude" not in loc or not (set(place.get("types") or []) & self._AREA_TYPES):
            return None  # a business or landmark, not an area
        label = place.get("formattedAddress") or (place.get("displayName") or {}).get("text") or text
        return LatLng(lat=loc["latitude"], lng=loc["longitude"]), label

    async def search(self, intent: Intent, origin: LatLng, radius_miles: float, limit: int) -> list[Target]:
        places = await self._query(intent.place_query, origin, radius_miles, 40, pages=2)
        targets = [t for i, p in enumerate(places) if (t := self._to_target(p, origin, f"t{i + 1}"))]
        targets = [t for t in targets if t.distance_miles <= radius_miles * 1.15]
        seen: set[str] = set()
        unique = []
        for t in targets:  # one call per phone number (chains share a line; duplicates waste calls)
            if t.phone not in seen:
                seen.add(t.phone)
                unique.append(t)
        targets = unique
        targets.sort(key=lambda t: (t.open_now is False, t.distance_miles))
        return [t.model_copy(update={"id": f"t{i + 1}"}) for i, t in enumerate(targets[:limit])]

    async def resolve_referral(
        self, name: str, phone: str | None, origin: LatLng, target_id: str, intent: Intent
    ) -> Target | None:
        try:
            places = await self._query(name, origin, 15, 3)
        except httpx.HTTPError:
            return None
        for place in places:
            target = self._to_target(place, origin, target_id, source="referral")
            if target:
                return target.model_copy(update={"tier": "backup"})
        return None


def demo_targets(settings: Settings, origin: LatLng) -> list[Target]:
    """Teammates' phones standing in for businesses during a live demo."""
    out = []
    for i, (name, phone) in enumerate(settings.demo_targets):
        lat, lng = offset_point(origin.lat, origin.lng, 0.8 + i * 0.7, 40 + i * 70)
        out.append(
            Target(
                id=f"t{i + 1}",
                name=name,
                address="Demo location",
                phone=phone,
                lat=round(lat, 5),
                lng=round(lng, 5),
                distance_miles=round(0.8 + i * 0.7, 1),
                open_now=True,
                source="demo",
            )
        )
    return out


def build_places(settings: Settings) -> Places:
    return GooglePlaces(settings.google_places_api_key) if settings.places_enabled else MockPlaces()  # type: ignore[arg-type]