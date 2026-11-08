"""The Swarm Commander: orchestrates many concurrent voice agents as one coordinated search.

What makes it a swarm rather than a pile of robocalls:
  * Shared knowledge. Every call report feeds a live knowledge base that is injected into the agents
    still to dial ("this whole chain is out", "X offers a substitute", "best price so far...").
  * Rerouting. A closed / out-of-stock / unreachable business immediately dispatches a backup agent,
    and a business that recommends someone else ("try Summit Pharmacy") spawns a brand-new target.
  * Prioritisation. Closures push open-now businesses forward; a dry chain pushes its other locations back.
  * Early stop. Once enough confirmed matches exist, calls that have not started are cancelled.
  * Ranking. Everything lands in one comparison, scored on price / distance / speed / hold-ability.

Author: Saamarth Attray
"""
from __future__ import annotations

import asyncio
import logging
import random
import re
import secrets
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal

from .agent.factory import BrainFactory
from .agent.session import CallSession
from .agent.types import BrainContext, CallOutcome
from .config import Settings
from .contract import (
    Capabilities,
    CONTRACT_VERSION,
    CreateSwarmRequest,
    ExtractedResult,
    Intent,
    LatLng,
    SwarmCompletedData,
    SwarmCreatedData,
    SwarmKnowledgeData,
    SwarmRankedData,
    SwarmReservedData,
    SwarmRerouteData,
    Target,
)
from .events import EventBus
from .ids import new_id
from .intent import extract_place, parse_intent
from .llm import LLMClient
from .places import Places, brand_key, demo_targets
from .ranking import Candidate, rank
from .reporter import CallReporter
from .repo import Repo
from .sim import SimulatedCallRunner, _seed, assign_plans
from .telephony.twilio_client import LiveCallContext, LiveCallRegistry, Telephony

log = logging.getLogger("swarmdial.commander")


