"""Simulated businesses: believable fake phone calls that run through the *real* swarm pipeline.

Simulated mode is the safety net for a hackathon demo (no telephony, no API keys, no flaky Wi-Fi) and
the way the frontend and tests exercise rerouting, referrals, partial matches, voicemail, "no robots"
hang-ups and so on.

Author: Saamarth Attray
"""
from __future__ import annotations

import asyncio
import hashlib
import random

from .agent.nlu import HOLD_ON
from .agent.session import CallSession
from .agent.types import CallOutcome
from .contract import Intent, Target
from .reporter import CallReporter

PLAN_CYCLE = [
    "has_it", "out_of_stock", "partial", "has_it_slow", "out_referral", "no_answer",
    "has_it_nohold", "voicemail", "has_it", "refuses_ai", "out_of_stock", "has_it",
]

ALTERNATIVES = {
    "pharmacy": "the generic version",
    "electronics": "the bundle with an extra controller",
    "baby_supplies": "the store-brand version",
    "hardware": "a slightly smaller model",
    "auto_parts": "the premium version",
    "grocery": "the store brand",
}
PRICE_RANGES = {
    "pharmacy": (6, 38), "electronics": (399, 549), "auto_parts": (89, 219), "hardware": (25, 179),
    "grocery": (4, 19), "baby_supplies": (14, 44), "plumber": (59, 149), "electrician": (69, 159),
    "locksmith": (49, 129), "hvac": (79, 189), "urgent_care": (75, 180), "emergency_vet": (95, 225),
    "dmv": (0, 0), "tire_shop": (89, 189),
}
STREETS = ["Main Street", "Oak Avenue", "Maple Drive", "Cedar Lane", "Park Boulevard", "Mill Road"]
REFERRAL_NAMES = {
    "food_donation": ["Harvest Hope Pantry", "Second Helpings Rescue", "Open Hands Pantry", "Mercy Meals"],
    "food_pantry": ["Harvest Hope Pantry", "Open Hands Pantry", "Community Table Food Bank"],
    "pharmacy": ["Summit Pharmacy", "Lakeside Drugs", "Keystone Pharmacy", "Redwood Pharmacy"],
    "electronics": ["Metro Computers", "Circuit Hub", "Pixel Plaza", "Capital Electronics"],
}


def _seed(*parts: object) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


def assign_plans(targets: list[Target], seed: str) -> dict[str, str]:
    rng = random.Random(_seed("plans", seed))
    plans: dict[str, str] = {}
    pool: list[str] = []
    for target in targets:
        if target.open_now is False:
            plans[target.id] = "closed"
            continue
        if not pool:
            pool = PLAN_CYCLE[:]
            rng.shuffle(pool)
        plans[target.id] = pool.pop()
    return plans


def referral_for(intent: Intent, rng: random.Random) -> str:
    pool = REFERRAL_NAMES.get(intent.category)
    if pool:
        return rng.choice(pool)
    adjective = rng.choice(["Summit", "Keystone", "Lakeside", "Redwood", "Harbor", "Pioneer"])
    noun = intent.place_query.replace(" repair", "").title()
    return f"{adjective} {noun}"


def _donation_script(plan: str, *, target: Target, rng: random.Random, referral: str, street: str) -> list[str]:
    """A food bank, pantry or shelter answering 'we have surplus food, can you pick it up?'."""
    eta = rng.choice([15, 20, 25, 30, 40, 45])
    until = rng.choice(["7", "8", "9"])
    scripts = {
        "closed": ["Sorry, our intake line is closed for the night. We open again at 9 tomorrow morning."],
        "has_it": [
            "Oh, that's wonderful. Let me check with our driver.",
            f"Okay, yes, we can send a volunteer to pick it up, about {eta} minutes from now.",
            "And yes, we have a walk-in cooler, so fresh food is no problem.",
        ],
        "has_it_slow": [
            "Hold on, let me see who's on shift.",
            "Still checking, one moment.",
            f"Okay, we can send someone, they can be there in about {eta + 15} minutes.",
            "Yes, we take fresh and refrigerated food, we have the space tonight.",
        ],
        "has_it_nohold": [
            "Sure, one sec.",
            f"We can't send anyone to pick up tonight, our van is out, but you can drop it off here until {until} pm.",
        ],
        "out_of_stock": ["Oh, I'm sorry, we're at capacity tonight, our fridges are completely full."],
        "out_referral": [
            f"We're full tonight, sorry. You could try {referral} on {street}, they have a big walk-in cooler and a van."
        ],
        "partial": [
            "Thank you for thinking of us. We don't take fresh food, only shelf-stable items, sorry."
        ],
    }
    return scripts.get(plan, scripts["out_of_stock"])


