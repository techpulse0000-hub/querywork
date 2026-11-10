# Querywork — Local Web Search Evals

A local React application, FastAPI engine, SQLite store, and TypeScript MCP adapter.

**Original search + desired outcome → AI generates queries → Tavily searches → isolated AI grades evidence → agent reviews outcomes → automatically refine within a budget.**

See [PROJECT.md](PROJECT.md) for the product overview, [notes.txt](notes.txt) for the project handoff and to-do list, and [CHANGELOG.md](CHANGELOG.md) for major updates.

## Start

The dependencies and interface are prepared in this workspace. Double-click **Launch.cmd**, or run `powershell -ExecutionPolicy Bypass -File Launch.ps1`. Open **http://127.0.0.1:8766**.

For a fresh installation, install Python 3.12+ and Node.js 22+, then run `Setup.ps1` first. The service runs locally in the background and survives closing the browser. To stop it, stop the Python process listening on port 8766 using Task Manager. Do not stop unrelated Python processes.

Demo mode is available immediately. Its example.com sources and deterministic grades are fictional fixtures; it makes no external API calls. Live mode uses your OpenAI and Tavily accounts.

## Configure live tests

Copy `.env.template` to `.env`, fill in `OPENAI_API_KEY`, `TAVILY_API_KEY`, `GENERATOR_MODEL`, and `GRADER_MODEL`, and restart the service. Choose model IDs available to your account that support developer messages and JSON output. No unavailable model is silently substituted. Keys are read server-side and never returned to the interface or exports.

Open **Environment** at **http://127.0.0.1:8766/environment** to enter your keys directly. **Save environment** stores entered values in the local `.env` file and applies them immediately; you can save the keys before choosing model IDs. **Save & validate connections** also checks provider access. Blank fields preserve existing values. Saved keys survive a restart and are excluded from API responses and experiment exports. Connection changes are rejected while jobs are running.

Validation checks model access and Tavily authentication; generation and grading behavior are exercised by the live smoke test itself. Then create a live experiment. Manual mode generates three alternatives plus the original baseline and permits two explicit refinements. Automatic mode generates batches of five or ten, grades and self-reviews each round, and continues until the target or configured budget is reached. Provider calls can retry, and reviews/rechecks also consume tokens. No live calls are made until configuration validation and a live operation are requested.

The core pipeline currently uses search excerpts (up to 16,000 characters per result). It does not verify current stock, business reliability, or contact success. Missing evidence remains unknown. Provider usage is saved; USD cost is unavailable until actual rates are configured. Do not treat the product's aggregate score as web-wide recall.

## Interface

- **New experiment:** describe your search, desired outcome, and optional must-have requirements.
- **Workbench:** edit generated terms, choose prompt versions, run searches, compare grades, expand evidence, and add feedback.
- **Prompt library:** edit generator instructions/user templates and grader instructions; saving creates a new immutable version.
- **History:** reopen previous experiments and rounds.
- **Settings:** connection validation, API token location, and OpenAPI links.

Every result receives a 0–3 grade. The application validates result IDs, requirement coverage, evidence quotations, unknown/failure caps, and duplicate identity. It computes `100 × sum(top ten grades) / 30`; missing positions score zero. Grader inputs contain only the desired outcome, requirements, and normalized result evidence. The grader also receives the evaluation date and duplicate policy. It excludes query wording, generator prompt/history/rationale, Tavily scores, and prior grades.

Regrading uses stored evidence and preserves earlier judgments. Retrying unfinished queries reuses completed search evidence. A new round always runs fresh searches. Provider content is treated as untrusted data. The two AI roles can use the same model through independent calls.

## HTTP API

Interactive docs: **http://127.0.0.1:8766/docs**. Schema: **http://127.0.0.1:8766/openapi.json**.

Read `data/api-token` locally and send it as `Authorization: Bearer <token>`. The UI uses an HttpOnly, SameSite cookie. Access is restricted to loopback hosts with origin checks.

| Method | Route under `/api/v1` | Purpose |
|---|---|---|
| GET | `/config` | Missing configuration and local paths; no secrets |
| POST | `/config/validate` | Validate live provider credentials/model access |
| GET / POST | `/experiments` | List or create cases |
| GET | `/experiments/{id}` | Read rounds, queries, evidence, and judgments |
| PUT | `/experiments/{id}/queries` | Edit alternatives before searching; preserve baseline |
| POST | `/experiments/{id}/generate` | Generate initial terms |
| POST | `/experiments/{id}/run` | Search and grade unfinished queries |
| POST | `/experiments/{id}/refine` | Generate the next round using feedback |
| POST | `/experiments/{id}/regrade` | Grade saved evidence without searching |
| GET | `/jobs/{id}` | Poll a persisted job |
| POST | `/jobs/{id}/cancel` | Stop new stages; retain completed work |
| GET / POST | `/prompts` | Read or create immutable prompt versions |
| GET | `/experiments/{id}/export/{json-or-csv}` | Export results |

Create body: `{"original_search":"find suppliers","outcome":"Find wholesale suppliers in Lagos","requirements":["Wholesale","Lagos"],"mode":"demo"}`.

Action body: `{"idempotency_key":"unique-per-intended-action","prompt_id":null,"feedback":"optional refinement feedback"}`. Reuse the same idempotency key when retrying a submission whose response was lost. Long-running actions return HTTP 202 with a job ID. Poll until complete, partial, failed, canceled, or interrupted. A new key retries unfinished work; it does not overwrite completed queries. UI and MCP calls share the same API and database.

