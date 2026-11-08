"""Twilio Programmable Voice: placing calls, TwiML, webhook signature checks, and the registry that links a
live phone call to the CallSession that is running it.

Author: Saamarth Attray
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from typing import Mapping, Protocol
from xml.sax.saxutils import escape, quoteattr

import httpx

from ..agent.session import CallSession
from ..agent.types import CallOutcome
from ..config import Settings
from ..reporter import CallReporter


class TelephonyError(RuntimeError):
    pass


@dataclass
class LiveCallContext:
    call_id: str
    swarm_id: str
    session: CallSession
    reporter: CallReporter
    future: "asyncio.Future[CallOutcome]"
    token: str = field(default_factory=lambda: secrets.token_urlsafe(16))
    call_sid: str | None = None
    stream_sid: str | None = None

    def resolve(self, outcome: CallOutcome) -> None:
        if not self.future.done():
            self.future.set_result(outcome)


class LiveCallRegistry:
    def __init__(self) -> None:
        self._calls: dict[str, LiveCallContext] = {}

    def register(self, ctx: LiveCallContext) -> None:
        self._calls[ctx.call_id] = ctx

    def get(self, call_id: str) -> LiveCallContext | None:
        return self._calls.get(call_id)

    def remove(self, call_id: str) -> None:
        self._calls.pop(call_id, None)


class Telephony(Protocol):
    async def place_call(self, *, call_id: str, to: str) -> str: ...

    async def hangup(self, call_sid: str) -> None: ...


class NullTelephony:
    async def place_call(self, *, call_id: str, to: str) -> str:
        raise TelephonyError("Twilio is not configured")

    async def hangup(self, call_sid: str) -> None:
        return None


class TwilioTelephony:
    API = "https://api.twilio.com/2010-04-01"

    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None):
        self.settings = settings
        self._http = http or httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0))
        self._auth = (settings.twilio_account_sid or "", settings.twilio_auth_token or "")

    def _may_record(self, to: str) -> bool:
        """Recording is only ever switched on for your own test phones, never for real businesses (consent)."""
        s = self.settings
        return bool(s.record_demo_calls and not s.allow_real_business_calls and to in {phone for _, phone in s.demo_targets})

    async def place_call(self, *, call_id: str, to: str) -> str:
        base = self.settings.public_base_url
        data = {
            "To": to,
            "From": self.settings.twilio_from_number,
            "Url": f"{base}/twilio/voice/{call_id}",
            "Method": "POST",
            "StatusCallback": f"{base}/twilio/status/{call_id}",
            "StatusCallbackMethod": "POST",
            "StatusCallbackEvent": ["initiated", "ringing", "answered", "completed"],
            "Timeout": "25",
        }
        if self._may_record(to):
            data["Record"] = "true"
            data["RecordingChannels"] = "dual"  # business and agent on separate channels
        resp = await self._http.post(
            f"{self.API}/Accounts/{self.settings.twilio_account_sid}/Calls.json", data=data, auth=self._auth
        )
        if resp.status_code >= 400:
            try:
                message = resp.json().get("message", resp.text)
            except ValueError:
                message = resp.text
            raise TelephonyError(f"Twilio {resp.status_code}: {message[:200]}")
        return resp.json()["sid"]

    async def hangup(self, call_sid: str) -> None:
        try:
            await self._http.post(
                f"{self.API}/Accounts/{self.settings.twilio_account_sid}/Calls/{call_sid}.json",
                data={"Status": "completed"},
                auth=self._auth,
            )
        except httpx.HTTPError:
            pass  # best effort: the call may already be over


# ----------------------------------------------------------------------------- TwiML
def twiml_connect_stream(ws_url: str, call_id: str, token: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response><Connect>"
        f"<Stream url={quoteattr(ws_url)}>"
        f"<Parameter name=\"call_id\" value={quoteattr(call_id)}/>"
        f"<Parameter name=\"token\" value={quoteattr(token)}/>"
        "</Stream></Connect></Response>"
    )


def twiml_hangup(message: str | None = None) -> str:
    say = f"<Say>{escape(message)}</Say>" if message else ""
    return f'<?xml version="1.0" encoding="UTF-8"?><Response>{say}<Hangup/></Response>'


# ----------------------------------------------------------------------------- webhook signatures
def compute_signature(url: str, params: Mapping[str, str], auth_token: str) -> str:
    payload = url + "".join(f"{key}{params[key]}" for key in sorted(params))
    digest = hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def validate_signature(url: str, params: Mapping[str, str], signature: str | None, auth_token: str) -> bool:
    if not signature:
        return False
    return hmac.compare_digest(compute_signature(url, params, auth_token), signature)
