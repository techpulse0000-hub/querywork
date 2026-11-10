# Verification — 29 October 2026

## Verified

- Production React/TypeScript build: passed (`npm run build`).
- Backend acceptance suite: 16 passed (`.venv/Scripts/python.exe -m pytest tests/test_app.py -q`).
- MCP integration: all five tools completed create → generate → run → inspect → refine against the running HTTP API.
- Windows launcher: verified both connection to the running app and startup after stopping the app's identified process.
- Persistence: the browser reopened the supplier demo and its two saved rounds after an actual service restart.
- Browser flow: sample input, generated alternatives, four completed searches/grades, evidence expansion, feedback, refinement, history, and connection settings.
- Layout: desktop inspection at 1440×1000 and mobile inspection at 390×844. Settings is reachable on mobile; demo labels remain visible.
- Session-key form: OpenAI/Tavily password inputs and generator/grader model fields verified in the browser. API tests confirm keys are not returned in responses or persisted in settings records; blank fields preserve configured keys. The service was restarted and the production interface rebuilt after this addition.

The acceptance suite checks the grader input allowlist, equal Tavily settings, unsupported quotation rejection, unknown/failure grade caps, duplicates, empty results versus failure, no repeated search on regrade, idempotent submissions, retry behavior, immutable prompts, authentication/origin checks, interrupted jobs, cancellation, retained evidence, and a mocked live-provider pipeline.

## Live-provider verification completed

Environment-page addition: `/environment` now has persistent `.env` saving. The added test verifies partial saves, preservation of existing/unrelated values, immediate loading, secret-free responses, and rejection of multiline injection. The earlier session-only API remains available, but the Environment form now saves locally as requested.

The user's configured keys were used for a live OpenAI → Tavily → independent grader test. Both AI roles used the confirmed `gpt-4o-mini` model. All four queries completed; the complete report is saved locally in `data/live-smoke-report.json`, experiment `3eae221de4354f5da142ac4035872a05`. No API keys appear in the report.

The initial live run exposed inconsistent grader JSON and unverifiable quotations. The grader now uses a strict schema with fixed result IDs and requirement names. Unverifiable evidence is marked unknown, removed as a supporting quotation, and capped below confirmed-match grade. Malformed structures remain errors. Failed grading was retried against saved evidence, without repeating the Tavily searches. Completed queries were retained.

Live search grades were 46.7, 10.0, 26.7, and 36.7. These are rubric judgments on search excerpts, not independent verification of supplier availability or business reliability.

Configured standard input/output rates are $0.15/$0.60 per million tokens; Tavily uses the $0.008 pay-as-you-go credit rate. See `PRICING.md` for official sources and billing caveats. The Environment page exposes editable pricing fields.

After configuring `.env` and restarting, run `.venv/Scripts/python.exe tests/live_smoke.py --live`. It explicitly runs one generation batch, four Tavily searches, and independent grading. Inspect the saved evidence and judge alignment before relying on live grades.

## Runtime

Querywork: http://127.0.0.1:8766

OpenAPI documentation: http://127.0.0.1:8766/docs

Port 8765 was occupied by the user's Lead Intelligence app and was left untouched. The selected port and all app/MCP/launcher references were moved to 8766.

## Automatic improvement verified

The new `optimize` job performs generation → Tavily search → isolated grading → comparison → feedback generation automatically. It freezes the goal and grader, retains the best historical result through regressions, filters repeated terms, and stops at the target or explicit query/round limits. Cancellation preserves evidence and the incumbent; restart marks an unfinished optimizer interrupted.

Four added acceptance tests cover a controlled 40 → 60 → 50 → 92 progression with best-so-far 40 → 60 → 60 → 92; demo target attainment across multiple rounds; the query budget; idempotency; generator feedback and grader isolation; cancellation; restart; and invalid prompt rejection without orphan jobs.

The live supplier experiment completed five automatic batches of five new terms (25 new searches), using its original frozen outcome and grader. Batch best scores including the original baseline were 46.7 → 40 → 63.3 → 40 → 50 → 63.3. Every batch graded without a provider failure. The best score improved from 46.7 to 63.3 and was retained through weaker rounds. The target of 90 was not reached; the run stopped at its configured query limit and returned the best available search. Full saved report: `data/automatic-smoke-report.json`.

Browser QA verified the automatic controls, disabled controls during a run, actual loaded limits, best search, per-round improvements/regressions, cancellation control, and correct numbering of new candidate terms. The original baseline is labeled only on the original query. Production build passed.

## Known limits

