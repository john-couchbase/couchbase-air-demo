"""
The storm, as a clock.

Three background loops run for the life of the process:

- arrivals: lands messages in Couchbase. A trickle on a normal morning; when
  the storm is triggered, flights are cancelled in the cluster and the surge
  arrives on a sharp-rise, long-tail curve.
- classify: runs the enrichment job over whatever has landed (beat 2).
- agent: drains the funnel into the frontier model (beat 3).

The loops pause when nobody is watching, or when the presenter says so: every
classified message can become a Model Service cache entry, and the trickle
would otherwise run all night. A storm in progress resumes where it stopped.

Nothing here is scripted beyond the arrival times. Which messages escalate,
what the cache answers and what it all costs are decided at runtime, which is
why two runs are never quite identical.
"""

from __future__ import annotations

import asyncio
import json
import math
import random
import time
from pathlib import Path

from aidpair.agent import AgentWorker
from aidpair.config import settings
from aidpair.db import coll, ks, query
from aidpair.llm import CACHE
from aidpair.meter import METER
from aidpair.classify import ClassifyWorker, new_run_tag

DATA = Path(__file__).resolve().parents[1] / "data"


class Scenario:
    def __init__(self) -> None:
        self.surge_pool = json.loads((DATA / "surge.json").read_text())
        self.baseline_pool = json.loads((DATA / "baseline.json").read_text())
        self.worker = AgentWorker()
        self.classifier = ClassifyWorker()
        self.touched: set[str] = set()
        self._tasks: list[asyncio.Task] = []
        # None while running; "idle" when no browser has watched for a while
        # (resumes on its own when one does); "user" from the Pause button
        # (resumes only from Resume, a storm or a reset).
        self.paused: str | None = None
        self.paused_at: float | None = None
        self.last_watched = time.time()
        self._reset_state()

    def _reset_state(self) -> None:
        self.phase = "normal"
        self.t0 = time.time()
        self.storm_at: float | None = None
        self.surge_done_at: float | None = None
        self.quiet_at: float | None = None
        self.arrivals: list[tuple[float, str]] = []   # (ts, kind)
        self._schedule: list[tuple[float, dict]] = []
        self._baseline_i = 0
        self._seq = 0
        self.rng = random.Random(7)

    # ---------------------------------------------------------------- control
    def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._tasks = [loop.create_task(self._arrivals()), loop.create_task(self._classify()),
                       loop.create_task(self._agent())]

    def pause(self, why: str = "user") -> None:
        if self.paused is None:
            self.paused_at = time.time()
        # The button outranks idle: a paused demo stays paused when someone looks.
        if self.paused != "user":
            self.paused = why
        self.classifier.paused = True

    def resume(self) -> None:
        if self.paused is None:
            return
        # Whatever was left of the surge arrives on its curve, from now.
        gap = time.time() - (self.paused_at or time.time())
        self._schedule = [(at + gap, m) for at, m in self._schedule]
        self.paused, self.paused_at = None, None
        self.classifier.paused = False

    def watched(self) -> None:
        """A browser with the demo in front of someone asked for state."""
        self.last_watched = time.time()
        if self.paused == "idle":
            self.resume()

    def _check_idle(self) -> None:
        limit = settings().idle_pause_min * 60
        if limit and self.paused is None and time.time() - self.last_watched > limit:
            self.pause("idle")

    def trigger_storm(self) -> None:
        if self.phase != "normal":
            return
        self.resume()
        s = settings()
        query(f"UPDATE {ks('flights')} SET status = storm_status, delay_min = storm_delay_min")
        now = time.time()
        self.storm_at = now
        self.phase = "storm"
        msgs = list(self.surge_pool[: s.surge_size])
        # The hero lands early, so their draft is ready when the presenter looks.
        hero = next((m for m in msgs if m["hero"]), None)
        if hero:
            msgs.remove(hero)
            msgs.insert(min(40, len(msgs)), hero)
        # Sharp rise, long tail: Beta(1.4, 3.6) over the surge window.
        offsets = sorted(self.rng.betavariate(1.4, 3.6) * s.surge_seconds for _ in msgs)
        self._schedule = [(now + o, m) for o, m in zip(offsets, msgs)]

    async def reset(self) -> None:
        from aidpair import memory
        # Hosted Agent Memory: drop this run's approvals before the set is cleared.
        await memory.forget_demo(set(self.touched))
        await asyncio.to_thread(self._clear)
        CACHE.reset()
        new_run_tag()  # a fresh Model Service cache space for this run
        METER.reset()
        self.classifier.done.clear()
        self.worker = AgentWorker()
        self._reset_state()
        # A reset is someone at the controls: start the new morning running.
        self.last_watched = time.time()
        self.resume()

    def _clear(self) -> None:
        """The database half of reset, run in a thread: over the WAN these
        statements take seconds, and the event loop must keep serving."""
        for c in ("messages", "resolutions", "meter"):
            query(f"DELETE FROM {ks(c)}")
        query(f"UPDATE {ks('flights')} SET status = scheduled_status, delay_min = NULL")
        # Only memory the demo wrote to is restored; everything else is untouched.
        if self.touched:
            mem = {m["id"]: m for m in json.loads((DATA / "memory.json").read_text())}
            col = coll("memory")
            for pid in self.touched:
                col.upsert(pid, mem[pid])
            self.touched.clear()

    # ------------------------------------------------------------------ loops
    def _land(self, m: dict, kind: str) -> None:
        self._seq += 1
        mid = f"msg_{int(time.time() * 1000)}_{self._seq:05d}"
        doc = {k: v for k, v in m.items() if k != "expected"}
        doc.update(type="message", id=mid, ts=time.time(), kind=kind)
        coll("messages").insert(mid, doc)
        self.arrivals.append((doc["ts"], kind))

    def _arrivals_tick(self) -> None:
        """One second of arrivals. Each landing is a write, so this runs in a
        thread: at the storm's peak a second's worth over the WAN is not quick."""
        s = settings()
        now = time.time()
        # Poisson trickle, every phase: the normal day never stops.
        for _ in range(_poisson(self.rng, s.baseline_per_min / 60)):
            m = self.baseline_pool[self._baseline_i % len(self.baseline_pool)]
            self._baseline_i += 1
            self._land(m, "baseline")
        while self._schedule and self._schedule[0][0] <= now:
            _, m = self._schedule.pop(0)
            self._land(m, "surge")
        if self.phase == "storm" and not self._schedule:
            self.phase = "recovering"
            self.surge_done_at = now

    async def _arrivals(self) -> None:
        while True:
            self._check_idle()
            if self.paused:
                await asyncio.sleep(1.0)
                continue
            try:
                await asyncio.to_thread(self._arrivals_tick)
            except Exception as e:  # keep the clock running whatever happens
                print("arrivals:", e)
            await asyncio.sleep(1.0)

    async def _classify(self) -> None:
        while True:
            try:
                await self.classifier.run()
            except Exception as e:
                print("classify:", e)
                await asyncio.sleep(1.0)

    async def _agent(self) -> None:
        while True:
            if self.paused:
                await asyncio.sleep(1.0)
                continue
            try:
                await self.worker.tick()
                if self.phase == "recovering" and await asyncio.to_thread(self._drained):
                    self.phase = "quiet"
                    self.quiet_at = time.time()
            except Exception as e:
                print("agent:", e)
            await asyncio.sleep(1.0)

    def _drained(self) -> bool:
        pending = query(
            f"SELECT COUNT(*) AS n FROM {ks('messages')} AS m "
            f"WHERE m.classification IS MISSING AND m.kind = 'surge'", fresh=True)[0]["n"]
        if pending or self.worker.inflight:
            return False
        from aidpair.classify import escalations
        return not escalations()


def _poisson(rng: random.Random, lam: float) -> int:
    l, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= l:
            return k
        k += 1


SCENARIO = Scenario()
