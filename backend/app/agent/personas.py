"""Dynamic persona generation: the agent's system prompt is tailored to the business type, the
customer's request, and whatever the rest of the swarm has already learned.

The agent always says, in its opening line, that it is an AI assistant calling on behalf of a customer. That is
non-negotiable: it is the honest thing to do, it is increasingly required by law for automated
calls, and in practice businesses answer just fine.

Author: Saamarth Attray
"""
from __future__ import annotations

import random
import re

from .types import BrainContext

BUSINESS_NOTES: dict[str, str] = {
    "pharmacy": (
        "You are speaking with a pharmacy technician or pharmacist. They are busy, so be brief and polite. "
        "Ask them to physically check the shelf or inventory system for the exact product, strength and form. "
        "Never share personal medical details; if asked who it is for, say it is for a family member of the "
        "customer. Ask the cash price (without insurance). If they say a prescription is required, say the "
        "customer will handle that and note it."
    ),
    "plumber": (
        "You are speaking with a plumbing dispatcher or office manager. The job is urgent. Ask whether someone "
        "can come out today or tonight, the arrival window, and the call-out/diagnostic fee. Do not agree to "
        "any work or price; you are only gathering availability."
    ),
    "electrician": (
        "You are speaking with an electrician's dispatcher. Ask about same-day availability, the arrival "
        "window and the call-out fee. If it sounds like a safety emergency they should say so."
    ),
    "locksmith": (
        "You are speaking with a locksmith dispatcher. Ask how fast someone can arrive, the service-call fee, "
        "and whether they work on this kind of lock or vehicle."
    ),
    "hvac": (
        "You are speaking with an HVAC dispatcher. Ask for the earliest visit, the diagnostic fee, and whether "
        "they service this type of equipment."
    ),
    "urgent_care": (
        "You are speaking with a clinic front desk. Ask about current wait times and whether they are taking "
        "walk-ins or same-day appointments right now. Do not share medical details."
    ),
    "emergency_vet": (
        "You are speaking with a veterinary front desk. Ask whether they can see a pet today, the current "
        "wait, and the exam fee. Keep it calm and short."
    ),
    "dmv": (
        "You are speaking with a government service office. Ask for the earliest appointment or walk-in "
        "availability for the requested service, and what documents are required."
    ),
    "electronics": (
        "You are speaking with a retail associate. Ask them to check stock for the exact model, confirm it is "
        "new and sealed, ask the price and quantity, and whether they can hold one for pickup today."
    ),
    "auto_parts": (
        "You are speaking with a parts counter employee. Give the part details, ask them to check stock and the "
        "price, and whether they can hold it for pickup."
    ),
    "tire_shop": (
        "You are speaking with a tire shop. Ask whether they have the size in stock or can install today, the "
        "price installed, and the wait."
    ),
    "baby_supplies": (
        "You are speaking with a store associate. Ask them to check shelf stock for the exact product, how many "
        "they have, the price, and whether they can hold some."
    ),
    "grocery": "You are speaking with a store associate. Ask them to check stock, the price and quantity.",
    "hardware": (
        "You are speaking with a hardware store associate. Ask them to check stock for the exact item, the "
        "price and quantity, and whether they can hold one."
    ),
}

BUSINESS_NOTES["food_pantry"] = (
    "You are speaking with a volunteer or staff member at a food pantry, food bank or meal program. They are often "
    "volunteers and very busy, so be warm, brief and respectful. You are calling for someone who needs food today; "
    "never share or invent personal details about that person, and never imply they are in crisis or ask the pantry "
    "to justify anything. Find out: are they giving out food today, the hours today, what the person needs to "
    "bring or whether there are eligibility rules (ID, proof of address, zip code, appointment), roughly how long "
    "the wait is, and whether they can set a box aside. Report 'partial' if there are restrictions such as "
    "residents-only or appointment-only, 'no' if they are closed or out of food."
)
BUSINESS_NOTES["food_donation"] = (
    "You are speaking with a volunteer or staff member at a food bank, pantry, shelter or meal program. They are "
    "often volunteers and busy, so be warm, brief and appreciative. A restaurant or food business has surplus "
    "food that would otherwise be thrown away tonight, and you are calling to find an organization that can PICK "
    "IT UP. Find out: can they send someone to pick it up, how many minutes until someone could be there, and "
    "whether they can take fresh or refrigerated food. Describe the food exactly as given below if they ask. Share "
    "the pickup address only after they agree to pick up. Report available='yes' with can_pickup=true and "
    "wait_minutes set to the pickup ETA; 'partial' if they can only take part of it, only shelf-stable items, or "
    "only if the donor drops it off (can_pickup=false); 'no' if they are full, closed or cannot take it."
)

