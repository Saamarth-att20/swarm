"""Phone-menu navigator: the automated half of a call, handled with rules instead of the language model.

Many businesses answer with a recording, a keypad menu or a voice assistant before a person. Those machines are
predictable, so we answer them with fast rules (no model call, no waiting, no rate limits) and keep the language
model for the real conversation with a person.

    move = navigator.decide(heard)
    None            -> not a machine: let the language model talk
    Move("wait")    -> stay silent and listen (recording, hold music, "please hold", a transfer)
    Move("say", .)  -> answer the machine in a few words ("Front store.", "No.", "Representative.")
    Move("keys", .) -> press keypad keys ("3" for "to speak to a member of the pharmacy staff, press 3")
    Move("intro")   -> a person just came on the line: introduce ourselves and ask our question again
    Move("end", .)  -> hang up for a reason (voicemail, closed, stuck in a menu)

We never read out personal details of the customer: identity checks (phone number, date of birth...) are declined by
asking for a representative, and the call ends if the machine insists.

Author: Saamarth Attray
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .types import BrainContext

_WORD_KEYS = {
    "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
    "seven": "7", "eight": "8", "nine": "9", "star": "*", "asterisk": "*", "pound": "#", "hash": "#",
}
_KEY = r"(\d|zero|one|two|three|four|five|six|seven|eight|nine|star|asterisk|pound|hash)"


def _key(raw: str) -> str:
    return _WORD_KEYS.get(raw.lower(), raw)


VOICEMAIL = re.compile(r"leave (?:a |your )?(?:message|name)|after the (?:tone|beep)|voice ?mail|mailbox", re.I)
CLOSED = re.compile(
    r"\b(?:currently|now|is|are|we're|we are) closed\b|outside (?:of )?(?:our )?(?:regular |normal )?"
    r"(?:business|store|pharmacy|office) hours|(?:will|we) re-?open",
    re.I,
)
TRANSFER = re.compile(
    r"transfer(?:ring)? you|connect(?:ing)? you|(?:stay|remain) on the line|please (?:hold|wait)|hold (?:on )?(?:while|for|please)|"
    r"one moment (?:while|please)|next available|thank you for (?:holding|your patience)|your call is (?:important|being)|"
    r"all (?:of our )?(?:representatives|agents|associates|team members|pharmacists|lines) are",
    re.I,
)
HOLDISH = re.compile(
    r"\b(?:hold on|hang on|bear with me|one (?:sec|second|moment|minute)|just a (?:sec|second|moment|minute)|"
    r"give me a (?:sec|second|minute|moment)|please hold)\b",
    re.I,
)
PRESS = re.compile(rf"\b(?:press|dial)\s+(?:the\s+)?{_KEY}\b|\bpress (?:the )?(?:pound|star|hash) key\b", re.I)
PAIR_KEY_FIRST = re.compile(rf"\b(?:press|dial)\s+{_KEY}\s+(?:for|to)\s+([^.,;?!]+)", re.I)
PAIR_DESC_FIRST = re.compile(rf"((?:for|to|if)\s[^.;?!]*?),?\s*(?:then\s+|please\s+|just\s+)?(?:press|dial)\s+{_KEY}\b", re.I)
PERSON = re.compile(
    r"speak (?:to|with)|talk (?:to|with)|(?:pharmacy|store|front|customer) (?:staff|team|associate|service|care)|pharmacist|"
    r"representative|operator|live (?:person|agent)|associate|team member|someone|something else|any(?:thing)? else|"
    r"all other|other (?:questions|inquiries)",
    re.I,
)
NOT_A_PERSON_OPTION = re.compile(r"prescriber|refill|hours|location|direction|spanish|espa|status|transfer a prescription|vaccine|appointment", re.I)
MENU_END = re.compile(r"hear (?:this|these|the) (?:menu|options)|to repeat|repeat (?:this|these|the) (?:menu|options)|main menu|press (?:star|\*)", re.I)
DEPT_CHOICE = re.compile(r"pharmacy or (?:the )?front ?store|front ?store or (?:the )?pharmacy|pharmacy or (?:the )?store", re.I)
OPEN_PROMPT = re.compile(
    r"you can say|please say|please tell me|tell me (?:what|why|which|how)|what (?:are you|can i|do you)|which department|"
    r"what are you calling about|say (?:anything|a department)|department name",
    re.I,
)
GATE_ASK = re.compile(
    r"(?:say|enter|provide|give me|tell me|state|speak)\b[^.?!]{0,40}?(?:digit|phone number|date of birth|birth ?date|last (?:four|4)|"
    r"social security|\bssn\b|zip|account number|prescription number|member id|your (?:full |first |last )?name)",
    re.I,
)
ANNOUNCE = re.compile(
    r"thank you for calling|welcome to|please note|calls? (?:may be|are|will be) (?:monitored|recorded)|recorded (?:for|to)|"
    r"this is an emergency|dial 911|seasonal|flu (?:shots|vaccines)|covid|walk in|no appointments|our (?:pharmacy |store )?hours are|"
    r"automated|virtual assistant|your call (?:may|will)",
    re.I,
)
HUMAN_CUE = re.compile(
    r"\b[Tt]his is (?!(?:an?|the|our|to|not)\b)[A-Z]\w+|\b[Mm]y name is|\b[Hh]ow (?:can|may) I (?:help|assist)|\b[Ss]peaking\b|\b[Ww]hat can I do for you"
)
# A voice assistant's own error messages ("Sorry. Please tell me again...", "Let's try this a different way"): not a person.
MACHINE_ERROR = re.compile(r"^\W*(?:i'?m )?sorry\b|didn'?t (?:get|catch|understand) that|let'?s try (?:this|that) (?:a )?different", re.I)

# (pattern, spoken answer). The order matters: the first match wins.
SCREENING: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"different (?:registered )?phone number|registered phone number|verif\w+ (?:the|your) phone|text message|send you a text|text you", re.I), "No."),
    (re.compile(r"are you (?:a |an )?(?:health ?care )?(?:provider|prescriber|doctor|physician|nurse|pharmacist|medical)", re.I), "No."),
    (re.compile(r"is this an emergency", re.I), "No."),
    (re.compile(r"are you (?:a |an )?(?:patient|member|existing|returning|current)|have you (?:used|called|filled)|are you calling (?:for|about) (?:a )?(?:refill|prescription)", re.I), "No."),
    (re.compile(r"looking for (?:a )?(?:product|item) in (?:our|the) store", re.I), "Yes."),
]
# Confirmations a person could also say ("...right?"): only treated as a machine's question once we know one is on the line.
SCREENING_LOOSE: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"is that (?:correct|right)|did i (?:get|hear) that right|\bright\?|is that what you", re.I), "Yes."),
]

_RX_WORDS = re.compile(
    r"prescri|refill|antibiotic|amoxicillin|insulin|vaccine|\bshot\b|inhaler|\brx\b|medication|ozempic|adderall|"
    r"statin|steroid|epinephrine|epipen|pharmacist",
    re.I,
)

MAX_MACHINE_TURNS = 16  # a menu maze that long is not going anywhere


@dataclass
class Move:
    kind: Literal["wait", "say", "keys", "intro", "end"]
    text: str = ""  # what to say (say) or which keys to press (keys)
    reason: str = ""  # end: end_call reason


def request_line(ctx: BrainContext) -> str:
    """One short sentence stating what we want, for a voice assistant that asks what we are calling about."""
    intent = ctx.intent
    if intent.kind == "product":
        return f"I'm checking if you have {intent.item} in stock."
    if intent.kind == "food":
        return f"I'm calling about {intent.item} today."
    return f"I'm calling about {intent.item}."


class IvrNavigator:
    def __init__(self, ctx: BrainContext) -> None:
        self.ctx = ctx
        self.automated = False  # we have recognised that a machine is on the line
        self.awaiting_human = False  # we are waiting for a person to come on (after a hold, a transfer or a keypress)
        self.machine_turns = 0
        self.open_attempts = 0
        self.gate_attempts = 0
        self.zero_pressed = False

    # ------------------------------------------------------------------ helpers
    def _front_store(self) -> bool:
        """Over-the-counter products are a front-store question; prescriptions and shots are a pharmacy one."""
        return self.ctx.intent.category == "pharmacy" and not _RX_WORDS.search(self.ctx.intent.item or "")

    def _screening_answer(self, text: str, loose: bool = False) -> str | None:
        for pattern, answer in [*SCREENING, *(SCREENING_LOOSE if loose else [])]:
            if pattern.search(text):
                return answer
        return None

    def _looks_automated(self, text: str) -> bool:
        return bool(
            PRESS.search(text)
            or OPEN_PROMPT.search(text)
            or DEPT_CHOICE.search(text)
            or self._screening_answer(text)
            or TRANSFER.search(text)
            or GATE_ASK.search(text)
            or (ANNOUNCE.search(text) and not HUMAN_CUE.search(text))
        )

    def _machine(self, move: Move, *, awaiting: bool = True) -> Move:
        self.automated = True
        self.awaiting_human = awaiting
        self.machine_turns += 1
        return move

    def _menu_options(self, text: str) -> list[tuple[str, str]]:
        options: list[tuple[str, str]] = []
        for sentence in re.split(r"(?<=[.?!])\s+", text):
            for match in PAIR_KEY_FIRST.finditer(sentence):
                options.append((_key(match.group(1)), match.group(2).strip()))
            for match in PAIR_DESC_FIRST.finditer(sentence):
                options.append((_key(match.group(2)), match.group(1).strip()))
        return options

    # ------------------------------------------------------------------ the decision
    def decide(self, heard: str) -> Move | None:
        text = " ".join(heard.split())
        active = self.automated or self.awaiting_human
        automated_looking = self._looks_automated(text)

        if VOICEMAIL.search(text):
            return Move("end", reason="voicemail")
        if (active or automated_looking) and CLOSED.search(text):
            return Move("end", reason="closed")
        if self.machine_turns >= MAX_MACHINE_TURNS:
            return Move("end", reason="ivr_unresolved")

        # "Would you like to give a different phone number? Yes or no": no. Checked before the identity gate below.
        strong = self._screening_answer(text)
        if strong == "No." and re.search(r"different|verif|text", text, re.I):
            return self._machine(Move("say", strong))

        # Identity checks: never give the customer's details. Ask for a person; give up if it insists.
        if GATE_ASK.search(text) and not PRESS.search(text) and (active or automated_looking):
            self.gate_attempts += 1
            if self.gate_attempts == 1:
                return self._machine(Move("say", "Representative."))
            if self.gate_attempts == 2:
                self.zero_pressed = True
                return self._machine(Move("keys", "0"))
            return Move("end", reason="ivr_unresolved")

        # "Please hold", "I'll transfer you": wait for the person.
        if TRANSFER.search(text) or (active and HOLDISH.search(text)):
            return self._machine(Move("wait"))

        # A numbered menu: press the option for a person (or the department we need); wait for the rest of a menu that
        # is read out in pieces; press 0 if the whole menu had no such option.
        options = self._menu_options(text) if PRESS.search(text) else []
        if PRESS.search(text) and (options or not OPEN_PROMPT.search(text)):
            usable = [(k, d) for k, d in options if PERSON.search(d) and not NOT_A_PERSON_OPTION.search(d)]
            if usable:
                self.zero_pressed = False
                return self._machine(Move("keys", usable[0][0]))
            if MENU_END.search(text):  # the whole menu has been read and none of it was a person
                if not self.zero_pressed:
                    self.zero_pressed = True
                    return self._machine(Move("keys", "0"))
                self.open_attempts += 1
                if self.open_attempts == 1:
                    return self._machine(Move("say", "Representative."))
                return Move("end", reason="ivr_unresolved")
            return self._machine(Move("wait"), awaiting=False)  # the rest of the menu is still coming

        if DEPT_CHOICE.search(text):
            return self._machine(Move("say", "Front store." if self._front_store() else "Pharmacy."))

        answer = self._screening_answer(text, loose=active)
        if answer and (active or automated_looking):
            return self._machine(Move("say", answer))

        if OPEN_PROMPT.search(text) and (active or automated_looking):
            self.open_attempts += 1
            if self.open_attempts == 1:
                return self._machine(Move("say", request_line(self.ctx)))
            if self.open_attempts == 2:
                return self._machine(Move("say", "Representative."))
            if self.open_attempts == 3 and not self.zero_pressed:
                self.zero_pressed = True
                return self._machine(Move("keys", "0"))
            return Move("end", reason="ivr_unresolved")

        if MACHINE_ERROR.search(text) and (active or automated_looking or len(text.split()) <= 8):
            return self._machine(Move("wait"), awaiting=False)

        # A recording that asks us nothing: listen.
        if ANNOUNCE.search(text) and not HUMAN_CUE.search(text) and "?" not in text:
            return self._machine(Move("wait"))

        # Nothing machine-like and we were waiting: a person has come on the line.
        if self.awaiting_human:
            self.awaiting_human = False
            self.automated = False
            return Move("intro")
        return None