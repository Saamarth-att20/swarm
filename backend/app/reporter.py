"""CallReporter: how one call tells the rest of the system what is happening.

Author: Saamarth Attray
"""
from __future__ import annotations

import time

from .contract import CallExtractedData, CallStateData, CallTranscriptData, ExtractedResult
from .events import EventBus
from .repo import Repo


class CallReporter:
    def __init__(
        self,
        *,
        bus: EventBus,
        repo: Repo,
        swarm_id: str,
        call_id: str,
        target_id: str,
        role: str = "inquiry",
    ):
        self.bus = bus
        self.repo = repo
        self.swarm_id = swarm_id
        self.call_id = call_id
        self.target_id = target_id
        self.role = role
        self.current_state: str = "queued"
        self.transcript_log: list[dict] = []

    async def state(self, state: str, reason: str | None = None) -> None:
        self.current_state = state
        await self.repo.update_call_state(self.call_id, state, reason)
        await self.bus.publish(
            self.swarm_id,
            CallStateData(
                call_id=self.call_id,
                target_id=self.target_id,
                state=state,  # type: ignore[arg-type]
                role=self.role,  # type: ignore[arg-type]
                reason=reason,
            ),
        )

    async def transcript(self, speaker: str, text: str, utterance_id: str, is_final: bool) -> None:
        await self.bus.publish(
            self.swarm_id,
            CallTranscriptData(
                call_id=self.call_id,
                target_id=self.target_id,
                utterance_id=f"{self.call_id}:{utterance_id}",
                speaker=speaker,  # type: ignore[arg-type]
                text=text,
                is_final=is_final,
            ),
            persist=is_final,
        )
        if is_final:
            self.transcript_log.append({"speaker": speaker, "text": text, "t": round(time.time(), 2)})

    async def extracted(self, result: ExtractedResult) -> None:
        if self.role == "inquiry":
            await self.repo.save_extracted(self.call_id, self.swarm_id, result)
        await self.bus.publish(
            self.swarm_id,
            CallExtractedData(call_id=self.call_id, target_id=self.target_id, result=result),
        )

    async def flush(self) -> None:
        await self.repo.save_transcript(self.call_id, self.transcript_log)
