"""
Beat 2: enrich at rest, in bulk, with the cheap model.

On the sandbox this is one SQL++ statement, `CLASSIFY_SQLPP` below, run by the
Query service with an AI Function bound to Nova Micro. Nothing leaves the
cluster to be enriched; the model is called from inside the statement.

Locally there is no AI Functions service, so `run_batch` does the same work in
two halves around the model call: SQL++ selects what landed, the same prompt
goes to the local stand-in, SQL++ writes the classification back onto the document.
The prompt is identical in both, which is what keeps the swap honest.

Classification never writes a name, a flight number or a city into its output. That is
what makes it safe to cache: two passengers who say the same thing get the same
classification, and the entities come from the booking in the join, not from the model.
"""

from __future__ import annotations

import asyncio
import time
import uuid

from aidpair.config import settings
from aidpair.db import coll, ks, query
from aidpair.llm import complete, parse_json, remote

INTENTS = ["status", "rebook", "refund", "hotel", "baggage", "complaint",
           "special_assistance", "other"]
NEEDS = ["minor", "mobility", "medical", "deadline", "family", "animal",
         "connection", "documents", "none"]

# The output shape is spelled out in the prompt, not only in SCHEMA. The SQL++
# AI Function (ai_completion) takes no schema, so on that path the prompt is the
# only thing telling the model which keys and values to use; without it a model
# invents its own ("status": "unknown", "needs": ["unaccompanied minor"]).
SYSTEM = """You classify messages sent to AIDP Air during a winter storm at Chicago O'Hare.
Return exactly one JSON object with these keys and nothing else, no prose, no code fence:
{"intent": "status" | "rebook" | "refund" | "hotel" | "baggage" | "complaint" | "special_assistance" | "other",
 "urgency": 1-5,
 "sentiment": "calm" | "frustrated" | "angry" | "distressed",
 "needs": a list drawn only from "minor", "mobility", "medical", "deadline", "family",
          "animal", "connection", "documents", "none",
 "language": the message's language as a two-letter code,
 "summary": a string}

urgency, judged by consequence, not by tone:
1 = general question unrelated to the storm
2 = asking for information or a refund; nothing is at stake today
3 = needs rebooking, a hotel, a bag or help; the ordinary storm case, including
    meetings, connections, children travelling with a parent, and angry customers.
    Wanting to fly today, tonight, tomorrow morning or "ASAP" is still 3.
4 = a specific, serious consequence if not solved today: a funeral, surgery,
    a once-only event, a job shift, a lost trip, a document or medicine they need
5 = safety or health right now, an unaccompanied child, or a person who cannot
    help themselves

Examples:
"Is my flight cancelled?" -> status, 2, ["none"]
"Cancelled, I need to get there today, what are my options?" -> rebook, 3, ["none"]
"Can I be rebooked for tomorrow morning? ASAP please" -> rebook, 3, ["none"]
"Cancelled, rebook me tomorrow, I have a meeting" -> rebook, 3, ["none"]
"My mother's funeral is tomorrow at 10am" -> rebook, 4, ["deadline", "family"]
"I'm getting married on Saturday and my wedding party is split across flights" -> rebook, 4, ["deadline", "family"]
"Stranded overnight, need hotel and meal vouchers" -> hotel, 3, ["none"]
"I'm stuck at ORD overnight, my flight was cancelled. Do you provide a hotel?" -> hotel, 3, ["none"]
"My bag was on the cancelled flight, where is it? ASAP" -> baggage, 3, ["none"]
"My passport is in my checked bag and I fly abroad tomorrow" -> baggage, 4, ["documents"]
"Worst airline ever, two hours on hold" -> complaint, 3, ["none"]
"Travelling with my two kids" -> 3, ["family"]
"My insulin is in my checked bag and I need it tonight" -> baggage, 5, ["medical"]
"I use a wheelchair and nobody has come to help" -> special_assistance, 5, ["mobility"]
"My 10 year old is flying alone and her flight is cancelled" -> status, 5, ["minor"]
"My son is autistic and overwhelmed by the crowd, is there a quiet place?" -> special_assistance, 4, ["medical", "family"]
"The new flight has no room for my service dog" -> special_assistance, 4, ["animal", "mobility"]
"Third cancellation this year, let me speak to someone who can decide" -> complaint, 3, ["none"], angry

needs: only circumstances the passenger states outright; never infer them.
Otherwise ["none"]. What each one covers:
  minor    = a child travelling without a parent; a child with a parent is "family"
  family   = they say they are travelling with family members (children, a parent, a partner)
  medical  = they name an illness, disability, pregnancy or condition, including autism or
             oxygen. Being stranded, tired, stressed or needing a hotel is not medical.
  mobility = a wheelchair, difficulty walking, or a service animal
sentiment: "angry" when they blame the airline, cite repeated failures or demand
someone with authority; "frustrated" when annoyed but simply asking for help.
summary: at most 12 words, in English, with no names, flight numbers or cities."""

