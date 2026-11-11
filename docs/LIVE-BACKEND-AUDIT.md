# Isolated Air backend audit

## Connected and verified locally

- Dedicated `vector-learning.air_demo.runs` collection on john-ai-learning.
- Ten concurrent database runs: separate progress, reset and pause.
- SQL++ request lookup, option lookup, urgency routing and usage aggregation.
- Capella Model Service classification and recovery. Four scenarios completed through the API.
- Policy 2026.1, actual model output, token counts and SQL tool evidence saved per run.
- Review saves remain in the visitor's record. They do not send messages or change airline bookings.
- Commands inspector under More, generated from the backend constants.
- Memory stays disabled.

## Differences from the original

The original Air cluster is off. This version uses curated airline scenario inputs copied into each new run, not the original shared passenger/flight tables or live airline inventory. SQL joins are replaced by scoped lookups and UNNEST queries over the run document.

The new cluster has no registered `ai_completion` function. Classification currently calls Capella Model Service directly; it does not run inference inside SQL++. The UI identifies that distinction. Enabling SQL AI inference is a separate remaining configuration step.

The backend executes context tools before asking the recovery model to choose an option. It does not claim autonomous model-selected tool calls or MCP execution.

## Isolation and limits

Each page instance receives a private random capability. Only its hash forms the document key. Reloading starts a new independent run; the old run expires after 24 hours. The browser never receives database/model credentials.

CAS claims and generations prevent duplicate advancement and stale results after reset. Expired work becomes an explicit error. Temporary capacity waits retry; uncertain failed model calls do not automatically retry.

Default limits: 12 steps per visitor across resets, 96 shared daily step reservations, three model operations concurrently, and 200 new sessions daily. Skipped recovery calls conservatively consume a reservation. Limits are shared in Couchbase across Vercel instances; they are not dollar billing caps.

Model prices reuse the original demo's configured estimates. Actual tokens are measured. No unconfigured GPU comparison or estimated cache hits from latency are shown.

## Checks

- 20 automated isolation, CAS, validation, HTTP and budget tests pass.
- Real Couchbase SQL integration passes with identical request IDs in different runs.
- Four real model scenarios complete through the HTTP API; another visitor cannot retrieve their decisions.
- Browser live start, conversations, commands, and phone/tablet layout checked locally.
- TypeScript production build and existing simulation regression tests pass.
- Commands manifest is compared with backend constants.

## Release status

Published to https://couchbase-air-simulation.vercel.app/ on 2026-11-11 (deployment `dpl_7QkeeEWe3aZp5H1nXa2rbUvzG1gw`). Protected preview completed real classification, SQL context, recovery, persistence and reset. Public production health, ten independent sessions, controls, SQL usage and Commands all passed. Original main branch and original cluster are unchanged.

The optional SQL AI Function has additional cluster prerequisites; see [Couchbase AI Functions](https://docs.couchbase.com/ai/build/ai-functions.html). No cluster upgrade or support-plan change was made.
