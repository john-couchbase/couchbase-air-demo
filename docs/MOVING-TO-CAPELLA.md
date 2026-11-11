# Moving to the Capella sandbox

The demo was built on a laptop that could not reach the sandbox. Everything below was written so
the move is credentials plus four commands. What could not be checked from here is listed
at the end as questions for the dev team; answer those first.

## What changes and what does not

| | Laptop | Sandbox |
|---|---|---|
| Cluster | Couchbase Server in Docker, `couchbase://localhost` | `couchbases://…cloud.couchbase.com` (TLS) |
| Models | LM Studio stand-ins | Deployed with the v4 API by `scripts/deploy_models.py` |
| Semantic cache | Emulated in the backend | The Model Service's, enabled on the deployment; verdict read from `x-cache` |
| Classification | `CLASSIFY_VIA=backend` (app calls the model) | `CLASSIFY_VIA=sqlpp` (the Query service runs the AI Function), or backend |
| Data, UI, SQL++, funnel, agent | unchanged | unchanged |

## Steps

**1. Bring the code over.** Clone the repo (or copy the folder), then create the Python
environment and build the web app as the README describes. Skip Docker and LM Studio.

**2. Fill in `.env.capella`** from `.env.example`, and run everything below with
`AIDP_ENV=capella` in front (see the README's "Local or Capella"):

- `CB_CONN=couchbases://cb.<id>.cloud.couchbase.com`, plus `CB_USER`/`CB_PASS` for a
  database user with read/write on the bucket. The bucket (`aidp-air`) and `travel-sample`
  must exist; load `travel-sample` from the Capella UI.
- `CAPELLA_API_KEY` (a Management API key) and `CAPELLA_ORG_ID`.
- `CB_CERT_PATH` only if the connection fails TLS verification. The Python SDK bundles the
  Capella CA, so it is normally not needed; AIDP Financial needed one only for agentc.
- Add the machine's public IP under the cluster's Allowed IP Addresses. If DNS resolves but
  ports 18091 and 11207 time out, that is what's wrong: Capella drops rather than refuses.

**3. Deploy the models.**

```bash
.venv/bin/python scripts/deploy_models.py --dry-run   # read what it will do
.venv/bin/python scripts/deploy_models.py             # create, wait, write endpoints + key to .env.capella
```

It is idempotent: models that already exist are reused and an existing `MODEL_API_KEY` is
kept. It writes `MODEL_BACKEND=model_service` and one `*_BASE_URL` / `*_MODEL_NAME` pair
per job. Correct `infra/models.json` first (see question 1).

**4. Load the data, then run it.**

```bash
.venv/bin/python scripts/provision.py
.venv/bin/python scripts/eval_classify.py 200     # the prompt was tuned on Llama 8B; check Nova
.venv/bin/python -m uvicorn aidpair.api:app --host 127.0.0.1 --port 8010
```

The Demo tab's "What is running" table should now show the models and cache as Live.
If the cache row still says Stand-in, no `x-cache` header came back, which means caching
is not enabled on the classify deployment (see question 2).

**5. Try the in-database path.** Enable AI Functions on the cluster and bind `ai_completion`
to the classify deployment (Capella UI: AI Data Plane → AI Functions). Give the database
user the **Query External Access** role, or every call fails with `missing_role:
query_external_access`. Then set `CLASSIFY_VIA=sqlpp` and restart. Classification runs
as `CLASSIFY_SQLPP` in the Query service. The bill marks its token counts as estimated
(≈), because SQL++ does not report usage back to the caller.

Measured on sbx-27 with Nova Micro:

- **One statement calls the model once per document, in turn**, at about 0.55 messages/s.
  Separate statements do run in parallel, so the app runs many one-message statements:
  4 statements x 4 messages = 1.6/s, 8 x 2 = 3.1/s, 32 x 1 = 4.7/s. The storm peaks at about
  3.4/s. `SQLPP_PARALLEL` (default 32) and `SQLPP_BATCH` (default 1) set the shape.
- **About one reply in ten comes back in a ```` ```json ```` fence** despite the prompt, so
  the statement strips it before `DECODE_JSON`.
- **`ai_completion` intermittently returns an empty string** with the classification
  prompt. How often depends on the message: "Is AD … to Fort Wayne still going? I have a
  meeting tomorrow morning." failed 8 of 20; most others rarely or never; short prompts
  never (0 of over 80). The same prompt and message sent to the gateway directly always
  answer. The cache is not involved: it happens with messages never sent before. (This
  was first reported as a cache-hit bug, which was wrong.) The app classifies such a
  message with a direct call instead and tags it `classified_by: "direct_fallback"`;
  only if that fails too is it marked for review. In a full storm: 32 of 379 messages
  took the fallback, 1 went to review, 14/14 specials escalated.
  `scripts/repro_ai_completion_empty.py` reproduces it and prints the failing query
  request IDs. **Cause, found 2026-10-07: `max_tokens`.** Inside `ai_completion` it is
  not the budget for the answer alone: at 120, 12 of 15 replies were empty and the rest
  cut off after about 25 tokens; at 220 (what the demo sent), 7 of 15 empty; at 500 and
  1000, none. A full answer is about 40 tokens. `CLASSIFY_SQLPP` now sends 500, which
  costs nothing extra. Reported to the dev team; the fallback stays as a safety net
  until they confirm.
- **Calls through `ai_completion` do not use the deployment's cache.** Measured again on
  2026-11-03 on the rj_couchbase cluster (us-east-2, Nova Micro, caching on): the same
  request sent directly came back `x-cache: HIT` in 136-144 ms; sent five times through
  `ai_completion` it took 1.8-2.9 s every time, with a plain SQL++ round trip of 34 ms. So
  on the SQL++ path the Storm tab reads 0% from cache, correctly. Present with
  `CLASSIFY_VIA=backend` to show the cache (a full storm there: 15% answered from cache,
  the dataset's exact-match rate). `scripts/check_cache.py` measures both paths.
- **This deployment sends `x-cache: MISS` on a miss**, where sbx-27 sent nothing; the app
  reads either.
- **The Model Service's cache outlives the demo's Reset.** After a few rehearsals, a storm
  was answered 100% from cache. With `CACHE_PER_RUN` (on by default), every Reset adds a
  new run id to the classify prompt. The gateway keys its cache on the system prompt
  (tested on us-east-2: the same message with a new tag misses; with the same tag it
  hits), so each run starts with an empty cache, and repeats within the run still hit.
- Changing the database user's roles briefly fails in-flight writes with
  `AuthenticationException`. Rerun `provision.py` if it was running.

**6. Afterwards, stop the meter.**

```bash
.venv/bin/python scripts/deploy_models.py off      # on / status / delete also exist
```

After a weekly scrub: steps 3 and 4 again. The data files and model spec are in the repo.

## Agent Memory, hosted (optional)

`MEMORY_BACKEND=ams` moves the agent's long-term memory from the `ops.memory` collection to
Capella's hosted **AgentMemory** service (REST; the spec is `docs/agentmemory-openapi.json`).
Set `MEMORY_URL` (the service base, `…/ams/<id>/`) and `MEMORY_TOKEN`.

- Each passenger is an AgentMemory user. Their history is the session `history`, loaded once
  with `scripts/seed_memory.py` (`--fresh` reloads without duplicating). Approvals write to
  the session `demo`, which Reset deletes, so every run starts from the same history.
- Before each decision the agent recalls by semantic search, the classification summary and
  destination as the query; the Recovery tab labels the card "Agent Memory · hosted service".
- If the service fails, that draft reads the collection instead and says so
  ("service unavailable, from the collection"); nothing stops.
- `scripts/memory_probe.py` checks what the endpoint speaks.

Checked 2026-10-14 against the us-east-1 service: healthy, recall in about 0.5 s, and the
history already loaded for all of a 20-passenger sample of the 1,031 with any.

## The MCP agent (optional)

`AGENT_VIA=mcp` gives Claude the tools of a hosted Couchbase MCP server (`MCP_URL`,
`MCP_TOKEN`), so it can look things up itself before deciding, in a loop of at most
`AGENT_MAX_STEPS` (6) calls. The default, `prefetch`, keeps the app gathering the context.

- Only tools whose names carry no write verb are offered (`MCP_TOOLS=auto`), and any SQL
  that would write is refused; changes go through a person.
- The Recovery tab lists each lookup ("Looked up through MCP · N calls"); if MCP fails, the
  draft takes the prefetch path and says so.
- **The MCP server must read the demo's own cluster.** The storm changes data (flights go
  cancelled, messages land); a server on another cluster gives Claude the wrong picture.
- Cost: describing the server's 21 tools adds about 5,000 input tokens to every step, so a
  decision costs roughly 2-4x the prefetch path.
- `scripts/mcp_check.py` lists the tools, runs a query and checks tool calling on the
  agent's model.

## The SQL++ path, tested locally

`scripts/local_ai_functions.py` creates a stand-in `default:ai_completion` UDF on the laptop
cluster that calls LM Studio through `CURL()` and returns the real function's shape,
`[{"response": "…"}]`. With it, `CLASSIFY_VIA=sqlpp` ran a full storm with the classify
statement executing unmodified in the Query service: 182 messages, **0 parse failures**.
It refuses to run against `couchbases://`.

Two things that run taught us, which will matter on the sandbox:

- **`ai_completion` takes no schema**, so the prompt is the only thing defining the output.
  Before the key list was written into the prompt, the model invented its own fields
  (`"status": "unknown"`). It is there now, and the backend eval did not regress (18/18
  specials, 3% of the crowd, 99% intent agreement).
- **It is slower.** Locally about 0.8 messages/s against about 2 for the backend path, with
  four small statements in parallel. An `UPDATE` calls the model once per document, in
  turn; on sbx-27 this was confirmed, and many statements in parallel make up for it
  (step 5).

## Questions for the dev team

1. **Catalog names for the Bedrock serverless models.** What `catalogModelName` do Nova Micro
   and Claude Sonnet take in `createModel`, and does `cloudConfig.compute` apply to them or
   only to provisioned models? `infra/models.json` currently guesses the Bedrock ids.
2. **Semantic caching via the API.** What is the exact shape of the caching settings on create
   or `PUT` (enabled, strategy, which embedding model, similarity threshold)? Is the cache
   verdict still returned in an `x-cache` response header, and is `X-cb-cache` still how a
   request selects a strategy? *Seen on sbx-27 (2026-10-06):* `x-cache: HIT` comes back on a
   hit only, never on a miss. Standard caching works. With `X-cb-cache: semantic`, nothing
   is stored or matched, not even an exact repeat after 60 s; any other value behaves like
   Standard. `scripts/repro_semantic_cache.py` reproduces it.
3. **Calling a deployed model.** Is the `connectionString` an OpenAI-compatible base URL (does
   it include `/v1`)? What goes in the request's `model` field: the deployment name or the
   `catalogModelName`? Do the Bedrock models accept `response_format` with a JSON schema?
   The app falls back automatically if not, but it helps to know.
4. **Model API keys.** Does an empty `allowedModels` mean all models? Which field of the
   create response holds the key? The script looks for `apiKey`, `key`, `token` and `secret`.
5. **AI Functions.** Can they be enabled and bound to a Model Service model through the API,
   or only in the UI? Do calls from SQL++ go through the deployment's semantic cache? Is
   token usage for those calls visible anywhere we can read it back? Do they run concurrently
   within one statement?
6. **Billing.** Does Capella bill serverless model usage at Bedrock list price, or at its own
   rate? The cost figures multiply measured tokens by Bedrock list prices
   (`aidpair/catalog.py`) and need to say what the customer actually pays.
7. **The list endpoint.** What is the response envelope of `GET …/aiServices/models`? The
   script accepts a bare list or `{"data": [...]}`.
