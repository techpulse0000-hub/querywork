# Research-guided outcome review upgrade

Implemented 7 November 2026, from the approved PROMPT-UPGRADE-DRAFT.md.

## Behavior

- New versioned generator and grader prompts follow role, task, guidelines and examples. Historical prompts and scores are preserved.
- Page-labelled passages from all three supplied PDFs reach the generator and round reviewer. Each round records passages and extraction hashes. Original PDFs and full text extractions remain in references/search-guides. Local paths alone are never presented as readable model attachments.
- Automatic rounds now run search, isolated grading, outcome self-review, then refinement. The final round is reviewed too. Next-batch feedback contains the previous completed outcome review.
- The reviewer checks each completed query and every returned result, citing source excerpts. It cannot change independent grades. A supported grading disagreement triggers one isolated regrade; unresolved disagreements are held out of best-query acceptance.
- Unsupported reviewer quotations are removed, the affected assessment is marked incomplete, and warnings are shown. Unsupported disputes cannot trigger regrading. The narrative diagnosis remains advisory, not verified evidence.
- Failed reviews preserve evidence. A retry checks cached results before generating another batch, without repeating their searches.
- Workbench: expand Round outcome checks for findings, per-result assessments, missing criteria, next tests, reference pages and estimated review cost. JSON exports retain full records.

## Models and limits

Query generation: configured generator (gpt-6.1-sol in the live test), high reasoning.
Outcome review: same model, medium reasoning, compact requirement codes converted back to readable criteria after validation, 240-second request timeout.
Independent grader: configured grader (gpt-4o-mini in the live test), with only outcome, requirements, evaluation date, duplicate policy and returned evidence.

Outcome review uses search excerpts capped at 4000 characters per result. It does not open source pages. Independent grades remain rubric assessments rather than verified purchasing intent.

## Local verification

- 23 regression tests passed; production TypeScript/Vite build passed.
- Tests cover references from all three documents, review evidence inputs, quote validation, review feedback reaching the next batch, final-round review, isolated dispute rechecks, holding unresolved disputes, and stopping/recovering after review failure without repeated searches.
- Desktop and mobile headless browser checks passed against the running app using fictional demo data. No mobile horizontal overflow. Screenshots: ../querywork-research-review-desktop.png and ../querywork-research-review-mobile.png.
- In-app browser automation could not initialize; the visual checks used a separate headless Chrome browser.

## Live test protocol and recovery

New experiment: 24bd18aa2ab74793aa96162e687d0a17.
Original query: sport teams about to start their tournament.
Same revised prospect goal; explicit upcoming-event cutoff updated from 30 October to 7 November 2026. Printing demand is not required. Mandatory requirements remain team/league identity, regional/national/international tournament, explicit future start date, and participant/organizer relationship.

Target: 80. Combined budget: ten actual searches over two rounds. Round one includes the original baseline plus five generated queries; round two can search four new queries. The fifth generated term is budget-skipped.

The initial whole-round review exceeded the original 90-second provider timeout. A retry with more time exhausted the high-reasoning response allowance. Medium reasoning and compact labels returned a report, exposing non-exact review quotes. Quote validation was changed to conservative warnings and incomplete assessments rather than accepting those quotes or aborting the whole round. Reviews were retried against the same six cached searches; these recovery attempts made no extra search calls.

Known usage from failed model responses is included in the test estimate where available. Timed-out requests can have provider-side charges without returned usage, so the estimate is not an invoice or a guaranteed spending ceiling.

Final live results will be recorded below after both outcome checks finish. The detailed credential-free record is data/research-upgrade-report.json; test metadata and prompt snapshots are in data/research-upgrade-test.json.


## Final live results

- Completed: ten actual searches, two rounds, 100 returned-result checks. Both round reviews completed; the second batch contains the first review as feedback. All retained review quotes were checked against their corresponding source excerpts.
- Batch bests: 43.3 then 60.0 (+16.7). Best retained: 60.0. Target 80 was not reached; the search budget stopped the run.
- Best query: `US Youth Futsal Atlantic Championships January 2027 accepted teams`. Independent grader counted five grade-3 results and four uncertain results. These are automated judgments, not independently verified leads.
- The final self-check explicitly warns that named hosts are not yet established as leagues, and no named team participation was confirmed. The 60 score must not be presented as verified prospect accuracy. This remains an evidence gap to resolve.
- Unsupported self-review quotations were flagged: 18 warnings in round one, nine in round two. Those quotes/disputes were not accepted as evidence or used to change grades. The narrative review remains advisory.
- Known estimated API cost: $0.811617 including recoverable usage for failed review attempts. Timeouts may have unreported provider charges.
- Structured assertions passed for all query/result coverage, retained exact quotes, all three reference documents, feedback propagation, and an empty final next-batch queue.
