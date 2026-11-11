"""
Provision the cluster from data/*.json. Idempotent: run it after every sandbox
scrub, or any time the demo state needs to go back to a normal morning.

    .venv/bin/python scripts/provision.py

Needs `travel-sample` loaded (the agent reads partner routes from it) and the
bucket named in CB_BUCKET to exist.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from couchbase.exceptions import (  # noqa: E402
    CollectionAlreadyExistsException, QueryIndexAlreadyExistsException,
    ScopeAlreadyExistsException,
)

from aidpair.config import settings  # noqa: E402
from aidpair.db import COLLECTIONS, bucket, coll, ks, query  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data"

INDEXES = [
    ("ix_msg_pending", "messages", "(ts) WHERE classification IS MISSING"),
    ("ix_msg_class", "messages", "(classification.urgency, classification.intent, ts)"),
    ("ix_msg_ts", "messages", "(ts)"),
    ("ix_res_status", "resolutions", "(status, created)"),
    ("ix_meter_ts", "meter", "(ts, job)"),
    ("ix_flight_dest", "flights", "(dest, status)"),
]


def main() -> None:
    s = settings()
    cm = bucket().collections()
    try:
        cm.create_scope(s.cb_scope)
    except ScopeAlreadyExistsException:
        pass
    for c in COLLECTIONS:
        try:
            cm.create_collection(s.cb_scope, c)
        except CollectionAlreadyExistsException:
            pass
    time.sleep(2)

    for name in COLLECTIONS:
        try:
            query(f"CREATE PRIMARY INDEX IF NOT EXISTS ON {ks(name)}")
        except QueryIndexAlreadyExistsException:
            pass
    # Renamed when "triage" became "classification"; an index keeps its old
    # definition under CREATE IF NOT EXISTS, so the old ones are dropped first.
    for ix in ("ix_msg_pending", "ix_msg_triage"):
        query(f"DROP INDEX IF EXISTS {ix} ON {ks('messages')}")
    for ix, c, spec in INDEXES:
        query(f"CREATE INDEX IF NOT EXISTS {ix} ON {ks(c)}{spec}")

    # Everything the demo writes is cleared; everything it reads is reloaded.
    for c in ("messages", "resolutions", "meter"):
        query(f"DELETE FROM {ks(c)}")

    for name, file in [("flights", "flights"), ("passengers", "passengers"),
                       ("bookings", "bookings"), ("memory", "memory")]:
        rows = json.loads((DATA / f"{file}.json").read_text())
        col = coll(name)
        for r in rows:
            if name == "flights":
                r = {**r, "status": r["scheduled_status"], "delay_min": None}
            col.upsert(r["id"], r)
        print(f"{name}: {len(rows)}")
    print("provisioned", ks("*"))


if __name__ == "__main__":
    main()
