# Querywork: complete product, implementation and decision handoff

Updated 10 November 2026. This document describes the checked-in implementation, the reasoning behind it, the approaches tested, the observed failures, and the work needed next. It is intended for someone who has not read the original conversation.

The same handoff and the entire workspace inventory are provided as plain text in [notes.txt](../notes.txt). Start with [README.md](../README.md) for installation and operation. [PROJECT.md](../PROJECT.md) is the shorter product overview; [CHANGELOG.md](../CHANGELOG.md) is the major-update index. [WORKSPACE-INVENTORY.md](WORKSPACE-INVENTORY.md) covers material elsewhere in the folder, including the original plan, earlier screenshots, private runtime artifacts and generated dependencies. Historical reports are evidence records, not claims of current model availability, pricing or live event schedules.

## 1. The problem we are solving

A search query can look reasonable but retrieve the wrong kind of result. Querywork tests that gap. The user supplies both an initial query and the outcome they actually want. AI generates alternative queries, Tavily searches the web, an isolated AI grader evaluates the returned evidence, and an automatic loop tries to improve retrieval without silently changing the goal.

The idea came from prompt evaluations: if prompts can be evaluated against expected behavior, search queries can be evaluated against expected evidence. The intended application was Lead Chain lead research, but the implementation is general rather than hard-coded to a particular product or industry.

For example, a person selling jersey-printing services wants potential customers. Searching for a team name plus "screen printing" can find shops already selling printing or existing merchandise stores. Those are not evidence of teams looking to buy the service. This failure drove an important goal correction, described below.

Intended users are lead researchers, research operators and people developing retrieval prompts. These are product personas, not validated paying customer segments. The commercial target customer, willingness to pay and final hosted product remain open questions.

## 2. What is built, and what is not

Built: a single-user local website, a Python API and background engine, SQLite persistence, provider configuration, a prompt library, manual query comparisons, automatic budgeted improvement, outcome self-review, evidence inspection, exports, an MCP adapter and Windows installation/launch scripts.

Not built: a multi-tenant SaaS service, user accounts, subscription billing, cloud deployment, a native mobile app, an autonomous outreach sender, a verified buyer database, or full-page crawling and extraction. The system evaluates returned search excerpts. It does not independently confirm buying intent, contact deliverability or every source's truth.

The app runs at http://127.0.0.1:8766/. Port 8765 belongs to the separate Lead Intelligence application in the original workspace and must not be modified.

## 3. Languages, frameworks and their jobs

| Technology | Used for | Reason for this choice / tradeoff |
| --- | --- | --- |
| Python | API, provider boundary, orchestration, evaluation validation, reference selection and tests | Direct JSON/HTTP handling and a small inspectable backend; no heavyweight agent framework is needed for this bounded workflow. |
| FastAPI | HTTP endpoints and generated OpenAPI documentation | Typed request validation and a documented interface shared by the browser and MCP adapter. |
| Pydantic | Request schemas and limits | Reject malformed inputs and enforce choices such as batch sizes and query budgets before work starts. |
| Uvicorn | Local ASGI server | Serves the FastAPI application on loopback. |
| httpx | OpenAI and Tavily requests | Explicit provider requests, timeouts and bounded retries. The implementation does not depend on the OpenAI or Tavily Python SDK. |
| TypeScript / TSX | Browser interface and MCP adapter | Makes data shapes and UI contracts explicit. TSX expresses React components. Types still need to agree with runtime responses. |
| React / React DOM | Interactive website | Forms, prompt editing, polling, history, query selection and evidence displays. |
| Vite | Development server and production frontend build | Fast local development and static assets served by FastAPI in the normal installed app. |
| HTML | Frontend entry document | Loads the built React application. |
| CSS | Layout, responsive behavior, colors and component styling | An existing custom stylesheet keeps this local app small; no Tailwind or shadcn runtime is used. |
| Lucide React | Interface icons | A consistent icon set instead of custom image assets for each control. |
| SQLite / SQL | Local durable record storage | No external database server is required. The current schema stores JSON documents in a generic records table; that simplifies iteration but limits relational querying and future scale. |
| JSON / JSON Schema | API payloads, stored documents and structured model output | Machine-readable contracts for queries, judgments and reviews. Schema-valid output is not necessarily factually correct. |
| Node.js / npm | Frontend build tools, MCP process and browser test scripts | Runs the TypeScript toolchain and adapter. Dependencies are installed with npm ci from the lockfile. |
| MCP SDK / Zod / tsx | Stdio MCP tools and their input validation | Lets a compatible AI host use the same local experiments through tools, without duplicating provider logic. |
| PowerShell / Windows CMD | Setup and launcher | Matches the original Windows environment. The scripts are not cross-platform installers. |
| Markdown / plain text | Readme, plans, prompt records, reports and handoff | Readable in GitHub and ordinary editors. notes.txt is available without a Markdown viewer. |
| PDF / extracted UTF-8 text | User-supplied research references | Original documents are preserved; selected page-labelled text is supplied to models. These files are not a new model or a fine-tuning dataset. |
| SVG / PNG | Historical score chart and screenshots | SVG preserves an editable chart; PNG and screenshots make results easy to view. They document saved tests rather than running new searches. |

