# Whole-workspace inventory and provenance

Reviewed 10 November 2026. Scope is the entire local workspace named `you-know-we-ve-got-prompt`, not just this chat or the source repository. Paths beginning with `outputs/`, `tmp/` or `work/` below are relative to that workspace. Paths in the technical handoff's code map are relative to the app root, `outputs/web-search-evals/`.

The GitHub repository contains the app root as its root. It is not a raw copy of the surrounding workspace. Original planning material and historical screenshots have therefore been copied into docs/planning/ and docs/screenshots/archive/ so a new maintainer can see the wider project context. Private state and generated dependencies are documented without uploading them.

## 1. Top-level layout

| Local area | What it contains / why it exists | Publication treatment |
| --- | --- | --- |
| outputs/web-search-evals/ | Canonical editable application, tests, reports, references and project documents. | Source is published as the repository root, with exclusions below. |
| outputs/web-search-evals-product-plan.md | Original 27 October concept, research/evaluation plan, proposed UX, metrics, contracts and acceptance gates. | Preserved in docs/planning/web-search-evals-product-plan-2026-10-27.md. It is a proposal, not proof of implementation. |
| outputs/querywork-*.png | Saved UI, live-result, configuration and publication screenshots from development. | Preserved under docs/screenshots/archive/; key recent images also have shorter canonical filenames under docs/screenshots/. |
| outputs/querywork-source-2026-11-10.zip | Sanitized source distribution generated for handoff. | Local delivery archive, not a runtime dependency. Rebuild it after changes; do not recursively put archives inside the source package. |
| outputs/querywork-publication/ | Sanitized staging copy used to build/upload a release snapshot. | Generated duplicate, not the editable source of truth. It is refreshed from the canonical app. |
| outputs/querywork-publication-manifest.json | File names, byte counts, content hashes, validation/publication metadata and commit reference. | Local publication bookkeeping. It may describe an earlier snapshot until regenerated; verify its commit/hash fields. No credentials are included. |
| tmp/pdfs/ | Temporary PDF text extraction and rendered pages used to read the supplied research guides. | Working artifacts, not runtime inputs. Canonical full text/PDFs live in references/search-guides/. |
| work/ | Empty working directory at review time. | No current project content or hidden implementation was found there. |
| README.md / notes.txt at workspace root | Local entry points added to make the wider folder understandable. | Point to or mirror the app documentation; they are not a second runtime application. |

## 2. Original plan versus implementation

The 17-section original plan covers the product concept, eval analogy, guided user journey, input brief, supplier example, strategy/query comparisons, run stages, judgment contract, metrics, benchmark methodology, refinement, AI role contracts, screens, storage/architecture, build sequence, cost/product success and open decisions.

Implemented foundations: separate original query/outcome/requirements; provider searches and isolated grading; a transparent 0-100 formula; manual query editing and feedback; prompt versions; saved evidence; local HTTP/MCP interfaces; history and exports; budgeted automatic refinement; winner-focused variants; PDF-guided prompts and round outcome checks.

Partially implemented: the broad notion of versioned strategies is represented by experiment/round/prompt snapshots rather than a dedicated reusable strategy registry. Stored evidence supports regrading/recovery but not a complete controlled retrieval replay system. Entity deduplication is heuristic rather than reliable canonical matching. Job checkpoints and histories are useful but not a fully immutable event log. Query budgets exist, but explicit hard dollar/time ceilings do not.

Not implemented from the plan: a guided clarification/brief approval wizard; separate typed preference/exclusion/quantity/location fields; a suite manager with human labels and held-out topics; the proposed 30-case/20-development/10-holdout benchmark; calibrated nDCG/reference-pool coverage/goal-progress dashboards; full-page extraction; distinct-entity ranking and cost-per-qualified-prospect metrics; a formal human correction workflow; project ownership/access records; an evidence retention/deletion UI; hosted multi-user isolation and product billing.

The original plan's manual round launch and original-plus-three default describe the first slice. Later user requirements replaced the main workflow with automatic five/ten-query batches and no default five-round handoff. Likewise, its proposed richer schema is not the actual SQLite schema. When these documents disagree, inspect the code and the current handoff; do not infer that a planning heading is a shipped feature.

