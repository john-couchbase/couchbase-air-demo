"""
Score classification against the dataset's `expected` labels, without the cluster.

    .venv/bin/python scripts/eval_classify.py [N]

Reports: whether every hand-written special reaches the frontier agent (the
number that matters), how many crowd messages would escalate (the funnel
width), intent agreement on the crowd, and the cache hit rate over the first N
surge messages.
"""
import asyncio, json, sys, time
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aidpair.classify import classify_one
from aidpair.llm import CACHE
from aidpair.meter import METER

D = Path(__file__).resolve().parents[1] / "data"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
surge = json.loads((D / "surge.json").read_text())
pax = {p["id"]: p for p in json.loads((D / "passengers.json").read_text())}

def escalates(t, tier):
    """Mirror of FUNNEL_SQLPP in aidpair/classify.py. Keep the two in step."""
    return t["urgency"] >= 3 and (
        t["urgency"] >= 4
        or any(n in ("minor", "medical", "mobility") for n in t["needs"])
        or tier == "Concierge"
        or (tier == "Platinum" and t.get("sentiment") in ("angry", "distressed")))

async def main():
    sample = surge[:N]
    specials = [m for m in surge if m["expected"].get("escalate")]
    batch = sample + [m for m in specials if m not in sample]
    sem = asyncio.Semaphore(16)
    async def go(m):
        async with sem: return m, await classify_one(m)
    t = time.time(); res = await asyncio.gather(*[go(m) for m in batch]); dt = time.time() - t
    miss_sp = [(m["text"][:70], r) for m, r in res if m["expected"].get("escalate")
               and not escalates(r, pax[m["passenger_id"]]["tier"])]
    crowd = [(m, r) for m, r in res if not m["expected"].get("escalate")]
    esc = sum(escalates(r, pax[m["passenger_id"]]["tier"]) for m, r in crowd)
    agree = sum(r.get("intent") == m["expected"].get("intent") for m, r in crowd)
    hits = Counter(r["cache"] for _, r in res)
    print(f"{len(batch)} messages in {dt:.1f}s ({len(batch)/dt:.1f}/s)")
    print(f"specials escalated: {len(specials)-len(miss_sp)}/{len(specials)}")
    for txt, r in miss_sp: print("  MISSED:", txt, "->", r["urgency"], r["needs"], r.get("intent"), r)
    print(f"crowd escalating: {esc}/{len(crowd)} ({esc/len(crowd):.0%})")
    print(f"crowd intent agreement: {agree}/{len(crowd)}")
    print(f"cache: {dict(hits)}  entries={CACHE.size()}")
    for m, r in crowd:
        if escalates(r, pax[m["passenger_id"]]["tier"]): print("  ESC:", r["urgency"], r.get("needs"), m["text"][:80])
    print("confusion:", Counter((m["expected"].get("intent"), r.get("intent")) for m, r in crowd if r.get("intent") != m["expected"].get("intent")).most_common(6))
    print("urgency dist (crowd):", Counter(r["urgency"] for _, r in crowd))
    cost = sum(c.cost for c in METER.snapshot()); av = sum(c.avoided for c in METER.snapshot())
    print(f"spend ${cost:.5f}  avoided ${av:.5f}")
asyncio.run(main())