def _food_seeker_script(plan: str, *, rng: random.Random, referral: str, street: str) -> list[str]:
    """A pantry answering 'is anyone giving out food today?'."""
    close = rng.choice(["2", "4", "6"])
    scripts = {
        "closed": ["Sorry, we're closed today. We're open again Thursday at 10."],
        "has_it": [
            "Yes, we're giving out food today.",
            f"We're open until {close} pm. Just bring a photo ID, no proof of address needed.",
        ],
        "has_it_slow": ["Hold on, let me check the schedule.", f"Yes, we're open until {close} pm today. Just bring an ID."],
        "has_it_nohold": [f"Yes, we're open today until {close} pm. It's by appointment only though, you can sign up at the door."],
        "out_of_stock": ["We ran out of food for today, sorry. We restock Monday."],
        "out_referral": [f"We're out of food today. You could try {referral} on {street}, they're open late."],
        "partial": [f"We're open until {close} pm, but we only serve residents of this zip code."],
    }
    return scripts.get(plan, scripts["out_of_stock"])


def build_script(plan: str, *, intent: Intent, target: Target, rng: random.Random) -> list[str]:
    item = intent.item
    low, high = PRICE_RANGES.get(intent.category, (10, 60))
    price = rng.randint(low, high) if high else 0
    qty = rng.randint(2, 7)
    wait = rng.choice([20, 30, 45, 60])
    alt = ALTERNATIVES.get(intent.category, "a similar one")
    street = rng.choice(STREETS)
    referral = referral_for(intent, rng)
    product = intent.kind == "product"
    price_bit = f"${price}" if price else "no charge"

    if intent.kind == "donation":
        return _donation_script(plan, target=target, rng=rng, referral=referral, street=street)
    if intent.kind == "food":
        return _food_seeker_script(plan, rng=rng, referral=referral, street=street)

    if plan == "closed":
        return (
            ["Hi, sorry, we're closed right now. We open again tomorrow at 8."]
            if product
            else ["Sorry, our office is closed right now. We open at 7 tomorrow morning."]
        )
    if plan == "voicemail":
        return [f"You've reached {target.name}. We can't take your call right now, please leave a message after the tone."]
    if plan == "refuses_ai":
        return ["Sorry, I don't talk to robots. Bye."]

    if product:
        scripts = {
            "has_it": [
                "Yeah, hang on, let me check the shelf.",
                f"Okay yeah, we do have {item}. We've got {qty} left.",
                f"It's ${price}, and yes, we can hold one for you for a couple of hours.",
            ],
            "has_it_slow": [
                "Hold on, let me go look in the back.",
                "Still looking, one sec.",
                f"Okay, found it. Yes, we do have {item}, {qty} left.",
                f"It's ${price} and we can hold it for you, no problem.",
            ],
            "has_it_nohold": [
                "Sure, one sec.",
                f"Yep, we do have {item}, {qty} left.",
                f"It's ${price}. We can't hold items though, it's first come first served.",
            ],
            "out_of_stock": [f"Let me check... no, we're out of {item} right now, sorry about that."],
            "out_referral": [
                f"Hmm, no, we're out of {item}. You could try {referral} on {street}, they usually carry it."
            ],
            "partial": [f"Let me look. We don't have {item}, but we do have {alt} for ${price}."],
        }
    else:
        scripts = {
            "has_it": [
                "Hold on, let me check the schedule.",
                f"Okay, yes, we do have a tech available tonight, about {wait} minutes out.",
                f"The fee is {price_bit}, and anything beyond that is quoted on site. I can hold the slot for you if you'd like.",
            ],
            "has_it_slow": [
                "Hang on, let me see who's free.",
                "Still checking, one moment.",
                f"Okay, we do have someone available, about {wait} minutes away.",
                f"It's {price_bit} and we can hold the slot for you.",
            ],
            "has_it_nohold": [
                "Sure, one sec.",
                f"Yes, we do have an opening, about {wait} minutes from now.",
                f"It's {price_bit}. We can't hold the slot though, it goes to whoever confirms first.",
            ],
            "out_of_stock": ["Sorry, we're fully booked tonight, nothing until tomorrow."],
            "out_referral": [f"We're fully booked tonight. You could try {referral}, they do emergency calls."],
            "partial": [f"We're booked up tonight, but we do have an opening tomorrow at 8 for {price_bit}."],
        }
    return scripts.get(plan, scripts["out_of_stock"])


