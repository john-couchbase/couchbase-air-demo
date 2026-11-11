"""
Check the MCP server, tool calling on the agent's model, and Agent Memory,
before setting AGENT_VIA=mcp or MEMORY_BACKEND=mcp|rest.

    AIDP_ENV=capella .venv/bin/python scripts/mcp_check.py

1. MCP_URL: connect, list every tool with its arguments, mark which the agent
   would be offered (read-only), and run one harmless query if a query tool exists.
2. The agent's model through the gateway: does it return tool_calls when given
   a tool? If not, AGENT_VIA=mcp cannot work on this model and falls back.
3. Agent Memory, when MEMORY_BACKEND is not "collection": list the memory
   server's tools (mcp) and try one recall.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aidpair import memory
from aidpair.agent import _openai_tools, read_only
from aidpair.config import settings
from aidpair.llm import chat_tools
from aidpair.mcp_client import MCPClient, auth_headers


def args_of(t: dict) -> str:
    sch = t.get("inputSchema") or {}
    req = set(sch.get("required") or [])
    return ", ".join(f"{k}{'*' if k in req else ''}" for k in (sch.get("properties") or {}))


async def list_server(label: str, url: str, header: str, token: str) -> tuple[MCPClient, list]:
    print(f"\n== {label}\n   {url}")
    c = MCPClient(url, auth_headers(header, token))
    await c.start()
    info = c.server.get("serverInfo") or {}
    print(f"   connected: {info.get('name', '?')} {info.get('version', '')}  "
          f"protocol {c.server.get('protocolVersion', '?')}  session {'yes' if c.session else 'no'}")
    tools = await c.tools()
    print(f"   {len(tools)} tools (* = required argument):")
    for t in tools:
        print(f"   {'R' if read_only(t['name']) else 'W'}  {t['name']}({args_of(t)})")
    return c, tools


async def main() -> int:
    s = settings()
    ok = True

    # 1. the MCP server
    if not s.mcp_url:
        print("MCP_URL is not set; skipping the MCP server")
    else:
        try:
            c, tools = await list_server("MCP server", s.mcp_url, s.mcp_auth_header, s.mcp_token)
            offered = [t["function"]["name"] for t in _openai_tools(tools)]
            print(f"   offered to the agent (MCP_TOOLS={s.mcp_tools}): {', '.join(offered) or 'NONE'}")
            ok &= bool(offered)
            q = next((t for t in tools if "query" in t["name"].lower() and read_only(t["name"])), None)
            if q:
                sch = q.get("inputSchema") or {}
                props = sch.get("properties") or {}
                key = next((k for k in (sch.get("required") or []) if
                            (props.get(k) or {}).get("type") == "string"), None) \
                    or next((k for k, v in props.items() if v.get("type") == "string"), None)
                if key:
                    stmt = "SELECT COUNT(*) AS n FROM `aidp-air`.`ops`.`flights`"
                    text, err = await c.call(q["name"], {key: stmt})
                    print(f"   try {q['name']}({key}=...): {'ERROR ' if err else ''}{text[:300]}")
                    ok &= not err
        except Exception as e:  # noqa: BLE001
            print(f"   FAILED: {str(e)[:500]}")
            ok = False

    # 2. tool calling on the agent's model
    print(f"\n== tool calling on the agent model ({s.agent_model_name or s.agent_model})")
    tool = [{"type": "function", "function": {
        "name": "get_flight_status", "description": "Status of an AIDP Air flight",
        "parameters": {"type": "object", "properties": {"flight_no": {"type": "string"}},
                       "required": ["flight_no"]}}}]
    try:
        msg, r = await chat_tools("agent", s.agent_model, [
            {"role": "user", "content": "Is flight AD 1252 cancelled? Use the tool."}], tool,
            max_tokens=200, temperature=None)
        calls = msg.get("tool_calls") or []
        if calls:
            print(f"   ok: {calls[0]['function']['name']}({calls[0]['function'].get('arguments')}) "
                  f"in {r.latency_ms} ms")
        else:
            print(f"   NO tool call; the model answered in text: {r.text[:200]!r}")
            ok = False
    except Exception as e:  # noqa: BLE001
        print(f"   FAILED: {str(e)[:400]}")
        ok = False

    # 3. Agent Memory
    mb = memory.backend()
    print(f"\n== Agent Memory (MEMORY_BACKEND={mb})")
    if mb == "collection":
        print("   the ops.memory collection; nothing to check here")
    elif mb == "ams":
        try:
            a = memory.ams()
            print(f"   {a.base}\n   health: {await a.health()}")
            uid = "aidp-air-check"
            r = await a.add_facts(uid, "connectivity check", memory.DEMO,
                                  ["Check: prefers a window seat and app notifications."], "check")
            print(f"   write: accepted {r.get('accepted_count')}, rejected {r.get('rejected_count')}")
            hits = await a.search(uid, "seat preference")
            print(f"   search: {len(hits)} block(s): {[memory._block_text(b)[:80] for b in hits][:3]}")
            await a.delete_session(uid, memory.DEMO)
            m = await memory.recall({"id": "pax_00002", "name": "test"}, "storm cancellation")
            print(f"   recall pax_00002 ({m['source']}): {json.dumps(m['notes'])[:300]}"
                  + ("" if m["notes"] else "  (empty until seed-memory has run)"))
            ok &= m["source"] == "ams"
        except Exception as e:  # noqa: BLE001
            print(f"   FAILED: {str(e)[:500]}")
            ok = False
    else:
        try:
            await list_server("Agent Memory server", s.memory_url, s.memory_auth_header,
                              s.memory_token)
            if not (s.memory_recall_tool and s.memory_write_tool):
                print("   MEMORY_RECALL_TOOL / MEMORY_WRITE_TOOL not set yet")
                ok = False
        except Exception as e:  # noqa: BLE001
            print(f"   FAILED: {str(e)[:500]}")
            ok = False

    print("\nall good" if ok else "\nfix the lines above, then rerun")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
