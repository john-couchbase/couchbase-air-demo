"""
Beat 3: reason at the top of the funnel, with the frontier model.

Only messages the funnel lets through reach this. For each one the agent
gathers everything it needs from the cluster - the passenger, the booking, the
flight, what Agent Memory holds about them, AIDP Air's own flights that are
still going, and partner flights read from `travel-sample` - and asks the
frontier model for one decision: which option, what goodwill, what to say.

The model proposes; a person approves. Approval is what writes to memory, so
the next time this passenger is disrupted the agent knows what was done.
"""

from __future__ import annotations

import asyncio
import json
import re
import time

from aidpair import memory
from aidpair.catalog import get
from aidpair.config import settings
from aidpair.db import coll, ks, query
from aidpair.llm import chat_tools, complete, parse_json, remote
from aidpair.mcp_client import client as mcp_client
from aidpair.mcp_client import reset as mcp_reset

POLICY = """AIDP Air irregular operations policy (weather), 2026.1
- Weather is outside our control: no cash compensation. Refunds on request for
  cancelled flights, any fare.
- Rebook on the earliest AIDP Air flight with seats at no charge, any cabin up
  to the one booked. Partner airlines may be used when AIDP Air cannot get the
  passenger there within 24 hours of the original departure, or when a stated,
  serious deadline would be missed.
- Overnight: hotel and meal vouchers for any passenger not at home.
- Goodwill miles, at agent discretion: Member up to 5,000; Silver 7,500;
  Gold 10,000; Platinum 25,000; Concierge 40,000. Consider prior disruptions
  in the last 12 months.
- Safety, health, unaccompanied minors and passengers needing assistance come
  before everything else: dispatch a person, do not only send a message."""

SYSTEM = (
    "You are AIDP Air's irregular-operations recovery agent. You decide what to do for one "
    "passenger, within policy, and draft the reply a human agent will approve. Pick an option "
    "id from the list you are given; never invent a flight. Reply in the passenger's language. "
    "Return exactly one JSON object with these keys and nothing else, no prose, no code fence:\n"
    '{"recommended_option": an option id, "why": a string, "backup_option": an option id,\n'
    ' "goodwill_miles": an integer, "vouchers": a list of strings,\n'
    ' "actions": a list of strings, "reply": the message to the passenger,\n'
    ' "memory_note": one line for Agent Memory}\n'
    # The keys are in the prompt as well as SCHEMA: the Model Service does not
    # enforce response_format, so without them Claude invents its own.
    # The limits keep a decision near 500 tokens. Unbounded, Claude Sonnet 5
    # wrote about 1,000, and the Recovery tab waited 12-50 seconds for each.
    "Keep it short, a person reads it on screen: why in at most two sentences; at most four "
    "actions, each a short imperative; vouchers as short names; reply at most 80 words; "
    "memory_note at most 20 words. Every key is required, reply included.\n"
    "\n" + POLICY
)

SCHEMA = {
    "type": "object",
    "properties": {
        "recommended_option": {"type": "string"},
        "why": {"type": "string"},
        "backup_option": {"type": "string"},
        "goodwill_miles": {"type": "integer"},
        "vouchers": {"type": "array", "items": {"type": "string"}},
        "actions": {"type": "array", "items": {"type": "string"}},
        "reply": {"type": "string"},
        "memory_note": {"type": "string"},
    },
    "required": ["recommended_option", "why", "backup_option", "goodwill_miles", "vouchers",
                 "actions", "reply", "memory_note"],
}

CONTEXT_SQLPP = f"""SELECT m.text, m.classification, p AS passenger, b AS booking, f AS flight,
       mem.preferences, mem.disruptions, mem.notes
FROM {ks('messages')} AS m
JOIN {ks('passengers')} AS p ON KEYS m.passenger_id
JOIN {ks('bookings')}   AS b ON KEYS m.pnr
JOIN {ks('flights')}    AS f ON KEYS b.flight_id
LEFT JOIN {ks('memory')} AS mem ON KEYS m.passenger_id
WHERE META(m).id = $id"""