## 3. Source and configuration files

Every first-party backend, frontend, adapter and test source file is listed with its purpose in section 11 of TECHNICAL-HANDOFF.md. This includes backend/__init__.py (Python package marker), the seven substantive backend modules, five frontend files, mcp/server.ts and eight test/harness files.

| App-root file | Purpose |
| --- | --- |
| index.html | Browser document that loads the React frontend. |
| package.json | Node dependency declarations and dev/build/MCP/test commands. |
| package-lock.json | Exact npm dependency resolution for npm ci; third-party code is installed from it. |
| requirements.txt | Human-readable Python dependency ranges. |
| requirements.lock.txt | Pinned Python installation snapshot used by Setup.ps1. |
| tsconfig.json | TypeScript compiler options and source inclusion. |
| vite.config.ts | React plugin and development /api proxy to the local backend. |
| Setup.ps1 | Python environment setup, locked dependency installation, npm ci and frontend build. |
| Launch.ps1 | Verify/start the local service on 8766; open browser unless suppressed. |
| Launch.cmd | Windows double-click wrapper for the PowerShell launcher. |
| .env.template | Deliberately blank-key setup template distributed with source. |
| .env | Actual local provider/model/rate configuration; private, never published. |
| .env.example | Legacy local example that contains real credentials in this workspace; ignored, never published. It is not interchangeable with the clean template. |
| .gitignore | Excludes secrets, private data, installed dependencies, build output and scratch files. |
| AGENTS.md | Maintenance requirements for future contributors/agents. |

## 4. All project documents and what to trust them for

| App-root document | Purpose / status |
| --- | --- |
| README.md | Current standalone installation, product, operation and developer entry guide. |
| notes.txt | Full plain-text handoff, including why decisions changed and what remains open. |
| PROJECT.md | Shorter product scope, personas, capabilities and priorities. |
| CHANGELOG.md | Major changes and why they matter. |
| docs/TECHNICAL-HANDOFF.md | Detailed source-based architecture, decisions, experiments, contracts and roadmap. |
| docs/WORKSPACE-INVENTORY.md | This document: surrounding folder, artifacts, ignored state and provenance. |
| docs/workspace-file-inventory.json | Machine-readable coverage of first-party artifacts and grouped generated/private areas. It lists metadata, not secrets or raw experiment content. |
| docs/planning/web-search-evals-product-plan-2026-10-27.md | Original proposal preserved from outside the app folder. Future features are explicitly distinguished above. |
| VERIFICATION.md | Cumulative historical implementation/verification log. Older sections intentionally describe earlier states and test counts; later sections supersede them. |
| PRICING.md | Dated GPT-4o mini/Tavily configuration and sources. Not the later Sol configuration or a current account price quote. |
| PROMPT-CHANGELOG.md | Old/new generator prompts and rationale for the October 30 upgraded-generation comparison. |
| PROMPT-UPGRADE-DRAFT.md | Approved four-part prompt proposal and later implementation note. Preserves planning wording as history; search_prompts.py is the executable current prompt source. |
| SOL-BENCHMARK.md | Combined upgraded-model/prompt experiment, recovery and audit of its misleading printing-related winner. |
| UPCOMING-TOURNAMENTS-TEST.md | Revised sports goal, frozen requirements, nominal 70 and separate evidence audit. |
| WINNER-STRATEGY-TEST.md | Winner-focused policy, controlled checks and live continuation that did not beat the existing 70. |
| RESEARCH-UPGRADE-TEST.md | PDF/reference/review implementation and the November 7 two-round test with failures, recovery and remaining qualification gaps. |
| references/search-guides/README.md | Original PDF names, extraction method and reference-pack limitations. |

Historical reports sometimes link to private data/ artifacts. Their absence from GitHub is intentional, not proof that the reports never existed. Replaying exact historical experiments requires a separately authorized private backup and valid provider access. A current fresh search is a different experiment.

## 5. Every original screenshot and chart

All original outputs/querywork-*.png images are preserved under docs/screenshots/archive/ using the same filename. These are dated development evidence, not a fresh current UI regression suite.