Runtime versions and dependencies are in package.json, package-lock.json, requirements.txt and requirements.lock.txt. The documented starting environment is Python 3.12+ and Node.js 22+. requirements.txt gives dependency ranges; requirements.lock.txt records the installed Python versions for reproduction. Model and provider availability must be validated against the account being used.

## 4. Architecture and boundaries

```text
Browser UI (React) -----------+
                             +--> FastAPI --> persisted job --> automatic engine
MCP host --> stdio adapter ---+         |                         |
                                       +--> SQLite               +--> OpenAI: generate queries
                                                                 +--> Tavily: search each query
                                                                 +--> OpenAI: isolated grade
                                                                 +--> OpenAI: outcome review
                                                                 +--> next batch or stop
Research PDFs --> extracted page-labelled passages --> generator and reviewer
```

The browser does not call OpenAI or Tavily directly. The backend reads provider keys from local configuration. The MCP adapter also does not call providers directly; it forwards to the same local HTTP API with a local access token. This keeps orchestration, budgets and stored evidence in one place.

Background work uses ThreadPoolExecutor(max_workers=1). Jobs are serial at this worker, which keeps the prototype straightforward and limits overlapping provider work. It is not a distributed queue and not a multi-user scalability design.

The application is the orchestrator. Models propose queries, judgments or reviews within schemas. Application code executes searches, persists checkpoints, counts logical searches, compares scores and chooses stop conditions. This distinction is essential: a prompt alone cannot enforce budgets or make its own score trustworthy.

## 5. The three AI responsibilities

### Search strategist / generator

Receives the original search, fixed outcome, requirements, useful prior queries, evidence gaps, failed approaches, source excerpts, known candidate entities, already-tried queries, reference passages and the latest completed outcome review. It returns queries containing text, note, stage, evidence_sought and target.

Its job is to find evidence, not to declare leads qualified. Discovery searches can identify candidates; verification searches must seek missing facts about those candidates. A term earns no score before it is actually searched and its results graded.

### Independent evidence grader

Uses a separate model call with an explicit input allowlist: outcome, requirements, evaluation date, duplicate policy and results containing id, rank, title, URL and content. It does not receive query wording, generator instructions/rationale, prior optimizer scores, target score, reference-guide passages or reviewer recommendations.

This isolates conversational context and reduces score-chasing contamination. It does not establish statistical independence or eliminate model bias. The grader can still make semantic errors, as historical tests demonstrate.

### Outcome reviewer

Uses the configured generator model in another call. It sees each completed query, its actual returned excerpts, independent judgments, the incumbent, the evaluation date, remaining budget and PDF-reference passages. It checks whether the research outcome is useful and what should be tested next.

It reviews every completed automatic round, including the last one. Manual run/regrade actions do not currently have the same automatic review step. Reviewer output is saved on the round and passed into the next automatic generation packet. It is not sent as guidance to the isolated grader.

There are three logical responsibilities but usually two configured model IDs: generator and grader. No swarm of autonomous agents, LangChain, AutoGen, vector database or separate agent server is installed. A bounded application-controlled loop was sufficient for the required behavior.

## 6. A complete automatic run

1. The user enters an initial query, desired outcome and mandatory requirements, then chooses target, batch size and search budget.
2. The backend checks that no job is already active for this experiment. Live work also requires configured and validated provider access. Idempotency keys prevent duplicate submission of the same intended operation.
3. The job captures the selected generator/grader prompts and model configuration. Existing evidence is processed under the selected grader before comparisons; old judgments are preserved when regrading.
4. The app gathers eligible candidates, unresolved criteria, recent discoveries, strong source excerpts, weak examples and the latest review. It chooses an anchor and local/nearby allocation.
5. The generator returns a batch. Already-tried text is filtered. A brand-new experiment also includes the user's original query as a baseline in its first round.
6. For each query, Tavily returns up to ten results. The app saves evidence before grading so a failed grade can be retried without repeating its search.
7. The isolated grader produces result-level grades and criterion judgments. The server validates IDs, criteria, exact quotations, hard failures, unknowns and duplicates before computing the numeric score.
8. The outcome reviewer checks all completed queries/results in the round. Supported disagreements trigger at most one fresh isolated regrade per disputed query. A criterion disagreement that remains unresolved puts the query in review_disputed status and excludes it from best-query selection.
9. The app compares the completed batch with its incumbent. Only a strictly higher eligible independent score is an improvement. Ties/losses retain the prior anchor. It records the comparison and either starts the next batch or stops.
10. The last completed round is reviewed too. When continuation is disallowed, the final next_tests list is emptied; suggested future research does not authorize more paid work.