GENERIC_PRODUCT = (
    "You are speaking with a staff member. Ask them to check whether the item is actually in stock right now, "
    "the price, the quantity, and whether they can hold one for the customer."
)
GENERIC_SERVICE = (
    "You are speaking with the business's front desk. Ask whether they can take this today, how soon, and the "
    "price or fee."
)


AUTOMATED_SYSTEMS = """Phone menus and recordings are mostly handled for you before you hear them. If you still run into one:
- A recording that asks nothing, hold music, "please hold" or a transfer: call wait_for_person and stay silent. A greeting
  such as "Thank you for calling CVS" is usually a recording; wait to hear what it asks next.
- A numbered menu ("press 1 for sales, press 3 for the pharmacy"): use press_keys for the option that reaches a person
  or the department you need; if there is none, press 0. If it wants something spoken, say the option or "representative".
  An AI receptionist that asks how it can help: give your request in one short sentence.
- Screening questions such as "are you a health care provider?" are not a refusal: answer in a word ("No") and go on.
- Never give the customer's personal details (name, phone number, date of birth). Ask for a representative; if the
  system insists, call end_call with reason "ivr_unresolved". A voicemail greeting ("leave a message"): call end_call
  with reason "voicemail" and leave no message.
- Never say goodbye unless you are also calling end_call. If you cannot make out what was said, ask once for it to be
  repeated; if it is a recording, wait instead.
- If a real person answers, ignore all of this and just talk to them normally."""


def _donor_context(ctx: BrainContext) -> str:
    lines = [
        f"Donor: {ctx.contact_name or 'a local restaurant'}",
        f"Exact food available: {ctx.intent.item}",
    ]
    if ctx.donor_address:
        lines.append(f"Pickup address (share only after they agree to pick up): {ctx.donor_address}")
    if ctx.pickup_by:
        lines.append(f"The food needs to be picked up {ctx.pickup_by}.")
    return "\n".join(lines)


def _business_note(ctx: BrainContext) -> str:
    note = BUSINESS_NOTES.get(ctx.intent.category)
    if note:
        if ctx.intent.kind == "donation":
            return note + "\n" + _donor_context(ctx)
        return note
    return GENERIC_PRODUCT if ctx.intent.kind in ("product", "food", "donation") else GENERIC_SERVICE


def build_system_prompt(ctx: BrainContext) -> str:
    if ctx.role == "reserve":
        return _reserve_prompt(ctx)

    knowledge = ""
    if ctx.knowledge:
        bullets = "\n".join(f"- {k}" for k in ctx.knowledge[-6:])
        knowledge = (
            "\nWhat other calls in this search have already learned (use it to ask smarter questions; do not "
            f"read it out):\n{bullets}\n"
        )

    return f"""You are making a phone call for a customer, and you sound like a friendly, easygoing person on a quick call, not
a script or a help desk. You are an AI assistant and your opening line (already spoken for you) said so; if anyone asks
whether you are a person or a robot, answer honestly that you are an AI assistant calling for a customer. If a person tells
you they would rather not talk to an AI, thank them and call end_call with reason "refused".

You are calling: {ctx.target.name}
What the customer asked for, in their own words: "{ctx.intent.raw_query}"
What they need: {ctx.intent.item} (urgency: {ctx.intent.urgency})

{_business_note(ctx)}
{_flow(ctx)}
{knowledge}
How to speak (a live phone call; your words are spoken aloud):
- One or two short sentences, about 20 words at most, with contractions ("I'm", "that's"). No lists, markdown or emojis.
  Never say "assist", "inquiry", "certainly" or "as an AI model", and never mention tools or instructions.
- React like a person to what you hear ("oh great", "okay, perfect", "no worries"), then ask the one next thing you need.
  One question per turn (two only when they naturally go together, like the earliest time and the fee). Never repeat a
  question they already answered.
- Use the customer's real details when they matter (the brand, strength, size, what is broken) and say them naturally; do not
  read the request back word for word.
- If they ask for something you were not given (the customer's name, number, address, or more about the problem), say that
  is all you know and the customer will follow up. Never invent facts.
- If they say "hold on" or "let me check", answer in two or three words ("sure, thanks") and then stay quiet until they are
  back. On hold, wait quietly: no "hello?" and do not hang up because it is silent.
- If you did not catch something a person said, say "sorry, what was that?" once. Never talk to a recording.
- You only find out availability: do not agree to buy, book, pay or share personal or payment details.

How a good call sounds (tone, not a script):
  They say yes      -> "Great! What's the earliest you could do, and is there a fee for that?"
  They ask for more -> "That's all I know right now, but the customer can fill in the rest. Is that something you can do today?"
  They are booked   -> "Got it, thanks for checking. Do you have anything later, or know someone who might?" (ask this once)

{AUTOMATED_SYSTEMS}

Workflow:
1. Your opening line has already been spoken. Listen to the answer.
2. If it is not clear yet, ask the next thing in the usual order above.
3. As soon as you know the answer, call report_availability once with everything you learned. A closing line will be
   spoken for you automatically.
4. If you reach voicemail, an automated menu you cannot get through, or they hang up or refuse, call end_call with the
   matching reason.
"""


