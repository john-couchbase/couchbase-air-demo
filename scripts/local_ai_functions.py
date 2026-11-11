"""
LOCAL ONLY. Stand in for Capella's AI Functions on a laptop cluster, so the
real classification statement runs unmodified in the Query service.

    .venv/bin/python scripts/local_ai_functions.py [--remove]
    .venv/bin/python scripts/local_ai_functions.py --gateway [--skip-cache]

Creates a global SQL++ UDF `default:ai_completion` that calls LM Studio with
CURL() and returns what the real function returns: [{"response": "..."}].
With it in place, CLASSIFY_VIA=sqlpp exercises the exact statement the sandbox
will run.

It refuses to run against couchbases:// (Capella), where it would shadow the
real AI Function.

--gateway points it at the local Model Service stand-in (aidpair/gateway.py,
port 8020) instead of LM Studio, for the sandbox-like local mode, and sends the
configured classify model name, which the gateway maps. --skip-cache makes it
call the gateway's /nocache path: whether AI Functions use the deployment's
cache on sbx-27 is the open dev-team question, so both are available.

It calls Mistral 7B rather than the Llama 3.1 the backend path uses. Local
Llama answers in tool-call format ('{"name": ..., "parameters": ...}') whenever
no JSON schema is sent, an LM Studio template quirk that Nova does not share.
Mistral answers plain JSON when asked, so no schema is sent at all, exactly as
the real function would not send one. Load it first:
    lms load mistralai/mistral-7b-instruct-v0.3 --parallel 16 --context-length 32768
"""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aidpair.config import settings  # noqa: E402
from aidpair.db import query  # noqa: E402

LMS = "http://host.docker.internal:1234/"   # LM Studio, as seen from inside Docker
GATEWAY = "http://host.docker.internal:8020/"   # the Model Service stand-in
SQLPP_MODEL = "mistralai/mistral-7b-instruct-v0.3"

UDF = """CREATE OR REPLACE FUNCTION ai_completion(o) {{
  [ {{ "response": CURL("{url}", {{
        "request": "POST",
        "header": ["Content-Type: application/json"],
        "data": ENCODE_JSON({{
          "model": "{{model}}",
          "temperature": IFMISSINGORNULL(o.temperature, 0),
          "max_tokens": IFMISSINGORNULL(o.max_tokens, 400),
          "messages": [{{"role": "system", "content": o.system_prompt}},
                       {{"role": "user", "content": o.user_prompt}}]
        }})
      }}).choices[0].message.content }} ]
}}"""


def main() -> None:
    s = settings()
    if s.cb_conn.startswith("couchbases://"):
        raise SystemExit("Refusing: this is a Capella cluster, where the real AI Function lives.")
    if "--remove" in sys.argv:
        query("DROP FUNCTION ai_completion IF EXISTS")
        print("removed default:ai_completion")
        return
    host = s.cb_conn.split("://", 1)[1].split("/")[0].split(",")[0]
    httpx.post(f"http://{host}:8091/settings/querySettings/curlWhitelist",
               auth=(s.cb_user, s.cb_pass),
               json={"all_access": False, "allowed_urls": [LMS, GATEWAY]}).raise_for_status()
    if "--gateway" in sys.argv:
        path = "nocache/v1" if "--skip-cache" in sys.argv else "v1"
        url, model = f"{GATEWAY}{path}/chat/completions", s.enrich_model
    else:
        url, model = f"{LMS}v1/chat/completions", SQLPP_MODEL
    query(UDF.format(url=url).replace("{model}", model))
    print(f"default:ai_completion -> {url} as {model}")
    r = query('SELECT RAW default:ai_completion({"system_prompt": '
              '"Return only the JSON object {\\"ok\\": true}.", '
              '"user_prompt": "Reply now.", "max_tokens": 20})[0].response')
    print("default:ai_completion ->", r)


if __name__ == "__main__":
    main()
