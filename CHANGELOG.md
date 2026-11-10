# Major updates

## 10 November 2026 - Complete maintainer handoff

- Replaced the short README with a standalone product, architecture, installation, operation and development guide.
- Added docs/TECHNICAL-HANDOFF.md and synchronized the full narrative into notes.txt.
- Documented languages/dependencies and rationale, the three AI responsibilities, provider boundaries, file map, JSON/SQLite records, API/MCP contracts, and recovery behavior.
- Reconstructed the approach history: manual evaluation, stronger generation, supplier-versus-buyer failure, corrected sports prospects, broad pivoting, winner-focused variants, four-part prompts, PDF references and outcome-review failure/recovery.
- Separated historical rubric results from verified prospect quality and explained why different cutoffs/rubrics cannot be compared as one model leaderboard.
- Recorded implementation limits including provisional best display, semantic quote/date/entity errors, URL normalization, reviewer authority, private-data dependencies and machine-specific harnesses.
- Added a whole-folder inventory from the actual workspace, including private-data file purposes and grouped installed/build/cache trees.
- Preserved the original product plan and all historical workspace screenshots in docs/; documented proposed features that are not implemented.
- Included earlier supplier/continuous-loop trials from VERIFICATION.md rather than relying only on the recent chat.
- Added tools/sync_handoff.py to build notes.txt from both canonical handoff documents; this documentation helper does not change application behavior or call providers.
- Expanded operational next steps and documentation maintenance rules. No runtime logic, models, provider settings, saved evidence or paid tests changed in this documentation update.

## 10 November 2026 - Project handoff and publication preparation

- Added notes.txt, PROJECT.md, this major-update log and ongoing documentation rules.
- Included the recorded test-score chart and existing desktop/mobile screenshots.
- Added a clean .env.template and excluded local scratch files from publication.
- Corrected README distinctions between manual and automatic runs and documented all six MCP tools.
- No new paid searches were requested or run for this documentation update. GitHub publication status must be verified separately.

## 7 November 2026 - Research-guided prompts and round outcome checks

- Added role/task/guidelines/examples prompts and reference passages from all three supplied PDFs.
- Added structured self-review of each automatic round, including the final one; previous findings feed the next generation.
- Added isolated dispute rechecks, conservative quote warnings, review cost records and cached-evidence recovery.
- Tuned the reviewer to medium reasoning, compact requirement codes and a longer timeout after live-test failures.
- Recorded ten searches, two completed reviews and scores 43.3 -> 60; target 80 not reached. Final review still flagged unverified prospect qualifications.
- Recorded validation: 23 regression tests, production build and desktop/mobile checks passed. See RESEARCH-UPGRADE-TEST.md.

## Earlier development - Winner-focused automatic research

- Started with a local search-query evaluation workbench, independent grading, evidence inspection, prompt versions, exports and MCP tools.
- Added local key inputs, persistent environment settings and provider validation.
- Added automatic budgeted rounds without a five-round manual handoff.
- Tested an upgraded generator with concise source-language queries and discovery/verification stages.
- Corrected the sports case from finding printing vendors to finding teams/league tournament prospects.
- Added winner-focused local variations and gradual nearby exploration while retaining the incumbent after ties/losses.
- Historical evidence and caveats are in SOL-BENCHMARK.md, UPCOMING-TOURNAMENTS-TEST.md and WINNER-STRATEGY-TEST.md. These runs use different goals/rubrics and should not be combined as a controlled accuracy comparison.