def build_reserve_script(rng: random.Random, *, succeed: bool, kind: str = "product") -> list[str]:
    if kind == "donation":
        if not succeed:
            return ["Oh no, I'm sorry, our driver just got called away, we can't send anyone tonight after all."]
        who = rng.choice(["Maria", "James", "Priya", "Luis", "Dana"])
        code = f"{rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{rng.randint(1000, 9999)}"
        return [
            "Sure, let me confirm that.",
            f"Okay, confirmed. {who} will come by in about {rng.choice([20, 25, 30])} minutes with the van. "
            f"The confirmation code is {code}.",
        ]
    if not succeed:
        return ["Hmm, sorry, we can't hold items over the phone."]
    code = f"{rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{rng.randint(1000, 9999)}"
    return [
        "Sure, one moment.",
        f"Okay, I've set one aside for you at the counter. Your confirmation code is {code}.",
    ]


class SimulatedCallRunner:
    """Plays one fake phone call: ring, answer, back-and-forth, hang up."""

    def __init__(self, speed: float = 1.0):
        self.speed = speed

    async def _sleep(self, seconds: float) -> None:
        await asyncio.sleep(max(0.0, seconds * self.speed))

    async def _business_says(self, session: CallSession, line: str) -> list[str]:
        uid = session.new_utterance_id()
        words = line.split()
        for fraction in (0.35, 0.7):
            cut = max(1, int(len(words) * fraction))
            await self._sleep(0.12 * cut)
            await session.business_partial(" ".join(words[:cut]), uid)
        await self._sleep(0.1 * max(1, len(words) - int(len(words) * 0.7)))
        spoken: list[str] = []
        async for sentence in session.respond(line, uid):
            spoken.append(sentence)
            await self._sleep(0.045 * len(sentence))
        return spoken

    async def run(
        self,
        *,
        session: CallSession,
        reporter: CallReporter,
        plan: str,
        target: Target,
        intent: Intent,
        rng: random.Random,
        role: str = "inquiry",
    ) -> CallOutcome:
        await reporter.state("dialing")
        await self._sleep(rng.uniform(1.4, 3.2))
        if plan == "no_answer":
            await self._sleep(rng.uniform(2.0, 4.0))
            return CallOutcome("failed", reason="No answer")

        await reporter.state("talking")
        opening = await session.start()
        await self._sleep(0.045 * len(opening) + 0.4)

        if role == "reserve":
            script = build_reserve_script(rng, succeed=rng.random() < (0.85 if intent.kind == "donation" else 0.9), kind=intent.kind)
        else:
            script = build_script(plan, intent=intent, target=target, rng=rng)

        index = 0
        while not session.finished and index < len(script) + 2:
            line = script[index] if index < len(script) else "Okay, was there anything else you needed?"
            index += 1
            await self._business_says(session, line)
            if HOLD_ON.search(line) and not session.finished:
                await self._sleep(rng.uniform(1.0, 2.2))

        if not session.finished:
            session.force_end("no_response")
        await self._sleep(0.3)
        return session.outcome()
