"""Tiny rule-based language understanding for what a business says on the phone.

Used by the offline ScriptedBrain (so the whole product demos with zero API keys) and as a safety net
in tests. The production path uses the LLM; this just needs to be right about common phrasings.

Author: Saamarth Attray
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

HOLD_ON = re.compile(
    r"\b(hold on|hang on|one (?:sec|second|moment|minute)|just a (?:sec|second|moment|minute)|"
    r"give me a (?:sec|second|minute|moment)|let me (?:check|look|see|grab|pull|confirm)|bear with me)\b",
    re.I,
)
CLOSED = re.compile(
    r"\b(we(?:'re| are) closed|we(?:'ve| have)? closed|closed (?:for the (?:day|night)|until|right now|at \d)|"
    r"not open|after hours|(?:office|store|shop|clinic) is closed|we close(?:d)? at)\b",
    re.I,
)
NO_STOCK = re.compile(
    r"\b(out of stock|sold out|don'?t have|do not have|we(?:'re| are) out|none left|no longer (?:carry|have)|"
    r"not in stock|don'?t carry|ran out|not available|unavailable|isn'?t available|fully booked|booked up|"
    r"no availability|no openings|nothing until|can'?t fit|can'?t send|can'?t come|no,? we\b|no,? sorry)",
    re.I,
)
HAS_STOCK = re.compile(
    r"\b(we do have|we have|we'?ve got|we got|yes,? we do|yeah,? we do|yes,? we can|yeah,? we can|"
    r"we can (?:send|get|fit|see|take|come|be there|do)|in stock|got (?:it|some|one)|have (?:it|some|one|a few)|"
    r"available|have an? (?:opening|slot|appointment)|there'?s an? (?:opening|slot))\b",
    re.I,
)
BUT_HAVE = re.compile(
    r"\bbut (?:we|i)(?: do| also| can)? (?:have|carry|got|offer)\s+(.+?)"
    r"(?:\s+(?:for|at)\s+\$|\s+if\b|[.,!?;]|$)",
    re.I,
)
ONLY_HAVE = re.compile(r"\bwe (?:only|just) (?:have|carry)\s+(.+?)(?:\s+(?:for|at)\s+\$|[.,!?;]|$)", re.I)
REFERRAL_SPLIT = re.compile(
    r"\b(?:you (?:could|might|can|should) (?:try|call|go to|check)|try|check with|head (?:over )?to)\b", re.I
)
REFERRAL = re.compile(
    r"(?i:you (?:could|might|can|should) (?:try|call|go to|check)|try|check with|head (?:over )?to)\s+"
    r"(?:(?i:calling)\s+)?(?:(?i:the)\s+)?"
    r"([A-Z][A-Za-z0-9&'’.\-]*(?:\s+[A-Z][A-Za-z0-9&'’.\-]*){0,3})"
)
PHONE = re.compile(r"(\+?1?[\s\-.]?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4})")
PRICE = re.compile(r"\$\s?(\d{1,6}(?:\.\d{1,2})?)")
PRICE_WORDS = re.compile(r"(\d{1,6}(?:\.\d{1,2})?)\s*(?:dollars|bucks)\b", re.I)
WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
QTY = re.compile(
    r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(?:left|in stock|units?|on hand|available|bottles?|boxes?|packs?|of them|remaining|in the back)\b",
    re.I,
)
WAIT_MIN = re.compile(r"(\d+)\s*(?:min(?:ute)?s?)\b", re.I)
WAIT_HOURS = re.compile(r"(\d+(?:\.\d+)?)\s*hours?\b", re.I)
HOLD_NO = re.compile(
    r"\b(?:can'?t|cannot|don'?t|do not|unable to|not able to|won'?t|no)\b\W+(?:\w+\W+){0,3}?"
    r"(?:hold|reserve|set (?:it |one )?aside|put (?:it |one )?aside)|first come|no holds",
    re.I,
)
HOLD_YES = re.compile(
    r"\b(?:can|could|will|happy to|glad to|we'?ll)\b[^.?!]{0,30}\b"
    r"(?:hold|reserve|set (?:it |one |that )?aside|put (?:it |one |that )?aside|save)\b",
    re.I,
)
IVR = re.compile(
    r"(press \d|press (?:one|two|three|zero)|for [a-z ]+,? press|main menu|your call is (?:important|being)|"
    r"to (?:reach|speak)[^.]*,? (?:say|press))",
    re.I,
)
VOICEMAIL = re.compile(
    r"(leave (?:a )?(?:message|your name)|after the (?:tone|beep)|voice ?mail|not available to take your call|"
    r"can'?t take your call|mailbox)",
    re.I,
)
REFUSED = re.compile(
    r"\b(?:don'?t|do not|won'?t|not)\b[^.?!]{0,20}\b(?:talk|speak|deal|work)\b[^.?!]{0,15}\b"
    r"(?:robots?|bots?|machines?|ai|computers?|recordings?)\b",
    re.I,
)
ARE_YOU_BOT = re.compile(
    r"(are you (?:a )?(?:real |actual )?(?:person|human|robot|bot|ai|machine)|is this (?:a )?(?:robot|recording|bot|ai))",
    re.I,
)
CONFIRMATION = re.compile(
    r"(?:confirmation|code|number|reference)(?: code| number)?\s*(?:is|:)?\s*([A-Z0-9][A-Z0-9\-]{3,})"
)
HOLD_SUCCESS = re.compile(
    r"(set (?:it|one|that) aside|put (?:it|one|that) aside|reserved|on hold|holding|i'?ll hold|we'?ll hold|"
    r"confirmation|under the name|at the (?:counter|register|desk)|"
    r"(?:will|'ll) (?:be there|come by|pick (?:it|that|them) up|swing by|stop by)|on (?:his|her|their|our) way|"
    r"(?:we(?:'re| are)|he(?:'s| is)|she(?:'s| is)) (?:coming|heading|sending)|(?:pickup|pick-up) (?:is )?(?:confirmed|scheduled|set))",
    re.I,
)


@dataclass
class Facts:
    price: float | None = None
    quantity: int | None = None
    can_hold: bool | None = None
    wait_minutes: int | None = None
    alternatives: list[str] = field(default_factory=list)
    referral_name: str | None = None
    referral_phone: str | None = None
    notes: str | None = None
    hours: str | None = None
    requirements: str | None = None
    needs: list[str] = field(default_factory=list)
    perishables_ok: bool | None = None
    can_pickup: bool | None = None


@dataclass
class Classification:
    kind: str  # has | no | partial | closed | wait | refused | voicemail | ivr | are_you_bot | unclear
    alt: str | None = None


def classify(text: str) -> Classification:
    if REFUSED.search(text):
        return Classification("refused")
    if VOICEMAIL.search(text):
        return Classification("voicemail")
    if IVR.search(text):
        return Classification("ivr")
    if ARE_YOU_BOT.search(text) and not HAS_STOCK.search(text):
        return Classification("are_you_bot")

    main = REFERRAL_SPLIT.split(text, maxsplit=1)[0]
    closed = CLOSED.search(main)
    no = NO_STOCK.search(main)
    has = HAS_STOCK.search(NO_STOCK.sub(" ", main))
    alt_match = BUT_HAVE.search(main) or ONLY_HAVE.search(main)
    alt = alt_match.group(1).strip() if alt_match else None

    if closed and not has:
        return Classification("closed")
    if alt and (no or closed or ONLY_HAVE.search(main)):
        return Classification("partial", alt)
    if no and not has:
        return Classification("no")
    if has and not no:
        return Classification("has")
    if HOLD_ON.search(text):
        return Classification("wait")
    return Classification("unclear")


def _num(token: str) -> int:
    return int(token) if token.isdigit() else WORD_NUM[token.lower()]


def extract_facts(text: str) -> Facts:
    facts = Facts()
    price = PRICE.search(text) or PRICE_WORDS.search(text)
    if price:
        facts.price = float(price.group(1))
    qty = QTY.search(text)
    if qty:
        facts.quantity = _num(qty.group(1))
    elif re.search(r"\b(?:a couple|couple of)\b", text, re.I):
        facts.quantity = 2
    elif re.search(r"\bjust one\b", text, re.I):
        facts.quantity = 1

    if HOLD_NO.search(text):
        facts.can_hold = False
    elif HOLD_YES.search(text):
        facts.can_hold = True

    minutes = WAIT_MIN.search(text)
    hours = WAIT_HOURS.search(text)
    if minutes:
        facts.wait_minutes = int(minutes.group(1))
    elif re.search(r"\bhalf an hour\b", text, re.I):
        facts.wait_minutes = 30
    elif re.search(r"\ban hour\b", text, re.I):
        facts.wait_minutes = 60
    elif hours:
        facts.wait_minutes = int(float(hours.group(1)) * 60)

    ref = REFERRAL.search(text)
    if ref:
        name = ref.group(1).strip(" .,'")
        if name and name.lower() not in {"i", "it", "the", "us"}:
            facts.referral_name = name
            tail = text[ref.end():]
            phone = PHONE.search(tail)
            if phone:
                facts.referral_phone = phone.group(1).strip()
    return facts


def extract_confirmation(text: str) -> str | None:
    match = CONFIRMATION.search(text)
    return match.group(1) if match else None


# ----------------------------------------------------------------------------- food pantries
FOOD_NO = re.compile(
    r"\b(we(?:'re| are) closed|closed (?:today|tomorrow|right now)|not open|no distribution|nothing today|"
    r"(?:ran|run) out|out of food|(?:all )?(?:out|gone) for (?:the day|today)|done for (?:the day|today)|"
    r"not giving out|no food (?:today|left)|we don'?t (?:have|do) (?:any )?(?:distribution|food)|"
    r"not accepting|no longer accepting|at capacity|we(?:'re| are) full|can'?t take|don'?t (?:take|accept) donations|"
    r"no donations)\b",
    re.I,
)
FOOD_PARTIAL = re.compile(
    r"\b((?:only|just)\s+(?:open\s+|for\s+|serving\s+|accepting\s+|taking\s+)?(?:residents|seniors|families|"
    r"registered|members|clients|zip|non-?perishable|shelf[- ]stable|canned|dry goods|monetary|money|cash)|"
    r"by appointment only|appointment only|appointment required|registered (?:clients|families) only|"
    r"don'?t (?:take|accept) (?:any )?(?:fresh|perishable|produce|frozen)|no (?:fresh|perishables?|frozen)|"
    r"drop[- ]?offs? only|you(?:'d| would| will)? (?:need|have|'ll have) to (?:bring|drop)|"
    r"(?:can'?t|cannot|don'?t|unable to) (?:do )?(?:pick ?-?ups?|pick (?:it|that|them) up|send (?:a|anyone|someone))[^.!?]*(?:but|you can|you could|bring|drop))",
    re.I,
)
FOOD_YES = re.compile(
    r"\b(yes|yeah|yep|sure|absolutely|we do|we(?:'re| are) open|open (?:today|until|till|from)|"
    r"we(?:'re| are) (?:giving out|serving|accepting|taking|distributing)|giving out|distribution|"
    r"we (?:accept|take)|happy to take|drop[- ]?offs? (?:are|is|from|between)|come (?:by|on in|down)|"
    r"we (?:can|could) (?:send|pick|come|get (?:someone|a volunteer|a driver)|have (?:someone|a volunteer|a driver))|"
    r"(?:send|have) (?:a |our )?(?:volunteer|driver|van|truck|someone)|happy to (?:pick|send|come))\b",
    re.I,
)
HOURS_RANGE = re.compile(
    r"\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?\s*(?:to|-|until|till|through)\s*\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)",
    re.I,
)
HOURS_OPEN = re.compile(r"(?:until|till|from|after)\s+\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)", re.I)
REQ_RE = re.compile(
    r"([^.!?]*\b(?:bring|photo id|an id|your id|id\b|proof of|zip code|residents? of|appointment|sign[- ]?up|register|"
    r"no (?:id|questions|paperwork)|nothing (?:to bring|needed)|just show up|walk[- ]?ins?)[^.!?]*[.!?]?)",
    re.I,
)
NEEDS_RE = re.compile(
    r"(?:we(?:'re| are)? (?:really )?(?:low on|short on|running low on|out of)|we (?:could|can) (?:really )?use|"
    r"we (?:most )?need|(?:most )?needed (?:are|is)|in need of|always need|need most(?: right now)?(?: is| are)?)\s+(.+?)(?:[.!?]|$)",
    re.I,
)
NO_PERISHABLE = re.compile(
    r"(?:don'?t|can'?t|cannot|no|not|unable to)\b[^.!?]{0,25}\b(?:fresh|perishable|refrigerat|frozen|produce)", re.I
)
YES_PERISHABLE = re.compile(
    r"(?:\b(?:take|accept|welcome|love|can use|happy to have)\b[^.!?]{0,25}\b(?:fresh|produce|refrigerat|frozen|perishable)|"
    r"\b(?:fresh|produce|refrigerated|frozen)\b[^.!?]{0,15}\b(?:is|are)? ?(?:fine|welcome|okay|great|no problem|not a problem|no issue)|"
    r"\b(?:walk-?in (?:cooler|fridge|freezer)|cold storage|refrigeration|big (?:fridge|freezer))\b)",
    re.I,
)


NO_PICKUP = re.compile(
    r"(?:can'?t|cannot|don'?t|do not|unable to|no)\b[^.!?]{0,20}\b(?:pick ?-?ups?|pick (?:it|that|them) up|send (?:a|anyone|someone|a driver))"
    r"|drop[- ]?offs? only|you(?:'d| would| will)? (?:need|have|'ll have) to (?:bring|drop)",
    re.I,
)
YES_PICKUP = re.compile(
    r"\b(?:we (?:can|could) (?:send|pick|come|get (?:someone|a volunteer|a driver)|have (?:someone|a volunteer|a driver))|"
    r"(?:send|have) (?:a |our )?(?:volunteer|driver|van|truck|someone)|happy to (?:pick|send|come)|"
    r"(?:pick(?:ing)? (?:it|that|them) up)|(?:be|get) there in)\b",
    re.I,
)


def classify_food(text: str) -> Classification:
    """Pantry-flavoured version of `classify`: kind in has | partial | no | wait | refused | voicemail | ivr | are_you_bot | unclear."""
    if REFUSED.search(text):
        return Classification("refused")
    if VOICEMAIL.search(text):
        return Classification("voicemail")
    if IVR.search(text):
        return Classification("ivr")
    if ARE_YOU_BOT.search(text) and not FOOD_YES.search(text):
        return Classification("are_you_bot")
    main = REFERRAL_SPLIT.split(text, maxsplit=1)[0]
    no = FOOD_NO.search(main)
    partial = FOOD_PARTIAL.search(main)
    yes = FOOD_YES.search(main)
    but_take = re.search(r"\bbut we (?:do )?(?:take|accept|have|offer)\b", main, re.I)
    if no and not (but_take or (yes and partial)):
        return Classification("no")
    if partial or but_take:
        return Classification("partial")
    if yes and not no:
        return Classification("has")
    if HOLD_ON.search(text):
        return Classification("wait")
    return Classification("unclear")


def extract_food_facts(text: str) -> Facts:
    facts = extract_facts(text)
    hours = HOURS_RANGE.search(text) or HOURS_OPEN.search(text)
    if hours:
        facts.hours = hours.group(0).strip().rstrip(".")
    req = REQ_RE.search(text)
    if req:
        facts.requirements = req.group(1).strip(" ,;")[:160]
    needs = NEEDS_RE.search(text)
    if needs:
        parts = re.split(r",\s*(?:and\s+)?|\s+and\s+", needs.group(1))
        facts.needs = [p.strip(" .") for p in parts if p.strip(" .")][:5]
    if NO_PICKUP.search(text):
        facts.can_pickup = False
    elif YES_PICKUP.search(text):
        facts.can_pickup = True
    if NO_PERISHABLE.search(text):
        facts.perishables_ok = False
    elif YES_PERISHABLE.search(text):
        facts.perishables_ok = True
    return facts