PARTNERS_SQLPP = """SELECT al.name AS airline, s.flight, s.utc AS dep, s.day
FROM `travel-sample`.inventory.route AS r
UNNEST r.schedule AS s
JOIN `travel-sample`.inventory.airline AS al ON KEYS r.airlineid
WHERE r.sourceairport = "ORD" AND r.destinationairport = $dest
  AND r.stops = 0 AND r.airline != "UA"
  AND ((s.day = 2 AND s.utc >= "19:00") OR (s.day = 3 AND s.utc <= "12:00"))
ORDER BY s.day, s.utc LIMIT 4"""


def _options(ctx: dict) -> list[dict]:
    f = ctx["flight"]
    opts: list[dict] = []
    same_day = query(
        f"SELECT RAW fl FROM {ks('flights')} AS fl WHERE fl.dest = $dest "
        f"AND fl.status != 'cancelled' AND META(fl).id != $id", dest=f["dest"], id=f["id"],
    )
    for fl in same_day:
        dep = fl["dep_local"]
        if fl.get("delay_min"):
            h, m = (int(x) for x in dep.split(":"))
            t = h * 60 + m + fl["delay_min"]
            dep = f"{t // 60 % 24:02d}:{t % 60:02d}"
        opts.append({"id": f"{fl['id']}-today", "carrier": "AIDP Air",
                     "flight": fl["flight_no"], "when": f"today {dep}", "seats": "available"})
    opts.append({"id": f"{f['id']}-tomorrow", "carrier": "AIDP Air", "flight": f["flight_no"],
                 "when": f"tomorrow {f['dep_local']}", "seats": "available"})
    for p in query(PARTNERS_SQLPP, dest=f["dest"]):
        opts.append({"id": f"{p['flight']}-{'today' if p['day'] == 2 else 'tomorrow'}",
                     "carrier": p["airline"], "flight": p["flight"],
                     "when": f"{'today' if p['day'] == 2 else 'tomorrow'} {p['dep'][:5]}",
                     "seats": "partner, request"})
    return opts


def _prompt(ctx: dict, options: list[dict]) -> str:
    p, f, b = ctx["passenger"], ctx["flight"], ctx["booking"]
    hist = ctx.get("disruptions") or []
    lines = [
        f"Passenger: {p['name']}, {p['tier']} tier, {p['lifetime_flights']} lifetime flights, "
        f"language {p['language']}.",
        f"Booking {b['pnr']}: {f['flight_no']} ORD-{f['dest']} ({f['dest_city']}) "
        f"departing {f['dep_local']}, {b['cabin']}, party of {b['party_size']}. "
        f"Status: {f['status']}{' - ' + f['cancel_reason'] if f.get('cancel_reason') else ''}.",
        "Agent memory - prior disruptions (last 12 months): "
        + ("; ".join(f"{h['when']} {h['what']} (goodwill: {h['goodwill']})" for h in hist)
           or "none"),
        "Agent memory - preferences: " + str(ctx.get("preferences") or {}),
        "Agent memory - notes: " + ("; ".join(ctx.get("notes") or []) or "none"),
        f"Classification ({get(settings().enrich_model).short}): "
        f"{ctx['classification'].get('summary')} | urgency "
        f"{ctx['classification'].get('urgency')} | needs {ctx['classification'].get('needs')}",
        "Options (pick by id):",
        *[f"  {o['id']}: {o['carrier']} {o['flight']} {o['when']} ({o['seats']})"
          for o in options],
        "",
        f"Message: {ctx['text']}",
    ]
    return "\n".join(lines)


def _gather(message_id: str) -> tuple[dict, list]:
    """Context and options for one message: three queries, so it runs in a
    thread, off the event loop. Memory is recalled separately (memory.py), so
    the hosted Agent Memory service can stand in for the collection."""
    rows = query(CONTEXT_SQLPP, fresh=True, id=message_id)
    if not rows:
        raise KeyError(message_id)
    ctx = rows[0]
    return ctx, _options(ctx)


MCP_GUIDE = """

You also have tools that read AIDP Air's Couchbase cluster directly. Use them to check
anything you need before deciding: the passenger and booking documents, the flight,
other AIDP Air flights to the same destination, partner routes. Data:
- `aidp-air`.`ops`.passengers, .bookings, .flights, .memory (document id = passenger id)
- `travel-sample`.inventory.route and .airline (partner routes out of ORD)
Keep it to a few lookups. Never invent a flight: recommended_option and backup_option
must be ids from the Options list. When you are done, answer with the JSON object only."""