Default controls are target 90, five generated terms and 100 new logical searches. Batch size can be five or ten. API limits allow target 1-100 and max_queries 1-500. max_rounds is optional (1-100) and is an explicit API cap, not a default five-round handoff.

The search budget counts new logical searches, including the original baseline. Therefore two batches of five generated terms may need eleven searches if every term plus the original is executed. The November 7 test allowed only ten: six in round one and four new queries in round two; one generated term was budget-skipped.

Search limits are not a monetary ceiling. Generation, grading, reviews, dispute regrades, provider retries and regrading saved evidence can cost tokens without adding logical searches. A resumed run may execute an older budget-skipped query before generating new terms. Cached complete evidence is reused when compatible, but starting another optimization run is not simply a free display refresh.

Stop reasons include target_reached, query_limit, round_limit, no_new_terms, provider_failure, generation_or_provider_failure, canceled and interrupted. A complete job means the bounded workflow finished, not that its target or research goal was met. Cancellation occurs at checkpoints; an in-flight provider request may finish before cancellation is observed.

## 7. Scoring and validation

Every returned result receives an integer grade:

- 0: irrelevant, demonstrated mandatory failure, or identified duplicate.
- 1: background information without a concrete plausible qualifying target.
- 2: plausible target with incomplete or ambiguous mandatory evidence.
- 3: direct outcome match with all mandatory requirements supported.

For each requirement the grader returns pass, fail or unknown and a supporting quote. Pass/fail quotes must be exact substrings of that result's content. Unsupported quotes are changed to unknown. Any mandatory fail forces grade 0; any unknown caps the grade at 2. Results are processed in returned order, with repeated normalized URL or case-folded entity labels contributing zero.

The aggregate is round(100 * sum(result grades) / 30, 1), using ten possible result slots worth three points each. Missing slots contribute zero. Seven grade-3 results and three zeros yield 70; six grade-3, one grade-2, one grade-1 and two zeros also yield 70. Thus score 70 is not necessarily seven leads, 70% correctness or a 70% chance of buying.

This metric measures URL-slot evidence yield. One official page naming sixteen useful teams still occupies one slot, while repeated pages can inflate apparent yield if entity aliases escape deduplication. A focused verification query with very few results can score lower even when it resolves a valuable fact. Unique prospect extraction and qualification need a separate metric.

Exact-quote checking only establishes that text appeared in the excerpt. It does not prove that the quote entails the criterion. Current semantic date/identity checks still depend substantially on model judgment. Grader-generated summary prose can disagree with the server's adjusted counts; use structured judgments and recomputed values, not a summary sentence alone.

The normal strategy retains the best score across worse trials. An outcome recheck or exclusion of a disputed query can revise eligibility, so the retained best should not be promised as unconditionally monotonic. During evaluation, a displayed independent best may precede completion of its round review; a stronger acceptance-state distinction is a to-do item.

## 8. Approaches tried, why they changed, and what we learned

### Initial manual query evaluation

Started with an initial query plus three alternatives, separate search/grading, evidence inspection and explicit refinements. This established an observable baseline and independent evidence scoring. It did not satisfy the desired autonomous workflow because users still had to trigger more rounds. Manual mode remains useful for inspection and controlled edits; automatic mode became the primary improvement path.

### Cheap-model baseline and upgraded query generation

The project first configured GPT-4o mini for both roles to keep experimentation inexpensive. The user then approved testing gpt-6.1-sol for more capable query generation, with high reasoning and a 12,000 completion-token cap. The grader remained GPT-4o mini. Model IDs are configuration values; they are not a promise of availability for another account today.

The prompt changed at the same time: concise language likely to occur in real sources, discovery followed by entity-specific verification, explicit time evidence, and recent candidate excerpts. This was a combined model-and-prompt experiment, not proof that the model change alone caused improvement.

### Why the jersey/screen-printing search failed

A high-scoring query combined a team name with jerseys or screen printing. It retrieved merchandise, suppliers and general athletics material. The original desired outcome implied printing buyers, while the explicit grading requirements were weaker and often checked team/date information. The optimizer could improve a metric that did not represent the real business goal.

The lesson was to fix the outcome and rubric together. Do not optimize a proxy score and then call its winners buyers. The user revised the prospect definition rather than requiring public evidence of a printing request that teams might never publish.

### Revised sports prospect goal

Find named teams participating in upcoming major tournaments, or leagues organizing them. The operational tournament scope for that experiment was organized regional, national or international competition. A qualifying excerpt needs identity, an explicit future start date and the participant/organizer relationship. Printing demand and optional contact details are not mandatory. The user intends to pitch prospects themselves.

