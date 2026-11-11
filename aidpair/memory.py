"""
Agent Memory, behind one interface: recall what is known about a passenger,
remember what was decided.

MEMORY_BACKEND picks where it lives:

  collection  `aidp-air`.`ops`.`memory`: one document per passenger, read with
              SQL++ and upserted by the app on approval. The original behaviour.
  ams         Capella's hosted AgentMemory service (REST, docs/agentmemory-openapi.json).
              One AgentMemory *user* per passenger. Their history lives in the
              session "history" (scripts/seed_memory.py loads it); what the demo
              approves goes to the session "demo", which Reset deletes, so every
              run starts from the same history. Recall is a semantic search over
              all of the passenger's sessions.
  mcp         a memory service reached over MCP, with tool names and argument
              templates from settings (MEMORY_RECALL_TOOL / _ARGS, MEMORY_WRITE_TOOL / _ARGS).

Whatever the backend, recall returns the shape the prompt and the Recovery tab
use, and a failing service never stops a draft: recall falls back to the collection.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx

from aidpair.config import settings
from aidpair.db import coll
from aidpair.mcp_client import auth_headers
from aidpair.mcp_client import client as mcp_client

HISTORY = "history"   # seeded once from data/memory.json
DEMO = "demo"         # what this run's approvals wrote; deleted on Reset


def backend() -> str:
    b = (settings().memory_backend or "collection").lower()
    return "ams" if b == "rest" else b


# ---------------------------------------------------------------- AgentMemory
class AMS:
    """A thin client for the AgentMemory REST API."""

    def __init__(self) -> None:
        s = settings()
        self.base = s.memory_url.rstrip("/")
        self.http = httpx.AsyncClient(
            base_url=self.base, timeout=30,
            headers={**auth_headers(s.memory_auth_header, s.memory_token),
                     "Content-Type": "application/json"})
        self._users: set[str] = set()
        self._sessions: set[tuple[str, str]] = set()

    async def _req(self, method: str, path: str, ok=(200, 201, 204), **kw) -> httpx.Response:
        r = await self.http.request(method, path, **kw)
        if r.status_code not in ok:
            raise RuntimeError(f"AgentMemory {method} {path} -> {r.status_code}: {r.text[:300]}")
        return r

    async def ensure_user(self, uid: str, name: str = "") -> None:
        if uid in self._users:
            return
        await self._req("POST", "/users", ok=(200, 201, 409),
                        json={"user_id": uid, "name": name or uid,
                              "metadata": {"app": "aidp-air", "namespace": settings().memory_namespace}})
        self._users.add(uid)

    async def ensure_session(self, uid: str, sid: str) -> None:
        if (uid, sid) in self._sessions:
            return
        await self._req("POST", f"/users/{uid}/sessions", ok=(200, 201, 409),
                        json={"session_id": sid, "metadata": {"app": "aidp-air"}})
        self._sessions.add((uid, sid))

    async def add_facts(self, uid: str, name: str, sid: str, facts: list[str],
                        kind: str, created_at: str | None = None) -> dict:
        await self.ensure_user(uid, name)
        await self.ensure_session(uid, sid)
        body: dict[str, Any] = {"facts": facts, "annotations": {"kind": kind, "app": "aidp_air"},
                                "async_processing": True}
        if created_at:
            body["created_at"] = created_at
        return (await self._req("POST", f"/users/{uid}/sessions/{sid}/memory", json=body)).json()

    async def search(self, uid: str, query: str, k: int = 8) -> list[dict]:
        """Semantic search over all of the user's sessions. A block only joins
        semantic search once its extraction is done, so a fresh write (or a
        slow extraction queue) can leave it empty; then the newest blocks are
        listed by filter instead, which includes those still processing."""
        out = await self._search(uid, query, k) if query else []
        return out or await self._search(uid, None, k)

    async def _search(self, uid: str, query: str | None, k: int) -> list[dict]:
        # The session in the path is only the anchor; session_ids "all" widens it.
        r = await self.http.post(f"/users/{uid}/sessions/{HISTORY}/memory/search", json={
            "query": query,
            "filters": {"session_ids": "all", "relevant_k": k,
                        **({} if query else {"order_by": "ingested_at"})}})
        if r.status_code == 404:   # no such user or session yet: nothing remembered
            return []
        if r.status_code >= 400:
            raise RuntimeError(f"AgentMemory search -> {r.status_code}: {r.text[:300]}")
        return r.json().get("memory_blocks") or []

    async def delete_session(self, uid: str, sid: str) -> None:
        await self._req("DELETE", f"/users/{uid}/sessions/{sid}", ok=(200, 204, 404))
        self._sessions.discard((uid, sid))

    async def health(self) -> dict:
        return (await self._req("GET", "/health")).json()


_ams: AMS | None = None


def ams() -> AMS:
    global _ams
    if _ams is None:
        _ams = AMS()
    return _ams


def _block_text(b: dict) -> str:
    if b.get("fact"):
        return b["fact"]
    if b.get("summary"):
        return b["summary"]
    m = b.get("message") or {}
    return " / ".join(x for x in (m.get("user_content"), m.get("assistant_content")) if x)


# ------------------------------------------------------------- MCP (generic)
def _fill(template: str, **values: Any) -> Any:
    def sub(v: Any) -> Any:
        if isinstance(v, str):
            for k, val in values.items():
                v = v.replace("{" + k + "}", str(val))
            return v
        if isinstance(v, list):
            return [sub(x) for x in v]
        if isinstance(v, dict):
            return {k: sub(x) for k, x in v.items()}
        return v
    return sub(json.loads(template))


def _as_notes(text: str) -> list[str]:
    try:
        v = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return [ln.strip() for ln in (text or "").splitlines() if ln.strip()][:12]
    if isinstance(v, dict):
        for k in ("memory_blocks", "results", "memories", "data", "items"):
            if isinstance(v.get(k), list):
                v = v[k]
                break
    if isinstance(v, list):
        return [(_block_text(m) or json.dumps(m)) if isinstance(m, dict) else str(m)
                for m in v][:12]
    return [json.dumps(v)[:400]]


async def _mcp(op: str, **values: Any) -> str:
    s = settings()
    name = s.memory_recall_tool if op == "recall" else s.memory_write_tool
    if not (s.memory_url and name):
        raise RuntimeError(f"MEMORY_URL and MEMORY_{op.upper()}_TOOL must be set")
    args = _fill(s.memory_recall_args if op == "recall" else s.memory_write_args,
                 namespace=s.memory_namespace, **values)
    text, err = await mcp_client(s.memory_url, s.memory_auth_header, s.memory_token).call(name, args)
    if err:
        raise RuntimeError(f"memory {op}: {text[:300]}")
    return text


# -------------------------------------------------------------------- public
async def _collection_recall(passenger: dict) -> dict:
    try:
        m = await asyncio.to_thread(lambda: coll("memory").get(passenger["id"]).content_as[dict])
    except Exception:
        m = {}
    return {"source": "collection", "disruptions": m.get("disruptions") or [],
            "preferences": m.get("preferences") or {}, "notes": m.get("notes") or []}


async def recall(passenger: dict, query: str) -> dict:
    """{"source", "disruptions", "preferences", "notes"}: the shape the prompt
    and the Recovery tab use. A failing service falls back to the collection."""
    b = backend()
    if b == "collection":
        return await _collection_recall(passenger)
    t = time.time()
    try:
        if b == "ams":
            blocks = await ams().search(passenger["id"], query)
            notes = [x for x in (_block_text(bl) for bl in blocks) if x][:8]
        else:
            notes = _as_notes(await _mcp("recall", passenger_id=passenger["id"],
                                         name=passenger.get("name", ""), query=query,
                                         note="", event=""))
    except Exception as e:
        print("memory recall (service -> collection):", str(e)[:300])
        return {**await _collection_recall(passenger), "source": "collection_fallback"}
    return {"source": b, "disruptions": [], "preferences": {}, "notes": notes,
            "latency_ms": int((time.time() - t) * 1000)}


async def remember(passenger: dict, note: str, event: str) -> None:
    """Called only on approval: a person signed off on what is written."""
    b = backend()
    if b == "collection":
        await asyncio.to_thread(_remember_collection, passenger["id"], note, event)
        return
    what, _, goodwill = event.partition(" | goodwill: ")
    fact = f"{time.strftime('%Y-%m-%d')}: {what}" + (f"; goodwill {goodwill}" if goodwill else "")
    facts = [fact] + ([note] if note else [])
    if b == "ams":
        await ams().add_facts(passenger["id"], passenger.get("name", ""), DEMO, facts, "approval")
    else:
        await _mcp("write", passenger_id=passenger["id"], name=passenger.get("name", ""),
                   query="", note=" ".join(facts), event=event)


async def forget_demo(passenger_ids: set[str]) -> None:
    """Reset: drop what this run's approvals wrote to the hosted service, so the
    next run starts from the seeded history again."""
    if backend() != "ams" or not passenger_ids:
        return
    sem = asyncio.Semaphore(8)

    async def one(pid: str) -> None:
        async with sem:
            try:
                await ams().delete_session(pid, DEMO)
            except Exception as e:
                print("memory reset:", pid, str(e)[:200])
    await asyncio.gather(*[one(p) for p in passenger_ids])


def _remember_collection(pid: str, note: str, event: str) -> None:
    mem = coll("memory")
    m = mem.get(pid).content_as[dict]
    what, _, goodwill = event.partition(" | goodwill: ")
    m.setdefault("disruptions", []).append({"when": "2026-02-10", "what": what,
                                            "goodwill": goodwill})
    if note:
        m.setdefault("notes", []).append(note)
    mem.upsert(pid, m)
