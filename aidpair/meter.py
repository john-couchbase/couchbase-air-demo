"""
The token meter. Every model call and every cache hit lands here.

Held in memory so the dashboard can poll it every second, and written to the
`meter` collection so the whole bill can be read back in SQL++ afterwards.

A cache hit is recorded with the tokens it would have cost and zero spend.
That is the only way "cost avoided" can be computed from something observed
rather than assumed.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import asdict, dataclass, field

from aidpair.catalog import get


@dataclass
class Call:
    ts: float
    job: str            # "classify" | "agent" | "embed"
    model: str
    tokens_in: int
    tokens_out: int
    cost: float         # USD at list price; 0 for a cache hit
    avoided: float      # USD a cache hit saved
    cache: str          # "miss" | "hit" | "n/a"
    latency_ms: int
    # True when the tokens were estimated from text length rather than read
    # from the model's usage report: the SQL++ path does not see usage.
    estimated: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


class Meter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.calls: list[Call] = []
        self.t0 = time.time()

    def reset(self) -> None:
        with self._lock:
            self.calls = []
            self.t0 = time.time()

    def record(self, job: str, model_id: str, tokens_in: int, tokens_out: int,
               latency_ms: int, cache: str = "n/a", estimated: bool = False) -> Call:
        m = get(model_id) if model_id in _priced() else None
        full = m.cost(tokens_in, tokens_out) if m else 0.0
        c = Call(time.time(), job, model_id, tokens_in, tokens_out,
                 0.0 if cache == "hit" else full, full if cache == "hit" else 0.0,
                 cache, latency_ms, estimated)
        with self._lock:
            self.calls.append(c)
        _persist(c)
        return c

    def snapshot(self) -> list[Call]:
        with self._lock:
            return list(self.calls)


def _priced() -> set[str]:
    from aidpair.catalog import CATALOG
    return set(CATALOG)


def _persist(c: Call) -> None:
    try:
        from aidpair.db import coll
        coll("meter").insert(c.id, {"type": "call", **asdict(c)})
    except Exception:
        # The meter in memory is what the dashboard reads. A failed write to the
        # cluster costs the SQL++ read-back, not the demo.
        pass


METER = Meter()