An upcoming event is a lead signal, not proof of a purchase need. A generic tournament calendar, venue or merchandise store is not automatically an eligible team/league. Historical experiments pinned upcoming to October 30; the November 7 test used a new cutoff. Those definitions must not be silently rewritten inside old records.

### Broad pivoting versus winner-focused refinement

Earlier prompts could pivot substantially after stalls. A revised sports run reached a nominal 70, then later batches fell back to 26.7, 16.7 and 10. The user proposed investigating the query that caused the score jump and generating nearby variations around it.

The current policy is deterministic application code in search_strategy.py. No incumbent means initial discovery. A fresh winner gets an all-local batch. After one non-improving batch, five-query allocation is four local plus one nearby; after two or more, three local plus two nearby. Ten-query batches use eight/two and six/four. Local changes preserve the useful source/topic family while changing one retrieval component. Ties/losses retain the anchor; unrelated wholesale pivots are discouraged.

This is an exploitation/exploration policy, not a guarantee of increasing scores. A live continuation followed the policy but did not beat its existing 70. Better orchestration alone cannot repair an unreliable grader or create missing public evidence.

### Four-part prompts and the three research guides

The user requested role, task, guidelines and examples, with concrete scoring illustrations. Stable instructions identify each role; runtime user messages supply the specific experiment and evidence. Synthetic examples teach buyer-versus-supplier distinctions, future-date requirements, incomplete evidence and score arithmetic. They are not fabricated live benchmarks.

The supplied guides cover keywords/synonyms, exact phrases, Boolean logic, domain and file-type restrictions, search logs and revisiting useful sources. Their database-specific and historical operator claims are not assumed to apply to Tavily. Current generator context explicitly says special query operator support has not been verified; plain-language queries remain the safe default.

### Outcome review and recovery

The user asked the agent to test each round's outcome itself. A separate review call now inspects the real returned evidence rather than simply reading a numeric score. The first implementation hit a provider timeout. A longer retry exhausted the high-reasoning response allowance without usable output. Medium reviewer reasoning and compact requirement codes produced a report, which exposed non-exact quotations.

The final behavior removes unsupported quotes, marks affected assessments incomplete and displays warnings. Unsupported disputes cannot trigger grading changes. Structural errors such as omitted query IDs still fail the review and stop the loop. Retrying reuses saved evidence rather than repeating its searches. Generation retains high reasoning; review uses medium reasoning with a 240-second timeout for the configured Sol model.

## 9. Historical experiments and correct interpretation

| Experiment | Protocol | Observed result | What it does / does not establish |
| --- | --- | --- | --- |
| Upgraded generation on the older sports/printing goal | 40 new searches, eight batches, target 80 | Previous best 56.7; new best 66.7; roughly 21.3 minutes including recovery; known estimate about $0.96 | Combined model/prompt improvement on a weak rubric. It did not establish verified printing buyers or a speed improvement. |
| Revised upcoming-tournament prospect experiment | 40 searches, eight batches, cutoff October 30 | Best 70 in batch five; about 16.4 minutes; estimate about $0.86; target 80 missed | More suitable discovery direction, but audit found past-event and entity-type false positives. |
| Winner-focused continuation of that experiment | 20 additional searches, four new batches | New batch bests 40, 20, 63.3, 10; retained old 70; about 11 minutes; estimate about $0.63 | Confirmed the local/nearby strategy was followed, but it produced no score improvement. |
| Research-guided outcome-review test, November 7 | Ten searches, two rounds, 100 returned-result checks; new cutoff November 7 | Batch bests 43.3 then 60; target 80 missed; both reviews completed; known estimate $0.811617 including recoverable failed-review usage | Verified the new loop and feedback propagation. Final reviewer still found insufficient team/league qualification. Not 60% verified prospect accuracy. |

These runs changed goals, time cutoffs, prompts or grading rules. They are not a clean leaderboard of algorithms or models. A tournament starting November 6 can qualify relative to October 30 and fail an upcoming-start requirement on November 7. Historical dates and prospect lists must be checked again before present-day outreach.

Historical reports: SOL-BENCHMARK.md, UPCOMING-TOURNAMENTS-TEST.md, WINNER-STRATEGY-TEST.md and RESEARCH-UPGRADE-TEST.md. Raw experiment data and some report links point to the original local data/ directory. That directory is deliberately absent from GitHub; a fresh clone cannot reproduce those exact saved cases from source alone. The published narrative reports and images preserve the conclusions and limitations.

The November 7 report records 18 unsupported-review-quote warnings in round one and nine in round two. Those quotes were not accepted. Its final self-check described useful event/host material but did not establish that each host was a league or confirm named-team participation. This is precisely why scores and self-review conclusions must be shown separately.

## 10. PDF reference implementation

references/search-guides contains three original PDFs, their extracted .txt files and a provenance README. research.py reads the text with PAGE markers, prioritizes configured baseline pages plus lexical relevance, and selects up to three pages per document. Each selected passage is capped at 4,500 characters and records document name, page and extraction SHA-256.