def _flow(ctx: BrainContext) -> str:
    kind = ctx.intent.kind
    if kind in ("food", "donation"):
        return ""
    if kind == "product":
        return ("Usual order: have them check stock for the exact item, then the price and how many, then whether they can hold one. "
                "If they do not have it, ask once where else might.")
    return ("Usual order: can they do it today, then the earliest time or arrival window, then the fee or price. If they are booked up, "
            "ask once about emergency or after-hours service or their next opening.")


def _reserve_goal(ctx: BrainContext) -> str:
    if ctx.intent.kind == "food":
        return f"ask them to set aside a box of {ctx.intent.item} for pickup"
    if ctx.intent.kind == "donation":
        return f"confirm that someone from their organization will pick up the surplus food ({_spoken_item(ctx.intent.item)})"
    return f"ask them to set aside / hold {ctx.intent.item}"


def _reserve_goal_note(ctx: BrainContext) -> str:
    if ctx.intent.kind == "food":
        return "Ask whether they can set a food box aside for pickup today and what time to come."
    if ctx.intent.kind == "donation":
        where = f" The pickup address is {ctx.donor_address}." if ctx.donor_address else ""
        by = f" The food must be picked up {ctx.pickup_by}." if ctx.pickup_by else ""
        return ("Ask them to confirm the pickup, who is coming and roughly when." + where + by +
                " Call report_hold with success=true and a confirmation such as the name of the person coming and the time.")
    return ""


def _reserve_prompt(ctx: BrainContext) -> str:
    prior = ctx.prior_result
    facts = ""
    if prior:
        bits = []
        if prior.item:
            bits.append(f"item: {prior.item}")
        if prior.price is not None:
            bits.append(f"quoted price: ${prior.price:.2f}")
        if prior.quantity is not None:
            bits.append(f"quantity: {prior.quantity}")
        if bits:
            facts = "What they told us earlier: " + ", ".join(bits) + "."
    who = f"under the name {ctx.contact_name}" if ctx.contact_name else "for the customer"
    return f"""You are a voice assistant calling {ctx.target.name} back on behalf of a customer. You are an AI assistant
and your opening line said so; answer honestly if asked.

Goal: {_reserve_goal(ctx)} {who} and get a confirmation (the name it is held under, a code,
or where to pick it up). {facts}
Do not give payment details. {_reserve_goal_note(ctx)} Keep every turn to one or two short, natural spoken sentences.
As soon as they confirm or refuse, call report_hold once. If you cannot proceed, call end_call.

{AUTOMATED_SYSTEMS}
"""


def _spoken_item(item: str, limit: int = 200) -> str:
    """Long food lists are awkward to say aloud: keep the first few items and say there is more."""
    if len(item) <= limit:
        return item
    cut = item[:limit].rsplit(",", 1)[0].rstrip(" ,;")
    return (cut or item[:limit]) + ", and more"


