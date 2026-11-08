"""Keypad (DTMF) tones as 8 kHz mu-law audio, so the agent can "press 3 for the pharmacy" on a phone menu.

Twilio Media Streams has no dedicated DTMF event, but audio we send into the stream is played to the far end of the
call, and phone menus detect in-band tones. Each key is two sine waves (one low, one high frequency) played for a
quarter of a second with a short pause between keys.

Author: Saamarth Attray
"""
from __future__ import annotations

import math
import re

SAMPLE_RATE = 8000
TONE_MS = 250
GAP_MS = 150
AMPLITUDE = 0.35  # of full scale per tone; two tones sum to 0.7, loud enough for menus without clipping

_LOW = {"1": 697, "2": 697, "3": 697, "4": 770, "5": 770, "6": 770, "7": 852, "8": 852, "9": 852, "*": 941, "0": 941, "#": 941}
_HIGH = {"1": 1209, "2": 1336, "3": 1477, "4": 1209, "5": 1336, "6": 1477, "7": 1209, "8": 1336, "9": 1477, "*": 1209, "0": 1336, "#": 1477}

MAX_KEYS = 12
_VALID = re.compile(r"[^0-9*#]")


def clean_digits(raw: object) -> str:
    """Keep only keypad characters (the model may send "3", "press 3", "1,2" or "#"), capped at a sane length."""
    return _VALID.sub("", str(raw or ""))[:MAX_KEYS]


def _mulaw(sample: int) -> int:
    """G.711 mu-law encode one 16-bit PCM sample."""
    bias, clip = 0x84, 32635
    sign = 0x80 if sample < 0 else 0
    sample = min(abs(sample), clip) + bias
    exponent = 7
    mask = 0x4000
    while exponent > 0 and not (sample & mask):
        exponent -= 1
        mask >>= 1
    mantissa = (sample >> (exponent + 3)) & 0x0F
    return ~(sign | (exponent << 4) | mantissa) & 0xFF


def dtmf_mulaw(digits: str) -> bytes:
    """Mu-law audio for a string of keypad characters (anything else is ignored)."""
    out = bytearray()
    silence = bytes([0xFF]) * int(SAMPLE_RATE * GAP_MS / 1000)
    for key in clean_digits(digits):
        f1, f2 = _LOW[key], _HIGH[key]
        for n in range(int(SAMPLE_RATE * TONE_MS / 1000)):
            t = n / SAMPLE_RATE
            value = AMPLITUDE * (math.sin(2 * math.pi * f1 * t) + math.sin(2 * math.pi * f2 * t))
            out.append(_mulaw(int(value * 32767)))
        out += silence
    return bytes(out)