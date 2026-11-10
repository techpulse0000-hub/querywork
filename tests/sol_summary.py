"""Consolidate the approved bounded benchmark, including any interrupted phase."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

root=Path(__file__).resolve().parents[1]
meta=json.loads((root/'data/sol-test-config.json').read_text())
phase1=root/'data/sol-live-phase1.json'
reports=([json.loads(phase1.read_text(encoding='utf-8'))] if phase1.exists() else [])
reports.append(json.loads((root/'data/sol-live-report.json').read_text(encoding='utf-8')))
rounds=[r for report in reports for r in report['rounds']]
queries=[q for r in rounds for q in r['queries']]
complete=[q for q in queries if q.get('status')=='complete']
with sqlite3.connect(root/'data/querywork.sqlite3') as db:
    jobs=[json.loads(db.execute("select body from records where kind='job' and id=?",(r['job_id'],)).fetchone()[0]) for r in reports]
elapsed=None
if jobs[-1].get('finished'):
    elapsed=round((datetime.fromisoformat(jobs[-1]['finished'])-datetime.fromisoformat(jobs[0]['created'])).total_seconds(),1)
summary=dict(models=reports[-1]['models'],status=reports[-1]['status'],target=80,
             total_new_searches=sum(r['searches'] for r in reports),new_batches=len(rounds),
             best_new=max((q['evaluation']['score'] for q in complete),default=None),
             best_retained=reports[-1]['best_retained'],baseline_best=meta['previous_best'],
             total_elapsed_seconds=elapsed,
             known_estimated_cost_usd=round(sum(r['estimated_generator_cost_usd']+r['estimated_search_and_grader_cost_usd'] for r in reports),6),
             cost_note='Known saved usage only; an interrupted generation request may have unrecorded billable usage. Provider invoices are authoritative.',
             batches=[dict(batch=i+1,best=max((q['evaluation']['score'] for q in r['queries'] if q.get('status')=='complete'),default=None),
                           searches=sum('results' in q for q in r['queries']),strategy=r['strategy']) for i,r in enumerate(rounds)],
             phase_job_ids=[r['job_id'] for r in reports])
(root/'data/sol-benchmark-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
lines=['# GPT-6.1 Sol live search comparison','',
       'Same saved sports-team goal, requirements, grader and Tavily settings. Generator model and prompts changed together, so this tests their combined effect.','',
       '- Generator: GPT-6.1 Sol, high reasoning. Grader: GPT-4o mini.',
       '- Target: 80. Approved limit: eight batches / 40 new searches.',
       f'- Completed status: {summary["status"]}; new searches: {summary["total_new_searches"]}; batches: {summary["new_batches"]}.',
       f'- Best new score: {summary["best_new"]}. Previous best: {summary["baseline_best"]}. Retained best: {summary["best_retained"]}.',
       f'- End-to-end elapsed: {elapsed} seconds, including the interruption and recovery.',
       f'- Estimated cost from saved usage: ${summary["known_estimated_cost_usd"]:.4f}. '+summary['cost_note'],'',
       '| New batch | Best query score | Retrieved queries | Strategy |','|---|---:|---:|---|']
lines.extend(f'| {r["batch"]} | {r["best"]} | {r["searches"]} | {r["strategy"]} |' for r in summary['batches'])
lines+=['','Full exact old/new prompts: [PROMPT-CHANGELOG.md](PROMPT-CHANGELOG.md).',
        'Full evidence and model usage remain in the local database and data/sol-live-phase1.json plus data/sol-live-report.json.','',
        'Limitations: scores assess search excerpts over ten result slots, with missing results scoring zero. Focused entity searches can therefore score low even when useful for discovery. The unchanged explicit requirements name teams and tournament dates; those alone do not establish printing demand. This run does not independently validate the grader or the completeness of public evidence.']
(root/'SOL-BENCHMARK.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps(summary))
