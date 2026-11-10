"""Explicit, bounded paid-provider check; run only after configuring credentials."""
import argparse
import json
import time
from pathlib import Path
import httpx

parser=argparse.ArgumentParser()
parser.add_argument('--live', action='store_true', help='Authorize one generated batch and four live searches/grades')
parser.add_argument('--experiment-id', help='Resume unfinished grading in an existing live experiment, reusing saved evidence')
args=parser.parse_args()
if not args.live:
    parser.error('Pass --live to explicitly run the paid-provider test')
root=Path(__file__).resolve().parents[1]
token=(root/'data/api-token').read_text().strip()
client=httpx.Client(base_url='http://127.0.0.1:8766/api/v1',headers={'Authorization':'Bearer '+token},timeout=120)
def request(method,path,body=None):
    r=client.request(method,path,json=body)
    if r.is_error:
        raise RuntimeError(f'API returned {r.status_code}: {r.text[:300]}')
    return r.json()
request('POST','/config/validate',{})
e=request('GET','/experiments/'+args.experiment_id) if args.experiment_id else request('POST','/experiments',dict(original_search='reusable food container wholesale suppliers Lagos',
    outcome='Find wholesale suppliers of reusable food containers with a physical business location in Lagos and a public business contact route.',
    requirements=['Sells reusable food containers wholesale','Has a physical business location in Lagos','Has a public business contact route'],mode='live'))
if e['mode']!='live':
    raise RuntimeError('Live smoke check requires a live experiment')
for operation in (('run',) if e['rounds'] else ('generate','run')):
    suffix=('-resume-'+str(time.time_ns())) if args.experiment_id else ''
    job=request('POST',f'/experiments/{e["id"]}/{operation}',{'idempotency_key':'live-smoke-'+operation+suffix})
    deadline=time.monotonic()+1500
    while time.monotonic()<deadline:
        state=request('GET','/jobs/'+job['id'])
        if state['status'] not in ('queued','running'):
            if state['status']!='complete':
                raise RuntimeError(f'{operation}: {state["status"]}: {state["stage"]}; inspect experiment {e["id"]}')
            break
        time.sleep(1)
    else:
        raise RuntimeError('Observation deadline reached; job may still be running. Inspect it before retrying.')
report=request('GET','/experiments/'+e['id'])
queries=report['rounds'][0]['queries']
assert len(queries)==4 and all(q['status']=='complete' for q in queries)
(root/'data/live-smoke-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Live provider workflow completed. Experiment:',e['id'])
for q in queries:
    print(q['text'], '=>', q['evaluation']['score'], '/ 100;', q['evaluation']['qualified'], 'qualifying results')
print('Evidence and prompt versions are saved in data/live-smoke-report.json and experiment history.')