Both generation and review record the passages supplied. This is lightweight local text selection, not embeddings, semantic vector retrieval or on-demand unrestricted PDF browsing. The current baseline selection is strong enough to dominate some relevance ranking, so more adaptive reference selection is a future improvement. Diagrams and layout may not survive text extraction; the original PDFs remain available for manual review.

Models receive selected extracted text, not automatic access to a local path or the full PDF on every request. Provider calls transmit that selected text along with the relevant experiment context. Reference passages are untrusted research data, not instructions that override the user's goal. The supplied documents retain their original authorship; a private repository does not imply a new license or ownership of them.

## 11. File-by-file orientation

| Path | Responsibility / where to change behavior |
| --- | --- |
| backend/app.py | FastAPI routes, request models, local access checks, configuration, JSON SQLite records, prompt defaults, job submission/execution, exports and static frontend serving. Start here for API and persistence behavior. |
| backend/engine.py | Provider HTTP requests, model-role selection, generation template filling, strict query schemas, Tavily result normalization, grader allowlist/schema, grade validation, duplicate checks and estimated cost. Start here for provider and evidence contracts. |
| backend/optimizer.py | Automatic loop, cached evidence, counters, feedback packet, per-round review/recheck, comparisons, history and stop conditions. Start here for autonomous behavior. |
| backend/search_strategy.py | Pure local/nearby variation policy and focus-source packet. Change this to alter exploitation/exploration allocation. |
| backend/search_prompts.py | Versioned strategist, grader and reviewer text plus generator user template. Prompt changes should be versioned and evaluated, not silently substituted in history. |
| backend/research.py | Local page selection and reference hashes. Change this for more adaptive guide retrieval. |
| backend/round_review.py | Review input/output schema, requirement-code mapping, result coverage checks, exact-quote filtering, supported disputes and final-round next-test handling. |
| src/main.tsx | React application shell, new experiment form, history, prompt editor, comparison workbench, evidence panels and job polling. |
| src/Optimization.tsx | Target/batch/budget controls, optimizer status, retained best and round comparison table. |
| src/RoundReviews.tsx | Review findings, per-result evidence, warnings, proposed next tests and reference/cost display. |
| src/Connections.tsx | Environment/session connection forms and provider settings UI. |
| src/style.css | Shared styling and responsive layouts. |
| index.html / vite.config.ts / tsconfig.json | Browser entry, dev proxy/build configuration and TypeScript checking. |
| mcp/server.ts | Six stdio MCP tools forwarding to the local HTTP API; reads its access token locally. |
| tests/test_app.py | Backend/API regressions, demo/provider fixtures, optimizer acceptance, isolation, references, reviews and recovery tests. |
| tests/mcp-smoke.ts | Adapter/tool transport smoke check against a running local service. |
| tests/live_smoke.py | Explicit paid-provider smoke harness; read its --live gate and budget before use. |
| tests/sol_report.py / sol_summary.py | Historical benchmark monitoring and aggregation. Not a fresh account-independent benchmark runner. |
| tests/research_live_test.py | Specific November 7 paid test/recovery harness, tied to saved IDs and dates. Do not casually run it in a fresh clone. |
| tests/research-ui.cjs / research-live-ui.cjs | Historical headless Chrome UI checks; contain machine-specific runtime/browser paths and create/read local test cases. Portability work remains. |
| tools/sync_handoff.py | Standard-library documentation helper: builds notes.txt from this handoff plus the whole-workspace inventory. It reads no private runtime data and makes no provider calls. |
| Setup.ps1 / Launch.ps1 / Launch.cmd | Windows dependency installation, build and hidden background server launch. |
| .env.template | Blank-key example for a new installation. Never put real keys here. |
| docs/ | Handoff, historical score chart and saved workbench screenshots. |
| requirements*.txt / package*.json | Dependency declarations and reproducibility locks. |
| AGENTS.md | Required maintenance practices for future changes in this project. |

## 12. Local data model and important fields

SQLite table: records(kind TEXT, id TEXT, body TEXT, PRIMARY KEY(kind,id)). body is JSON. The app uses parameterized SQL and a process-local reentrant lock. Record kinds include experiment, prompt, job and settings. IDs are generated UUID-style hexadecimal strings. This is not a normalized relational schema with separate result tables.

Experiment: id, created, original_search, outcome, requirements, mode, models, search_settings, grader_prompt_id, rounds, feedback, jobs, optimization and optional optimization_history. The API adds job_states when reading a full experiment.

Round: id, created, automatic flag, optimization_id, generator_prompt/model/usage, feedback, strategy, anchor_query_id/score, variation_allocation, reference passages, queries, outcome_review/status, review model/reasoning/usage/cost, attempts and error history where available.

