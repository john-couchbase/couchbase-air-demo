# Air demo design updates

Use the `couchbase-design` and `ui-pattern-repair` skills together for UI changes. Their shared source is https://github.com/jkupchanko/agent-skills; keep both installed side by side. If unavailable, report that limitation and use the established interface as the reference.

- Treat a reported UI issue as a pattern: check equivalent components and the screens under More while preserving accepted layouts.
- Keep tool inputs and results aligned, clearly separated, and readable. Keep Decision and Draft reply distinct; put secondary details behind a disclosure.
- Preserve the compact Centra/Inter hierarchy, neutral card borders and cream option highlights. Avoid oversized typography and stacked metadata that unnecessarily increases card height.
- Verify phone, tablet, desktop, empty and populated states relevant to the change. Keep simulation descriptions consistent with the actual fixtures; never label simulated services as live.
- Build with `npm run build:simulation --prefix web` and run `node web/tests/simulation.test.mjs` (Node 24) for simulation changes.
- Keep work on `john/air-demo-refresh`. Do not merge or push to main without explicit authorization. Report local commit, GitHub push, and Vercel deployment separately. A successful deployment is not a successful push.
- Update shared skills only when requested or when an explicitly authorized skill-maintenance task is active; project-specific implementation details belong here instead.

- Do not use decorative middle-dot separators in demo copy. Use labeled rows, whitespace, or short sentences. Preserve the round text-message bubbles; surrounding panels and process sections use compact squared corners.