| Original filename | What it records |
| --- | --- |
| querywork-desktop.png | Early manual comparison workbench using fictional demo evidence; its high demo scores are not live accuracy. |
| querywork-key-form.png | Earlier session-key entry screen with blank provider inputs. Persistent Environment saving was added later. |
| querywork-automatic-improvement.png | Earlier automatic-run controls/result presentation. |
| querywork-continuous-setup.png | Target/batch/budget setup after removing the default manual handoff. |
| querywork-sol-result.png | Historical upgraded-generator result view. |
| querywork-upcoming-tournament-result.png | Historical revised tournament-prospect result view. |
| querywork-winner-strategy-result.png | Winner-focused continuation and retained-best display. |
| querywork-research-review-desktop.png | Desktop demo outcome-review display. |
| querywork-research-review-mobile.png | Mobile demo outcome-review display. |
| querywork-research-live-desktop.png | Desktop completed live-review display, including qualification caveats. |
| querywork-research-live-mobile.png | Mobile completed live-review display and unverified-quote warnings. |
| querywork-github-notes.png | Browser proof that the notes file was published on the private repository. Its displayed commit/text may precede later documentation updates. |

Canonical recent copies are docs/screenshots/automatic-improvement-setup.png, outcome-review-desktop.png and outcome-review-mobile.png. docs/test-scores.svg and test-scores.png depict the recorded November 7 43.3-to-60 progression versus target 80. The chart is not a new measurement and does not show verified prospect accuracy.

No video file exists in the inspected folder. The written handoff, references, chart and screenshots are the available onboarding material.

## 6. PDF originals, canonical extractions and temporary copies

| Canonical stem under references/search-guides/ | Original document / role |
| --- | --- |
| advanced-search-techniques.pdf and .txt | Eight-page Open University search guide: keywords, phrases, logic, database differences, saved searches and spelling variants. |
| advanced-internet-search-techniques.pdf and .txt | Three-page internet-search tip sheet: phrases, source restrictions, Boolean/exclusion techniques, file types and wildcard cautions. |
| in-real-time-search-tips.pdf and .txt | Nineteen-page Suzanne R. Graham document from 2012: wording, variants, phrases, source/file restrictions and revisiting useful sources; historical claims need caution. |

Outside the app, tmp/pdfs/guide-1.txt, guide-2.txt and guide-3.txt are the same extraction sequence in the order above. guide-1-page-4.png, guide-2-page-2.png and guide-3-page-10.png are rendered sample pages used to inspect visual examples. Those scratch images are not agent training data or screenshots of the website. The model gets selected canonical text passages, not automatic access to either the temporary files or every PDF page.

## 7. Private runtime data: all named files, purposes and boundaries

The inspected app data/ directory held 24 files. Only names and roles are documented here; values, keys, tokens, database rows and raw provider responses are not published. File names alone do not prove that all historical reports are independent experiments.

| Local data file | Role |
| --- | --- |
| api-token | Secret local bearer/cookie access token. Never display or publish it. |
| querywork.sqlite3 | Canonical persisted records: experiments, prompts, jobs and settings. Not a public fixture database. |
| generator-provider-status.json | Latest selected Sol provider metadata/finish reason/usage; not a complete trace of every request. |
| live-smoke-report.json | Initial paid four-query provider pipeline report. |
| automatic-smoke-report.json | Supplier-case automatic continuation report. |
| continuous-live-job.json | Saved metadata for the specifically approved five-query sports continuation. |
| continuous-live-report.json | Result of that five-query continuation; previous incumbent retained. |
| sol-test-config.json | Model/prompt comparison metadata, saved-case IDs and setup. |
| sol-prompt-change.json | Recorded generator prompt/model change before testing. |
| sol-live-phase1.json | Interrupted first phase of the upgraded-generation test. |
| sol-live-report.json | Later phase/recovery result record. |
| sol-benchmark-summary.json | Consolidated upgraded-generation findings across phases. |
| upcoming-test-config.json | Revised tournament-prospect goal, rubric and run metadata. |
| upcoming-live-report.json | Eight-batch/40-search revised-goal run evidence. |
| upcoming-test-summary.json | Its summarized result and cost/timing metadata. |
| upcoming-evidence-audit.json | Separate temporal/entity error findings and source checks. |
| upcoming-prospects.csv | Nineteen historically source-checked outreach prospects; not a current buyer list. |
| winner-test-config.json | Winner-focused continuation limits and saved experiment metadata. |
| winner-strategy-change.json | Recorded prompt/policy change before the continuation. |
| winner-live-report.json | New batches, evidence, usage and retained-best record. |
| winner-test-summary.json | Consolidated continuation result, including the carried-over search. |
| research-upgrade-test.json | November 7 experiment, prompt versions, retry job IDs and known failed-review usage. |
| research-upgrade-report.json | Detailed two-round evidence/review/test record. |
| research-upgrade-summary.json | Completed result and structural verification summary. |