# The current demo run's cache tag (see settings.cache_per_run). Set by
# new_run_tag() on every Reset; None until the first, and for scripts and evals.
_run_tag: str | None = None


def new_run_tag() -> str | None:
    """Start a new cache space for the classify prompt. Tested on us-east-2: the
    same message with a new tag misses, and with the same tag hits."""
    global _run_tag
    _run_tag = uuid.uuid4().hex[:8]
    return _run_tag


def classify_prompt() -> str:
    """SYSTEM, plus the run tag when the Model Service's cache is per run."""
    if _run_tag and remote() and settings().cache_per_run:
        return SYSTEM + f"\n\nRun {_run_tag}."
    return SYSTEM


SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": INTENTS},
        "urgency": {"type": "integer", "minimum": 1, "maximum": 5},
        "sentiment": {"type": "string", "enum": ["calm", "frustrated", "angry", "distressed"]},
        "needs": {"type": "array", "items": {"type": "string", "enum": NEEDS}},
        "language": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["intent", "urgency", "sentiment", "needs", "language", "summary"],
}

# What runs on the sandbox. Shown on screen verbatim; kept beside the prompt so
# the two cannot drift apart. On sbx-27 about one reply in ten comes back in a
# ```json code fence despite the prompt, so the fence is stripped before decoding.
# max_tokens is 500, not 220: inside ai_completion it is not the budget for the
# answer alone. At 220 replies came back truncated or as "" (7 in 15); at 120 a
# reply stopped after about 25 tokens; at 500 none did, and a full answer is
# still about 40 tokens, so the higher cap costs nothing.
CLASSIFY_SQLPP = f"""UPDATE {ks('messages')} AS m
SET m.classification = DECODE_JSON(REGEXP_REPLACE(TRIM(
      default:ai_completion({{
        "system_prompt": $classify_prompt,
        "user_prompt":   m.text,
        "temperature":   0,
        "max_tokens":    500
      }})[0].response), "^```(json)?|```$", "")),
    m.classified_at = NOW_MILLIS() / 1000
WHERE m.classification IS MISSING;"""

# What the sqlpp mode actually executes: the statement above, scoped to one
# batch of ids so concurrent runs never classify the same message twice.
CLASSIFY_SQLPP_BATCH = CLASSIFY_SQLPP.replace(
    "WHERE m.classification IS MISSING;",
    "WHERE META(m).id IN $ids AND m.classification IS MISSING\n"
    "RETURNING META(m).id AS id, m.text, m.classification;")

