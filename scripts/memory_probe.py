"""
What does the Agent Memory endpoint speak? Tries a few likely shapes against
MEMORY_URL and prints what comes back, so the right MEMORY_BACKEND and paths can
be set. Read-only: GETs, and an MCP initialize (which changes nothing).

    AIDP_ENV=capella .venv/bin/python scripts/memory_probe.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aidpair.config import settings
from aidpair.mcp_client import auth_headers

s = settings()
base = s.memory_url.rstrip("/")
H = auth_headers(s.memory_auth_header, s.memory_token)
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": {"name": "aidp-air-probe", "version": "0"}}}
MCP_H = {**H, "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

print(f"MEMORY_URL {base}/\n")
with httpx.Client(timeout=20, follow_redirects=False) as h:
    def show(label: str, r: httpx.Response) -> None:
        loc = f" -> {r.headers['location']}" if r.headers.get("location") else ""
        body = r.text.replace("\n", " ")[:220]
        print(f"{r.status_code}  {label}{loc}\n     {r.headers.get('content-type', '')}  {body}\n")

    for path in ["", "/mcp", "/mcp/", "/sse"]:
        try:
            show(f"POST {path or '/'} (MCP initialize)", h.post(base + (path or "/"), json=INIT, headers=MCP_H))
        except Exception as e:  # noqa: BLE001
            print(f"ERR  POST {path}: {e}\n")
    for path in ["/", "/openapi.json", "/docs", "/health", "/v1", "/v1/memories", "/memories",
                 "/api/v1/memories"]:
        try:
            show(f"GET {path}", h.get(base + path, headers=H))
        except Exception as e:  # noqa: BLE001
            print(f"ERR  GET {path}: {e}\n")