The corresponding top-level narrative reports are the shareable summaries. Do not upload this data directory just to make old report links work. Reports can contain user search goals and results even when they contain no provider keys. Any private backup transfer needs its own clear scope.

## 8. Installed, built and cached content

These groups were inspected by directory/file counts rather than copied line by line into the handoff. Snapshot counts change as software runs.

| Group at review time | Contents / purpose | How to reproduce or treat it |
| --- | --- | --- |
| .venv/ - 2,047 files | Installed Python interpreter environment, dependencies, scripts and package metadata. | Recreate with Setup.ps1 / the pinned requirements. Do not treat vendor code as original project implementation. |
| node_modules/ - 9,550 files | Installed React/Vite/TypeScript/MCP and transitive npm packages. | Recreate with npm ci from package-lock.json. Do not upload it. |
| dist/ - three files | Built index.html and hashed JS/CSS assets. | Recreate with npm run build. Source is under src/ and index.html. |
| .pytest_cache/ - five files | Test-run bookkeeping, collected IDs and related cache metadata. | Disposable generated cache, not product data or test specifications. |
| backend/__pycache__/ and tests/__pycache__/ | Compiled Python bytecode caches. | Recreated by Python; substantive source is in .py files. |
| tmp/test-temp/ | Temporary local test scratch; may include generated tokens/settings. | Excluded even if a test value is fictional. Not a setup template or portable fixture. |
| outputs/querywork-publication/ | Release staging duplicate (59 files before this documentation expansion). | Regenerate; do not edit as canonical source or interpret its old count as the current repository size. |

The machine-readable inventory groups these areas to keep coverage complete without listing more than ten thousand dependency/cache files. Lockfiles document which dependencies are installed; their own upstream documentation remains authoritative for those libraries.

## 9. Folder-wide historical details added to the handoff

VERIFICATION.md records more than the later sports experiments. The initial paid supplier run had query scores 46.7, 10, 26.7 and 36.7 after schema/quotation issues were corrected. Its later automatic continuation used 25 new searches and retained a best 63.3, missing target 90. These were excerpt-based supplier evaluations, not business reliability checks.

The continuous-loop correction was first tested with deterministic/demo cases. A proposed paid continuation was initially not executed because explicit payload/provider approval was required; the later approved five-query sports continuation completed with new scores 6.7, 10, 6.7, 10 and 20, retaining its prior 56.7. This failed to show retrieval improvement and helped motivate a discovery/verification strategy rather than more restrictive all-in-one terms.

These records are part of the folder's development history. They are not replaced by the latest chat summary or folded into a fictitious single uninterrupted benchmark. Some early VERIFICATION.md statements describe five tools, earlier test counts, old pivots or manual limits that later changed; use it as a chronological log.

## 10. Coverage and maintenance rule

docs/workspace-file-inventory.json records the inspected first-party file paths, their classification/publication treatment, and grouped dependency/private/generated areas. Its scope is the surrounding workspace. The canonical application remains outputs/web-search-evals/ locally and the GitHub repository root remotely.

After major changes, review the folder itself: new plans, scripts, references, screenshots, data artifacts and build/config files may exist outside the chat narrative. Update the inventory and full handoff when that happens. Keep secrets and private state excluded even when documenting their role. Record observed facts separately from proposals and historical measurements.