class PlaceNotFound(Exception):
    """The request named a place that could not be found on the map."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class LiveModeUnavailable(Exception):
    def __init__(self, missing: list[str], message: str | None = None):
        super().__init__(message or "Live calling is not configured: " + "; ".join(missing))
        self.missing = missing


class RateGate:
    """Spaces out outbound dials (Twilio accounts default to about one new call per second)."""

    def __init__(self, interval: float):
        self.interval = interval
        self._lock = asyncio.Lock()
        self._next = 0.0

    async def wait(self) -> None:
        if self.interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            delay = self._next - now
            if delay > 0:
                await asyncio.sleep(delay)
            self._next = max(now, self._next) + self.interval


@dataclass
class SwarmRun:
    swarm_id: str
    request: CreateSwarmRequest
    origin: LatLng
    settings: Settings
    intent: Intent | None = None
    targets: dict[str, Target] = field(default_factory=dict)
    backlog: list[Target] = field(default_factory=list)
    calls: dict[str, str] = field(default_factory=dict)  # call_id -> target_id
    reporters: dict[str, CallReporter] = field(default_factory=dict)
    results: dict[str, ExtractedResult] = field(default_factory=dict)  # inquiry results by call_id
    knowledge: list[str] = field(default_factory=list)
    tasks: set[asyncio.Task] = field(default_factory=set)
    task_by_call: dict[str, asyncio.Task] = field(default_factory=dict)
    started: set[str] = field(default_factory=set)
    sim_plans: dict[str, str] = field(default_factory=dict)
    brand_dry: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    reserved: dict[str, str] = field(default_factory=dict)  # inquiry call_id -> reserve call_id
    reserve_tasks: set[asyncio.Task] = field(default_factory=set)
    started_at: float = field(default_factory=time.time)
    stop_after: int = 3
    max_total_calls: int = 20
    next_target_num: int = 1
    calls_started: int = 0
    calls_made: int = 0
    calls_completed: int = 0
    calls_failed: int = 0
    positives: int = 0
    best_price: float | None = None
    best_wait: int | None = None
    first_yes_seen: bool = False
    search_label: str | None = None  # a place named in the request ("Los Angeles, CA"): where we are searching
    stopping: bool = False
    cancelled: bool = False
    main_task: asyncio.Task | None = None
    sem: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(12))
    dial_gate: RateGate = field(default_factory=lambda: RateGate(0))


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()


class SwarmCommander:
    def __init__(
        self,
        *,
        settings: Settings,
        repo: Repo,
        bus: EventBus,
        places: Places,
        brain_factory: BrainFactory,
        llm: LLMClient | None,
        telephony: Telephony,
        registry: LiveCallRegistry,
    ):
        self.settings = settings
        self.repo = repo
        self.bus = bus
        self.places = places
        self.brain_factory = brain_factory
        self.llm = llm if (llm is not None and settings.llm_enabled) else None
        self.telephony = telephony
        self.registry = registry
        self._runs: dict[str, SwarmRun] = {}
        self._last_dialed: dict[str, float] = {}  # business phone -> when we last dialed it
        self._calls_today = 0
        self._day = time.strftime("%Y-%m-%d")

    # ===================================================================== public API
    def capabilities(self) -> Capabilities:
        missing = self.settings.live_missing()
        return Capabilities(
            version=CONTRACT_VERSION,
            live_available=not missing,
            live_missing=missing,
            llm_provider=self.settings.llm_provider if self.settings.llm_enabled else "scripted",
            places_provider="google" if self.settings.places_enabled else "mock",
            demo_targets=0 if self.settings.allow_real_business_calls else len(self.settings.demo_targets),
        )

    async def _llm_place(self, query: str) -> str | None:
        """Last resort when the wording defeats the rules ("my flight lands in the City of Angels"): ask the model."""
        llm = getattr(self, "llm", None)
        if llm is None:
            return None
        try:
            data = await llm.complete_json(
                "Does this request name a place (city, state, neighbourhood or zip) where the thing should be found, "
                "which may be somewhere other than where the person is now (a trip, a move, a friend's town)? "
                'Reply with JSON: {"mention": the exact words from the request naming the place, or null, '
                '"place": that place as "City, ST" or a zip, or null}. Never guess a place the request does not name.',
                query,
            )
        except Exception as exc:
            log.warning("place lookup by the model failed: %s", exc)
            return None
        mention, place = data.get("mention"), data.get("place")
        if isinstance(mention, str) and isinstance(place, str) and mention.strip() and place.strip() \
                and mention.strip().lower() in query.lower():  # it must really be in the request
            return place.strip()[:80]
        return None

    async def _named_place(self, req: CreateSwarmRequest) -> tuple[LatLng, str] | None:
        """If the request names a place ("... in Los Angeles", "going to LA"), search there instead of around the user.

        Returns None when no place is named (or this build cannot look places up). Raises PlaceNotFound when a place
        was named but could not be found, so we never quietly search somewhere else.
        """
        geocode = getattr(self.places, "geocode", None)
        if geocode is None:
            return None
        name = extract_place(req.query) or await self._llm_place(req.query)
        if not name:
            return None
        try:
            found = await geocode(name)
        except Exception as exc:
            log.warning("could not look up %r: %s", name, exc)
            raise PlaceNotFound(name) from exc
        if not found:
            raise PlaceNotFound(name)
        log.info("searching near %s (named in the request) instead of the user's location", found[1])
        return found

    async def create_swarm(self, req: CreateSwarmRequest) -> str:
        try:
            named = await self._named_place(req)
        except PlaceNotFound as exc:
            if req.mode == "live":  # real calls: never quietly search somewhere other than what was asked for
                raise LiveModeUnavailable(
                    [f'Couldn\'t find "{exc.name}". Try a city and state, like "Los Angeles, CA", or a zip code'],
                    f'We couldn\'t find "{exc.name}" on the map.',
                ) from exc
            named = None
        if req.mode == "live":
            missing = self.settings.live_missing()
            if missing:
                raise LiveModeUnavailable(missing)
            if named is None and self.settings.allow_real_business_calls and (req.lat is None or req.lng is None):
                # Never fall back to the server's default coordinates for real businesses: that would phone strangers
                # in the wrong city.
                raise LiveModeUnavailable(
                    ["Allow location access in your browser (the lock icon next to the address bar), then try again"],
                    "We need your location to find real businesses near you.",
                )
        origin = named[0] if named else LatLng(
            lat=req.lat if req.lat is not None else self.settings.default_lat,
            lng=req.lng if req.lng is not None else self.settings.default_lng,
        )
        swarm_id = new_id("s", 10)
        await self.repo.create_swarm(
            swarm_id=swarm_id,
            user_id=req.user_id or "anonymous",
            query=req.query,
            mode=req.mode,
            origin_lat=origin.lat,
            origin_lng=origin.lng,
            radius_miles=req.radius_miles,
        )
        run = SwarmRun(
            swarm_id=swarm_id,
            request=req,
            origin=origin,
            settings=self.settings,
            stop_after=req.stop_after_matches or (2 if req.purpose == "donate" else self.settings.target_yes_count),
            sem=asyncio.Semaphore(self.settings.max_concurrent_calls),
            dial_gate=RateGate(self.settings.dial_stagger_s if req.mode == "live" else 0),
        )
        run.search_label = named[1] if named else None
        self._runs[swarm_id] = run
        run.main_task = asyncio.create_task(self._run(run), name=f"swarm-{swarm_id}")
        return swarm_id

    async def cancel(self, swarm_id: str) -> bool:
        run = self._runs.get(swarm_id)
        if run is None or run.cancelled:
            return False
        run.cancelled = True
        for task in list(run.tasks):
            task.cancel()
        return True

    async def shutdown(self) -> None:
        """Stop every in-flight swarm (server shutdown)."""
        pending: list[asyncio.Task] = []
        for run in self._runs.values():
            run.cancelled = True
            for task in [*run.tasks, *run.reserve_tasks, run.main_task]:
                if task is not None and not task.done():
                    task.cancel()
                    pending.append(task)
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def reserve(self, swarm_id: str, call_id: str) -> str:
        run = self._runs.get(swarm_id)
        if run is None:
            raise KeyError("swarm not found (or the server restarted since it ran)")
        result = run.results.get(call_id)
        if result is None or result.available not in ("yes", "partial"):
            raise ValueError("that call did not find a match to reserve")
        existing = run.reserved.get(call_id)
        if existing:
            return existing
        target = run.targets[run.calls[call_id]]
        reserve_call_id = new_id("c")
        run.calls[reserve_call_id] = target.id
        run.reserved[call_id] = reserve_call_id
        await self.repo.create_task_and_call(swarm_id=swarm_id, call_id=reserve_call_id, target=target, role="reserve")
        reporter = CallReporter(
            bus=self.bus, repo=self.repo, swarm_id=swarm_id, call_id=reserve_call_id, target_id=target.id, role="reserve"
        )
        run.reporters[reserve_call_id] = reporter
        await reporter.state("queued")
        task = asyncio.create_task(self._reserve_worker(run, target, call_id, reserve_call_id, reporter, result))
        run.reserve_tasks.add(task)
        task.add_done_callback(run.reserve_tasks.discard)
        return reserve_call_id

    # ===================================================================== swarm lifecycle
    async def _run(self, run: SwarmRun) -> None:
        try:
            intent = await parse_intent(run.request.query, run.request.radius_miles, run.request.priority, self.llm, run.request.purpose)
            run.intent = intent
            await self.repo.save_intent(run.swarm_id, intent)
            if run.search_label:  # make it obvious on the dashboard that we are not searching around the user
                await self.bus.publish(
                    run.swarm_id, SwarmKnowledgeData(note=f"Searching near {run.search_label}, as you asked", source_call_id=None)
                )

            targets = await self._find_targets(run, intent)
            if not targets:
                raise ValueError("No businesses found nearby. Try a larger radius or a different request.")
            wanted = run.request.max_calls or self.settings.max_targets
            n_primary = min(wanted, len(targets))
            primary = [t.model_copy(update={"tier": "primary"}) for t in targets[:n_primary]]
            backups = [
                t.model_copy(update={"tier": "backup"})
                for t in targets[n_primary : n_primary + self.settings.backup_targets]
            ]
            run.backlog = list(backups)
            for t in primary + backups:
                run.targets[t.id] = t
            run.next_target_num = len(targets) + 1
            run.max_total_calls = len(primary) + len(backups) + 4
            if run.request.mode == "simulated":
                run.sim_plans = assign_plans(primary + backups, run.swarm_id)

            await self.bus.publish(
                run.swarm_id,
                SwarmCreatedData(
                    query=run.request.query,
                    mode=run.request.mode,
                    intent=intent,
                    origin=run.origin,
                    targets=primary + backups,
                ),
            )
            if run.cancelled:
                await self._finalize(run, "cancelled")
                return

            for target in primary:
                await self._start_call(run, target)

            while run.tasks:
                done, _ = await asyncio.wait(set(run.tasks), return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    run.tasks.discard(task)
                    if not task.cancelled() and task.exception():
                        log.error("worker crashed", exc_info=task.exception())

            await self._finalize(run, "cancelled" if run.cancelled else "completed")
        except Exception as exc:
            log.exception("swarm %s failed", run.swarm_id)
            await self._finalize(run, "error", error=str(exc))

    async def _find_targets(self, run: SwarmRun, intent: Intent) -> list[Target]:
        need = self.settings.max_targets + self.settings.backup_targets
        if run.request.mode == "live":
            if not self.settings.allow_real_business_calls:
                demos = demo_targets(self.settings, run.origin)
                if not demos:
                    raise ValueError("Live mode needs DEMO_TARGETS (teammate phone numbers) configured.")
                return demos
            if not self.settings.places_enabled:
                raise ValueError("Calling real businesses requires GOOGLE_PLACES_API_KEY.")
        targets = await self.places.search(intent, run.origin, intent.radius_miles, need)
        if run.request.mode == "live":
            # Real businesses: never dial one Google says is closed right now (unknown hours are still called)
            targets = [t for t in targets if t.open_now is not False]
            if not targets:
                raise ValueError("Nothing nearby is open right now. Try a wider radius or call again when places open.")
            targets = self._apply_dial_limits(targets)
        return targets

    def _apply_dial_limits(self, targets: list[Target]) -> list[Target]:
        """Don't re-phone a business that was called minutes ago, and stop at the daily call cap."""
        now = time.time()
        cooldown = self.settings.redial_cooldown_min * 60
        fresh = [t for t in targets if now - self._last_dialed.get(t.phone, 0) >= cooldown]
        if not fresh:
            raise ValueError(
                f"Every matching business was already called in the last {self.settings.redial_cooldown_min} minutes. "
                "Try a different request or a wider radius."
            )
        cap = self.settings.max_calls_per_day
        if cap:
            if self._day != time.strftime("%Y-%m-%d"):
                self._day, self._calls_today = time.strftime("%Y-%m-%d"), 0
            room = cap - self._calls_today
            if room <= 0:
                raise ValueError(f"Daily live-call safety cap reached ({cap}). Raise MAX_CALLS_PER_DAY to continue.")
            fresh = fresh[:room]
        return fresh

    def _note_dialed(self, phone: str) -> None:
        self._last_dialed[phone] = time.time()
        self._calls_today += 1

    async def _finalize(self, run: SwarmRun, status: Literal["completed", "cancelled", "error"], error: str | None = None) -> None:
        best_call_id = None
        if run.intent is not None and status != "error":
            candidates = [
                Candidate(call_id=cid, target=run.targets[run.calls[cid]], result=res)
                for cid, res in run.results.items()
                if run.calls.get(cid) in run.targets
            ]
            rankings, best_call_id, criteria = rank(candidates, run.intent)
            await self.bus.publish(
                run.swarm_id, SwarmRankedData(rankings=rankings, best_call_id=best_call_id, criteria=criteria)
            )
        elapsed = round(time.time() - run.started_at, 1)
        await self.bus.publish(
            run.swarm_id,
            SwarmCompletedData(
                status=status,
                calls_made=run.calls_made,
                calls_completed=run.calls_completed,
                calls_failed=run.calls_failed,
                positives=run.positives,
                elapsed_s=elapsed,
                error=error,
            ),
        )
        await self.repo.update_swarm(
            run.swarm_id,
            status=status,
            best_call_id=best_call_id,
            completed_at=time.time(),
            summary={"calls_made": run.calls_made, "positives": run.positives, "elapsed_s": elapsed, "error": error},
        )

    # ===================================================================== calls
    async def _start_call(self, run: SwarmRun, target: Target, pre=None) -> str:
        call_id = new_id("c")
        run.calls[call_id] = target.id
        run.calls_started += 1
        await self.repo.create_task_and_call(swarm_id=run.swarm_id, call_id=call_id, target=target)
        reporter = CallReporter(
            bus=self.bus, repo=self.repo, swarm_id=run.swarm_id, call_id=call_id, target_id=target.id
        )
        run.reporters[call_id] = reporter
        if pre is not None:
            await pre(call_id)
        await reporter.state("queued")
        task = asyncio.create_task(self._worker(run, target, call_id, reporter), name=f"call-{call_id}")
        run.tasks.add(task)
        run.task_by_call[call_id] = task
        return call_id

    def _context(
        self, run: SwarmRun, target: Target, role: Literal["inquiry", "reserve"] = "inquiry",
        prior: ExtractedResult | None = None,
    ) -> BrainContext:
        assert run.intent is not None
        return BrainContext(
            intent=run.intent,
            target=target,
            knowledge=list(run.knowledge[-6:]),
            role=role,
            contact_name=run.request.contact_name,
            donor_address=run.request.donor_address,
            pickup_by=run.request.pickup_by,
            prior_result=prior,
        )

    async def _worker(self, run: SwarmRun, target: Target, call_id: str, reporter: CallReporter) -> None:
        try:
            # The slot is held until the result has been processed, so with limited concurrency the next call
            # never starts before the commander has decided whether to stop early or reroute.
            async with run.sem:
                outcome = await self._run_call(run, target, call_id, reporter)
                await self._finish_call(run, target, call_id, reporter, outcome)
        except asyncio.CancelledError:
            # cancelled while still queued for a slot
            if reporter.current_state not in ("completed", "failed", "cancelled"):
                await reporter.state("cancelled", "Swarm cancelled" if run.cancelled else "Enough matches found")

    async def _run_call(self, run: SwarmRun, target: Target, call_id: str, reporter: CallReporter) -> CallOutcome:
        if run.stopping or run.cancelled:
            return CallOutcome("cancelled", reason="Swarm cancelled" if run.cancelled else "Enough matches found")
        run.started.add(call_id)
        try:
            return await asyncio.wait_for(
                self._execute(run, target, call_id, reporter), timeout=self.settings.call_timeout_s
            )
        except asyncio.TimeoutError:
            return CallOutcome("failed", reason="Call timed out")
        except asyncio.CancelledError:
            return CallOutcome("cancelled", reason="Swarm cancelled" if run.cancelled else "Enough matches found")
        except Exception as exc:
            log.exception("call %s crashed", call_id)
            return CallOutcome("failed", reason=f"Call error: {str(exc)[:120]}")

    async def _finish_call(
        self, run: SwarmRun, target: Target, call_id: str, reporter: CallReporter, outcome: CallOutcome
    ) -> None:
        await reporter.flush()
        await reporter.state(outcome.state, outcome.reason)
        if outcome.state == "cancelled":
            return
        run.calls_made += 1
        if outcome.state == "completed":
            run.calls_completed += 1
        else:
            run.calls_failed += 1
        await self._on_done(run, target, call_id, outcome)

    async def _execute(
        self, run: SwarmRun, target: Target, call_id: str, reporter: CallReporter,
        role: Literal["inquiry", "reserve"] = "inquiry", prior: ExtractedResult | None = None,
    ) -> CallOutcome:
        ctx = self._context(run, target, role, prior)
        session = CallSession(ctx, self.brain_factory(ctx), reporter)
        if run.request.mode == "simulated":
            rng = random.Random(_seed(run.swarm_id, call_id))
            plan = "reserve" if role == "reserve" else run.sim_plans.get(target.id, "has_it")
            await asyncio.sleep(rng.uniform(0, 1.2) * self.settings.sim_speed)
            runner = SimulatedCallRunner(self.settings.sim_speed)
            return await runner.run(
                session=session, reporter=reporter, plan=plan, target=target, intent=ctx.intent, rng=rng, role=role
            )
        return await self._execute_live(run, target, call_id, reporter, session)

    async def _execute_live(
        self, run: SwarmRun, target: Target, call_id: str, reporter: CallReporter, session: CallSession
    ) -> CallOutcome:
        if not target.phone:
            return CallOutcome("failed", reason="No phone number")
        loop = asyncio.get_running_loop()
        live = LiveCallContext(
            call_id=call_id, swarm_id=run.swarm_id, session=session, reporter=reporter, future=loop.create_future(),
            token=secrets.token_urlsafe(16),
        )
        self.registry.register(live)
        try:
            await run.dial_gate.wait()
            await reporter.state("dialing")
            live.call_sid = await self.telephony.place_call(call_id=call_id, to=target.phone)
            if target.source != "demo":
                self._note_dialed(target.phone)
            await self.repo.set_call_provider_sid(call_id, live.call_sid)
            return await live.future
        finally:
            if not live.future.done() and live.call_sid:
                await self.telephony.hangup(live.call_sid)
            self.registry.remove(call_id)

    # ===================================================================== reacting to results
    async def _on_done(self, run: SwarmRun, target: Target, call_id: str, outcome: CallOutcome) -> None:
        result = outcome.result
        if result is not None:
            run.results[call_id] = result
            await self._learn(run, target, call_id, result)
            if result.available == "yes":
                run.positives += 1

        if run.cancelled or run.stopping:
            return
        if run.positives >= run.stop_after:
            await self._stop_early(run)
            return

        needs_backup = outcome.state == "failed" or (result is not None and result.available in ("no", "unknown"))
        if result is not None and run.intent is not None and run.intent.kind == "donation" and result.can_pickup is False:
            needs_backup = True  # drop-off only is no use to a donor who needs the food collected
        if not needs_backup or run.calls_started >= run.max_total_calls:
            return

        if result is not None and result.referral_name:
            referral = await self._referral_target(run, result)
            if referral is not None:
                await self._reroute(
                    run, call_id, target, referral, "referral",
                    f"{target.name} recommended {referral.name}, calling them now", new_target=referral,
                )
                return

        if run.backlog:
            nxt = run.backlog.pop(0)
            if result is not None and result.closed:
                kind, reason = "closed", f"{target.name} is closed, redirecting to {nxt.name}"
            elif result is not None:
                if run.intent is not None and run.intent.kind == "donation":
                    why = "can't pick it up" if result.can_pickup is False else "can't take it tonight"
                    kind, reason = "no_stock", f"{target.name} {why}, trying {nxt.name}"
                else:
                    kind, reason = "no_stock", f"{target.name} doesn't have it, trying {nxt.name}"
            else:
                kind, reason = "failed", f"{target.name}: {outcome.reason or 'no answer'}. Trying {nxt.name}"
            await self._reroute(run, call_id, target, nxt, kind, reason)  # type: ignore[arg-type]

    async def _reroute(
        self, run: SwarmRun, from_call_id: str, from_target: Target, to: Target, kind: str, reason: str,
        new_target: Target | None = None,
    ) -> None:
        async def announce(new_call_id: str) -> None:
            await self.bus.publish(
                run.swarm_id,
                SwarmRerouteData(
                    from_call_id=from_call_id,
                    from_target_id=from_target.id,
                    to_target_id=to.id,
                    to_call_id=new_call_id,
                    kind=kind,  # type: ignore[arg-type]
                    reason=reason,
                    new_target=new_target,
                ),
            )

        await self._start_call(run, to, pre=announce)

    async def _referral_target(self, run: SwarmRun, result: ExtractedResult) -> Target | None:
        assert run.intent is not None
        name = (result.referral_name or "").strip()
        wanted = _norm(name)
        if not wanted:
            return None
        for existing in run.targets.values():
            have = _norm(existing.name)
            if wanted in have or have in wanted:
                return None  # already in the swarm
        target_id = f"t{run.next_target_num}"
        target = await self.places.resolve_referral(name, result.referral_phone, run.origin, target_id, run.intent)
        if target is None:
            return None
        run.next_target_num += 1
        run.targets[target.id] = target
        if run.request.mode == "simulated":
            run.sim_plans[target.id] = "has_it"
        return target

    async def _stop_early(self, run: SwarmRun) -> None:
        run.stopping = True
        queued = [t for cid, t in run.task_by_call.items() if cid not in run.started and not t.done()]
        if queued:
            note = f"{run.positives} confirmed matches found, cancelling {len(queued)} queued calls"
        else:
            note = f"{run.positives} confirmed matches found, no further calls needed"
        await self._note(run, note, None)
        for task in queued:
            task.cancel()

    # ===================================================================== shared knowledge
    async def _note(self, run: SwarmRun, note: str, source_call_id: str | None) -> None:
        run.knowledge.append(note)
        await self.bus.publish(run.swarm_id, SwarmKnowledgeData(note=note, source_call_id=source_call_id))

    async def _learn_donation(self, run: SwarmRun, target: Target, call_id: str, result: ExtractedResult) -> None:
        """What the swarm learns while finding someone to collect surplus food."""
        eta = f" in about {result.wait_minutes} min" if result.wait_minutes is not None else ""
        if result.available == "yes":
            if not run.first_yes_seen:
                run.first_yes_seen = True
                await self._note(run, f"{target.name} can pick it up{eta}, first confirmed pickup", call_id)
            elif result.wait_minutes is not None and (run.best_wait is None or result.wait_minutes < run.best_wait):
                await self._note(run, f"Faster pickup: {target.name}{eta}", call_id)
            if result.wait_minutes is not None and (run.best_wait is None or result.wait_minutes < run.best_wait):
                run.best_wait = result.wait_minutes
        elif result.available == "partial":
            if result.can_pickup is False:
                await self._note(run, f"{target.name} can't send anyone, drop-off only", call_id)
            else:
                await self._note(run, f"{target.name} only takes part of it: {result.notes or 'limited items'}", call_id)
        elif result.closed:
            self._prioritize_open(run)
            await self._note(run, f"{target.name} is closed for the night, moving open organizations to the front", call_id)
        elif result.available == "no":
            await self._note(run, f"{target.name} is at capacity tonight", call_id)

    async def _learn(self, run: SwarmRun, target: Target, call_id: str, result: ExtractedResult) -> None:
        assert run.intent is not None
        item = run.intent.item
        price = f" at ${result.price:,.2f}" if result.price is not None else ""
        if run.intent.kind == "donation":
            await self._learn_donation(run, target, call_id, result)
            return
        if result.available == "yes":
            if not run.first_yes_seen:
                run.first_yes_seen = True
                await self._note(run, f"{target.name} has it{price}, first confirmed match", call_id)
            elif result.price is not None and (run.best_price is None or result.price < run.best_price):
                await self._note(run, f"New lowest price: ${result.price:,.2f} at {target.name}", call_id)
            if result.price is not None and (run.best_price is None or result.price < run.best_price):
                run.best_price = result.price
        elif result.available == "partial":
            alt = result.alternatives[0] if result.alternatives else "a close substitute"
            await self._note(run, f"{target.name} doesn't have {item} but offers {alt}{price}", call_id)
        elif result.closed:
            self._prioritize_open(run)
            await self._note(run, f"{target.name} is closed, moving open-now businesses to the front of the queue", call_id)
        elif result.available == "no":
            key = brand_key(target.name)
            run.brand_dry[key] += 1
            if run.brand_dry[key] == 2:
                self._deprioritize_brand(run, key)
                brand = target.name.split()[0]
                await self._note(
                    run, f"{brand} looks out of stock at multiple locations, deprioritizing its other stores", call_id
                )

    @staticmethod
    def _prioritize_open(run: SwarmRun) -> None:
        run.backlog.sort(key=lambda t: (t.open_now is False, t.distance_miles))

    @staticmethod
    def _deprioritize_brand(run: SwarmRun, key: str) -> None:
        run.backlog.sort(key=lambda t: brand_key(t.name) == key)  # stable: dry-brand stores sink to the end

    # ===================================================================== reserve (the "closer")
    async def _reserve_worker(
        self, run: SwarmRun, target: Target, call_id: str, reserve_call_id: str, reporter: CallReporter,
        prior: ExtractedResult,
    ) -> None:
        try:
            outcome = await asyncio.wait_for(
                self._execute(run, target, reserve_call_id, reporter, role="reserve", prior=prior),
                timeout=self.settings.call_timeout_s,
            )
        except asyncio.TimeoutError:
            outcome = CallOutcome("failed", reason="Call timed out")
        except Exception as exc:
            log.exception("reserve call crashed")
            outcome = CallOutcome("failed", reason=f"Call error: {str(exc)[:120]}")

        await reporter.flush()
        await reporter.state(outcome.state, outcome.reason)
        hold = outcome.hold
        success = bool(hold and hold.success)
        if success:
            detail = f" {hold.confirmation}." if hold and hold.confirmation else ""
            if run.intent is not None and run.intent.kind == "donation":
                message = f"{target.name} confirmed a pickup.{detail}"
            else:
                message = f"{target.name} is holding it for you.{detail}"
        else:
            where = f" at {target.phone}" if target.phone else ""
            if run.intent is not None and run.intent.kind == "donation":
                message = f"{target.name} couldn't confirm the pickup. Call them directly{where} or try the next organization."
            else:
                message = f"Couldn't confirm a hold with {target.name}. You can call them directly{where}."
        run.reserved.pop(call_id, None) if not success else None
        await self.bus.publish(
            run.swarm_id,
            SwarmReservedData(
                call_id=call_id,
                target_id=target.id,
                reserve_call_id=reserve_call_id,
                success=success,
                confirmation=hold.confirmation if hold else None,
                message=message,
            ),
        )