- Search excerpts are evidence; full-page extraction is not part of this first build.
- USD costs are estimates only when the corresponding rates and provider usage are available. They are not invoice reconciliation.
- Identity deduplication uses normalized URLs and model-supplied entity names; ambiguous identities still need human review.
- A dependency emits a Starlette/httpx test-client deprecation warning; the tests pass.
- Local single-user application; no hosted accounts, billing, or native installer.

## Continuous optimization correction — 2026-10-30

Removed the default five-round handoff. The initial form passes the selected target, batch size, and total search budget to the optimizer. Defaults are target 90, batch 5, budget 100; an explicit API-only round cap remains supported. Maximum query budget is 500. Reports distinguish accepted improvements from exploratory batches and retain the best independent score.

Generator feedback now includes unmet requirements, source excerpts, varied retrieval directions, and a pivot after two non-improving rounds. Generator output uses a strict JSON schema. The goal and independent grader remain frozen.

Validation: 17 pytest tests passed; TypeScript and Vite production build passed; demo MCP integration passed. The added deterministic regression reached its target on round seven from a single request (no max_rounds supplied), with a strategy pivot and monotonic retained best. This verifies control flow, not live retrieval quality. Browser demo verified that target 93 and budget 36 entered on the initial form were passed through; it completed four automatic rounds and reached the fictional fixture score of 93.3. Screenshot: ../querywork-continuous-setup.png.

A bounded five-query live continuation of the saved sports experiment was proposed but automatic approval review rejected it pending explicit approval for the payload and provider destinations. It was not executed. No live score improvement is claimed for this correction.

## Approved live continuation — 2026-10-30

After explicit user approval, job 9bdcbf7f90ea4093a69d99587df45bd7 completed exactly five new live searches on the saved sports-team experiment 20a45d056dcd405491ea301e264e810a. No round cap was supplied. It stopped at the approved five-query budget. All five searches and grades completed. New scores were 6.7, 10.0, 6.7, 10.0, and 20.0; the prior 56.7 incumbent was retained and the 90 target was not reached. This batch did not demonstrate improved live retrieval. Evidence summaries show supplier/general tournament pages and missing team names or start dates. The batch’s strict combined queries often returned few results, which also limits a score computed over ten result slots. Further testing should examine a different discovery strategy rather than treating higher scores as guaranteed. Full report: data/continuous-live-report.json.

## GPT-6.1 Sol model/prompt comparison — 2026-10-30

Generator migrated to gpt-6.1-sol with high reasoning; grader remained gpt-4o-mini and its existing prompt. Exact old/new prompts recorded before execution in PROMPT-CHANGELOG.md and saved as an immutable prompt version in the app. Current-date, discovery/verification stage, recent candidate source excerpts, entity follow-up and strict output metadata are supported. All 18 tests passed.

User-authorized live comparison: eight batches, 40 new searches, target 80. Best new batch scores: 33.3, 30, 16.7, 20, 56.7, 66.7, 23.3, 23.3. Incumbent rose from 56.7 to 66.7 on batch six; 70 and 80 not reached. End-to-end 1279.7 seconds including interruption and recovery. Known saved usage cost estimate $0.959884, excluding potential unsaved billing for the interrupted generation. One interrupted job followed by a bounded continuation; no more than 40 new searches were executed. Full findings and evidence audit: SOL-BENCHMARK.md; machine-readable summary: data/sol-benchmark-summary.json.

## Revised upcoming-tournament goal — 2026-10-30

Fresh experiment 5e2b44c4eca04ba0b8948a33972da590 used the original query and a revised goal requiring upcoming team participation or league organization, without printing-demand evidence. GPT-6.1 Sol generator, separately versioned GPT-4o mini grader, target 80, eight rounds, 40-search cap. Completed all 40 searches in 983.6 seconds, stopped at budget, best automatic score 70 on round five. Saved usage cost estimate $0.856282. Official-source review yielded 19 exported prospects, but caught temporal/entity false positives in automatic judgments. Full report: UPCOMING-TOURNAMENTS-TEST.md. General grader default restored; the case-specific grader remains pinned to this test.

## Winner-focused optimization — 2026-10-30

Implemented a single optimization-agent loop with controlled winner variations, source-level investigation, strict incumbent retention, and a gradual nearby-exploration allocation. New code: backend/search_strategy.py; prompt v3; every round stores anchor ID/score and allocation. All 19 tests and production build passed.

Live warm-start continuation on the same tournament experiment began at 70, target 80, four batches and a 20-search cap. Completed 660.0 seconds. New batch bests 40, 20, 63.3, 10; retained best 70. Exactly 20 searches: 19 generated variations and one carried-over budget-skipped query. No score improvement established. Estimated saved usage $0.630044. Full report: WINNER-STRATEGY-TEST.md; summary: data/winner-test-summary.json.
