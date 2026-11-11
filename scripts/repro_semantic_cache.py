"""
Test the Model Service cache: does Standard work, and does Semantic?

Every run uses a fresh random case number, so nothing is cached beforehand.
For each way of asking (no X-cb-cache header, then X-cb-cache: semantic, plus
any values in CACHE_VALUES) it sends, to /v1/chat/completions:

  seed        a new message
  repeat      the same message again, word for word
  one word    the message with one word changed ("can" -> "could")
  reworded    the same request in different words

and reports the x-cache response header of each. Then it stores a seed with
the semantic header and checks again after 10, 30 and 60 seconds, in case
semantic entries are written in the background.

What working looks like:
  Standard: repeat HIT; one word and reworded miss.
  Semantic: repeat, one word and reworded all HIT.

Observed on sbx-27 (2026-10-06): Standard works. With X-cb-cache: semantic,
nothing is ever stored or matched, not even an exact repeat after 60 seconds.
Any other value behaves like Standard.

Needs only httpx (pip install httpx). Settings come from the environment:

    MODEL_BASE_URL  the Model Service gateway, ending in /v1
    MODEL_API_KEY   a key for that gateway
    MODEL_NAME      a deployment with caching enabled (default amazon.nova-micro-v1:0)
    CACHE_VALUES    optional, comma separated: more X-cb-cache values to try

    python repro_semantic_cache.py
"""

from __future__ import annotations

import os
import random
import sys
import time

import httpx

MODEL = os.environ.get("MODEL_NAME", "amazon.nova-micro-v1:0")
SYSTEM = "Classify the passenger message in one word."


def env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        sys.exit(f"Set {name} (see the top of this file).")
    return v


def messages(n: int) -> dict[str, str]:
    return {
        "seed": f"My flight to Denver was cancelled, case {n}, can you rebook me tonight?",
        "repeat": f"My flight to Denver was cancelled, case {n}, can you rebook me tonight?",
        "one word": f"My flight to Denver was cancelled, case {n}, could you rebook me tonight?",
        "reworded": f"Case {n}: Denver flight got cancelled, please put me on another one tonight",
    }


def call(http: httpx.Client, text: str, value: str | None) -> tuple[str, float, str]:
    headers = {"X-cb-cache": value} if value else {}
    t = time.time()
    r = http.post("/chat/completions", headers=headers, json={
        "model": MODEL, "max_tokens": 10, "temperature": 0,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": text}]})
    r.raise_for_status()
    return r.headers.get("x-cache") or "miss", time.time() - t, r.json().get("id", "")


def run(http: httpx.Client, value: str | None) -> dict[str, str]:
    label = f"X-cb-cache: {value}" if value else "no X-cb-cache header"
    print(f"\n{label}")
    got = {}
    for i, (step, text) in enumerate(messages(random.randint(10000, 99999)).items()):
        verdict, secs, rid = call(http, text, value)
        got[step] = verdict
        print(f"  {step:<9} {verdict:<5} {secs:4.1f}s  id={rid}")
        if i == 0:
            time.sleep(4)   # let the seed be stored before asking again
    return got


def delayed(http: httpx.Client) -> list[str]:
    print("\nX-cb-cache: semantic, checked after a delay")
    m = messages(random.randint(10000, 99999))
    print(f"  seed      {call(http, m['seed'], 'semantic')[0]}")
    t0, seen = time.time(), []
    for wait in (10, 30, 60):
        time.sleep(max(0.0, wait - (time.time() - t0)))
        rep = call(http, m["repeat"], "semantic")[0]
        one = call(http, m["one word"], "semantic")[0]
        seen += [rep, one]
        print(f"  +{wait:>2}s      repeat {rep:<5} one word {one}")
    return seen


def main() -> None:
    http = httpx.Client(base_url=env("MODEL_BASE_URL").rstrip("/"), timeout=60,
                        headers={"Authorization": f"Bearer {env('MODEL_API_KEY')}"})
    extra = [v.strip() for v in os.environ.get("CACHE_VALUES", "").split(",") if v.strip()]
    print(f"gateway: {env('MODEL_BASE_URL')}\nmodel:   {MODEL}")

    standard = run(http, None)
    semantic = run(http, "semantic")
    for v in extra:
        run(http, v)
    later = delayed(http)

    def hit(v: str) -> bool:
        return "hit" in v.lower()

    std_ok = hit(standard["repeat"])
    sem_ok = hit(semantic["one word"]) or hit(semantic["reworded"])
    sem_any = any(hit(v) for v in semantic.values()) or any(hit(v) for v in later)
    print("\nStandard cache:", "WORKS (exact repeat hit)" if std_ok else "NOT WORKING (exact repeat missed)")
    if sem_ok:
        print("Semantic cache: WORKS (a changed or reworded message hit)")
    elif sem_any:
        print("Semantic cache: PARTLY (some hits, but not on changed or reworded messages)")
    else:
        print("Semantic cache: NOT WORKING (no request with X-cb-cache: semantic ever hit)")


if __name__ == "__main__":
    main()
