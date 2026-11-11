"""
The demo's HTTP surface, and the built web app, on one port.

    .venv/bin/python -m uvicorn aidpair.api:app --host 127.0.0.1 --port 8000

Start it from a terminal you own, not from an editor's preview manager: a
process the editor started is one the editor can reap mid-demo.

The dashboard polls. At one request a second, polling is simpler to reason
about on stage than a stream, and a dropped poll heals itself.
"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from aidpair import agent, classify
from aidpair.catalog import CATALOG
from aidpair.config import settings
from aidpair.db import coll, ks, query
from aidpair.llm import CACHE
from aidpair.memory import backend as memory_backend
from aidpair.meter import METER
from aidpair.scenario import SCENARIO

BUCKET_S = 5


@asynccontextmanager
async def lifespan(_: FastAPI):
    # The workers push every database call to a thread so the event loop stays
    # free for requests. The default pool (cores + 4) is smaller than the 32
    # statements the SQL++ path keeps in flight on its own.
    asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=64))
    await SCENARIO.reset()
    SCENARIO.start()
    yield


app = FastAPI(title="AIDP Air - serverless models demo", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


def _gateway_standin() -> bool:
    """Remote mode, but the "Model Service" is aidpair/gateway.py on this
    machine: the sandbox-like local mode. Reported as a stand-in everywhere, so
    the UI never calls a laptop Live."""
    from urllib.parse import urlparse
    s = settings()
    urls = [s.model_base_url, s.classify_base_url, s.agent_base_url]
    return s.model_backend != "local" and any(
        urlparse(u).hostname in ("localhost", "127.0.0.1", "host.docker.internal")
        for u in urls if u)


def _backend() -> dict:
    s = settings()
    local = s.model_backend == "local"
    gw = _gateway_standin()
    return {
        "models": "local_standin" if local else "gateway_standin" if gw else "model_service",
        "cache": "local_standin" if local else "gateway_standin" if gw else "model_service",
        # Which path classification takes, stated plainly. "sqlpp" runs the AI
        # Function in the Query service (a CURL UDF stand-in on a laptop);
        # "backend" means the app calls the model itself with the same prompt.
        "classify_via": s.classify_via,
        # On the sqlpp path the cache verdict is estimated from response time.
        "cache_estimated": s.classify_via == "sqlpp" and not local,
        "cache_hit_ms": s.sqlpp_cache_hit_ms,
        "cache_per_run": s.cache_per_run and not local,
        # Agent Memory: "collection" (ops.memory) or the hosted service ("ams" / "mcp").
        "memory": memory_backend(),
        # How the agent gathers context: "prefetch" (SQL++ by the app) or "mcp".
        "agent_via": "mcp" if s.agent_via == "mcp" and s.mcp_url else "prefetch",
        "ai_functions": ("query_service" if s.classify_via == "sqlpp" and not local and not gw
                         else "local_standin"),
        "endpoint": s.model_base_url,
        "stand_ins": {
            s.enrich_model: CATALOG[s.enrich_model].local_model,
            s.agent_model: CATALOG[s.agent_model].local_model,
        } if local else {},
    }


@app.get("/api/state")
def state(watching: bool = False) -> dict:
    """watching: the page is in front of someone (a visible tab). Only that
    keeps the demo from pausing; a tab left in the background does not."""
    s = settings()
    if watching:
        SCENARIO.watched()
    counts = query(
        f"""SELECT COUNT(*) AS inbound,
                   COUNT(m.classification) AS classified,
                   SUM(CASE WHEN m.kind = 'surge' THEN 1 ELSE 0 END) AS surge,
                   SUM(CASE WHEN m.classification.`cache` = 'hit' THEN 1 ELSE 0 END) AS cache_hits,
                   COUNT(m.escalated) AS escalated
            FROM {ks('messages')} AS m""", fresh=True)[0]
    res = query(f"""SELECT r.status, COUNT(*) AS n FROM {ks('resolutions')} AS r
                    GROUP BY r.status""", fresh=True)
    by = {r["status"]: r["n"] for r in res}
    calls = METER.snapshot()
    spend = {j: round(sum(c.cost for c in calls if c.job == j), 6) for j in ("classify", "agent")}
    now = time.time()
    elapsed = now - SCENARIO.t0
    return {
        "phase": SCENARIO.phase,
        # None, "idle" (no one watching) or "user" (the Pause button).
        "paused": SCENARIO.paused,
        "idle_pause_min": s.idle_pause_min,
        "elapsed_s": round(elapsed, 1),
        "storm_at_s": round(SCENARIO.storm_at - SCENARIO.t0, 1) if SCENARIO.storm_at else None,
        "quiet_at_s": round(SCENARIO.quiet_at - SCENARIO.t0, 1) if SCENARIO.quiet_at else None,
        "funnel": {
            "inbound": counts["inbound"], "classified": counts["classified"],
            "surge": counts["surge"] or 0,
            "escalated": by.get("drafted", 0) + by.get("approved", 0),
            "in_agent": len(SCENARIO.worker.inflight),
            "approved": by.get("approved", 0),
        },
        "cache": {
            "hits": counts["cache_hits"] or 0,
            "misses": sum(1 for c in calls if c.job == "classify" and c.cache == "miss"),
            "entries": CACHE.size(),
            "avoided_usd": round(sum(c.avoided for c in calls), 6),
        },
        "spend": {**spend, "total": round(sum(spend.values()), 6)},
        "tokens": {
            j: {"in": sum(c.tokens_in for c in calls if c.job == j and c.cache != "hit"),
                "out": sum(c.tokens_out for c in calls if c.job == j and c.cache != "hit"),
                "calls": sum(1 for c in calls if c.job == j and c.cache != "hit")}
            for j in ("classify", "agent")
        },
        "reserved": {
            "label": s.reserved_gpu_label, "per_hour": s.reserved_gpu_per_hour,
            "so_far": round(s.reserved_gpu_per_hour * elapsed / 3600, 6),
        },
        "models": {"classify": s.enrich_model, "agent": s.agent_model},
        # Display names, so every label follows the configured models.
        "model_names": {
            job: {"name": CATALOG[mid].name, "short": CATALOG[mid].short}
            for job, mid in (("classify", s.enrich_model), ("agent", s.agent_model))
        },
        "backend": _backend(),
        "live": _live(calls, now),
    }


LIVE_WINDOW_S = 10


def _live(calls: list, now: float) -> dict:
    """What the system is doing right now, over the last ten seconds. Drives the
    Demo tab's system diagram: requests in flight are counted directly from the
    workers, rates and spend from the meter."""
    s = settings()
    since = now - LIVE_WINDOW_S
    recent = [c for c in calls if c.ts >= since]
    arrivals = sum(1 for ts, _ in SCENARIO.arrivals if ts >= since)
    # Every model call that isn't a cache hit; the SQL++ path records "n/a".
    cls_miss = sum(1 for c in recent if c.job == "classify" and c.cache != "hit")
    cls_hit = sum(1 for c in recent if c.job == "classify" and c.cache == "hit")
    return {
        "window_s": LIVE_WINDOW_S,
        "arrivals_per_s": round(arrivals / LIVE_WINDOW_S, 2),
        "classify_per_s": round(cls_miss / LIVE_WINDOW_S, 2),
        "cache_per_s": round(cls_hit / LIVE_WINDOW_S, 2),
        "classify_in_flight": len(SCENARIO.classifier.inflight),
        "classify_slots": (s.sqlpp_parallel * s.sqlpp_batch if s.classify_via == "sqlpp"
                           and s.model_backend != "local" else s.enrich_concurrency),
        "agent_in_flight": len(SCENARIO.worker.inflight),
        "agent_slots": s.agent_concurrency,
        "spend_per_min": round(sum(c.cost for c in recent) * 60 / LIVE_WINDOW_S, 5),
        "reserved_per_min": round(s.reserved_gpu_per_hour / 60, 5),
    }


@app.get("/api/timeline")
def timeline() -> dict:
    """Everything the charts need, bucketed from the demo's own clock."""
    s = settings()
    t0 = SCENARIO.t0
    n = int((time.time() - t0) // BUCKET_S) + 1
    rows = [{"t": i * BUCKET_S, "baseline": 0, "surge": 0, "classified": 0, "hits": 0,
             "classify_usd": 0.0, "agent_usd": 0.0, "agent_calls": 0} for i in range(n)]

    def b(ts: float) -> dict | None:
        i = int((ts - t0) // BUCKET_S)
        return rows[i] if 0 <= i < n else None

    for ts, kind in SCENARIO.arrivals:
        if (r := b(ts)):
            r[kind] += 1
    for ts in SCENARIO.classifier.done:
        if (r := b(ts)):
            r["classified"] += 1
    for c in METER.snapshot():
        if (r := b(c.ts)) is None:
            continue
        if c.job == "classify":
            r["classify_usd"] += c.cost
            r["hits"] += c.cache == "hit"
        elif c.job == "agent":
            r["agent_usd"] += c.cost
            r["agent_calls"] += 1
    reserved_per_bucket = s.reserved_gpu_per_hour * BUCKET_S / 3600
    cum = 0.0
    for r in rows:
        cum += r["classify_usd"] + r["agent_usd"]
        r["serverless_cum"] = round(cum, 6)
        r["reserved_cum"] = round(reserved_per_bucket * (r["t"] / BUCKET_S + 1), 6)
        r["reserved_rate"] = round(reserved_per_bucket, 6)
        r["classify_usd"] = round(r["classify_usd"], 6)
        r["agent_usd"] = round(r["agent_usd"], 6)
    return {"bucket_s": BUCKET_S, "rows": rows,
            "storm_at_s": (SCENARIO.storm_at - t0) if SCENARIO.storm_at else None,
            "quiet_at_s": (SCENARIO.quiet_at - t0) if SCENARIO.quiet_at else None}


@app.get("/api/feed")
def feed(limit: int = 14) -> list[dict]:
    """The most recently classified messages. Newest-arrived would be more
    literal, but at the peak those are all still queued and the feed becomes a
    column of "not yet classified"; the queue depth is shown beside it instead."""
    return query(
        f"""SELECT m.id, m.ts, m.kind, m.channel, m.`language`, m.text, m.classification,
                   m.escalated IS NOT MISSING AS escalated, p.tier, f.flight_no, f.dest_city
            FROM {ks('messages')} AS m
            JOIN {ks('passengers')} AS p ON KEYS m.passenger_id
            JOIN {ks('flights')} AS f ON KEYS m.flight_id
            WHERE m.classified_at IS NOT MISSING
            ORDER BY m.classified_at DESC LIMIT $limit""", limit=limit)


@app.get("/api/resolutions")
def resolutions() -> list[dict]:
    done = query(
        f"""SELECT r.id, r.name, r.tier, r.flight_no, r.dest_city, r.status, r.created,
                   r.classification.urgency AS urgency, r.classification.summary AS summary,
                   r.classification.needs AS needs, r.decision.recommended_option AS chosen,
                   (SELECT RAW m.hero FROM {ks('messages')} AS m USE KEYS r.message_id)[0]
                     AS hero
            FROM {ks('resolutions')} AS r
            ORDER BY r.classification.urgency DESC, r.created""", fresh=True)
    # Escalations Claude is still working on, so the Recovery tab can list them
    # the moment they escalate rather than 10-20 seconds later. A draft keeps
    # its message's id, so the row turns into the decision when it lands.
    have = {r["id"] for r in done}
    ids = [i for i in SCENARIO.worker.inflight if i not in have]
    if not ids:
        return done
    drafting = query(
        f"""SELECT META(m).id AS id, p.name, p.tier, f.flight_no, f.dest_city,
                   "drafting" AS status, m.ts AS created,
                   m.classification.urgency AS urgency, m.classification.summary AS summary,
                   m.classification.needs AS needs, m.hero, m.text AS message
            FROM {ks('messages')} AS m USE KEYS $ids
            JOIN {ks('passengers')} AS p ON KEYS m.passenger_id
            JOIN {ks('bookings')} AS b ON KEYS m.pnr
            JOIN {ks('flights')} AS f ON KEYS b.flight_id""", ids=ids)
    return sorted(done + drafting, key=lambda r: (-(r.get("urgency") or 0), r.get("created") or 0))


@app.get("/api/resolutions/{rid}")
def resolution(rid: str) -> dict:
    try:
        return coll("resolutions").get(rid).content_as[dict]
    except Exception:
        raise HTTPException(404, rid)


@app.post("/api/resolutions/{rid}/approve")
async def approve(rid: str) -> dict:
    res = await agent.approve(rid)
    SCENARIO.touched.add(res["passenger_id"])
    return res


@app.get("/api/memory/{pid}")
def memory(pid: str) -> dict:
    return coll("memory").get(pid).content_as[dict]


@app.post("/api/storm")
def storm() -> dict:
    SCENARIO.trigger_storm()
    return {"phase": SCENARIO.phase}


@app.post("/api/pause")
def pause() -> dict:
    SCENARIO.pause("user")
    return {"paused": SCENARIO.paused}


@app.post("/api/resume")
def resume() -> dict:
    SCENARIO.watched()
    SCENARIO.resume()
    return {"paused": SCENARIO.paused}


@app.post("/api/reset")
async def reset() -> dict:
    await SCENARIO.reset()
    return {"phase": SCENARIO.phase}


@app.get("/api/bill")
def bill() -> dict:
    """The run's bill, read back out of the cluster in SQL++."""
    stmt = f"""SELECT c.job, c.model,
       SUM(CASE WHEN c.`cache` = 'hit' THEN 0 ELSE 1 END) AS calls,
       SUM(CASE WHEN c.`cache` = 'hit' THEN 1 ELSE 0 END) AS cache_hits,
       SUM(CASE WHEN c.`cache` = 'hit' THEN 0 ELSE c.tokens_in END)  AS tokens_in,
       SUM(CASE WHEN c.`cache` = 'hit' THEN 0 ELSE c.tokens_out END) AS tokens_out,
       ROUND(SUM(c.cost), 5)    AS spend_usd,
       ROUND(SUM(c.avoided), 5) AS avoided_usd,
       MAX(IFMISSINGORNULL(c.estimated, FALSE)) AS estimated
FROM {ks('meter')} AS c
GROUP BY c.job, c.model
ORDER BY spend_usd DESC"""
    return {"statement": stmt, "rows": query(stmt, fresh=True)}


@app.get("/api/sqlpp")
def sqlpp() -> dict:
    return {
        "classify": classify.CLASSIFY_SQLPP,
        "classify_prompt": classify.SYSTEM,
        "funnel": classify.FUNNEL_SQLPP,
        "context": agent.CONTEXT_SQLPP,
        "partners": agent.PARTNERS_SQLPP,
        "policy": agent.POLICY,
    }


@app.get("/api/models")
def models() -> dict:
    s = settings()
    return {
        "catalog": [
            {"id": m.id, "name": m.name, "provider": m.provider, "role": m.role,
             "in_per_m": m.in_per_m, "out_per_m": m.out_per_m,
             "used_for": [j for j, mid in (("classify", s.enrich_model),
                                            ("agent", s.agent_model)) if mid == m.id],
             "local_standin": (m.local_model if s.model_backend == "local" or _gateway_standin()
                               else None)}
            for m in CATALOG.values()
        ],
        "backend": _backend(),
    }


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "phase": SCENARIO.phase, "backend": _backend()}


_dist = Path(__file__).resolve().parents[1] / "web" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="web")