WRITE_WORDS = {"upsert", "insert", "replace", "delete", "remove", "create", "drop", "update",
               "write", "put", "set", "alter", "flush", "grant", "revoke", "add", "save", "store",
               "patch", "purge", "truncate", "execute", "run_mutation"}


def read_only(name: str) -> bool:
    """By name: a tool whose name has a write verb as a word (add_memory,
    upsertDocument, delete-index) is never offered to the model."""
    words = re.split(r"[_\-\s.]+", re.sub(r"([a-z])([A-Z])", r"\1_\2", name).lower())
    return not WRITE_WORDS.intersection(words)


_SQL_WRITE = re.compile(r"^\s*(INSERT|UPSERT|UPDATE|DELETE|MERGE|CREATE|DROP|ALTER|GRANT|"
                        r"REVOKE|BUILD|EXECUTE|INFER|PREPARE)\b", re.IGNORECASE)


def _writes(args: dict) -> bool:
    return any(isinstance(v, str) and _SQL_WRITE.search(v) for v in args.values())


def _openai_tools(tools: list[dict]) -> list[dict]:
    spec = settings().mcp_tools.strip()
    allow = None if spec.lower() == "auto" else {t.strip() for t in spec.split(",") if t.strip()}
    out = []
    for t in tools:
        if (t["name"] not in allow) if allow is not None else not read_only(t["name"]):
            continue
        out.append({"type": "function", "function": {
            "name": t["name"], "description": (t.get("description") or "")[:1000],
            "parameters": t.get("inputSchema") or {"type": "object", "properties": {}},
        }})
    return out


async def _decide_mcp(prompt: str) -> tuple[dict, int, int, list[dict]]:
    """The tool-using loop: the model may call the MCP server's read-only tools,
    a few times, before it answers. Returns (decision, tokens in, tokens out, trace)."""
    s = settings()
    mcp = mcp_client(s.mcp_url, s.mcp_auth_header, s.mcp_token)
    tools = _openai_tools(await mcp.tools())
    if not tools:
        raise RuntimeError("the MCP server offers none of MCP_TOOLS")
    allowed = {t["function"]["name"] for t in tools}
    msgs: list[dict] = [{"role": "system", "content": SYSTEM + MCP_GUIDE},
                        {"role": "user", "content": prompt}]
    trace: list[dict] = []
    ti = to = 0
    temp = None if remote() else 0.2
    for step in range(s.agent_max_steps):
        last = step == s.agent_max_steps - 1
        msg, r = await chat_tools("agent", s.agent_model, msgs, [] if last else tools,
                                  max_tokens=2000, temperature=temp)
        ti, to = ti + r.tokens_in, to + r.tokens_out
        calls = msg.get("tool_calls") or []
        if not calls:
            return parse_json(r.text), ti, to, trace
        msgs.append({"role": "assistant", "content": msg.get("content") or "",
                     "tool_calls": calls})
        for c in calls:
            fn = c.get("function") or {}
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            t = time.time()
            if name not in allowed:
                text, err = f"tool {name} is not available", True
            elif _writes(args):
                # A query tool can still write. The agent only reads; changes go
                # through a person.
                text, err = "refused: only SELECT statements are allowed", True
            else:
                try:
                    text, err = await mcp.call(name, args)
                except Exception as e:  # a failed lookup is reported to the model
                    text, err = f"error: {str(e)[:300]}", True
            trace.append({"tool": name, "args": args, "ms": int((time.time() - t) * 1000),
                          "chars": len(text), "error": err, "preview": text[:300]})
            msgs.append({"role": "tool", "tool_call_id": c.get("id", name),
                         "content": text[:6000]})
    raise RuntimeError(f"no decision after {s.agent_max_steps} steps")


