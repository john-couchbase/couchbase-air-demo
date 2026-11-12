# Local SQL inference test

SQL completion on HOLCluster returned OK and correctly classified a cancellation after a support workaround. The permanent product fix is not confirmed.

The optional `air_live.sql_models.local_sql_model(direct_model)` adapter tries SQL for classification and uses the existing direct model if connection, query, response parsing or classification validation fails. Recovery remains direct. Hosted SQL is opt-in: set server-only AIR_SQL_ENABLED=1 and AIR_SQL_JSON in Vercel. Without both, the hosted runtime keeps direct inference. Set AIR_SQL_ENABLED=0 and redeploy to disable SQL.

Set `AIR_SQL_CONFIG` to a private JSON file outside Git containing `connection_string`, `username`, and `password` for the cluster hosting the function. The existing john-ai-learning credentials do not grant HOLCluster access. No credentials or network permissions were created by this change.

SQL responses currently contain text but no token accounting. `usage_available: false` means unknown usage, not free inference. The local UI explicitly marks incomplete SQL costs. The backend reserves an additional call from the existing shared daily budget before making a direct fallback. Do not report zero SQL cost from the compatibility token fields.

Tests: `.venv/bin/python -m unittest discover -s tests -p test_sql_models.py`.

Verified locally: a dedicated execution-only HOLCluster credential ran the actual SDK adapter and returned a valid rebook classification, with fallback disabled. Private configuration is kept outside Git. The local HTTP backend now uses this adapter when configured; the Commands view and classification status identify the SQL route. VERCEL environments require explicit enablement and private JSON configuration; local file paths cannot activate hosted SQL. Hosted SQL was subsequently authorized; see the hosted verification below.

Start the API with AIR_SQL_CONFIG, AIR_RUNTIME_CONFIG and AIR_MODEL_CONFIG pointing to private configuration files. Run uvicorn air_live.http:app on port 8011. Start the frontend with AIR_LOCAL_API=http://127.0.0.1:8011 npm run dev:live --prefix web -- --host 127.0.0.1 --port 5186. Trigger storm to run SQL classification followed by direct recovery.

Full browser storm verified: four SQL classifications, zero fallbacks, three direct recovery calls and one low-priority skip. Four passenger results reached the completed state; SQL context/tool results and partial costs appeared in the UI. Five adapter tests and twenty live-backend tests passed. Failure injection verifies direct fallback and credential-error redaction. Vercel was not changed during that local verification.

## Hosted rollout

Use the existing Vercel project. Store the approved execution-only HOLCluster credential as sensitive AIR_SQL_JSON, never in source or VITE variables. Preserve runtime datastore and direct-model variables. Confirm the SQL cluster admits hosted egress; do not widen access automatically. Test a preview storm and independent visitor sessions before promoting. The shared allowance counts the SQL attempt and reserves one additional call before fallback. SQL usage and caching are unavailable in the observed function response.

## Hosted verification — November 12, 2026 UTC

Preview and production each completed an eight-step storm: four SQL classifications, zero fallbacks, three recovery model calls and one lower-priority skip. All four saved decisions and tools were readable by their own session. A second visitor stayed ready and could not read the first visitor’s decisions. Commands identified SQL++; usage totals excluded unavailable SQL tokens. Production deployment: dpl_Ga1wTkNio8RKEZRN2g4DxcpzuM78. Existing HOLCluster network rules were unchanged. AIR_SQL_JSON is a sensitive server variable; AIR_SQL_ENABLED explicitly enables SQL.

Cost tracking separates SQL classification, direct classification/fallback and recovery. Measured direct tokens are retained even when SQL usage is unknown. Attempt counts include a SQL attempt preceding a saved fallback result. Only saved run results are covered; failed calls that never produce a result, expired/reset history, database and hosting are not a complete billing ledger. Dollar amounts use existing demo rates and are estimates, not invoice totals.