# The funnel. Model output joined to operational data: urgency and needs come
# from the cheap model, tier comes from the passenger record.
FUNNEL_SQLPP = f"""SELECT m.id, m.hero, m.classification, p.tier, p.name, b.pnr, f.flight_no
FROM {ks('messages')} AS m
JOIN {ks('passengers')} AS p ON KEYS m.passenger_id
JOIN {ks('bookings')}   AS b ON KEYS m.pnr
JOIN {ks('flights')}    AS f ON KEYS b.flight_id
WHERE m.classification IS NOT MISSING AND m.escalated IS MISSING
  AND m.classification.urgency >= 3
  AND ( m.classification.urgency >= 4
     OR ANY n IN m.classification.needs SATISFIES n IN ["minor","medical","mobility"] END
     OR p.tier = "Concierge"
     OR (p.tier = "Platinum" AND m.classification.sentiment IN ["angry","distressed"]) )"""


async def classify_one(msg: dict) -> dict:
    s = settings()
    r = await complete("classify", s.enrich_model, classify_prompt(), msg["text"], schema=SCHEMA,
                       max_tokens=400, cached=True)
    t = parse_json(r.text)
    if "urgency" not in t or "intent" not in t:
        # Unusable reply (cut off or not JSON). Once more, uncached, so a bad
        # answer in the gateway's cache is not simply served again.
        r = await complete("classify", s.enrich_model, classify_prompt(), msg["text"],
                           schema=SCHEMA, max_tokens=800, cached=False)
        t = parse_json(r.text)
    if "urgency" not in t:
        # Still nothing usable: route it to a person rather than guess low.
        t = {"intent": "other", "urgency": 3, "needs": ["none"], "sentiment": "calm",
             "language": msg.get("language", "en"), "summary": "Unparsed reply; review",
             "unparsed": (r.text or "")[:200]}
    t.setdefault("needs", ["none"])
    t.setdefault("intent", "other")
    t["urgency"] = int(t.get("urgency") or 1)
    return {**t, "model": s.enrich_model, "cache": r.cache,
            "tokens_in": r.tokens_in, "tokens_out": r.tokens_out}


