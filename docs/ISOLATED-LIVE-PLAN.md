# Isolated live airline backend implementation plan

Goal: keep the approved interface while making each visitor's Capella-backed run independent.
Architecture: Vercel request-driven Python API, new Couchbase run collection, private browser-tab capabilities, CAS-protected work claims. Existing models, memory disabled.
Spec: ISOLATED-LIVE-DESIGN.md. User approved new isolated collection.

- [x] Verify destination cluster connectivity and both model completions. Original source cluster stays off.
- [x] Add new server package for session capability validation, generation/lease state and Couchbase CAS storage. Test ten users, cross-run reads, overlapping advance, stale completion after reset and call limits.
- [x] Add bounded model execution and context tools, storing actual outputs and usage in the caller's run. Validate model output before applying a proposal. No memory imports or fallback.
- [x] Add Vercel HTTP routes and a server-side readiness check. Configure a scoped runtime credential and limits; never publish admin credentials.
- [x] Adapt frontend live requests and conversation navigation to session records; show failures explicitly. Preserve simulation build for rollback.
- [x] Verify preview end to end before switching production. Keep original demo and shared records untouched.

Evidence: see LIVE-BACKEND-AUDIT.md. Both model roles and isolated SQL tools passed. Preview inference passed; public site now serves the isolated backend. Production isolation, SQL usage and Commands checks passed.

Rulings: use the already-running cluster and curated run-local inputs because the source cluster is off; use direct Model Service because the new cluster has no registered SQL AI Function; keep page-local capabilities so duplicated tabs do not share ownership. These differences are explicit in the audit and Commands UI.
