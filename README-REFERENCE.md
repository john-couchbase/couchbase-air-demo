# AIDP Air: isolated live demo

[Open the demo](https://couchbase-air-simulation.vercel.app/)

This branch connects the refreshed airline demo to Capella while keeping each visitor’s run separate.

- **Couchbase:** run-local requests, SQL++ lookups, decisions, usage and saved reviews.
- **Model Service:** Nova 2 Lite classifies requests; Claude Sonnet 5 drafts recovery proposals.
- **Commands:** open **More → Commands** for the SQL, prompts, policy and save operation.
- **Isolation:** independent page sessions, CAS-protected updates and 24-hour records. Reloading starts a new run.
- **Limits:** 96 daily step reservations across all visitors, three concurrent model operations, 12 steps per session across resets.
- **Not connected:** Agent Memory, SQL AI Functions, real airline booking systems or live partner inventory. Scenario inputs are fictional; model responses and database operations are live.

Reviews are saved in the demo. They do not send messages or change actual bookings. Costs shown are estimates from configured rates, not a billing statement.

See [the backend audit](docs/LIVE-BACKEND-AUDIT.md) for verification and differences from the original.

### Local connected version

Install `requirements.txt` plus `uvicorn`. Supply `AIR_RUNTIME_CONFIG` and `AIR_MODEL_CONFIG` pointing to private JSON files outside this repository, or encrypted `AIR_RUNTIME_JSON` and `AIR_MODEL_JSON` environment values. Never commit credentials.

Run `python -m uvicorn air_live.http:app --port 8010`, then `npm run dev:live --prefix web`. The separate `npm run dev --prefix web` still opens the scripted simulation. `vercel.live.json` describes the connected deployment with `web/dist` copied to `public`.

## Original demo reference

The documentation below describes the original shared backend, not the isolated hosted implementation above. Do not run its provisioning/reset scripts against the hosted run collection.

# AIDP Air: Serverless Models in the Couchbase AI Data Plane

A field demo of **Serverless Bedrock Frontier Models** in the AI Data Plane Model Service.
A winter storm closes AIDP Air's hub at O'Hare. 52 flights cancel and the support queue takes
a surge nobody forecast. Three beats:

1. **Enrich at rest, in bulk.** Every message is classified where it landed (what the passenger
   wants, how urgent it is) by a small, cheap model (Nova Micro), called from a SQL++ statement. Repeated questions come from the
   semantic cache.
2. **Reason at the top of the funnel.** A SQL++ join of model output and passenger tier picks
   the few (about 8%) that need judgment. A frontier model (Claude Sonnet) reads the booking,
   real partner routes from `travel-sample`, and Agent Memory, then drafts a decision. A person
   approves it, which writes back to memory.
3. **Go quiet.** The queue drains and spend drops to zero, next to the flat line of a reserved
   GPU.

The three tenets it proves: an unforecast **burst**, a **model per task** rather than per
fleet, and inference **inside the data** workflow.

## Run it locally

Needs Docker, LM Studio and Python 3.11. Everything the demo writes lives in `aidp-air`.`ops`.

```bash
# 1. Couchbase Server (once). Set a password and put it in .env.local as CB_PASS.
docker run -d --name aidp-air-cb -p 8091-8097:8091-8097 -p 11210:11210 couchbase/server:enterprise-7.6.6
docker exec aidp-air-cb couchbase-cli cluster-init -c localhost --cluster-username Administrator \
  --cluster-password "$CB_PASS" --services data,index,query --cluster-ramsize 2048 --cluster-index-ramsize 512
docker exec aidp-air-cb couchbase-cli bucket-create -c localhost -u Administrator -p "$CB_PASS" \
  --bucket aidp-air --bucket-type couchbase --bucket-ramsize 512 --wait
curl -u Administrator:"$CB_PASS" -X POST http://localhost:8091/sampleBuckets/install -d '["travel-sample"]'

# 2. Python, data, and the cluster contents. provision.py is idempotent.
uv venv --python 3.11 && uv pip install -r pyproject.toml --extra dev
cp .env.example .env.local    # then fill in CB_PASS
AIDP_ENV=local .venv/bin/python scripts/provision.py

# 3. Models. --context-length matters: LM Studio splits it across the parallel slots.
lms load meta-llama-3.1-8b-instruct --parallel 16 --context-length 32768 -y
lms load text-embedding-nomic-embed-text-v1.5 -y

# 4. Build the app and serve everything on :8010, from a terminal you own.
npm install --prefix web
AIDP_ENV=local ./scripts/present.sh
```

Open http://localhost:8010, press **Trigger storm**, and a run goes from storm to quiet in
about four minutes. **Reset** (click twice) restores a normal morning. **Pause** stops new messages and
model calls until you press Resume; the demo also pauses by itself after 10 minutes with
nobody watching (`IDLE_PAUSE_MIN`) and picks up when someone opens it again.

## Sandbox-like local mode

`AIDP_ENV=sandbox-local` runs the laptop the way sbx-27 runs it, so a sandbox problem can be
reproduced and fixed here before it is taken back. The app runs in its remote mode against
`aidpair/gateway.py`, a stand-in for the Model Service gateway on :8020 that imitates what was
observed on sbx-27: an exact-match cache, `x-cache: HIT` on hits only, nothing stored for
`X-cb-cache: semantic`. Classification goes through the SQL++ statement, with `ai_completion` as
a local UDF calling the gateway, and the cache verdict is estimated from statement time, as on
the sandbox.

```bash
cp .env.sandbox-local.example .env.sandbox-local    # then fill in CB_PASS
lms load mistralai/mistral-7b-instruct-v0.3 --parallel 16 --context-length 32768 -y
AIDP_ENV=sandbox-local ./scripts/present.sh         # starts and stops the gateway too
```

Three switches in `.env.sandbox-local` cover the open questions: `SANDBOX_AI_FUNCTIONS_USE_CACHE`
(do AI Functions use the cache?), `GATEWAY_EXTRA_MS` (a slow network to Capella) and
`GATEWAY_SEMANTIC_WORKS` (as if semantic caching were fixed). `curl localhost:8020/stats` shows
the gateway's own hit count, to check the app's estimate against.

First run, everything as observed on sbx-27 with AI Functions using the cache: **14% answered
from cache** (the dataset predicts 11-14% for exact-match), and the app's timing estimate counted
57 of the gateway's 59 hits. The banner and the Demo tab label every part of this mode as a
stand-in.

## Presenting

**The talk track is [docs/RUN-OF-SHOW.md](docs/RUN-OF-SHOW.md):** beats, what to point at, the
questions you will get and what to do if something breaks.

**Present from http://localhost:8010, started with `./scripts/present.sh` in a terminal you
own.** Never present from the Vite dev server (`npm run dev`, port 5174). In AIDP Financial
the dev server kept dying mid-demo: a server started by the editor's preview manager is the
editor's to kill, and it does, with no error in any log. The same applies to the API itself,
so don't start it from the editor either.

`present.sh` rebuilds the web app every time, so you can't present a stale build, and runs
without `--reload`, so a stray file save can't restart the server mid-demo. Use port 5174 only
while editing the UI.

## What is real and what is a stand-in

The **Demo** tab reports this live, and a banner stays on screen while anything is a stand-in.

| | Locally | On sbx-27 |
|---|---|---|
| Cluster, SQL++, `travel-sample`, meter, Agent Memory collection | Real | Real |
| Nova Micro and Claude Sonnet | LM Studio (Llama 3.1 8B) | Model Service, Bedrock |
| AI Functions | Backend runs the same prompt, writes back with SQL++ | `default:ai_completion` in the Query service |
| Semantic cache | Emulated in the backend (nomic embeddings, cosine 0.93) | Chosen when the model is deployed |

Token counts are always measured. Prices are Bedrock on-demand list prices
(`aidpair/catalog.py`). The reserved GPU rate is set in config and labelled as such.

## Map

- `scripts/build_dataset.py`: builds `data/*.json` once, deterministically (already committed).
  The network is United's ORD routes from `travel-sample`, re-badged. The carrier, passengers
  and messages are invented.
- `scripts/provision.py`: loads the cluster. Rerun it after every sandbox scrub.
- `scripts/eval_classify.py`: scores classification against the dataset's labels. Use it after any
  prompt or model change. Last local run: all 18 special cases escalate, 4% of the crowd
  escalates, 98% intent agreement.
- `aidpair/classify.py`: beat 2. The prompt, the AI Functions statement and the funnel.
- `aidpair/agent.py`: beat 3. Context gathering, options, the policy and approval.
- `aidpair/scenario.py`: the storm clock and the background workers.
- `aidpair/api.py`: the HTTP surface. It also serves `web/dist`.
- `tests/test_endpoints.py`: calls every read endpoint against the running API. SQL++
  reserved words (`cache`, `language`, `option`) have broken three of them so far.

## Local or Capella

One codebase runs both. `AIDP_ENV` picks the settings file, and nothing else changes:

```bash
AIDP_ENV=local   ./scripts/present.sh    # .env.local: Docker + LM Studio
AIDP_ENV=capella ./scripts/present.sh    # .env.capella: sbx-27 + Model Service
```

The same goes for every script (`AIDP_ENV=capella .venv/bin/python scripts/provision.py`).
Unset, it reads `.env`. A name with no matching file stops with an error rather than
falling back to the laptop defaults. All `.env.*` files except `.env.example` are gitignored.

The two differ only where the model does: on the Model Service the cache is the gateway's
and the agent sends no temperature (Claude Sonnet 5 rejects one); locally the cache is
emulated and the agent runs at 0.2. The prompts are shared, and score the same on both
(`eval_classify.py`: 18/18 escalations, 1-2% of the crowd).

## Moving to the sandbox

See [docs/MOVING-TO-CAPELLA.md](docs/MOVING-TO-CAPELLA.md): credentials, then
`deploy_models.py`, `provision.py`, run. Models are deployed with the Capella v4 API and
switched off afterwards with `deploy_models.py off`. The doc ends with the questions for the
dev team that have to be answered before the first run.

Two classification paths, set by `CLASSIFY_VIA`:

- `backend` (default): the app calls the model per message with the same prompt. It sees
  every token count and cache verdict, and it is fast.
- `sqlpp`: the Query service runs `CLASSIFY_SQLPP`, the real AI Function statement. Tested
  locally through `scripts/local_ai_functions.py`, a `CURL()` UDF standing in for
  `ai_completion`. Token counts are estimated on this path.

## Prerequisites

- Docker, for Couchbase Server Enterprise 7.6.6 locally.
- [LM Studio](https://lmstudio.ai) with its `lms` CLI, for the local stand-in models.
- Python 3.11 and [uv](https://docs.astral.sh/uv/).
- Node and npm, to build the web app.
- For Capella: access to the sbx-27 sandbox, a database user, and a Capella Management API key
  and organization ID (see [docs/MOVING-TO-CAPELLA.md](docs/MOVING-TO-CAPELLA.md)).

## Setup

Clone the repo, then follow [Run it locally](#run-it-locally) steps 1-4: start Couchbase
Server, install the Python dependencies (`uv venv --python 3.11 && uv pip install -r
pyproject.toml --extra dev`), copy `.env.example` to `.env.local` and fill in `CB_PASS`,
run `scripts/provision.py`, load the models in LM Studio, and `npm install --prefix web`.
For Capella, copy `.env.example` to `.env.capella` instead and follow
[Moving to the sandbox](#moving-to-the-sandbox).

## Configuration

Settings come from `.env.<AIDP_ENV>` (see [Local or Capella](#local-or-capella)); every key
is described in `.env.example`. The ones that aren't obvious:

- `CB_CONN`, `CB_USER`, `CB_PASS`, `CB_BUCKET`: the cluster. Locally a `couchbase://`
  address for Docker; on sbx-27 a `couchbases://cb.<id>.cloud.couchbase.com` address.
- `CAPELLA_API_KEY`, `CAPELLA_ORG_ID`: used only by `scripts/deploy_models.py`.
- `CLASSIFY_VIA`: `backend` (the app calls the model per message) or `sqlpp` (the Query
  service runs the AI Function statement; token counts are estimated).
- `MODEL_BACKEND`: `local` serves every model from LM Studio and labels figures as stand-ins;
  `deploy_models.py` sets `model_service` and writes the per-job endpoints.
- `SURGE_SIZE`, `SURGE_SECONDS`: the storm's shape. The defaults suit one laptop GPU.
- `IDLE_PAUSE_MIN`: pause after this many minutes with nobody watching; `0` never pauses.

## Usage

Start the demo with `AIDP_ENV=local ./scripts/present.sh` (or `AIDP_ENV=capella`) from a
terminal you own, and open http://localhost:8010. Press **Trigger storm**: the run goes from
storm to quiet in about four minutes. Approve the agent's drafted decisions as they appear,
watch spend drop to zero, then click **Reset** twice to restore a normal morning. **Pause**
stops new messages and model calls until you press Resume. The talk track, what to point at,
and what to do if something breaks are in [docs/RUN-OF-SHOW.md](docs/RUN-OF-SHOW.md); see
also [Presenting](#presenting).

## Attribution

Original work by @pgryzan-couchbase. The route network comes from Couchbase's `travel-sample`
bucket (United's ORD routes, re-badged as AIDP Air); the carrier, passengers and messages
are invented.

## License

No license has been chosen yet. This repo is internal to Couchbase-SE; don't redistribute it
until a license is picked.

## Maintainer

@pgryzan-couchbase (Patrick Gryzan)
