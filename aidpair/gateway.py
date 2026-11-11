"""
LOCAL ONLY. A stand-in for the Capella Model Service gateway, so the laptop can
run the demo the way sbx-27 runs it.

    .venv/bin/python -m uvicorn aidpair.gateway:app --host 0.0.0.0 --port 8020

The app then runs in its remote mode (MODEL_BACKEND=model_service) against
http://localhost:8020/v1: the same code, header parsing, run tags, SQL++ path
and timing estimate that run on the sandbox. Only the gateway is imitated, and
it imitates what was observed on sbx-27 (docs/MOVING-TO-CAPELLA.md):

- Exact-match cache: a request identical to an earlier one (same model,
  messages, temperature, max_tokens, response format) is answered from the
  cache in about GATEWAY_HIT_MS, with `x-cache: HIT`. Misses carry no x-cache
  header at all, as on sbx-27.
- Semantic is broken: a request with `X-cb-cache: semantic` is looked up but its
  answer is never stored, so the cache never fills for it. GATEWAY_SEMANTIC_WORKS=1
  turns that into a working exact cache instead, to see the demo if it is fixed.
- AI Functions and the cache: the local ai_completion UDF calls /v1 (uses the
  cache) or /nocache/v1 (skips it), chosen by scripts/local_ai_functions.py.
  Which one sbx-27 does is the open dev-team question; this lets us see both.
- GATEWAY_EXTRA_MS adds latency to every response, to imitate a slow network
  between the presenting laptop and Capella.

Model names are mapped to LM Studio: Claude-family names to the frontier
stand-in, everything else to the small one. A small-model request without a
JSON schema goes to Mistral, because local Llama answers schema-less prompts
in tool-call format (an LM Studio template quirk Nova does not share).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

UPSTREAM = os.environ.get("GATEWAY_UPSTREAM", "http://localhost:1234/v1").rstrip("/")
SMALL = os.environ.get("GATEWAY_SMALL_MODEL", "meta-llama-3.1-8b-instruct")
FRONTIER = os.environ.get("GATEWAY_FRONTIER_MODEL", "meta-llama-3.1-8b-instruct")
NOSCHEMA = os.environ.get("GATEWAY_NOSCHEMA_MODEL", "mistralai/mistral-7b-instruct-v0.3")
EMBED = os.environ.get("GATEWAY_EMBED_MODEL", "text-embedding-nomic-embed-text-v1.5")
HIT_MS = int(os.environ.get("GATEWAY_HIT_MS", "100"))          # sbx-27: a direct repeat ~0.1 s
EXTRA_MS = int(os.environ.get("GATEWAY_EXTRA_MS", "0"))
SEMANTIC_WORKS = os.environ.get("GATEWAY_SEMANTIC_WORKS", "0") == "1"

app = FastAPI(title="Model Service gateway stand-in (local only)")
_client = httpx.AsyncClient(timeout=httpx.Timeout(300.0), limits=httpx.Limits(max_connections=96))
_cache: dict[str, dict] = {}
STATS = {"hits": 0, "misses": 0, "bypassed": 0, "semantic_not_stored": 0}


def _local_model(name: str, has_schema: bool) -> str:
    n = name.lower()
    if any(k in n for k in ("claude", "anthropic", "sonnet", "haiku", "opus")):
        return FRONTIER
    return SMALL if has_schema else NOSCHEMA


def _key(body: dict) -> str:
    """Exact match on everything that shapes the answer, including the system
    prompt, so the app's per-run tag gives each run its own cache space."""
    k = {f: body.get(f) for f in ("model", "messages", "temperature", "max_tokens",
                                  "response_format")}
    return hashlib.sha256(json.dumps(k, sort_keys=True).encode()).hexdigest()


async def _sleep(ms: int) -> None:
    if ms > 0:
        await asyncio.sleep(ms / 1000)


async def _complete(request: Request, use_cache: bool) -> JSONResponse:
    body = await request.json()
    strategy = (request.headers.get("x-cb-cache") or "").lower()
    key = _key(body)
    t0 = time.time()

    if use_cache and key in _cache:
        STATS["hits"] += 1
        await _sleep(HIT_MS + EXTRA_MS - int((time.time() - t0) * 1000))
        return JSONResponse(_cache[key], headers={"x-cache": "HIT"})

    upstream = {**body, "model": _local_model(body.get("model", ""),
                                              "response_format" in body)}
    r = await _client.post(f"{UPSTREAM}/chat/completions", json=upstream)
    await _sleep(EXTRA_MS)
    if r.status_code != 200:
        return JSONResponse(r.json() if r.content else {}, status_code=r.status_code)
    data = r.json()
    data["model"] = body.get("model", data.get("model"))   # answer under the name asked for

    if not use_cache:
        STATS["bypassed"] += 1
    else:
        STATS["misses"] += 1
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content")
        if strategy == "semantic" and not SEMANTIC_WORKS:
            STATS["semantic_not_stored"] += 1      # sbx-27: looked up, never stored
        elif content:
            _cache[key] = data
    return JSONResponse(data)     # a miss carries no x-cache header, as on sbx-27


@app.post("/v1/chat/completions")
async def chat(request: Request) -> JSONResponse:
    return await _complete(request, use_cache=True)


@app.post("/nocache/v1/chat/completions")
async def chat_nocache(request: Request) -> JSONResponse:
    """What ai_completion calls when AI Functions are set to skip the cache."""
    return await _complete(request, use_cache=False)


@app.post("/v1/embeddings")
async def embeddings(request: Request) -> JSONResponse:
    body = await request.json()
    r = await _client.post(f"{UPSTREAM}/embeddings", json={**body, "model": EMBED})
    return JSONResponse(r.json(), status_code=r.status_code)


@app.get("/stats")
def stats() -> dict:
    return {**STATS, "entries": len(_cache), "hit_ms": HIT_MS, "extra_ms": EXTRA_MS,
            "semantic_works": SEMANTIC_WORKS}


@app.post("/reset")
def reset() -> dict:
    """Empty the cache, like redeploying the model. The demo's own Reset does not
    call this, on purpose: on sbx-27 the cache outlives a Reset too."""
    _cache.clear()
    for k in STATS:
        STATS[k] = 0
    return stats()
