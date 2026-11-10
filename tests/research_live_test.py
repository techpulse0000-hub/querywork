"""Bounded user-authorized research upgrade smoke test. Never prints secrets."""
import json
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
META=ROOT/'data/research-upgrade-test.json'
REPORT=ROOT/'data/research-upgrade-report.json'
token=(ROOT/'data/api-token').read_text().strip()

def api(path,body=None):
    request=Request('http://127.0.0.1:8766/api/v1'+path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    with urlopen(request,timeout=120) as response:return json.load(response)

if '--start' in sys.argv:
    api('/config/validate',{})
    old=api('/experiments/5e2b44c4eca04ba0b8948a33972da590')
    e=api('/experiments',dict(original_search=old['original_search'],
        outcome=old['outcome'].replace('2026-10-30','2026-11-07'),
        requirements=[r.replace('2026-10-30','2026-11-07') for r in old['requirements']],mode='live'))
    prompts=api('/prompts')
    selected={role:next(p for p in prompts if p['role']==role and p['name']=='Research-guided v4 - evidence review - '+role) for role in ('generator','grader')}
    job=api('/experiments/'+e['id']+'/optimize',dict(idempotency_key='research-upgrade-2026-11-07',
        target_score=80,batch_size=5,max_queries=10,max_rounds=2,
        prompt_id=selected['generator']['id'],grader_prompt_id=selected['grader']['id']))
    META.write_text(json.dumps(dict(experiment_id=e['id'],job_id=job['id'],models=e['models'],prompts=selected),indent=2),encoding='utf-8')
    print(json.dumps(dict(experiment_id=e['id'],job_id=job['id'],max_searches=10,max_rounds=2)),flush=True)

meta=json.loads(META.read_text(encoding='utf-8'))
if '--resume' in sys.argv:
    api('/config/validate',{})
    diagnostic=json.loads((ROOT/'data/generator-provider-status.json').read_text())
    if diagnostic.get('finish_reason') in ('length','stop'):
        usage=diagnostic.get('usage',{});details=usage.get('prompt_tokens_details',{})
        cached=details.get('cached_tokens',0);writes=details.get('cache_write_tokens',0)
        previous=meta.get('known_failed_review_cost_usd',0) if usage!=meta.get('failed_review_usage') else 0
        meta['known_failed_review_cost_usd']=previous+(max(0,usage.get('prompt_tokens',0)-cached-writes)*2+cached*.1+writes*2.5+usage.get('completion_tokens',0)*10)/1e6
        meta['failed_review_usage']=usage
    job=api('/experiments/'+meta['experiment_id']+'/optimize',dict(idempotency_key='research-upgrade-review-recovery-quotes-2026-11-07',
        target_score=80,batch_size=5,max_queries=4,max_rounds=1,
        prompt_id=meta['prompts']['generator']['id'],grader_prompt_id=meta['prompts']['grader']['id']))
    meta['previous_job_id']=meta['job_id'];meta['job_id']=job['id']
    META.write_text(json.dumps(meta,indent=2),encoding='utf-8')
last=None
for _ in range(360):
    job=api('/jobs/'+meta['job_id']);e=api('/experiments/'+meta['experiment_id'])
    rounds=e['rounds'];state=e.get('optimization',{})
    costs=meta.get('known_failed_review_cost_usd',0)+sum((r.get('generator_estimated_cost_usd') or 0)+(r.get('review_estimated_cost_usd') or 0)+
              sum(q.get('estimated_cost_usd') or 0 for q in r['queries']) for r in rounds)
    progress=dict(status=job['status'],stage=job['stage'],searches=state.get('searches'),
                  cumulative_searches=sum('results' in q for r in rounds for q in r['queries']),
                  best=state.get('best'),rounds=len(rounds),
                  reviews=[r.get('outcome_review_status') for r in rounds],estimated_cost_usd=round(costs,6))
    signature=(job['status'],job['stage'],str(progress['reviews']))
    if signature!=last:print(json.dumps(progress),flush=True);last=signature
    REPORT.write_text(json.dumps(dict(**progress,experiment_id=e['id'],job_id=job['id'],
        stop_reason=state.get('stop_reason'),comparisons=state.get('comparisons'),round_details=rounds),indent=2),encoding='utf-8')
    if job['status'] not in ('queued','running'):break
    time.sleep(5)