Query: id, text, note, status, optional discovery/verification metadata, results, search usage, retrieval timestamp, evaluation, grader prompt/usage, evaluation_history, elapsed time, estimated cost, errors and optional dispute-recheck metadata.

Result: local id, rank, title, URL and excerpt content. Evaluation: structured judgments, aggregate score, grade-3 count, uncertain count and model summary. Criteria remain tied to the declared requirement strings. Job: operation, experiment ID, idempotency key, prompt snapshots, options, stage, status, cancellation flag and timestamps.

Query states include ready, retrieved, complete, budget_skipped, search_failed, grading_failed and review_disputed. Job states include queued, running, complete, partial, failed, canceled and interrupted. The optimization substate uses its own running/finished/failed/canceled/interrupted labels. Do not confuse these different layers when building a new UI.

On restart, the app marks unfinished persisted jobs interrupted; it does not automatically resume paid work. Retry is an explicit operation. Prompt saving creates a new database version rather than editing the old record. Old experiments can pin older graders even when new defaults exist.

The code preserves evaluation and optimization histories, but it is not a complete immutable audit-event store. Some round review snapshots are replaced on retry while attempts/errors are retained where implemented. If regulatory or forensic auditability becomes a requirement, design a dedicated append-only history.

## 13. HTTP API and MCP contracts

All API routes below are under /api/v1. Local interactive documentation is at /docs and the schema at /openapi.json.

| Method / route | Purpose |
| --- | --- |
| GET /config | Report missing settings, models and local paths without key values. |
| POST /config/environment | Save selected provider/model/rate inputs to local .env and apply them. Blank secrets preserve existing values. |
| POST /config/session | Apply connection values for the process session without persisting those session secrets. |
| POST /config/validate | Check provider credentials/model access and record a configuration fingerprint. Does not prove research quality. |
| GET / POST /prompts | List prompt versions or create a new generator/grader version. |
| GET / POST /experiments | List experiment summaries or create a case. |
| GET /experiments/{id} | Read the full saved case with rounds, evidence and job states. |
| PUT /experiments/{id}/queries | Edit unsearched manual alternatives while preserving the original baseline. |
| POST /experiments/{id}/generate | Generate the initial manual candidate batch. |
| POST /experiments/{id}/run | Search and grade unfinished manual queries. |
| POST /experiments/{id}/refine | Generate a manual refinement from prior results and feedback. |
| POST /experiments/{id}/regrade | Regrade stored evidence without a fresh search; prior evaluations are preserved. |
| POST /experiments/{id}/optimize | Run budgeted automatic generation/search/grading/review/refinement. |
| GET /jobs/{id} | Poll persisted job status and stage. |
| POST /jobs/{id}/cancel | Request cancellation at the next checkpoint. |
| GET /experiments/{id}/export/json | Download the full experiment document, including review details. |
| GET /experiments/{id}/export/csv | Download the current result/criterion-oriented CSV projection; it is not a complete review-history representation. |

Example case: {"original_search":"find sports prospects","outcome":"Find named teams participating in future regional tournaments","requirements":["Named team","Explicit future start date","Confirmed participation"],"mode":"demo"}.

Example automatic action: {"idempotency_key":"one-intended-run","target_score":80,"batch_size":5,"max_queries":10,"max_rounds":2,"prompt_id":null,"grader_prompt_id":null}. A response with HTTP 202 contains a job; poll it to completion. Reusing an idempotency key returns the previous intended submission, while a new key represents another operation.

MCP tools: create_experiment, generate_terms, run_experiment, get_experiment, refine_experiment and optimize_experiment. The server runs over stdio with npm run mcp. Configure absolute installation paths in the host. It reads data/api-token relative to its installation, or QUERYWORK_TOKEN; QUERYWORK_URL can override the default local API address. The HTTP optimize endpoint exposes more selection/feedback controls than the current MCP optimize tool schema.

## 14. Provider settings, model choices and costs

Tavily defaults: general topic, basic search, max_results 10, include_answer false, include_raw_content false, auto_parameters false, include_usage true. Search results are normalized to the local schema; content is capped at 16,000 characters for normal grading. Review uses up to 4,000 characters per result. Shorter review excerpts can omit material available to the grader; both evidence scopes must be stated honestly.

OpenAI calls use Chat Completions and structured JSON output. Reasoning-model prefixes use a developer message; other models use a system message. The explicit high/medium reasoning and 12,000 completion-token behavior is implemented for gpt-6.1-sol. Selecting another model does not automatically configure its reasoning settings or pricing correctly; validate support before changing configuration.

Most provider calls default to 90 seconds; round review requests allow 240. Transient 429/5xx and network/timeout cases have bounded retry handling, normally up to two attempts. Model access validation is a preflight, not proof that every later structured request will succeed. A diagnostic file records selected Sol finish-reason/usage metadata without keys; it is not a full provider trace for every request.

