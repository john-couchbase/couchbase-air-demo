"""
A minimal MCP client over Streamable HTTP: initialize, list tools, call a tool.

Kept to httpx rather than the mcp SDK so it has no new dependency and its
behaviour is easy to read when a hosted endpoint answers in a way we did not
expect. It speaks JSON-RPC 2.0 by POST; the server may answer with plain JSON or
with an SSE stream, and may hand back an Mcp-Session-Id that later requests echo.
"""

from __future__ import annotations

import asyncio
import itertools
import json
from typing import Any

import httpx

PROTOCOL = "2025-03-26"


class MCPError(Exception):
    pass


def auth_headers(header: str, token: str) -> dict:
    """Authorization gets "Bearer " unless the token already names a scheme;
    any other header (x-api-key, ...) gets the token as is."""
    if not token:
        return {}
    if header.lower() == "authorization" and " " not in token:
        token = f"Bearer {token}"
    return {header: token}


class MCPClient:
    def __init__(self, url: str, headers: dict | None = None, timeout: float = 60.0) -> None:
        self.url = url
        self.headers = {"Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream", **(headers or {})}
        self.http = httpx.AsyncClient(timeout=timeout)
        self.session: str | None = None
        self.server: dict = {}
        self._ids = itertools.count(1)
        self._ready = False
        self._lock = asyncio.Lock()
        self._tools: list[dict] | None = None

    # ------------------------------------------------------------- transport
    async def _post(self, payload: dict) -> dict | None:
        h = dict(self.headers)
        if self.session:
            h["Mcp-Session-Id"] = self.session
        r = await self.http.post(self.url, json=payload, headers=h)
        if r.headers.get("mcp-session-id"):
            self.session = r.headers["mcp-session-id"]
        if r.status_code == 202 or not r.content:
            return None
        if r.status_code >= 400:
            raise MCPError(f"{payload.get('method')} -> HTTP {r.status_code}: {r.text[:300]}")
        if "text/event-stream" in r.headers.get("content-type", ""):
            # The answer is the SSE event whose JSON-RPC id matches ours.
            found = None
            for line in r.text.splitlines():
                if line.startswith("data:"):
                    try:
                        msg = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    if msg.get("id") == payload.get("id"):
                        found = msg
            if found is None:
                raise MCPError(f"{payload.get('method')}: no reply in the event stream")
            return found
        return r.json()

    async def _rpc(self, method: str, params: dict | None = None) -> Any:
        msg = await self._post({"jsonrpc": "2.0", "id": next(self._ids), "method": method,
                                "params": params or {}})
        if msg is None:
            raise MCPError(f"{method}: empty reply")
        if msg.get("error"):
            raise MCPError(f"{method}: {msg['error']}")
        return msg.get("result")

    # ------------------------------------------------------------------- API
    async def start(self) -> None:
        async with self._lock:
            if self._ready:
                return
            res = await self._rpc("initialize", {
                "protocolVersion": PROTOCOL, "capabilities": {},
                "clientInfo": {"name": "aidp-air", "version": "0.1"},
            })
            self.server = res or {}
            await self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
            self._ready = True

    async def tools(self) -> list[dict]:
        await self.start()
        if self._tools is None:
            out, cursor = [], None
            while True:
                res = await self._rpc("tools/list", {"cursor": cursor} if cursor else {})
                out += (res or {}).get("tools", [])
                cursor = (res or {}).get("nextCursor")
                if not cursor:
                    break
            self._tools = out
        return self._tools

    async def call(self, name: str, args: dict) -> tuple[str, bool]:
        """(text, is_error). Text parts are joined; anything else is JSON-encoded."""
        await self.start()
        res = await self._rpc("tools/call", {"name": name, "arguments": args}) or {}
        parts = []
        for c in res.get("content") or []:
            parts.append(c.get("text") if c.get("type") == "text" else json.dumps(c))
        if not parts and res.get("structuredContent") is not None:
            parts.append(json.dumps(res["structuredContent"]))
        return "\n".join(p for p in parts if p), bool(res.get("isError"))

    async def close(self) -> None:
        await self.http.aclose()


_clients: dict[str, MCPClient] = {}


def client(url: str, header: str, token: str) -> MCPClient:
    """One client (and MCP session) per endpoint for the life of the process."""
    if url not in _clients:
        _clients[url] = MCPClient(url, auth_headers(header, token))
    return _clients[url]


def reset(url: str) -> None:
    """Forget a session, e.g. after the server dropped it; the next call starts afresh."""
    _clients.pop(url, None)
