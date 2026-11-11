# Independent live airline demo

Keep the approved interface. Replace scripted answers with the existing Capella Model Service and database. Agent Memory stays disabled, with no fallback to saved passenger memory.

## Hosting and ownership

Use the existing Vercel site with server-only API functions. Each browser tab receives its own high-entropy session capability, kept in page memory so duplicated tabs cannot inherit a shared capability and sent in an authorization header. Do not put the capability in links or logs. Store only its hash in document keys. Every read, write, pause and reset must resolve the caller's run on the server.

Create a dedicated collection for this demo's run records. The original cluster is off. Seed curated fictional flight/passenger inputs into each private run; do not modify or depend on the original shared collections. Flight disruptions and booking adjustments are run-local overlays. Do not call the legacy Scenario.reset, which deletes shared records. Do not expose the administrative database credential to the browser or use it as the deployed runtime credential.

## Request-driven execution

Vercel functions advance a bounded piece of a run per request; do not depend on background loops surviving function shutdown. Persist progress, tool results, classification, decisions, token usage and errors. Use Couchbase CAS to claim work and avoid duplicate model calls from overlapping polls. Claims have a lease and an attempt ID. A reset changes the run generation; late results from the old generation cannot commit into the new run. Uncertain provider outcomes are reported, not retried indefinitely.

Read endpoints do not create chargeable work. The browser explicitly requests advancement while the run is active. Set per-run call limits, shared daily limits and bounded concurrency before enabling public usage. Do not silently substitute scripted decisions when the live service fails.

## Actual services

Classify messages through the existing configured AI Function if available for the isolated records; otherwise explicitly report direct Model Service classification as such. The reasoning model receives current booking context and tool evidence. Return measured token usage and observed cache headers; do not claim a cache hit from timing alone. Tool results, selected options and drafted replies must come from the same run. Do not portray fictional airline records as a connection to a real airline booking system.

## Verification

- Ten independently authenticated sessions have different records and progress.
- Restart, pause, approval and completion in one session do not affect nine others.
- Cross-session access is denied even if a request ID is known.
- Concurrent advancement calls claim each work item once; reset during a call discards stale results.
- Memory is never contacted, including failure paths.
- UI uses live request IDs, classifications, errors and outcomes rather than the four fixture IDs.
- Phone, tablet and desktop retain the approved layout.
- Verify database connectivity, minimal model calls, then production end to end before replacing the published simulation.

## Current evidence

See LIVE-BACKEND-AUDIT.md for current verification and remaining differences. Real database isolation, SQL++ tools, and four model scenarios have passed. Hosted preview inference and public production isolation checks passed.
