"""Read the approved Sol benchmark's local records and save a credential-free report."""
import json
import sqlite3
import time
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
config_path=ROOT/(sys.argv[1] if len(sys.argv)>1 else 'data/sol-test-config.json')
output_path=ROOT/(sys.argv[2] if len(sys.argv)>2 else 'data/sol-live-report.json')
meta=json.loads(config_path.read_text())
milestones={}
last=None

def sol_cost(usage):
    details=usage.get('prompt_tokens_details',{})
    cached=details.get('cached_tokens',0)
    writes=details.get('cache_write_tokens',0)
    plain=max(0,usage.get('prompt_tokens',0)-cached-writes)
    return (plain*2+cached*.1+writes*2.5+usage.get('completion_tokens',0)*10)/1_000_000

for _ in range(240):
    with sqlite3.connect(ROOT/'data/querywork.sqlite3') as db:
        e=json.loads(db.execute("select body from records where kind='experiment' and id=?",(meta['experiment_id'],)).fetchone()[0])
        j=json.loads(db.execute("select body from records where kind='job' and id=?",(meta['job_id'],)).fetchone()[0])
    state=e['optimization']
    rounds=[r for r in e['rounds'] if r.get('optimization_id')==meta['job_id']]
    scores=[q['evaluation']['score'] for r in rounds for q in r['queries'] if q.get('status')=='complete']
    best_new=max(scores) if scores else None
    elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(j['created'])).total_seconds()
    for score in (60,70,80):
        if best_new is not None and best_new>=score:milestones.setdefault(str(score),round(elapsed,1))
    progress=dict(status=j['status'],stage=j['stage'],new_rounds=state['new_rounds'],searches=state['searches'],best_new=best_new,best_retained=state['best']['score'] if state['best'] else None,
                  batches=[[q.get('evaluation',{}).get('score') for q in r['queries']] for r in rounds],elapsed_seconds=round(elapsed,1))
    signature=(j['status'],state['new_rounds'],state['searches'],len(scores))
    if signature!=last:
        print(json.dumps(progress),flush=True);last=signature
    final=j['status'] not in ('queued','running')
    if final:
        progress['elapsed_seconds']=round((datetime.fromisoformat(j['finished'])-datetime.fromisoformat(j['created'])).total_seconds(),1)
    report=dict(**progress,experiment_id=e['id'],job_id=j['id'],stop_reason=state.get('stop_reason'),target=state['target'],models=state.get('models'),
                previous_best=meta.get('previous_best'),milestone_observed_seconds=milestones,
                estimated_generator_cost_usd=round(sum(sol_cost(r['generator_usage']) for r in rounds),6),
                estimated_search_and_grader_cost_usd=round(sum(q.get('estimated_cost_usd') or 0 for r in rounds for q in r['queries']),6),
                best=state['best'],rounds=rounds,error=j.get('error'))
    output_path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    if final:break
    time.sleep(5)
