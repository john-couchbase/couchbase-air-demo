"""
Reproduce: default:ai_completion intermittently returns [{"response": ""}].

Seen on Capella sbx-27 with ai_completion bound to Amazon Nova Micro. With the
classification prompt below, a share of calls come back with an empty string
instead of the model's answer. It depends on the message: TRIGGER (below)
failed 7 of 20 and 3 of 10 in two runs; four other storm messages failed 0 of
20. It happens with messages that have never been sent before (each carries a
random tag), so the Model Service cache is not involved. The same prompt and messages sent straight to the gateway's
/v1/chat/completions never come back empty, and short prompts through
ai_completion never did either (0 of over 80). Each empty reply's query
request ID is printed, so it can be found in the Query service logs.

The script runs three groups of N calls (default 20). Every message carries a
fresh random tag, so nothing is cached beforehand:

  A. SQL++ ai_completion, classification prompt, TRIGGER   - empties expected
  B. Gateway directly, same prompt and messages             - control, 0 expected
  C. SQL++ ai_completion, classification prompt, OTHERS     - for comparison
  D. SQL++ ai_completion, a one-line prompt, TRIGGER        - control, 0 expected

Needs only the Couchbase Python SDK and httpx:

    pip install couchbase httpx

Settings come from the environment (no secrets in this file):

    CB_CONN         couchbases://cb.<id>.<domain>
    CB_USER         database user. Needs the Query External Access role, or
                    every ai_completion call fails with missing_role.
    CB_PASS
    CB_CERT_PATH    optional; the cluster CA, if the SDK's bundled one is not enough
    MODEL_BASE_URL  the Model Service gateway, ending in /v1 (for group B)
    MODEL_API_KEY   a key for that gateway
    MODEL_NAME      the model ai_completion is bound to (default amazon.nova-micro-v1:0)
    MAX_TOKENS      optional, default 220. The cause: at 120, 12 of 15 calls came back
                    empty; at 220, 7 of 15; at 500 and 1000, none. Replies that did come
                    back at 120 were cut off after about 25 tokens, though a full answer
                    is about 40 and fits in 120 when the gateway is called directly.

    python repro_ai_completion_empty.py [N]
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
import uuid
from datetime import timedelta

import httpx
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions, QueryOptions

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
MODEL = os.environ.get("MODEL_NAME", "amazon.nova-micro-v1:0")
# 220 is what the demo sent when this was found. Set MAX_TOKENS=500 to see it go:
# at 500 no call came back empty.
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "220"))

# The prompt the AIDP Air demo classifies with, verbatim.
CLASSIFY_PROMPT = (
    "You classify messages sent to AIDP Air during a winter storm at Chicago O'Hare.\n"
    'Return exactly one JSON object with these keys and nothing else, no prose, no code fence:\n'
    '{"intent": "status" | "rebook" | "refund" | "hotel" | "baggage" | "complaint" | "special_assistance" | "other",\n'
    ' "urgency": 1-5,\n'
    ' "sentiment": "calm" | "frustrated" | "angry" | "distressed",\n'
    ' "needs": a list drawn only from "minor", "mobility", "medical", "deadline", "family",\n'
    '          "animal", "connection", "documents", "none",\n'
    ' "language": the message\'s language as a two-letter code,\n'
    ' "summary": a string}\n'
    '\n'
    'urgency, judged by consequence, not by tone:\n'
    '1 = general question unrelated to the storm\n'
    '2 = asking for information or a refund; nothing is at stake today\n'
    '3 = needs rebooking, a hotel, a bag or help; the ordinary storm case, including\n'
    '    meetings, connections, children travelling with a parent, and angry customers.\n'
    '    Wanting to fly today, tonight, tomorrow morning or "ASAP" is still 3.\n'
    '4 = a specific, serious consequence if not solved today: a funeral, surgery,\n'
    '    a once-only event, a job shift, a lost trip, a document or medicine they need\n'
    '5 = safety or health right now, an unaccompanied child, or a person who cannot\n'
    '    help themselves\n'
    '\n'
    'Examples:\n'
    '"Is my flight cancelled?" -> status, 2, ["none"]\n'
    '"Cancelled, I need to get there today, what are my options?" -> rebook, 3, ["none"]\n'
    '"Can I be rebooked for tomorrow morning? ASAP please" -> rebook, 3, ["none"]\n'
    '"Cancelled, rebook me tomorrow, I have a meeting" -> rebook, 3, ["none"]\n'
    '"My mother\'s funeral is tomorrow at 10am" -> rebook, 4, ["deadline", "family"]\n'
    '"Stranded overnight, need hotel and meal vouchers" -> hotel, 3, ["none"]\n'
    '"My bag was on the cancelled flight, where is it? ASAP" -> baggage, 3, ["none"]\n'
    '"My passport is in my checked bag and I fly abroad tomorrow" -> baggage, 4, ["documents"]\n'
    '"Worst airline ever, two hours on hold" -> complaint, 3, ["none"]\n'
    '"Travelling with my two kids" -> 3, ["family"]\n'
    '"My insulin is in my checked bag and I need it tonight" -> baggage, 5, ["medical"]\n'
    '"I use a wheelchair and nobody has come to help" -> special_assistance, 5, ["mobility"]\n'
    '"My 10 year old is flying alone and her flight is cancelled" -> status, 5, ["minor"]\n'
    '"My son is autistic and overwhelmed by the crowd, is there a quiet place?" -> special_assistance, 4, ["medical", "family"]\n'
    '"The new flight has no room for my service dog" -> special_assistance, 4, ["animal", "mobility"]\n'
    '"Third cancellation this year, let me speak to someone who can decide" -> complaint, 3, ["none"], angry\n'
    '\n'
    'needs: only circumstances the passenger states outright; never infer them.\n'
    'Otherwise ["none"]. What each one covers:\n'
    '  minor    = a child travelling without a parent; a child with a parent is "family"\n'
    '  medical  = an illness, disability, pregnancy or condition, including autism or oxygen\n'
    '  mobility = a wheelchair, difficulty walking, or a service animal\n'
    'sentiment: "angry" when they blame the airline, cite repeated failures or demand\n'
    'someone with authority; "frustrated" when annoyed but simply asking for help.\n'
    'summary: at most 12 words, in English, with no names, flight numbers or cities.'
)

SHORT_PROMPT = "You answer in one short sentence."

# The message that fails most often.
TRIGGER = "Is AD {n} to Fort Wayne still going? I have a meeting tomorrow morning."
# Messages that did not fail in testing.
OTHERS = [
    "My flight AD {n} was cancelled. Can you rebook me on the next flight to Denver?",
    "Can I get my luggage back? I'm going home, AD {n} is cancelled.",
    "How do I get my money back for AD {n}? Traveling with my elderly mother.",
    "Stranded overnight after AD {n} was cancelled. Do I get a hotel?",
]

STATEMENT = """SELECT default:ai_completion({
    "system_prompt": $system,
    "user_prompt":   $user,
    "temperature":   0,
    "max_tokens":    $max_tokens
}) AS out"""


def env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        sys.exit(f"Set {name} (see the top of this file).")
    return v


def connect() -> Cluster:
    cert = os.environ.get("CB_CERT_PATH")
    auth = (PasswordAuthenticator(env("CB_USER"), env("CB_PASS"), cert_path=cert) if cert
            else PasswordAuthenticator(env("CB_USER"), env("CB_PASS")))
    opts = ClusterOptions(auth)
    opts.apply_profile("wan_development")
    c = Cluster(env("CB_CONN"), opts)
    c.wait_until_ready(timedelta(seconds=30))
    return c


def fresh_messages(templates: list[str]) -> list[str]:
    return [random.choice(templates).format(n=random.randint(100, 9999))
            + f" [{uuid.uuid4().hex[:6]}]" for _ in range(N)]


def via_sqlpp(c: Cluster, system: str, user: str) -> tuple[str | None, float, str]:
    t = time.time()
    res = c.query(STATEMENT, QueryOptions(named_parameters={
        "system": system, "user": user, "max_tokens": MAX_TOKENS}))
    rows = list(res.rows())
    out = rows[0]["out"]
    text = out[0].get("response") if isinstance(out, list) and out else None
    return text, time.time() - t, res.metadata().request_id()


def direct(http: httpx.Client, system: str, user: str) -> tuple[str, float, str]:
    t = time.time()
    r = http.post("/chat/completions", json={
        "model": MODEL, "max_tokens": MAX_TOKENS, "temperature": 0,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}]})
    r.raise_for_status()
    j = r.json()
    return j["choices"][0]["message"].get("content") or "", time.time() - t, j.get("id", "")


def run(label: str, fn, system: str, messages: list[str]) -> int:
    print(f"\n{label}")
    empty = 0
    for i, m in enumerate(messages, 1):
        text, secs, rid = fn(system, m)
        if text == "":
            empty += 1
            print(f"  {i:>2}  {secs:4.1f}s  EMPTY   request_id={rid}  message={json.dumps(m)}")
        elif text is None:
            print(f"  {i:>2}  {secs:4.1f}s  NO RESPONSE FIELD  request_id={rid}")
        else:
            print(f"  {i:>2}  {secs:4.1f}s  ok      {json.dumps(text)[:70]}")
    print(f"  -> {empty}/{len(messages)} empty")
    return empty


def main() -> None:
    c = connect()
    http = httpx.Client(base_url=env("MODEL_BASE_URL").rstrip("/"), timeout=60,
                        headers={"Authorization": f"Bearer {env('MODEL_API_KEY')}"})
    print(f"model: {MODEL}   N: {N}   max_tokens: {MAX_TOKENS}   "
          f"classification prompt: {len(CLASSIFY_PROMPT)} chars")
    print("statement:\n" + STATEMENT)

    msgs = fresh_messages([TRIGGER])
    a = run("A. SQL++ ai_completion, classification prompt, TRIGGER",
            lambda s, m: via_sqlpp(c, s, m), CLASSIFY_PROMPT, msgs)
    b = run("B. Gateway directly, same prompt and messages",
            lambda s, m: direct(http, s, m), CLASSIFY_PROMPT, msgs)
    cc = run("C. SQL++ ai_completion, classification prompt, OTHERS",
             lambda s, m: via_sqlpp(c, s, m), CLASSIFY_PROMPT, fresh_messages(OTHERS))
    d = run("D. SQL++ ai_completion, one-line prompt, TRIGGER",
            lambda s, m: via_sqlpp(c, s, m), SHORT_PROMPT, fresh_messages([TRIGGER]))

    print(f"\nSummary: A {a}/{N} empty, B {b}/{N} empty, C {cc}/{N} empty, D {d}/{N} empty")
    if a and not b:
        print("REPRODUCED: ai_completion returned \"\" where the gateway itself answered.")
    elif not a:
        print(f"Not reproduced at max_tokens {MAX_TOKENS}. At 220 or below it shows up "
              "within 20 calls; above that, try a larger N (e.g. 50) to be sure.")


if __name__ == "__main__":
    main()