The engine contains historical Sol rate logic: $2/M uncached input, $0.10/M cached input, $2.50/M cache-write input and $10/M output. Other models use configured INPUT_USD_PER_MILLION and OUTPUT_USD_PER_MILLION, and Tavily uses TAVILY_USD_PER_CREDIT. These are project accounting values, not a fresh November 10 price quote. PRICING.md documents an earlier GPT-4o mini configuration. Review account pricing and update implementation when changing models.

Usage estimates separate generation, query search/grading, review and recheck costs where recorded. Returned usage for some failed outputs can be retained. Timeouts can be billed without returned usage; aggregate grading usage also does not preserve every possible provider cache detail. Do not promise a precise invoice total or treat max_queries as a dollar cap.

## 15. Installation, operation and recovery

1. Clone the private repository or unpack the source archive. Work inside the app root containing backend/, src/ and package.json.
2. Install Python 3.12+ and Node.js 22+ with npm. In PowerShell run: powershell -ExecutionPolicy Bypass -File .\Setup.ps1.
3. Setup creates .venv, installs requirements.lock.txt, runs npm ci and builds the frontend with TypeScript/Vite. It uses a known Python 3.12 installation path when present, otherwise python on PATH. Its pip --python command requires a sufficiently capable pip in that interpreter.
4. Start with Launch.cmd or powershell -ExecutionPolicy Bypass -File .\Launch.ps1. The launcher validates the service identity on port 8766 and starts Uvicorn hidden when needed. It opens the local browser unless -NoBrowser is used.
5. Use demo mode first. Demo sources and deterministic scores are fictional and cannot validate real search quality.
6. For live mode open Environment, enter keys/models, save and validate. Alternatively copy .env.template to .env and fill it locally. The old local .env.example is deliberately ignored because it previously contained real keys; it is not the published template.
7. Create a fresh, clearly scoped experiment. State geography, time window, entity types and what counts as major when relevant. Use a small explicit budget for the first paid check.
8. Inspect both structured grades and round outcome reviews. A high score with missing identity/relationship proof is not a verified lead list. Export JSON for the most complete handoff.

If the page is unavailable, check that the frontend has been built and the correct server is listening on 8766. Run .venv/Scripts/python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8766 in a terminal for visible diagnostics. Do not stop unrelated Python services.

If credentials/models change, validate again; validation is tied to a fingerprint. If a job fails, inspect its stage and saved evidence before retrying. An interrupted review should reuse existing searches. Old budget-skipped queries can consume new budget on resumption. A restart preserves data but marks in-progress jobs interrupted, so never restart casually during a paid run.

Back up data/ privately to preserve experiments, prompts, jobs and the local access token. It is excluded from GitHub by design. For a new storage location set QUERYWORK_DATA before process startup. Keep .env private too, but do not send keys in a bug report or commit them with a backup.

For frontend development run npm run dev; the Vite proxy forwards /api to 8766. The built same-origin site is the normal authenticated path. For the dev origin, first establish the backend browser session or otherwise configure local access as documented; it is not a public unauthenticated API.

## 16. Security and publication boundaries

The service binds to loopback. Middleware restricts allowed hosts/origins and accepts a local bearer token or HttpOnly SameSite browser cookie. This is a local access boundary, not internet-grade user authentication. Secrets are read server-side, filtered from configuration responses and kept out of experiment exports. Environment writes are local; these are not an encrypted cloud secret vault.

The GitHub repository is private at https://github.com/techpulse0000-hub/querywork. The initial source publication contains the code, clean template, guides, documents and images. It excludes .env, the legacy .env.example, data/, databases, local API token, .venv/, node_modules/, dist/, caches and scratch files. Initial publication verified all 59 file contents against their prepared Git blob hashes; later documentation revisions must be verified independently.

Do not expose this server with --host 0.0.0.0 and assume it is ready for customers. A hosted version needs user authentication, tenant isolation, credential storage, job ownership, rate/budget enforcement, monitoring and deployment controls. Likewise, repository privacy does not grant redistribution rights to the third-party PDFs.

## 17. What has been tested, and what those checks mean

The November 7 upgrade recorded 23 passing regression tests, a passing TypeScript/Vite production build and desktop/mobile headless checks. Tests cover API/persistence/idempotency, configuration secret handling, empty versus failed searches, reuse/regrade, duplicate suppression, evidence validation, model request construction, automatic continuation past five rounds, winner retention and variation allocation, cancellation/restart, all-three-document references, review coverage and feedback, unsupported quotes, isolated dispute rechecks, and recovery without repeated searches.

The live test exercised actual OpenAI/Tavily calls under an explicit ten-search budget and recovered from timeout, output-length and quotation issues. It established working integration and saved feedback, not robust accuracy across industries. Demo fixtures prove deterministic application behavior, not external facts. Headless visual tests verify rendering and controls, not search quality.

