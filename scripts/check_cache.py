"""
Why does the Storm tab say 0% answered from cache on the sandbox?

    AIDP_ENV=capella .venv/bin/python scripts/check_cache.py

Run it on the machine you present from, on the network you present on: one of
the possible causes is that machine's round trip to Capella.

A storm should show about 11% on the exact-match cache (36 of the first 320
surge messages are word-for-word repeats). 0% means no hit is being observed
at all. This checks the three places that can happen:

  A. Settings: which classification path is in use, and the hit threshold.
  B. The gateway, called directly: does a repeat come back with x-cache: HIT?
     If not, the deployment is not caching at all.
  C. The same repeat through SQL++ (ai_completion), timed from this machine,
     beside a plain SELECT for the network round trip. On the sqlpp path the
     app never sees a verdict; it counts a statement faster than
     SQLPP_CACHE_HIT_MS as a hit. If AI Functions bypass the cache, the repeat
     is no faster than the first call; if they use it but this network is
     slow, the repeat is faster but still over the threshold.

Each probe uses a fresh run tag in the prompt, the way the app does per run,
so earlier rehearsals cannot make it look like a hit. Costs six small calls.
"""

from __future__ import annotations

import os
import statistics
import sys
import time
import uuid
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aidpair.classify import SYSTEM  # noqa: E402
from aidpair.config import env_file, settings  # noqa: E402
from aidpair.db import query  # noqa: E402
from aidpair.llm import remote, route  # noqa: E402

MSG = "Is my flight cancelled because of the snow?"   # a real storm message, no placeholders


def gateway(prompt: str) -> tuple[int, int, str | None]:
    s = settings()
    base, name = route("classify", s.enrich_model)
    key = getattr(s, "classify_api_key", "") or s.model_api_key
    headers = {"Authorization": f"Bearer {key}"}
    if s.model_cache_strategy:
        headers["X-cb-cache"] = s.model_cache_strategy
    t = time.time()
    r = httpx.post(f"{base.rstrip('/')}/chat/completions", headers=headers, timeout=120, json={
        "model": name, "temperature": 0, "max_tokens": 500,
        "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": MSG}]})
    return r.status_code, int((time.time() - t) * 1000), r.headers.get("x-cache")


def sqlpp(prompt: str) -> int:
    t = time.time()
    query('SELECT RAW default:ai_completion({"system_prompt": $p, "user_prompt": $m, '
          '"temperature": 0, "max_tokens": 500})[0].response', p=prompt, m=MSG)
    return int((time.time() - t) * 1000)


def main() -> None:
    s = settings()
    print("A. Settings")
    print(f"   env file            {env_file()}  (AIDP_ENV={os.environ.get('AIDP_ENV', '')!r})")
    print(f"   CLASSIFY_VIA        {s.classify_via}")
    print(f"   CACHE_PER_RUN       {s.cache_per_run}")
    print(f"   MODEL_CACHE_STRATEGY {s.model_cache_strategy or '(blank: deployment default)'}")
    print(f"   SQLPP_CACHE_HIT_MS  {s.sqlpp_cache_hit_ms}")
    if not remote():
        raise SystemExit("\nThis is the local setup. Run it with AIDP_ENV=capella on the "
                         "machine that presents.")

    print("\nB. Gateway, direct (the backend path)")
    p = SYSTEM + f"\n\nRun probe-{uuid.uuid4().hex[:8]}."
    first = gateway(p)
    time.sleep(2)
    second = gateway(p)
    for label, (code, ms, xc) in (("first ", first), ("repeat", second)):
        print(f"   {label}  HTTP {code}  {ms:5d} ms  x-cache: {xc or '(none)'}")
    gateway_hits = bool(second[2] and "hit" in second[2].lower())

    print("\nC. SQL++ ai_completion, timed from this machine (the sqlpp path)")
    rtt = [_timed_select() for _ in range(3)]
    p2 = SYSTEM + f"\n\nRun probe-{uuid.uuid4().hex[:8]}."
    try:
        s_first = sqlpp(p2)
    except Exception as e:
        if "query_external_access" in str(e):
            print("   ai_completion exists, but the database user lacks the Query External")
            print("   Access role, so every call is refused. Add the role to CB_USER in Capella")
            print("   (Cluster -> Settings -> Database Access), wait a minute, run this again.")
            return
        if "Invalid function" not in str(e) and "3000" not in str(e):
            raise
        print("   ai_completion is not available on this cluster: AI Functions are not")
        print("   enabled, or not bound to a model (Capella UI: AI Data Plane -> AI Functions).")
        print("\nVerdict")
        print("   The gateway caches" + (" (a direct repeat came back x-cache: HIT)."
                                          if gateway_hits else "? No: no x-cache: HIT on a repeat."))
        print("   With CLASSIFY_VIA=backend the Storm tab shows those hits. The sqlpp path")
        print("   cannot be checked until AI Functions are enabled; then run this again.")
        return
    time.sleep(2)
    s_repeat = sqlpp(p2)
    print(f"   plain SELECT        {statistics.median(rtt):5.0f} ms  (network + query overhead)")
    print(f"   ai_completion first {s_first:5d} ms")
    print(f"   ai_completion repeat{s_repeat:6d} ms  threshold {s.sqlpp_cache_hit_ms} ms")

    print("\nVerdict")
    if not gateway_hits:
        print("   The deployment did not cache a word-for-word repeat (no x-cache: HIT).")
        print("   Caching is off on the classify deployment, or not on its Standard strategy.")
        print("   Nothing in the app can show hits until it is: enable caching on the")
        print("   deployment, and leave MODEL_CACHE_STRATEGY blank (semantic is broken on sbx-27).")
        return
    print("   The gateway caches: a direct repeat came back x-cache: HIT, so the backend")
    print("   path (CLASSIFY_VIA=backend) counts real hits on the Storm tab.")
    print(f"   You are on the {s.classify_via} path. On the SQL++ path:")
    if s_repeat >= 0.6 * s_first:
        print("   Through SQL++, the repeat was no faster than the first call: AI Functions")
        print("   are not using the cache. That is the open dev-team question. Until it is")
        print("   answered, 0% is the honest figure on the sqlpp path; CLASSIFY_VIA=backend")
        print("   shows the cache working.")
    elif s_repeat >= s.sqlpp_cache_hit_ms:
        print(f"   Through SQL++ the repeat WAS a cache hit ({s_repeat} ms vs {s_first} ms), but")
        print(f"   this machine's round trip pushes it over the {s.sqlpp_cache_hit_ms} ms threshold,")
        print("   so the app counts it as a miss. Set SQLPP_CACHE_HIT_MS to about "
              f"{_suggest(s_repeat, s_first)} in .env.capella and restart.")
    else:
        print("   Through SQL++ the repeat was fast enough to count as a hit. If the Storm tab")
        print("   still shows 0%, send me this output.")


def _timed_select() -> int:
    t = time.time()
    query("SELECT RAW 1")
    return int((time.time() - t) * 1000)


def _suggest(hit_ms: int, miss_ms: int) -> int:
    """Halfway between a hit and a model call, rounded to 50 ms."""
    return int(round(((hit_ms + miss_ms) / 2) / 50) * 50)


if __name__ == "__main__":
    main()