async def resolve(message_id: str) -> dict:
    s = settings()
    ctx, options = await asyncio.to_thread(_gather, message_id)
    c = ctx.get("classification") or {}
    mem = await memory.recall(ctx["passenger"],
                              query=f"{c.get('summary', '')} {ctx['flight'].get('dest_city', '')}")
    ctx.update(disruptions=mem["disruptions"], preferences=mem["preferences"],
               notes=mem["notes"])
    prompt = _prompt(ctx, options)
    t = time.time()
    via, trace = "prefetch", []
    if s.agent_via == "mcp" and s.mcp_url:
        try:
            d, ti, to, trace = await _decide_mcp(prompt)
            via = "mcp"
        except Exception as e:
            # MCP down, or the gateway refused tools: this draft takes the
            # original path, and says so.
            print("agent (mcp -> prefetch):", message_id, str(e)[:300])
            mcp_reset(s.mcp_url)
            via = "prefetch_fallback"
    # On the Model Service, no temperature: Claude Sonnet 5 rejects any value
    # but the default. The local stand-in keeps the 0.2 it was tuned at. Sonnet
    # 5 also writes longer decisions than 4.6 did; 700 tokens cut them off.
    if via != "mcp":
        r = await complete("agent", s.agent_model, SYSTEM, prompt, schema=SCHEMA,
                           max_tokens=2000, temperature=None if remote() else 0.2)
        d, ti, to = parse_json(r.text), r.tokens_in, r.tokens_out
    doc = {
        "type": "resolution", "id": message_id, "message_id": message_id,
        "passenger_id": ctx["passenger"]["id"], "name": ctx["passenger"]["name"],
        "tier": ctx["passenger"]["tier"], "flight_no": ctx["flight"]["flight_no"],
        "dest_city": ctx["flight"]["dest_city"], "message": ctx["text"],
        "classification": ctx["classification"], "options": options, "decision": d,
        "memory_used": {"disruptions": ctx.get("disruptions") or [],
                        "preferences": ctx.get("preferences") or {},
                        "notes": ctx.get("notes") or [], "source": mem["source"]},
        "agent_via": via, "tool_calls": trace,
        "prompt": prompt, "model": s.agent_model,
        "tokens_in": ti, "tokens_out": to,
        "latency_ms": int((time.time() - t) * 1000),
        "status": "drafted", "created": time.time(),
    }
    await asyncio.to_thread(coll("resolutions").upsert, message_id, doc)
    return doc


async def approve(message_id: str) -> dict:
    """A person signed off. This is the only thing that writes Agent Memory,
    wherever it lives (memory.py)."""
    res = await asyncio.to_thread(lambda: coll("resolutions").get(message_id).content_as[dict])
    d = res.get("decision") or {}
    event = (f"winter storm cancellation, {res['flight_no']} | goodwill: "
             f"{d.get('goodwill_miles', 0):,} miles"
             + (f" + {', '.join(d['vouchers'])}" if d.get("vouchers") else ""))
    await memory.remember({"id": res["passenger_id"], "name": res.get("name", "")},
                          d.get("memory_note") or "", event)
    res["status"] = "approved"
    res["approved"] = time.time()
    await asyncio.to_thread(coll("resolutions").upsert, message_id, res)
    return res


class AgentWorker:
    """Drains the funnel with bounded concurrency. The frontier model is the
    expensive one, so it only ever sees what the funnel let through."""

    def __init__(self) -> None:
        self.inflight: set[str] = set()

    async def tick(self) -> int:
        """Start work for any free slot. Returns how many were started. Called
        every couple of seconds; each draft runs as its own task, so a slow one
        never holds the others back."""
        from aidpair.classify import escalations
        free = settings().agent_concurrency - len(self.inflight)
        if free <= 0:
            return 0
        todo = [r for r in await asyncio.to_thread(escalations) if r["id"] not in self.inflight]
        # Hero first if she is waiting, so the presenter never waits for her.
        todo.sort(key=lambda r: (not r.get("hero"), -(r["classification"].get("urgency") or 0)))
        col = coll("messages")

        async def go(row: dict) -> None:
            from couchbase.subdocument import upsert
            try:
                await resolve(row["id"])
            except Exception as e:
                print("agent:", row["id"], e)
            finally:
                # Marked either way: a message that fails to resolve must not be
                # retried forever. It shows as escalated with no draft.
                try:
                    await asyncio.to_thread(col.mutate_in, row["id"], [upsert("escalated", time.time())])
                except Exception:
                    pass
                self.inflight.discard(row["id"])

        for r in todo[:free]:
            self.inflight.add(r["id"])
            asyncio.create_task(go(r))
        return min(free, len(todo))