class ClassifyWorker:
    """Keeps every model slot busy. A batch-and-wait loop idles all sixteen
    slots behind the slowest call in each batch; this refills a slot the moment
    it frees up."""

    def __init__(self) -> None:
        self.inflight: set[str] = set()
        self.done: list[float] = []
        # Set by the scenario while the demo is paused: no new calls start.
        self.paused = False

    async def run(self) -> None:
        conc = settings().enrich_concurrency
        col = coll("messages")

        async def go(m: dict) -> None:
            try:
                t = await classify_one(m)
            except Exception as e:  # one bad call must not stall the queue
                t = {"intent": "other", "urgency": 3, "needs": ["none"], "sentiment": "calm",
                     "language": m.get("language", "en"), "summary": "Classification failed; review",
                     "error": str(e)[:200], "cache": "n/a"}
            try:
                await asyncio.to_thread(
                    col.mutate_in, m["id"], _set(classification=t, classified_at=time.time()))
                self.done.append(time.time())
            except Exception:
                pass  # the message was cleared by a reset while this call was in flight
            finally:
                self.inflight.discard(m["id"])

        if settings().classify_via == "sqlpp":
            await self._run_sqlpp()
            return

        while True:
            free = 0 if self.paused else conc - len(self.inflight)
            if free > 0:
                rows = await asyncio.to_thread(
                    query,
                    f"SELECT RAW m FROM {ks('messages')} AS m WHERE m.classification IS MISSING "
                    f"ORDER BY m.ts LIMIT {conc * 2}", fresh=True)
                for m in [r for r in rows if r["id"] not in self.inflight][:free]:
                    self.inflight.add(m["id"])
                    asyncio.create_task(go(m))
            await asyncio.sleep(0.25)


    async def _fallback(self, row: dict) -> None:
        """Classify one message the SQL++ path got no answer for, by calling the
        model directly. `classified_by` records that it did not come from the statement.
        Only if that fails too is the message marked for a person."""
        try:
            t = await classify_one({"text": row.get("text") or ""})
            t["classified_by"] = "direct_fallback"
        except Exception as e:
            print("classify (fallback):", str(e)[:300])
            t = {"intent": "other", "urgency": 3, "needs": ["none"], "sentiment": "calm",
                 "language": "en", "summary": "Classification failed; review", "cache": "n/a"}
        try:
            await asyncio.to_thread(coll("messages").mutate_in, row["id"], _set(classification=t))
        except Exception as e:
            print("classify (fallback write):", str(e)[:300])

    async def _run_sqlpp(self) -> None:
        """The real in-database path: the Query service runs the AI Function over
        a batch of landed messages and writes the classification back itself.

        What it gives up is visibility. No per-call usage or cache verdict comes
        back through SQL++, so tokens are estimated from text length (flagged
        estimated in the meter) and the cache is not observed. Both are open
        questions for the dev team; see docs/MOVING-TO-CAPELLA.md."""
        from aidpair.meter import METER
        s = settings()
        # Many small statements in parallel rather than one big one: within a
        # statement the AI Function calls the model once per document, in turn
        # (about 0.55 messages/s on sbx-27), but separate statements do run in
        # parallel. Measured on sbx-27: 4 x 4 = 1.6/s, 8 x 2 = 3.1/s, 32 x 1 = 4.7/s,
        # against a storm that peaks at about 3.4/s.
        batch, parallel = s.sqlpp_batch, s.sqlpp_parallel

        async def one(ids: list[str]) -> None:
            t0 = time.time()
            try:
                rows = await asyncio.to_thread(
                    query, CLASSIFY_SQLPP_BATCH, ids=ids, classify_prompt=classify_prompt())
            except Exception as e:
                print("classify (sqlpp):", str(e)[:300])
                rows = []
            finally:
                self.inflight.difference_update(ids)
            ms = int((time.time() - t0) * 1000)
            for r in rows:
                c = r.get("classification") or {}
                if not c:
                    # ai_completion returned "" here, which on sbx-27 happened
                    # when max_tokens left too little room (see CLASSIFY_SQLPP).
                    # At 500 it has not been seen; kept as a safety net until the
                    # dev team confirms. Ask the gateway directly for this message.
                    # scripts/repro_ai_completion_empty.py reproduces it.
                    await self._fallback(r)
                    self.done.append(time.time())
                    continue
                # No cache verdict comes back through SQL++, so estimate it from
                # the statement's time; only fair with one message per statement.
                verdict = ("n/a" if batch != 1
                           else "hit" if ms < s.sqlpp_cache_hit_ms else "miss")
                if verdict != "n/a":
                    try:
                        await asyncio.to_thread(coll("messages").mutate_in, r["id"], _set(**{
                            "classification.cache": verdict,
                            "classification.cache_estimated": True}))
                    except Exception:
                        pass  # the message was cleared by a reset in the meantime
                METER.record("classify", s.enrich_model,
                             (len(SYSTEM) + len(r.get("text") or "")) // 4,
                             len(str(c)) // 4, ms // max(1, len(rows)),
                             cache=verdict, estimated=True)
                self.done.append(time.time())

        while True:
            free = 0 if self.paused else parallel - len(self.inflight) // batch
            if free > 0:
                rows = await asyncio.to_thread(
                    query,
                    f"SELECT m.id FROM {ks('messages')} AS m WHERE m.classification IS MISSING "
                    f"ORDER BY m.ts LIMIT {batch * parallel * 2}", fresh=True)
                pending = [r["id"] for r in rows if r["id"] not in self.inflight]
                for i in range(0, min(len(pending), free * batch), batch):
                    ids = pending[i:i + batch]
                    self.inflight.update(ids)
                    asyncio.create_task(one(ids))
            await asyncio.sleep(0.5)


def _set(**fields):
    from couchbase.subdocument import upsert
    return [upsert(k, v) for k, v in fields.items()]


def escalations() -> list[dict]:
    return query(FUNNEL_SQLPP, fresh=True)
