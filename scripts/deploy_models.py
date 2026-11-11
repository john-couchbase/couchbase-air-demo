"""
Deploy, inspect, switch off and delete the demo's models, through the Capella
v4 Management API. Rerun it after every sandbox scrub.

    .venv/bin/python scripts/deploy_models.py [deploy|status|off|on|delete] [--dry-run]

deploy  (default) For each entry in infra/models.json: find it by name or
        create it, apply its update (caching), wait until it has finished
        deploying, read its endpoint, then create one model API key and write
        everything the app needs into .env. Idempotent: an existing model is
        reused, and an existing MODEL_API_KEY is kept.
status  Print each model's status and endpoint.
off/on  Switch every demo model off or on (DELETE / POST activationState).
        Off between demos, so an idle sandbox is not billed.
delete  Delete every demo model. Asks first.

--dry-run prints every request it would make and changes nothing. It needs no
credentials, which is how this was written and checked on a machine that
cannot reach the sandbox.

Needs CAPELLA_API_KEY (a management API key) and CAPELLA_ORG_ID in .env.
The model API key it creates is a different thing: that one calls the models.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "infra" / "models.json").read_text())
_ENV_NAME = os.environ.get("AIDP_ENV", "").strip()
ENV_PATH = ROOT / (f".env.{_ENV_NAME}" if _ENV_NAME else ".env")

ENV = {**dotenv_values(ENV_PATH), **os.environ}
API = ENV.get("CAPELLA_API_BASE", "https://cloudapi.cloud.couchbase.com").rstrip("/")
ORG = ENV.get("CAPELLA_ORG_ID", "$CAPELLA_ORG_ID")
KEY = ENV.get("CAPELLA_API_KEY", "")
DRY = "--dry-run" in sys.argv
BASE = f"{API}/v4/organizations/{ORG}/aiServices/models"

POLL_S = 15
POLL_LIMIT_S = 45 * 60


# ------------------------------------------------------------------- http
def call(method: str, url: str, body: dict | None = None) -> dict | list | None:
    if DRY:
        print(f"  {method} {url}" + (f"\n    {json.dumps(body)}" if body else ""))
        return None
    r = httpx.request(method, url, json=body, timeout=60,
                      headers={"Authorization": f"Bearer {KEY}"})
    if r.status_code >= 400:
        raise SystemExit(f"{method} {url} -> {r.status_code}\n{r.text[:800]}")
    return r.json() if r.content else {}


def items(resp) -> list[dict]:
    """The list endpoint's envelope is not documented in what we were given;
    accept a bare list or the usual {"data": [...]}."""
    if isinstance(resp, list):
        return resp
    if isinstance(resp, dict):
        for k in ("data", "models", "items"):
            if isinstance(resp.get(k), list):
                return resp[k]
    return []


def first(d, *keys):
    if isinstance(d, str):
        return d
    for k in keys:
        if isinstance(d, dict) and d.get(k):
            return d[k]
    return None


# ------------------------------------------------------------------ steps
def find(name: str) -> dict | None:
    for m in items(call("GET", BASE)):
        if m.get("name") == name:
            return m
    return None


def ensure(entry: dict) -> str:
    name = entry["create"]["name"]
    existing = None if DRY else find(name)
    if existing:
        mid = first(existing, "id", "modelId")
        print(f"{name}: exists ({mid}, {existing.get('status')})")
    else:
        print(f"{name}: creating")
        resp = call("POST", BASE, entry["create"])
        mid = first(resp, "id", "modelId") or f"${entry['job'].upper()}_MODEL_ID"
    if entry.get("update"):
        call("PUT", f"{BASE}/{mid}", entry["update"])
    return mid


def wait(mid: str, name: str) -> None:
    if DRY:
        print(f"  (poll GET {BASE}/{mid} every {POLL_S}s until status != deploying)")
        return
    t0 = time.time()
    while True:
        m = call("GET", f"{BASE}/{mid}")
        status = (m or {}).get("status", "")
        if status.lower() != "deploying":
            print(f"{name}: {status}")
            return
        if time.time() - t0 > POLL_LIMIT_S:
            raise SystemExit(f"{name}: still deploying after {POLL_LIMIT_S // 60} minutes")
        print(f"{name}: deploying ({int(time.time() - t0)}s)")
        time.sleep(POLL_S)


def endpoint(mid: str) -> str:
    resp = call("GET", f"{BASE}/{mid}/connectionString")
    return first(resp, "connectionString", "url", "endpoint") or f"$ENDPOINT_OF_{mid}"


def api_key() -> str:
    if ENV.get("MODEL_API_KEY") and ENV["MODEL_API_KEY"] != "lm-studio":
        print(f"model API key: keeping the one in {ENV_PATH.name}")
        return ENV["MODEL_API_KEY"]
    resp = call("POST", f"{BASE}/apiKeys", {
        "name": SPEC["api_key_name"], "expiry": 180, "allowedModels": [],
        "region": SPEC["region"],
    })
    key = first(resp, "apiKey", "key", "token", "secret")
    if not key and not DRY:
        print("model API key: created, but no key field recognised in the response:")
        print(json.dumps(resp, indent=1)[:800])
    return key or "$MODEL_API_KEY"


def write_env(values: dict[str, str]) -> None:
    if DRY:
        print(f"\nwould write to {ENV_PATH.name}:")
        for k, v in values.items():
            print(f"  {k}={v}")
        return
    text = ENV_PATH.read_text() if ENV_PATH.exists() else ""
    for k, v in values.items():
        line = f"{k}={v}"
        if re.search(rf"^{k}=.*$", text, re.M):
            text = re.sub(rf"^{k}=.*$", line, text, flags=re.M)
        else:
            text += ("" if text.endswith("\n") else "\n") + line + "\n"
    ENV_PATH.write_text(text)
    print(f"\nwrote {len(values)} settings to {ENV_PATH.name}")


# --------------------------------------------------------------- commands
def deploy() -> None:
    out: dict[str, str] = {"MODEL_BACKEND": "model_service"}
    for e in SPEC["models"]:
        mid = ensure(e)
        wait(mid, e["create"]["name"])
        job = e["job"].upper()
        out[f"{job}_MODEL_ID"] = mid
        out[f"{job}_BASE_URL"] = endpoint(mid)
        # The name the endpoint expects in the request's "model" field. In the
        # AIDP Financial deployment it was the catalog name; confirm here.
        out[f"{job}_MODEL_NAME"] = e["create"]["catalogModelName"]
    out["MODEL_API_KEY"] = api_key()
    write_env(out)


def status() -> None:
    for e in SPEC["models"]:
        name = e["create"]["name"]
        m = None if DRY else find(name)
        if DRY:
            call("GET", BASE)
            continue
        if not m:
            print(f"{name}: not deployed")
            continue
        mid = first(m, "id", "modelId")
        print(f"{name}: {m.get('status')}  {mid}  {endpoint(mid)}")


def activation(on: bool) -> None:
    for e in SPEC["models"]:
        name = e["create"]["name"]
        m = None if DRY else find(name)
        mid = first(m, "id", "modelId") if m else f"${e['job'].upper()}_MODEL_ID"
        if m is None and not DRY:
            print(f"{name}: not deployed")
            continue
        call("POST" if on else "DELETE", f"{BASE}/{mid}/activationState")
        print(f"{name}: {'on' if on else 'off'}")


def delete() -> None:
    if not DRY and input("Delete every demo model? Type 'delete' to confirm: ") != "delete":
        return
    for e in SPEC["models"]:
        name = e["create"]["name"]
        m = None if DRY else find(name)
        if m is None and not DRY:
            continue
        mid = first(m, "id", "modelId") if m else f"${e['job'].upper()}_MODEL_ID"
        call("DELETE", f"{BASE}/{mid}")
        print(f"{name}: deleted")


def main() -> None:
    cmd = next((a for a in sys.argv[1:] if not a.startswith("--")), "deploy")
    if not DRY and (not KEY or ORG.startswith("$")):
        raise SystemExit(f"Set CAPELLA_API_KEY and CAPELLA_ORG_ID in {ENV_PATH.name}, or use --dry-run.")
    {"deploy": deploy, "status": status, "off": lambda: activation(False),
     "on": lambda: activation(True), "delete": delete}[cmd]()


if __name__ == "__main__":
    main()