Routine commands: .venv/Scripts/python.exe -m pytest tests/test_app.py -q; npm run build; npm run test:mcp with the local service running. Historical browser/live harnesses require adaptation for their local paths, saved IDs and dates. Do not run them blindly in a fresh clone. This detailed-documentation update uses source inspection and document/package checks, not new paid searches or a new accuracy benchmark.

## 18. Known limitations and prioritized next work

Priority 1: make the evidence metric trustworthy. Add deterministic date parsing where possible; distinguish event, venue, host organization, league and team; improve alias-level deduplication; preserve meaningful URL parameters rather than stripping all query strings indiscriminately; and validate that a quote actually supports its criterion. An event ID in a query parameter can identify a different event, so current URL normalization can overmerge pages.

Priority 2: make review authority and acceptance clear. Narrative reviews can still overstate unsupported facts even when their quotations are filtered. Some unsupported disputes are ignored, so an advisory warning alone does not invalidate an independent score. Show provisional, reviewed and disputed states explicitly. Preserve old reviews when criteria/evidence change and build a more complete event history.

Priority 3: measure useful prospect yield separately from URL-slot scores. Extract unique entities and event relationships, verify full pages when needed, and separate optional contact enrichment from qualification. Combine evidence across sources only under a defined entity-level policy; the current per-result grader must not borrow facts from another result.

Priority 4: run controlled evaluations. Assemble human-labelled cases across several goals with fixed dates and requirements. Keep one axis stable when comparing models, prompts or scoring. Record qualified unique prospects, false positives, unresolved facts, time, tokens and cost rather than only best score. Targets such as 80 or 90 must reflect validated rubric behavior, not aspirations.

Priority 5: improve operation. Generalize pricing beyond one hard-coded reasoning model, account for failed/retry usage more consistently, reduce review latency, make reference selection more adaptive, remove absolute paths/saved IDs from test harnesses, and add explicit cost ceilings if users need spending guarantees.

Priority 6: productize only after validating demand. Decide the customer and workflow, then design hosted authentication, user isolation, queue/worker management, billing, monitoring and deployment. The existing local app is a research prototype, not evidence of product-market fit.

Recommended next developer session: run demo/local regressions; read engine.py, round_review.py and optimizer.py together; reproduce one documented false-positive case from available non-secret evidence or a new approved fixture; add a meaningful correctness check; version the rubric; compare on a fixed small benchmark. Do not simply increase the query count or change the generator model and assume the quality problem is solved.

## 19. Maintenance and handoff requirements

After every major change update notes.txt, README.md where behavior/setup changes, PROJECT.md, CHANGELOG.md and this handoff as appropriate. Record the problem, implemented behavior, rationale, alternatives rejected, relevant files, prompt/model/rubric versions, checks actually run, measured outcomes, failures, limitations and next tasks. Edit this handoff and WORKSPACE-INVENTORY.md first, then run `python tools/sync_handoff.py` to synchronize notes.txt with both canonical documents.

Preserve historical scores and evaluation cutoffs. Label old screenshots and price assumptions with their dates. A documentation update is not a live validation. Verify GitHub publication against the actual branch rather than merely creating a commit object. Never upload keys or private data as a shortcut to making another developer's setup identical.

No video walkthrough has been recorded. The published handoff, code map, chart and screenshots are the current onboarding materials. A future video should distinguish fictional demo behavior from paid live results and avoid displaying keys or private data.

## 20. Scope beyond the chat and application source

The complete local workspace contains the original product plan, older screenshots, publication staging/archives, temporary PDF inspection artifacts, private experiment reports and installed/build/cache directories in addition to the app. The appended plain-text inventory and WORKSPACE-INVENTORY.md document each area and every first-party artifact; third-party/generated trees are grouped rather than listing thousands of dependency files.

The October 27 plan is preserved under docs/planning/ with its original content. It proposed richer brief fields, human-labelled benchmark splits, nDCG/reference-pool metrics, entity-level yield, ownership/access records and other capabilities not all implemented. Read the inventory's proposal-versus-implementation map before treating that plan as the current specification.

VERIFICATION.md also records early paid supplier checks, a 25-search automatic continuation and a separate five-query sports continuation. Those trials predate the later sports/prompt/review experiments in section 9; the inventory describes their outcomes and why they influenced subsequent approaches. They are not new measurements and are not one combined controlled benchmark.

Every original outputs/querywork-*.png screenshot is archived in docs/screenshots/archive/. Canonical recent copies remain where the README already links them. Temporary PDF renders are documented as scratch evidence; the original PDFs and full canonical extractions remain under references/search-guides/. Private data files are named and explained without publishing their contents, keys or tokens.

The surrounding workspace root has a README navigation guide and a copy of the full notes for local handoff. The GitHub repository root maps to the local outputs/web-search-evals/ directory, not the whole surrounding filesystem. This mapping explains why local parent-folder paths and generated/private data may not exist in a fresh clone.
