# GPT-6.1 Sol live search comparison

Same saved sports-team goal, requirements, grader and Tavily settings. Generator model and prompts changed together, so this tests their combined effect.

- Generator: GPT-6.1 Sol, high reasoning. Grader: GPT-4o mini.
- Target: 80. Approved limit: eight batches / 40 new searches.
- Completed status: complete; new searches: 40; batches: 8.
- Best new score: 66.7. Previous best: 56.7. Retained best: 66.7.
- End-to-end elapsed: 1279.7 seconds, including the interruption and recovery.
- Estimated cost from saved usage: $0.9599. Known saved usage only; an interrupted generation request may have unrecorded billable usage. Provider invoices are authoritative.

| New batch | Best query score | Retrieved queries | Strategy |
|---|---:|---:|---|
| 1 | 33.3 | 5 | refine_and_explore |
| 2 | 30.0 | 5 | refine_and_explore |
| 3 | 16.7 | 5 | pivot_to_new_sources_and_intent_signals |
| 4 | 20.0 | 5 | refine_and_explore |
| 5 | 56.7 | 5 | refine_and_explore |
| 6 | 66.7 | 5 | pivot_to_new_sources_and_intent_signals |
| 7 | 23.3 | 5 | refine_and_explore |
| 8 | 23.3 | 5 | refine_and_explore |

Full exact old/new prompts: [PROMPT-CHANGELOG.md](PROMPT-CHANGELOG.md).
Full evidence and model usage remain in the local database and data/sol-live-phase1.json plus data/sol-live-report.json.

Limitations: scores assess search excerpts over ten result slots, with missing results scoring zero. Focused entity searches can therefore score low even when useful for discovery. The unchanged explicit requirements name teams and tournament dates; those alone do not establish printing demand. This run does not independently validate the grader or the completeness of public evidence.

## Evidence audit and conclusion

The winning new query was `"Hackettstown Tigers" ("jerseys" OR "screen printing") "2026"`. The frozen grader assigned 66.7 and marked five results qualifying. Manual inspection of its leading excerpts showed team schedules, scores and athletics websites, rather than explicit requests for jersey printing. Some excerpts refer to already completed events. Multiple pages also describe the same organization. Therefore the score improvement is a rubric result, not 66.7% accuracy or five verified distinct buyers.

The generator now performs named-entity follow-up, and the best score rose by 10 points on test batch six. It did not reach 70 or 80. No speed improvement is established. Before using these scores to promise lead quality, the grader needs explicit evidence for printing demand, a future tournament start date relative to the test date, and stronger entity deduplication. Those were deliberately not changed during this comparison.

One generation operation failed after three batches; the remaining five batches were resumed separately without repeating searches or exceeding the 40-search ceiling. The original failure did not retain enough provider diagnostics to determine its cause; explicit empty-output diagnostics are now present. The app therefore shows separate optimization runs, while this report combines the eight test batches.