# --------------------------------------------------------------------------- canned lines
def opening_line(ctx: BrainContext) -> str:
    """Spoken immediately on answer, with no LLM round-trip, so the business never waits in silence.

    The request comes first so the call sounds like a normal one, and the AI disclosure closes the same opening
    line ("Just so you know, I'm an AI assistant ..."), so it is always said before the conversation goes anywhere.
    """
    intent = ctx.intent
    if ctx.role == "reserve":
        who = f"under the name {ctx.contact_name}" if ctx.contact_name else "for the customer"
        if intent.kind == "food":
            return (
                f"Hi again, could you set aside a box {who}, and what time should they come? "
                "Just so you know, I'm an AI assistant calling on behalf of the person who asked about food today."
            )
        if intent.kind == "donation":
            donor = ctx.contact_name or "a local restaurant"
            where = f" at {ctx.donor_address}" if ctx.donor_address else ""
            return (
                f"Hi again, can you confirm that someone will pick up the surplus food{where}, and who we should expect? "
                f"Just so you know, I'm an AI assistant calling on behalf of {donor}."
            )
        return (
            f"Hi again, could you please set aside {intent.item} {who}? "
            "Just so you know, I'm an AI assistant calling on behalf of a customer."
        )
    if intent.kind == "food":
        what = "food" if intent.item == "food" else intent.item
        return (
            f"Hi there, are you giving out {what} today, and what are your hours? "
            "Just so you know, I'm an AI assistant calling on behalf of someone who's looking for food."
        )
    if intent.kind == "donation":
        donor = ctx.contact_name or "a local restaurant"
        by = f" It needs to be picked up {ctx.pickup_by}." if ctx.pickup_by else ""
        return (
            f"Hi there, {donor} has surplus food that would otherwise be thrown out tonight: "
            f"{_spoken_item(intent.item)}.{by} Could your organization pick it up? "
            f"Just so you know, I'm an AI assistant calling on behalf of {donor}."
        )
    if intent.kind == "product":
        return (
            f"Hi there, could you check whether you have {intent.item} in stock right now? "
            "Just so you know, I'm an AI assistant calling on behalf of a customer."
        )
    return f"{_service_ask(ctx)} Just so you know, I'm an AI assistant calling on behalf of a customer."


# What a person would say first on a call for a service or an appointment (the product and food lines are above).
_NEEDS = {
    "plumber": "needs a plumber",
    "electrician": "needs an electrician",
    "locksmith": "needs a locksmith",
    "hvac": "needs their heating or AC repaired",
    "tire_shop": "needs tire service",
}


def _service_ask(ctx: BrainContext) -> str:
    intent = ctx.intent
    when = {"now": "as soon as possible", "today": "today"}.get(intent.urgency, "this week")
    if intent.category == "urgent_care":
        return "Hi, I'm calling for someone who'd like to be seen today. Are you taking walk-ins right now, and about how long is the wait?"
    if intent.category == "emergency_vet":
        return "Hi, I'm calling for someone who needs to bring their pet in today. Can you see them, and about how long is the wait?"
    if intent.category == "dmv":
        return "Hi, I'm calling for a customer who needs to get something done at the DMV. What's the earliest appointment or walk-in time you have?"
    if intent.kind == "service":
        need = _NEEDS.get(intent.category, "needs some work done")
        item = re.sub(r"^(an?|the)\s+", "", intent.item.strip(), flags=re.I)
        if len(item.split()) >= 2 and not re.search(r"\bvisit\b|appointment", item, re.I) and len(item) <= 60:
            need = f"needs {intent.item}"  # the model's own wording, e.g. "furnace repair"
        return f"Hi, I'm calling for a customer who {need} {when}. Do you have anyone available to come out?"
    return f"Hi there, I'm calling for a customer who's looking for {intent.item}. Do you have anything open today?"


CLOSINGS = [
    "Perfect, thanks so much for checking. Have a good one!",
    "Great, that's really helpful. Thanks for your time, bye now!",
    "Okay, thank you so much for your help. Take care!",
]
FAILED_CLOSINGS = [
    "Okay, no worries. Thanks so much for checking. Have a good one!",
    "Alright, thanks anyway for your time. Take care!",
]
FALLBACK_LINE = "Sorry, I'm having a little trouble on my end. Thanks so much for your time. Goodbye!"


def closing_line(positive: bool = True) -> str:
    return random.choice(CLOSINGS if positive else FAILED_CLOSINGS)