## MCP integration

Start the local service first. Configure a compatible MCP host with an absolute application directory:

```json
{
  "mcpServers": {
    "querywork": {
      "command": "C:/Program Files/nodejs/node.exe",
      "args": ["C:/ABSOLUTE/APP/node_modules/tsx/dist/cli.mjs", "C:/ABSOLUTE/APP/mcp/server.ts"]
    }
  }
}
```

Replace both `C:/ABSOLUTE/APP` prefixes with this app's directory. The adapter reads its token relative to its own installation. `QUERYWORK_URL` and `QUERYWORK_TOKEN` environment overrides are supported. It uses stdio and exposes `create_experiment`, `generate_terms`, `run_experiment`, `get_experiment`, `refine_experiment`, and `optimize_experiment`. Long-running tools return jobs; `get_experiment` includes current job states. Clients supply idempotency keys. No host configuration is changed automatically.

## Development and tests

Backend: `.venv/Scripts/python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8766`.

Frontend: `npm run build` produces `dist/`, served by FastAPI. `npm run dev` is available for development; first open the backend URL to establish the browser session, or use the built same-origin interface for complete auth testing.

Tests: `.venv/Scripts/python.exe -m pytest tests/test_app.py -q`, `npm run build`, and (with the local service running) `npm run test:mcp`.

When credentials are ready, the explicit paid-provider check is `.venv/Scripts/python.exe tests/live_smoke.py --live`. It validates credentials, generates one batch, searches four queries, grades them independently, and saves a source-linked report. It does not run without the `--live` flag.

The database, API token, and local settings live under `data/`, excluded from source control. Back up that directory to preserve experiments. Set `QUERYWORK_DATA` to use another storage directory. On restart, unfinished persisted jobs are marked interrupted and are explicitly retryable.

The first version is single-user local software. Hosted accounts, billing, native installers, larger benchmark suites, and page extraction are future extensions.

## Automatic improvement

Choose **Run automatic improvement** on the new-experiment form, or use the **Automatic improvement** panel in an existing workbench. Default controls are target 90/100, five new terms per round, and a total budget of 100 new search queries. Enter the target and budget before starting. One click continues across rounds; there is no default five-round stop. Batch size can be five or ten. Each run can be canceled; completed evidence, scores, and the best search remain saved.

The engine sends the strongest three graded searches, weaker examples, criterion-level feedback, and the already-tried queries back to the generator. It generates a fresh batch, searches and independently grades it, and compares the batch best with the prior best. A worse round never replaces a better incumbent. The original outcome, must-haves, model configuration, search settings, and selected grader remain fixed throughout the run. Saved evidence from older rounds is regraded if its grader prompt differs from the run's rubric.

Stop reasons are explicit: target reached, maximum new rounds, search-query limit, no new terms, provider failure, cancellation, or interruption. Search limits count logical queries; a provider operation can retry once, so billed requests may exceed that query count. A 90 score is an assessment against the declared rubric, not a guarantee of independently verified facts. If the target cannot be reached, the app returns the best supported result rather than inventing a higher score.

API: `POST /api/v1/experiments/{id}/optimize` with `idempotency_key`, `target_score`, `batch_size`, and `max_queries` (optional `max_rounds` is an explicit API-only cap). Optional `prompt_id` selects the generator and `grader_prompt_id` selects the fixed grader. The request returns a persisted job immediately. `GET /api/v1/experiments/{id}` exposes `optimization` with the best query, comparison history, counters, and stopping reason. The matching MCP tool is `optimize_experiment`.

The browser shows per-round best scores, improvement or regression, best-so-far scores, query counts, and the final best search. Defaults in demo mode demonstrate the loop using clearly fictional evidence; live mode uses your configured providers.


The optimizer investigates the incumbent query and its source judgments before generating the next batch. A new winner gets an entire batch of close variations. After one non-improving round, 80% stay local and 20% explore nearby combinations; after two or more, 60% stay local and 40% explore nearby. Ties and losses retain the anchor, and only a strictly better independent grade replaces it. Feedback includes unmet requirements and source excerpts; grading remains isolated from generation and previous scores. The retained best score is monotonic, but trial scores can fall and an evidence-backed target is never guaranteed.

Winner-focused strategy: every new batch records `anchor_query_id`, `anchor_score`, `variation_allocation`, and the evidence-backed `focus` packet. The independent grader never receives the focus packet or prior scores. See `WINNER-STRATEGY-TEST.md` for the live test and limitations.


## Research-guided outcome checks

Automatic improvement now supplies page-labelled passages from all three user-provided search guides to the query generator and outcome reviewer. Each completed automatic round, including the final round, receives a structured self-check of the actual returned evidence. The next batch receives that review. Expand **Round outcome checks** in the workbench to inspect findings, proposed tests and source references.

The reviewer uses the configured generator model with medium reasoning; query generation keeps high reasoning for gpt-6.1-sol. Independent grading stays isolated. Quoted grading disagreements trigger one fresh independent regrade; unresolved disagreements are excluded from best-query acceptance without rewriting their scores. Review costs are recorded separately. A failed review stops the loop; starting automatic improvement again reuses cached evidence and retries its review before generating another batch.

New defaults are saved as **Research-guided v4 - evidence review** prompt versions. Existing prompt versions and experiments remain available. The PDFs are stored in `references/search-guides/`; the model receives their extracted passages, not local path strings or assumed file access. Evidence checks use search excerpts and do not claim full-page verification. See `RESEARCH-UPGRADE-TEST.md` for validation and live-test results.
