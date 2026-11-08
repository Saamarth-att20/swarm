"""Minimal OpenAI-compatible chat client (works with Groq's Llama 3 70B and OpenAI's GPT-4o-mini).

Streams tokens + tool calls so the voice loop can start speaking the first sentence while the model is
still generating the rest.

Author: Saamarth Attray
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from typing import Any, AsyncIterator

import httpx

from .agent.types import BrainEvent, ToolCall
from .config import Settings

log = logging.getLogger("swarmdial.llm")


class LLMError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


class LLMClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None):
        self.settings = settings
        self._http = http or httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0))

    @property
    def _url(self) -> str:
        return f"{self.settings.resolved_llm_base_url.rstrip('/')}/chat/completions"

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.llm_api_key}", "Content-Type": "application/json"}

    async def complete_json(self, system: str, user: str) -> dict[str, Any]:
        payload = {
            "model": self.settings.resolved_llm_model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "max_tokens": 400,
        }
        resp = await self._http.post(self._url, headers=self._headers, json=payload)
        if resp.status_code >= 400:
            raise LLMError(f"LLM error {resp.status_code}: {resp.text[:300]}")
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)

    async def stream_chat(
        self, messages: list[dict], tools: list[dict] | None = None, *, max_tokens: int = 180, retries: int = 3
    ) -> AsyncIterator[BrainEvent]:
        payload: dict[str, Any] = {
            "model": self.settings.resolved_llm_model,
            "messages": messages,
            "temperature": 0.6,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if "gpt-oss" in str(payload["model"]):
            # Reasoning model: keep its thinking short (a phone call cannot wait) and leave room for the reply.
            payload["reasoning_effort"] = "low"
            payload["max_tokens"] = max(max_tokens, 300)

        fallback = self.settings.llm_fallback_model
        attempt = 0
        while True:
            emitted = False
            try:
                async for event in self._stream_once(payload):
                    emitted = True
                    yield event
                return
            except LLMError as exc:
                # Several live calls share one API key, so rate limits (429) and the occasional failed tool-call
                # generation are normal. Back off briefly and retry; on the last try switch to a fallback model
                # (it has its own rate-limit bucket).
                if emitted or attempt >= retries:
                    raise
                attempt += 1
                can_switch = bool(fallback) and payload["model"] != fallback
                if can_switch and (exc.status == 429 or attempt == retries):
                    # A rate limit will not clear in time for a live call, and the backup model has its own allowance.
                    payload["model"] = fallback
                    payload.pop("reasoning_effort", None)
                    payload["max_tokens"] = max_tokens
                    log.warning("LLM %s; switching to fallback model %s", exc.status or "stream failed", fallback)
                    continue
                if "gpt-oss" not in str(payload["model"]):
                    payload.pop("reasoning_effort", None)
                delay = min(exc.retry_after, 1.0) if exc.retry_after else 0.3 * attempt
                log.warning("LLM stream failed (%s); retry %d/%d in %.1fs", exc, attempt, retries, delay)
                await asyncio.sleep(delay)

    async def _stream_once(self, payload: dict[str, Any]) -> AsyncIterator[BrainEvent]:
        pending: dict[int, dict[str, str]] = {}
        try:
            async with self._http.stream("POST", self._url, headers=self._headers, json=payload) as resp:
                if resp.status_code >= 400:
                    body = (await resp.aread()).decode("utf-8", "replace")
                    retry_after = None
                    with contextlib.suppress(ValueError, TypeError):
                        retry_after = float(resp.headers.get("retry-after"))
                    raise LLMError(f"LLM error {resp.status_code}: {body[:300]}", resp.status_code, retry_after)
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if delta.get("content"):
                        yield BrainEvent(kind="text", text=delta["content"])
                    for tc in delta.get("tool_calls") or []:
                        slot = pending.setdefault(tc.get("index", 0), {"id": "", "name": "", "args": ""})
                        if tc.get("id"):
                            slot["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            slot["name"] = fn["name"]
                        if fn.get("arguments"):
                            slot["args"] += fn["arguments"]
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM transport error: {exc}") from exc

        for index in sorted(pending):
            slot = pending[index]
            if not slot["name"]:
                continue
            try:
                args = json.loads(slot["args"]) if slot["args"].strip() else {}
            except json.JSONDecodeError:
                args = {}
            yield BrainEvent(
                kind="tool_call",
                tool_call=ToolCall(id=slot["id"] or f"call_{uuid.uuid4().hex[:8]}", name=slot["name"], arguments=args),
            )