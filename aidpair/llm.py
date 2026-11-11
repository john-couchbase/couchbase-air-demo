"""
Model calls, through one OpenAI-compatible endpoint, with the semantic cache
in front of them.

On the sandbox the endpoint is the AI Data Plane Model Service and the cache is
the one the endpoint was deployed with: it answers before the model is reached
and says so in an `x-cache` header. Locally the endpoint is LM Studio, which has
no cache, so `SemanticCache` below stands in for it and every hit it produces is
labelled `local_standin`. The two are never mixed in one figure.

Only a job that asks for it is cached. Classification is: its output is written to be
the same for any passenger who says the same thing. The agent is not: every
draft is about one person.
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
import time
from dataclasses import dataclass

import httpx
import numpy as np

from aidpair.catalog import get
from aidpair.config import settings
from aidpair.meter import METER


@dataclass
class Result:
    text: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cache: str                 # "hit" | "miss" | "n/a"
    cache_source: str          # "model_service" | "local_standin" | "none"
    similarity: float | None = None


_clients: dict[str, httpx.AsyncClient] = {}

# Endpoints that refused a JSON schema. Structured output is not guaranteed on
# every deployment; the prompts ask for JSON anyway and parse_json copes, so a
# refusal costs one retried call and is then remembered for that model.
_no_schema: set[str] = set()


def client(base_url: str | None = None, api_key: str | None = None) -> httpx.AsyncClient:
    """One pooled client per endpoint. Locally every model shares LM Studio's;
    on the Model Service each deployed model has its own connection string,
    and may have its own key."""
    s = settings()
    base = (base_url or s.model_base_url).rstrip("/")
    if base not in _clients:
        _clients[base] = httpx.AsyncClient(
            base_url=base,
            headers={"Authorization": f"Bearer {api_key or s.model_api_key}"},
            timeout=httpx.Timeout(300.0),
            limits=httpx.Limits(max_connections=64),
        )
    return _clients[base]


def remote() -> bool:
    return settings().model_backend != "local"


def route(job: str, model_id: str) -> tuple[str, str]:
    """(endpoint, model name) for a job. Locally: LM Studio and the stand-in.
    Remotely: the job's own deployment, as written by deploy_models.py, falling
    back to the shared endpoint and the catalog id."""
    s = settings()
    if not remote():
        return s.model_base_url, get(model_id).local_model
    base = getattr(s, f"{job}_base_url", "") or s.model_base_url
    name = getattr(s, f"{job}_model_name", "") or model_id
    return base, name


async def embed(texts: list[str]) -> np.ndarray:
    s = settings()
    base = (s.embed_base_url or s.model_base_url) if remote() else s.model_base_url
    name = (s.embed_model_name or s.embed_model) if remote() else s.embed_model
    key = s.embed_api_key if remote() else None
    r = await client(base, key).post("/embeddings", json={"model": name, "input": texts})
    r.raise_for_status()
    v = np.array([d["embedding"] for d in r.json()["data"]], dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


# --------------------------------------------------------------------- cache
_NUM = re.compile(r"\b[A-Z]{2}\s?\d{2,4}\b|\d+")


def cache_key_text(text: str) -> str:
    """What the cache compares. Flight numbers and digits are masked so two
    people asking the same question about different flights look the same -
    which is only safe because classification never writes the flight into its output."""
    return _NUM.sub("#", text.strip().lower())


class SemanticCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.vecs: list[np.ndarray] = []
        self.vals: list[str] = []
        self.keys: list[str] = []
        self.exact: dict[str, str] = {}
        self._inflight: dict[str, asyncio.Future] = {}

    def reset(self) -> None:
        with self._lock:
            self.vecs, self.vals, self.keys, self.exact = [], [], [], {}
            self._inflight = {}

    def lookup(self, key: str, vec: np.ndarray) -> tuple[str | None, float | None]:
        with self._lock:
            if key in self.exact:
                return self.exact[key], 1.0
            if not self.vecs:
                return None, None
            m = np.stack(self.vecs)
            sims = m @ vec
            i = int(np.argmax(sims))
            best = float(sims[i])
        if best >= settings().cache_threshold:
            return self.vals[i], best
        return None, best

    def store(self, key: str, vec: np.ndarray, value: str) -> None:
        with self._lock:
            self.exact[key] = value
            self.vecs.append(vec)
            self.vals.append(value)
            self.keys.append(key)

    def size(self) -> int:
        return len(self.vals)


CACHE = SemanticCache()


# --------------------------------------------------------------------- calls
async def _chat(job: str, model_id: str, messages: list[dict], *, schema: dict | None,
                max_tokens: int, temperature: float | None,
                headers: dict | None = None) -> tuple[str, int, int, int, str | None]:
    base, name = route(job, model_id)
    api_key = getattr(settings(), f"{job}_api_key", "") if remote() else ""
    body: dict = {
        "model": name, "messages": messages,
        "max_tokens": max_tokens,
    }
    if temperature is not None:
        body["temperature"] = temperature
    key = f"{base}|{name}"
    if schema and key not in _no_schema:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "out", "strict": True, "schema": schema},
        }
    t = time.time()
    r = await client(base, api_key).post("/chat/completions", json=body, headers=headers)
    if r.status_code == 400 and "response_format" in body:
        _no_schema.add(key)
        body.pop("response_format")
        r = await client(base, api_key).post("/chat/completions", json=body, headers=headers)
    r.raise_for_status()
    j = r.json()
    u = j.get("usage") or {}
    # A reply cut off by max_tokens can arrive with no content at all.
    return (j["choices"][0]["message"].get("content") or "", u.get("prompt_tokens", 0),
            u.get("completion_tokens", 0), int((time.time() - t) * 1000),
            r.headers.get("x-cache"))


async def chat_tools(job: str, model_id: str, messages: list[dict], tools: list[dict], *,
                     max_tokens: int, temperature: float | None) -> tuple[dict, Result]:
    """One OpenAI-style chat call that may answer with tool_calls. Returns the
    assistant message as sent back (content and/or tool_calls) and its Result.
    Metered like any other call; never cached, every step is about one person."""
    base, name = route(job, model_id)
    api_key = getattr(settings(), f"{job}_api_key", "") if remote() else ""
    body: dict = {"model": name, "messages": messages, "max_tokens": max_tokens}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    if temperature is not None:
        body["temperature"] = temperature
    t = time.time()
    r = await client(base, api_key).post("/chat/completions", json=body)
    if r.status_code >= 400:
        raise httpx.HTTPStatusError(f"chat with tools -> {r.status_code}: {r.text[:300]}",
                                    request=r.request, response=r)
    j = r.json()
    u = j.get("usage") or {}
    ti, to = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
    ms = int((time.time() - t) * 1000)
    METER.record(job, model_id, ti, to, ms)
    msg = j["choices"][0]["message"]
    return msg, Result(msg.get("content") or "", ti, to, ms, "n/a", "none")


async def complete(job: str, model_id: str, system: str, user: str, *,
                   schema: dict | None = None, max_tokens: int = 400,
                   temperature: float | None = 0.0, cached: bool = False) -> Result:
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if not cached:
        text, ti, to, ms, _ = await _chat(job, model_id, msgs, schema=schema,
                                          max_tokens=max_tokens, temperature=temperature)
        METER.record(job, model_id, ti, to, ms)
        return Result(text, ti, to, ms, "n/a", "none")

    if remote():
        # The Model Service's own cache, chosen when the model was deployed.
        # The gateway sends x-cache only on a hit, so no header is a miss.
        # X-cb-cache is sent only when configured: on sbx-27 a request that
        # names a strategy is looked up but its answer is never stored, so
        # the cache never fills. Left blank, the deployment's strategy applies.
        s = settings()
        hdrs = {"X-cb-cache": s.model_cache_strategy} if s.model_cache_strategy else None
        text, ti, to, ms, xcache = await _chat(
            job, model_id, msgs, schema=schema, max_tokens=max_tokens,
            temperature=temperature, headers=hdrs)
        verdict = "hit" if xcache and "hit" in xcache.lower() else "miss"
        if verdict == "hit" and not (ti or to):
            ti, to = (len(system) + len(user)) // 4, len(text) // 4
        METER.record(job, model_id, ti, to, ms, cache=verdict)
        return Result(text, ti, to, ms, verdict, "model_service")

    key = cache_key_text(user)
    t0 = time.time()
    vec = (await embed([key]))[0]
    hit, sim = CACHE.lookup(key, vec)
    if hit is None and key in CACHE._inflight:
        # Single flight: a dozen people typing the same words at the same moment
        # should cost one call, not a dozen racing to fill the cache.
        hit = await CACHE._inflight[key]
        sim = 1.0
    if hit is not None:
        ms = int((time.time() - t0) * 1000)
        # Tokens a miss would have spent, estimated from the stored answer; only
        # used for cost avoided, never added to spend.
        ti = (len(system) + len(user)) // 4
        to = len(hit) // 4
        METER.record(job, model_id, ti, to, ms, cache="hit")
        return Result(hit, ti, to, ms, "hit", "local_standin", sim)

    fut: asyncio.Future = asyncio.get_running_loop().create_future()
    CACHE._inflight[key] = fut
    try:
        text, ti, to, ms, xcache = await _chat(job, model_id, msgs, schema=schema,
                                               max_tokens=max_tokens, temperature=temperature)
        CACHE.store(key, vec, text)
        fut.set_result(text)
    except Exception as e:
        fut.set_exception(e)
        fut.exception()  # retrieved, so no "never retrieved" warning
        raise
    finally:
        CACHE._inflight.pop(key, None)
    METER.record(job, model_id, ti, to, ms, cache="miss")
    return Result(text, ti, to, ms, "miss",
                  "model_service" if xcache else "local_standin", sim)


def parse_json(text: str) -> dict:
    """The model's JSON, or {} if there is none. Never raises: a reply can come
    back in a code fence, with prose around it, or cut off by max_tokens, and one
    bad reply must not take down a worker or an eval."""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    for candidate in (text, *(m.group(0) for m in [re.search(r"\{.*\}", text, re.S)] if m)):
        try:
            v = json.loads(candidate)
            return v if isinstance(v, dict) else {}
        except json.JSONDecodeError:
            pass
    # Cut off mid-object: close an open string, drop a dangling key, close braces.
    i = text.find("{")
    if i < 0:
        return {}
    t = text[i:]
    if t.count('"') % 2:
        t += '"'
    t = re.sub(r',\s*"[^"]*"\s*:?\s*"?$', "", t)
    t += "]" * max(0, t.count("[") - t.count("]")) + "}" * max(0, t.count("{") - t.count("}"))
    try:
        v = json.loads(t)
        return v if isinstance(v, dict) else {}
    except json.JSONDecodeError:
        return {}
