"""
Settings, read once from the environment.

Every endpoint the demo talks to is named here, so moving from the laptop to
the sandbox is a change of settings file and nothing else. Locally the "Bedrock"
models are LM Studio stand-ins; on sbx-27 they are real Model Service endpoints.

AIDP_ENV picks the file: AIDP_ENV=local reads .env.local, AIDP_ENV=capella
reads .env.capella. Unset, it reads .env.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def env_file() -> str:
    name = os.environ.get("AIDP_ENV", "").strip()
    if not name:
        return ".env"
    path = f".env.{name}"
    # A typo must not fall through to the defaults, which point at a laptop.
    if not os.path.exists(path):
        raise SystemExit(f"AIDP_ENV={name}, but {path} does not exist")
    return path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=env_file(), extra="ignore")

    cb_conn: str = "couchbase://localhost"
    cb_user: str = "Administrator"
    cb_pass: str = ""
    cb_bucket: str = "aidp-air"
    cb_scope: str = "ops"
    # Only for couchbases:// when the SDK's bundled Capella CA is not enough
    # (AIDP Financial needed one for agentc; the Python SDK alone usually does not).
    cb_cert_path: str = ""

    # OpenAI-compatible endpoint serving the models. LM Studio locally; the
    # AI Data Plane Model Service gateway on the sandbox.
    model_base_url: str = "http://localhost:1234/v1"
    model_api_key: str = "lm-studio"

    # "local" means every model in the catalog is served by a local stand-in
    # and every figure derived from it is labelled as such in the UI.
    model_backend: str = "local"

    # Per-job endpoints on the Model Service, written by scripts/deploy_models.py.
    # Each deployed model has its own connection string. Blank falls back to
    # model_base_url, which is the local case.
    # A job's API key is only needed when its endpoint has its own; blank falls
    # back to model_api_key.
    classify_base_url: str = ""
    classify_model_name: str = ""
    classify_api_key: str = ""
    agent_base_url: str = ""
    agent_model_name: str = ""
    agent_api_key: str = ""
    embed_base_url: str = ""
    embed_model_name: str = ""
    embed_api_key: str = ""

    # How messages are classified. "backend": the app calls the model per
    # message, which sees every token count and cache verdict. "sqlpp": the
    # Query service runs CLASSIFY_SQLPP with the AI Function, which is the real
    # in-database path; token counts are then estimated, see classify.py.
    classify_via: str = "backend"
    # The sqlpp path: messages per statement, and statements in flight at once.
    sqlpp_batch: int = 1
    sqlpp_parallel: int = 32
    # SQL++ does not return the cache verdict, so on the sqlpp path a statement
    # that finishes this fast is counted as a cache hit, marked estimated. On
    # us-east-2 with Nova 2 Lite, hits took about 110-200 ms, model calls 500+.
    sqlpp_cache_hit_ms: int = 300
    # The Model Service's cache outlives the demo's Reset, so a rehearsed storm
    # ends up answered entirely from it. With this on, each Reset tags the
    # classify prompt with a new run id; the gateway keys on the system prompt,
    # so each run starts with an empty cache and repeats within it still hit.
    cache_per_run: bool = True

    # ------------------------------------------------------------ Agent Memory
    # Where the agent's long-term memory lives (see aidpair/memory.py):
    #   collection: `aidp-air`.`ops`.`memory`, the original behaviour.
    #   ams:        Capella's hosted AgentMemory service (REST). MEMORY_URL is its base
    #               (…/ams/<id>), MEMORY_TOKEN its key. Load history with seed_memory.py.
    #   mcp:        a memory service over MCP, with the tool names / argument templates
    #               below. Placeholders: {passenger_id} {name} {query} {note} {event} {namespace}.
    memory_backend: str = "collection"
    memory_namespace: str = "aidp-air"
    memory_url: str = ""
    memory_token: str = ""
    memory_auth_header: str = "Authorization"
    memory_recall_tool: str = ""
    memory_recall_args: str = '{"user_id": "{passenger_id}", "query": "{query}"}'
    memory_write_tool: str = ""
    memory_write_args: str = '{"user_id": "{passenger_id}", "content": "{note}"}'

    # --------------------------------------------------------------------- MCP
    # How the agent gets its context.
    #   prefetch: the app gathers booking, flight, options and memory with SQL++ and
    #             sends them in one request (the original behaviour).
    #   mcp:      the model is also given the MCP server's tools and looks up what it
    #             needs itself, in a loop of at most agent_max_steps model calls.
    #             Any MCP or tool-calling failure falls back to prefetch for that draft.
    agent_via: str = "prefetch"
    mcp_url: str = ""                    # Streamable HTTP endpoint of the MCP server
    mcp_token: str = ""
    mcp_auth_header: str = "Authorization"
    # Which of the server's tools the model is offered. "auto": every tool whose
    # name does not suggest a write (upsert, insert, replace, delete, create, drop,
    # update, ...), so writes stay behind human approval. Or a comma-separated list.
    mcp_tools: str = "auto"
    agent_max_steps: int = 6

    # Which catalog entries each job uses. Chosen per task, not per fleet.
    enrich_model: str = "amazon.nova-micro-v1:0"
    agent_model: str = "anthropic.claude-sonnet-5"
    embed_model: str = "text-embedding-nomic-embed-text-v1.5"

    # Local stand-ins for the catalog entries.
    local_small_model: str = "meta-llama-3.1-8b-instruct"
    local_frontier_model: str = "meta-llama-3.1-8b-instruct"

    enrich_concurrency: int = 16
    agent_concurrency: int = 8

    # Semantic cache: cosine similarity at or above this is a hit.
    cache_threshold: float = 0.93
    # X-cb-cache value sent to the Model Service ("semantic", "exact"). Blank
    # uses the deployment's own strategy, the only setting that fills the cache.
    model_cache_strategy: str = ""

    # Surge shape. Arrivals follow Beta(1.4, 3.6) over surge_seconds, which
    # peaks at about 2.3 x surge_size / surge_seconds per second. The default
    # peaks near 3/s: 15x the trickle, and about what one laptop GPU classifies
    # with the cache warm. The sandbox can run it several times larger.
    baseline_per_min: int = 12
    surge_size: int = 320
    surge_seconds: int = 240

    # The trickle never stops on its own, and every message it classifies can
    # land in the Model Service's semantic cache. With no browser watching for
    # this many minutes the demo pauses (no arrivals, no model calls) and picks
    # up again when someone opens it. 0 never pauses.
    idle_pause_min: float = 10

    # The provisioned alternative the cost chart is drawn against. Illustrative
    # and editable: an on-demand GPU instance sized for peak, billed per hour.
    reserved_gpu_label: str = "g6e.12xlarge (4x L40S), on demand"
    reserved_gpu_per_hour: float = 10.49


@lru_cache
def settings() -> Settings:
    return Settings()
