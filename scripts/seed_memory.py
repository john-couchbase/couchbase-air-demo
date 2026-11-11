"""
Load the passengers' history from data/memory.json into Capella's AgentMemory
service (MEMORY_BACKEND=ams). provision.py already loads the ops.memory collection;
this is the hosted equivalent.

    AIDP_ENV=capella .venv/bin/python scripts/seed_memory.py [--all] [--limit N] [--fresh]

One AgentMemory user per passenger. Their prior disruptions, notes and preferences
become facts in the session "history", each disruption dated by created_at. By
default only passengers with something to remember are written (--all writes a user
for everyone). --fresh deletes each passenger's "history" session first, so a rerun
does not duplicate facts. Idempotent otherwise only for users and sessions.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aidpair import memory

LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 10**9


async def main() -> None:
    if memory.backend() != "ams":
        raise SystemExit("Set MEMORY_BACKEND=ams (and MEMORY_URL / MEMORY_TOKEN) first.")
    a = memory.ams()
    print("AgentMemory:", await a.health())
    pax = {p["id"]: p for p in json.loads((ROOT / "data" / "passengers.json").read_text())}
    rows = json.loads((ROOT / "data" / "memory.json").read_text())
    if "--all" not in sys.argv:
        rows = [m for m in rows if m.get("disruptions") or m.get("notes")
                or any((m.get("preferences") or {}).values())]
    rows = rows[:LIMIT]
    sem = asyncio.Semaphore(8)
    users = facts = failed = 0
    t0 = time.time()

    async def one(m: dict) -> None:
        nonlocal users, facts, failed
        pid = m["passenger_id"]
        name = pax.get(pid, {}).get("name", "")
        async with sem:
            try:
                if "--fresh" in sys.argv:
                    await a.delete_session(pid, memory.HISTORY)
                for d in m.get("disruptions") or []:
                    await a.add_facts(pid, name, memory.HISTORY,
                                      [f"{d.get('when')}: {d.get('what')}; goodwill {d.get('goodwill')}"],
                                      "prior_disruption", created_at=f"{d.get('when')}T12:00:00Z")
                    facts += 1
                extra = list(m.get("notes") or [])
                prefs = {k: v for k, v in (m.get("preferences") or {}).items() if v}
                if prefs:
                    extra.append("Preferences: " + ", ".join(f"{k} {v}" for k, v in prefs.items()))
                if extra:
                    await a.add_facts(pid, name, memory.HISTORY, extra, "profile")
                    facts += len(extra)
                if not (m.get("disruptions") or extra):
                    await a.ensure_user(pid, name)
                users += 1
            except Exception as e:  # noqa: BLE001
                failed += 1
                if failed <= 3:
                    print("failed:", pid, str(e)[:300])
        if users and users % 100 == 0:
            print(f"  {users} passengers...")

    await asyncio.gather(*[one(m) for m in rows])
    print(f"{users} passengers, {facts} facts written, {failed} failed, "
          f"{time.time() - t0:.0f}s. Facts become searchable once extraction finishes.")


if __name__ == "__main__":
    asyncio.run(main())
