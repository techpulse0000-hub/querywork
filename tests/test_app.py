import os
import tempfile
import time
os.environ['QUERYWORK_DATA'] = tempfile.mkdtemp(prefix='querywork-test-')
from fastapi.testclient import TestClient
from backend import app as service, engine
import pytest

@pytest.fixture
def client():
    with TestClient(service.app, headers={'Authorization': 'Bearer ' + service.TOKEN}) as c:
        yield c

def wait(c, job):
    for _ in range(200):
        j = c.get('/api/v1/jobs/' + job['id']).json()
        if j['status'] not in ('queued', 'running'):
            return j
        time.sleep(.01)
    raise AssertionError('Job did not finish')

def case(c):
    r = c.post('/api/v1/experiments', json=dict(original_search='find suppliers', outcome='Find reusable container suppliers in Lagos', requirements=['Wholesale', 'Lagos'], mode='demo'))
    assert r.status_code == 201
    return r.json()

def action(c, e, op, key, **kwargs):
    r = c.post(f'/api/v1/experiments/{e["id"]}/{op}', json=dict(idempotency_key=key, **kwargs))
    assert r.status_code == 202, r.text
    return r.json()

def test_full_workflow_persistence_idempotency_and_exports(client, monkeypatch):
    c = client
    e = case(c)
    j = action(c,e,'generate','generate-1')
    assert wait(c,j)['status'] == 'complete'
    assert action(c,e,'generate','generate-1')['id'] == j['id']
    e = c.get('/api/v1/experiments/'+e['id']).json()
    assert len(e['rounds']) == 1 and len(e['rounds'][0]['queries']) == 4
    j = action(c,e,'run','run-1')
    assert wait(c,j)['status'] == 'complete'
    e = c.get('/api/v1/experiments/'+e['id']).json()
    scores = [q['evaluation']['score'] for q in e['rounds'][0]['queries']]
    assert scores == sorted(scores) and len(set(scores)) > 1
    monkeypatch.setattr(engine,'search',lambda *args: (_ for _ in ()).throw(AssertionError('Regrade must not search')))
    assert wait(c,action(c,e,'regrade','regrade-1'))['status'] == 'complete'
    assert service.get('experiment',e['id'])['rounds'][0]['queries'][0]['results']
    assert c.get(f'/api/v1/experiments/{e["id"]}/export/json').status_code == 200
    assert 'evidence_mode' in c.get(f'/api/v1/experiments/{e["id"]}/export/csv').text
    assert wait(c,action(c,e,'refine','refine-1',feedback='Require clearer product evidence'))['status'] == 'complete'
    monkeypatch.undo()
    assert wait(c,action(c,e,'run','run-refined'))['status'] == 'complete'
    assert wait(c,action(c,e,'refine','refine-2',feedback='Try more synonyms'))['status'] == 'complete'
    assert c.post(f'/api/v1/experiments/{e["id"]}/refine',json={'idempotency_key':'too-many','feedback':'Again'}).status_code == 409

def test_grader_allowlist_and_evidence_validation():
    e = dict(outcome='Find supplier',requirements=['Lagos'],original_search='SECRET QUERY',feedback='SECRET CONTEXT')
    results=[dict(id='r1',rank=1,title='Supplier',url='https://example.com',content='Located in Lagos',score=.99)]
    text=str(engine.grading_input(e,results))
    assert 'SECRET' not in text and 'score' not in text and 'feedback' not in text
    response={'judgments':[dict(id='r1',grade=3,entity='Supplier',reason='Match',criteria=[dict(requirement='Lagos',status='pass',quote='Invented quote')])]}
    checked=engine.validate_grades(e,results,response)
    assert checked['qualified']==0 and checked['uncertain']==1
    assert checked['judgments'][0]['grade']<=2
    assert checked['judgments'][0]['criteria'][0]['status']=='unknown'
    assert checked['judgments'][0]['criteria'][0]['quote']==''
    response['judgments'][0]['criteria'][0].update(status='unknown',quote='')
    assert engine.validate_grades(e,results,response)['qualified'] == 0
    response['judgments'][0]['criteria'][0].update(status='fail',quote='Lagos')
    assert engine.validate_grades(e,results,response)['score'] == 0

def test_empty_vs_failure_and_retry_without_repeat_search(client, monkeypatch):
    c=client;e=case(c);wait(c,action(c,e,'generate','g'))
    calls=[]
    def search(e,q,i):
        calls.append(i)
        if i==0:return [],{}
        if i==1:raise RuntimeError('network')
        return [dict(id='r1',rank=1,title='Demo',url='https://example.com',content='Unknown')],{}
    monkeypatch.setattr(engine,'search',search)
    assert wait(c,action(c,e,'run','r'))['status']=='partial'
    data=c.get('/api/v1/experiments/'+e['id']).json()['rounds'][0]['queries']
    assert data[0]['evaluation']['score']==0 and data[0]['status']=='complete'
    assert data[1]['status']=='search_failed' and 'evaluation' not in data[1]
    assert wait(c,action(c,e,'run','retry'))['status']=='partial'
    assert calls.count(0)==1 and calls.count(1)==2

def test_auth_origin_live_config_and_prompt_versions(client):
    with TestClient(service.app) as anonymous:
        assert anonymous.get('/api/v1/experiments').status_code==401
    assert client.get('/api/v1/config',headers={'origin':'https://attacker.example'}).status_code==403
    before=client.get('/api/v1/prompts').json()
    p=client.post('/api/v1/prompts',json=dict(role='generator',name='Changed',system='New instructions',user_template='{outcome}')).json()
    assert p['id'] not in {x['id'] for x in before}
    assert all(service.get('prompt',x['id'])==x for x in before)
    e=client.post('/api/v1/experiments',json=dict(original_search='x',outcome='y',mode='live')).json()
    assert client.post(f'/api/v1/experiments/{e["id"]}/generate',json={'idempotency_key':'live'}).status_code==400

def test_restart_marks_jobs_interrupted(client):
    j=service.save('job',dict(id=service.ident(),status='running',experiment_id='restart-test',key='restart'))
    with TestClient(service.app):
        pass
    assert service.get('job',j['id'])['status']=='interrupted'

def test_duplicate_results_do_not_inflate_score():
    e={'outcome':'Supplier','requirements':[]}
    r=[dict(id='a',rank=1,title='A',url='https://example.com/a',content='Supplier'),dict(id='b',rank=2,title='B',url='https://example.com/b',content='Supplier')]
    result=engine.validate_grades(e,r,{'judgments':[dict(id=x['id'],grade=3,entity='Same business',criteria=[]) for x in r]})
    assert result['qualified']==1 and result['score']==10

def test_live_pipeline_with_mocked_http_providers(client, monkeypatch):
    for key in ('OPENAI_API_KEY','TAVILY_API_KEY','GENERATOR_MODEL','GRADER_MODEL'):
        monkeypatch.setenv(key,'test-'+key)
    tavily_calls=[]; grader_requests=[]
    def provider(method,url,**kwargs):
        if method=='GET':return {}
        body=kwargs['json']
        if 'tavily' in url:
            tavily_calls.append(body)
            return {'results':[{'url':'https://supplier.example/catalog','title':'Supplier','content':'Wholesale supplier located in Lagos','score':.987}], 'usage':{'credits':1}}
        prompt=body['messages'][-1]['content']
        if body['model']=='test-GENERATOR_MODEL':
            return {'choices':[{'message':{'content':'{"queries":[{"text":"term A","note":"A"},{"text":"term B","note":"B"},{"text":"term C","note":"C"}]}'}}], 'usage':{'total_tokens':30}}
        grader_requests.append(body)
        return {'choices':[{'message':{'content':'{"judgments":[{"id":"r1","grade":3,"entity":"Supplier","reason":"Explicit evidence","criteria":[{"requirement":"Lagos","status":"pass","quote":"located in Lagos"}]}],"summary":"One candidate"}'}}], 'usage':{'total_tokens':50}}
    monkeypatch.setattr(engine,'request',provider)
    assert client.post('/api/v1/config/validate').status_code==200
    e=client.post('/api/v1/experiments',json={'original_search':'SECRET BASELINE','outcome':'Find a wholesale supplier','requirements':['Lagos'],'mode':'live'}).json()
    assert wait(client,action(client,e,'generate','live-gen'))['status']=='complete'
    assert wait(client,action(client,e,'run','live-run'))['status']=='complete'
    assert len(tavily_calls)==4 and len(grader_requests)==4
    assert all({k:v for k,v in call.items() if k!='query'}==engine.SEARCH_SETTINGS for call in tavily_calls)
    for body in grader_requests:
        assert len(body['messages'])==2
        text=body['messages'][-1]['content']
        assert 'SECRET BASELINE' not in text and 'term A' not in text and '0.987' not in text
        assert set(__import__('json').loads(text))=={'outcome','requirements','evaluation_date','duplicate_policy','evidence_mode','results'}

def test_cancellation_retains_retrieved_evidence_and_no_more_calls(client,monkeypatch):
    import threading
    c=client;e=case(c);wait(c,action(c,e,'generate','g'))
    entered=threading.Event();release=threading.Event();calls=[]
    def blocked_search(exp,q,index):
        calls.append(index);entered.set();release.wait(5)
        return [dict(id='r1',rank=1,title='Evidence',url='https://example.com',content='Saved evidence')],{}
    monkeypatch.setattr(engine,'search',blocked_search)
    j=action(c,e,'run','r');assert entered.wait(5)
    c.post('/api/v1/jobs/'+j['id']+'/cancel');release.set()
    assert wait(c,j)['status']=='canceled'
    data=c.get('/api/v1/experiments/'+e['id']).json()
    assert calls==[0] and data['rounds'][0]['queries'][0]['results'][0]['content']=='Saved evidence'
    assert data['job_states'][-1]['status']=='canceled'

def test_session_credentials_are_not_returned_or_persisted(client,monkeypatch):
    for name in ('OPENAI_API_KEY','TAVILY_API_KEY','GENERATOR_MODEL','GRADER_MODEL'):
        monkeypatch.setenv(name,'')
    response=client.post('/api/v1/config/session',json={'openai_key':'private-openai-test-key','tavily_key':'private-tavily-test-key','generator_model':'test-generator','grader_model':'test-grader'})
    assert response.status_code==200 and response.json()['ready']
    assert 'private-' not in response.text
    assert client.get('/api/v1/config').json()['openai_configured']
    assert 'private-' not in client.get('/api/v1/config').text
    assert 'private-' not in str(service.all_records('settings'))
    response=client.post('/api/v1/config/session',json={'generator_model':'changed','grader_model':'test-grader'})
    assert response.status_code==200 and os.environ['OPENAI_API_KEY']=='private-openai-test-key'

def test_environment_save_preserves_values_and_survives_reload(client,monkeypatch,tmp_path):
    from dotenv import dotenv_values
    env_file=tmp_path/'.env'
    env_file.write_text('UNRELATED=value\nTAVILY_API_KEY=existing-tavily\n',encoding='utf-8')
    monkeypatch.setattr(service,'ENV_FILE',env_file)
    for name in ('OPENAI_API_KEY','TAVILY_API_KEY','GENERATOR_MODEL','GRADER_MODEL','UNRELATED'):
        monkeypatch.setenv(name,'')
    response=client.post('/api/v1/config/environment',json={'openai_key':'private-persistent-key'})
    assert response.status_code==200 and response.json()['saved']
    assert 'private-persistent-key' not in response.text
    values=dotenv_values(env_file)
    assert values['OPENAI_API_KEY']=='private-persistent-key' and values['TAVILY_API_KEY']=='existing-tavily'
    assert values['UNRELATED']=='value' and os.environ['OPENAI_API_KEY']=='private-persistent-key'
    response=client.post('/api/v1/config/environment',json={'generator_model':'generator','grader_model':'grader'})
    assert response.json()['ready'] and dotenv_values(env_file)['OPENAI_API_KEY']=='private-persistent-key'
    before=env_file.read_text()
    assert client.post('/api/v1/config/environment',json={'tavily_key':'bad\nINJECTED=secret'}).status_code==422
    assert env_file.read_text()==before

def test_pricing_and_gpt4o_mini_request(client,monkeypatch,tmp_path):
    monkeypatch.setattr(service,'ENV_FILE',tmp_path/'.env')
    for name in ('OPENAI_API_KEY','INPUT_USD_PER_MILLION','OUTPUT_USD_PER_MILLION','TAVILY_USD_PER_CREDIT','GENERATOR_MODEL','GRADER_MODEL'):
        monkeypatch.setenv(name,'')
    payload={'generator_model':'gpt-4o-mini','grader_model':'gpt-4o-mini','input_usd_per_million':.15,'output_usd_per_million':.60,'tavily_usd_per_credit':.008}
    response=client.post('/api/v1/config/environment',json=payload)
    assert response.status_code==200
    assert response.json()['tavily_usd_per_credit']=='0.008'
    assert engine.estimated_cost({'prompt_tokens':1000,'completion_tokens':1000},1)==.00875
    assert client.post('/api/v1/config/environment',json={'tavily_usd_per_credit':-1}).status_code==422
    requests=[]
    def provider(method,url,**kwargs):
        requests.append(kwargs['json'])
        return {'choices':[{'message':{'content':'{}'}}],'usage':{}}
    monkeypatch.setattr(engine,'request',provider)
    engine.completion('gpt-4o-mini','Instructions','Task')
    assert requests[0]['model']=='gpt-4o-mini'
    assert requests[0]['messages'][0]['role']=='system'
    assert 'reasoning_effort' not in requests[0]

def test_sol_generator_reasoning_prompt_and_usage(monkeypatch):
    import json
    seen=[]
    def provider(method,url,**kwargs):
        seen.append(kwargs['json'])
        return {'choices':[{'message':{'content':json.dumps({'queries':[dict(text=f'query {i}',note='Test candidate',stage='verification',evidence_sought='Printing tender',target='Example team') for i in range(5)]})}}],
                'usage':{'prompt_tokens':1000,'completion_tokens':2000}}
    monkeypatch.setattr(engine,'request',provider)
    exp=dict(mode='live',models={'generator':'gpt-6.1-sol'},original_search='sports teams',outcome='Find printing buyers',requirements=['Team name'],
             feedback={'stage':'discovery_and_verification','discovered_entities':[{'entity':'Example team','url':'https://example.com'}]})
    terms,usage=engine.generate(exp,dict(system=engine.GENERATOR,user_template=engine.TEMPLATE),count=5)
    body=seen[0]
    assert body['reasoning_effort']=='high' and body['max_completion_tokens']==12000
    assert body['messages'][0]['role']=='developer'
    user=body['messages'][1]['content']
    assert 'Example team' in user and 'Generate 5 distinct queries' in user
    assert '{current_date}' not in user and '{stage}' not in user
    assert terms[0]['stage']=='verification' and terms[0]['target']=='Example team'
    assert usage['model']=='gpt-6.1-sol'
    assert engine.estimated_cost(usage)==.022
    assert engine.estimated_cost(dict(model='gpt-6.1-sol',prompt_tokens=1000,completion_tokens=1000,
                                     prompt_tokens_details={'cached_tokens':400,'cache_write_tokens':300}))==.01139
    monkeypatch.setattr(engine,'request',lambda *a,**kw:{'choices':[{'finish_reason':'length','message':{'content':None}}],'usage':{}})
    with pytest.raises(ValueError,match='finish reason: length'):
        engine.completion('gpt-6.1-sol','Instructions','Task')


def test_grader_schema_and_wrong_shape_rejected():
    e={'requirements':['Location'],'outcome':'Find a supplier'}
    r=[{'id':'r1','rank':1,'title':'Supplier','url':'https://example.com','content':'Location'}]
    with pytest.raises(ValueError,match='Criteria must be an array'):
        engine.validate_grades(e,r,{'judgments':[{'id':'r1','grade':3,'criteria':{'Location':{'status':'pass'}}}]})
    schema=engine.grading_schema(r,e['requirements'])
    assert schema['additionalProperties'] is False
    assert schema['properties']['judgments']['required']==['r1']
    criterion=schema['properties']['judgments']['properties']['r1']['properties']['criteria']
    assert criterion['required']==['c0']
    assert criterion['properties']['c0']['properties']['requirement']['enum']==['Location']

def test_automatic_improvement_compares_rounds_and_retains_best(client,monkeypatch):
    c=client;e=case(c);generation=[];graded=[]
    scores=[40,60,50,92]
    def generate(exp,prompt,count=3):
        n=len(generation);generation.append(exp['feedback'])
        return [{'text':f'iteration {n} candidate {i}','note':'Explore stronger terms'} for i in range(count)],{}
    def search(exp,q,i):
        return [dict(id='r1',rank=1,title='Source',url='https://example.com',content=q['text'])],{}
    def grade(exp,results,prompt):
        graded.append(engine.grading_input(exp,results))
        content=results[0]['content'];n=int(content.split()[1]) if content.startswith('iteration') else 0
        return dict(score=scores[n],qualified=1,uncertain=0,summary='Test evaluation',judgments=[]),{}
    monkeypatch.setattr(engine,'generate',generate);monkeypatch.setattr(engine,'search',search);monkeypatch.setattr(engine,'grade',grade)
    j=action(c,e,'optimize','auto',target_score=90,batch_size=5,max_rounds=5,max_queries=30)
    assert wait(c,j)['status']=='complete'
    data=c.get('/api/v1/experiments/'+e['id']).json();state=data['optimization']
    assert state['stop_reason']=='target_reached' and state['best']['score']==92
    assert [r['batch_best'] for r in state['comparisons']]==[40,60,50,92]
    assert [r['best_so_far'] for r in state['comparisons']]==[40,60,60,92]
    assert state['searches']==21
    assert generation[1]['best'][0]['evaluation']['score']==40
    assert generation[3]['best'][0]['evaluation']['score']==60
    assert all(set(p)=={'outcome','requirements','evaluation_date','duplicate_policy','evidence_mode','results'} for p in graded)
    assert action(c,e,'optimize','auto')['id']==j['id']

def test_automatic_continues_past_five_rounds_and_keeps_winner(client,monkeypatch):
    c=client;e=case(c);packets=[]
    def generate(exp,prompt,count=3):
        n=len(packets);packets.append(exp['feedback'])
        return [dict(text=f'plan {n} approach {i}',note='Different retrieval strategy') for i in range(count)],{}
    def search(exp,q,i):
        return [dict(id='r1',rank=1,title='Source',url='https://example.com',content=q['text'])],{}
    def grade(exp,results,prompt):
        text=results[0]['content'];n=int(text.split()[1]) if text.startswith('plan') else 0
        return dict(score=94 if n==6 else 40,qualified=1,uncertain=0,summary='Evidence judgment',
                    judgments=[dict(id='r1',grade=1,entity='Example team',criteria=[dict(requirement='Wholesale',status='unknown',quote='')])]),{}
    monkeypatch.setattr(engine,'generate',generate)
    monkeypatch.setattr(engine,'search',search)
    monkeypatch.setattr(engine,'grade',grade)
    job=action(c,e,'optimize','continuous',target_score=93,max_queries=40)
    assert wait(c,job)['status']=='complete'
    state=c.get('/api/v1/experiments/'+e['id']).json()['optimization']
    assert state['max_rounds'] is None and state['new_rounds']==7
    assert state['target']==93 and state['searches']==36
    assert state['stop_reason']=='target_reached'
    assert [r['best_so_far'] for r in state['comparisons']]==[40]*6+[94]
    assert packets[3]['strategy']=='broaden_near_winner'
    assert packets[3]['focus']['score']==40
    assert packets[3]['allocation']=={'local_variations':3,'nearby_exploration':2}
    assert packets[3]['unresolved_requirements']['Wholesale']>0
    assert packets[3]['source_examples'][0]['sources'][0]['title']=='Source'
    assert packets[3]['stage']=='discovery_and_verification'
    assert packets[3]['discovered_entities'][0]['entity']=='Example team'
    assert state['comparisons'][1]['accepted_improvement'] is False
    assert state['comparisons'][-1]['accepted_improvement'] is True


def test_score_jump_focuses_next_batch_and_retains_anchor_on_ties(client,monkeypatch):
    c=client;e=case(c);packets=[]
    scores=[20,30,50,45,50,60,80]
    def generate(exp,prompt,count=3):
        n=len(packets);packets.append(exp['feedback'])
        return [dict(text=f'variant {n} query {i}',note='Controlled local change') for i in range(count)],{}
    def search(exp,q,i):
        return [dict(id='r1',rank=1,title='Official winning source',url='https://example.com/tournament',content=q['text'])],{}
    def grade(exp,results,prompt):
        text=results[0]['content'];n=int(text.split()[1]) if text.startswith('variant') else 0
        return dict(score=scores[n],qualified=1,uncertain=0,summary='Evidence judgment',
                    judgments=[dict(id='r1',grade=3,criteria=[dict(requirement='Wholesale',status='pass',quote=text)])]),{}
    monkeypatch.setattr(engine,'generate',generate);monkeypatch.setattr(engine,'search',search);monkeypatch.setattr(engine,'grade',grade)
    job=action(c,e,'optimize','winner-neighborhood',target_score=80,max_queries=40)
    assert wait(c,job)['status']=='complete'
    data=c.get('/api/v1/experiments/'+e['id']).json()
    assert [r['best_so_far'] for r in data['optimization']['comparisons']]==[20,30,50,50,50,60,80]
    assert packets[3]['strategy']=='exploit_winner'
    anchor=packets[3]['focus']['query_id']
    assert packets[3]['focus']['score']==50
    assert packets[3]['allocation']=={'local_variations':5,'nearby_exploration':0}
    assert packets[4]['focus']['query_id']==anchor
    assert packets[4]['allocation']=={'local_variations':4,'nearby_exploration':1}
    assert packets[5]['focus']['query_id']==anchor
    assert packets[5]['allocation']=={'local_variations':3,'nearby_exploration':2}
    assert packets[6]['focus']['score']==60
    assert packets[6]['focus']['query_id']!=anchor
    assert packets[6]['allocation']=={'local_variations':5,'nearby_exploration':0}
    assert packets[3]['focus']['strongest_sources'][0]['domain']=='example.com'
    assert data['rounds'][3]['anchor_query_id']==anchor
    assert data['rounds'][3]['variation_allocation']['local_variations']==5


def test_automatic_search_budget_and_demo_target(client):
    c=client;e=case(c)
    j=action(c,e,'optimize','limited',max_queries=2,max_rounds=5,batch_size=10,target_score=100)
    assert wait(c,j)['status']=='complete'
    state=c.get('/api/v1/experiments/'+e['id']).json()['optimization']
    assert state['stop_reason']=='query_limit' and state['searches']==2 and state['best']
    e=case(c);j=action(c,e,'optimize','demo',batch_size=5,max_rounds=5,target_score=90)
    assert wait(c,j)['status']=='complete'
    data=c.get('/api/v1/experiments/'+e['id']).json()
    assert data['optimization']['stop_reason']=='target_reached'
    assert data['optimization']['best']['score']>=90
    assert len(data['rounds'])>1

def test_automatic_cancel_and_restart_preserve_best(client,monkeypatch):
    import threading
    c=client;e=case(c);entered=threading.Event();release=threading.Event()
    real_search=engine.search
    def blocked(exp,q,i):
        if i==1:entered.set();release.wait(5)
        return real_search(exp,q,i)
    monkeypatch.setattr(engine,'search',blocked)
    j=action(c,e,'optimize','cancel-auto',max_rounds=3)
    assert entered.wait(5)
    c.post('/api/v1/jobs/'+j['id']+'/cancel');release.set()
    assert wait(c,j)['status']=='canceled'
    data=c.get('/api/v1/experiments/'+e['id']).json()
    assert data['optimization']['status']=='canceled' and data['optimization']['best']
    assert data['rounds'][0]['queries'][1]['results']
    data['optimization'].update(id='interrupted-auto',status='running',stop_reason=None)
    service.save('experiment',data)
    service.save('job',dict(id='interrupted-auto',status='running',operation='optimize',experiment_id=e['id'],key='interrupted-auto'))
    with TestClient(service.app):pass
    data=service.get('experiment',e['id'])
    assert data['optimization']['status']=='interrupted' and data['optimization']['best']

def test_invalid_optimizer_prompt_does_not_leave_a_queued_job(client):
    e=case(client);before=len(service.all_records('job'))
    wrong=next(p['id'] for p in client.get('/api/v1/prompts').json() if p['role']=='generator')
    response=client.post(f'/api/v1/experiments/{e["id"]}/optimize',json={'idempotency_key':'wrong-grader','grader_prompt_id':wrong})
    assert response.status_code==400 and len(service.all_records('job'))==before


def test_pdf_references_and_final_round_review_feed_next_batch(client,monkeypatch):
    from backend import research
    refs=research.select({'outcome':'Find teams with tournament start dates'})
    assert len({r['document'] for r in refs})==3
    assert all(r['page']>0 and r['text'] and len(r['extraction_sha256'])==64 for r in refs)
    assert any('Phrase searching' in r['text'] for r in refs)
    packets=[]
    original=engine.generate
    def generate(exp,prompt,count=3):
        packets.append(exp.get('feedback',{}))
        return original(exp,prompt,count)
    monkeypatch.setattr(engine,'generate',generate)
    e=case(client)
    job=action(client,e,'optimize','review-feedback',max_queries=10,max_rounds=2,target_score=100)
    assert wait(client,job)['status']=='complete'
    data=client.get('/api/v1/experiments/'+e['id']).json()
    assert len(data['rounds'])==2
    assert packets[1]['round_review']['per_query_checks']
    for r in data['rounds']:
        assert r['outcome_review_status']=='complete'
        expected={q['id']:len(q['results']) for q in r['queries'] if q['status']=='complete'}
        assert {q['query_id']:len(q['result_checks']) for q in r['outcome_review']['per_query_checks']}==expected
        assert len({ref['document'] for ref in r['research_references']})==3
    assert data['rounds'][-1]['outcome_review']['stop_summary']


def test_real_review_validates_quotes_and_receives_evidence_not_just_scores(monkeypatch):
    import json
    from backend import round_review, research
    exp=dict(mode='live',models={'generator':'gpt-6.1-sol'},outcome='Find teams',requirements=['Future start'],evaluation_date='2026-11-07')
    r=dict(id='round',queries=[dict(id='q1',text='team tournament',status='complete',evaluation={'score':70},
        results=[dict(id='r1',rank=1,title='Schedule',url='https://example.com',content='Team starts December 12, 2026.')])])
    seen=[]
    answer=dict(per_query_checks={'q1':dict(conclusion='Explicit future date',result_checks={'r1':dict(assessment='match',evidence_quotes=['starts December 12, 2026'],missing_requirements=[])})},
                winner_diagnosis='Schedule contains date.',grader_disagreements=[],next_tests=['Verify participation'],stop_summary='Excerpts only.')
    def complete(model,system,user,schema,**kwargs):
        seen.append(json.loads(user.split('\nUse the supplied')[0]))
        assert kwargs['timeout']==240
        assert kwargs['reasoning_effort']=='medium'
        return answer,{'model':model,'prompt_tokens':100,'completion_tokens':50}
    monkeypatch.setattr(engine,'completion',complete)
    report,usage=round_review.perform(exp,r,None,research.select(exp))
    assert seen[0]['queries'][0]['results'][0]['content']=='Team starts December 12, 2026.'
    assert len({ref['document'] for ref in seen[0]['references']})==3
    assert report['per_query_checks'][0]['result_checks'][0]['evidence_quotes']
    answer['per_query_checks']['q1']['result_checks']['r1']['evidence_quotes']=['Invented fact']
    checked,_=round_review.perform(exp,r,None,[])
    result=checked['per_query_checks'][0]['result_checks'][0]
    assert result['assessment']=='incomplete' and result['evidence_quotes']==[]
    assert checked['evidence_warnings']


def test_review_dispute_is_rechecked_without_review_context_and_held(client,monkeypatch):
    from backend import round_review
    calls=[]
    def grade(exp,results,prompt):
        calls.append(engine.grading_input(exp,results))
        return dict(score=100,qualified=1,uncertain=0,summary='Initial assessment',judgments=[dict(id=results[0]['id'],grade=3,
                    criteria=[dict(requirement='Wholesale',status='pass',quote='past date')])]),{}
    def review(exp,r,incumbent,refs,prompt=None):
        return dict(per_query_checks=[],winner_diagnosis='Incorrect timing',next_tests=[],stop_summary='Recheck required',
                    grader_disagreements=[dict(query_id=q['id'],result_id='r1',requirement='Wholesale',expected_status='fail',reason='Recheck this evidence',quote='past date') for q in r['queries'] if q.get('status')=='complete']),{}
    monkeypatch.setattr(engine,'grade',grade)
    monkeypatch.setattr(round_review,'perform',review)
    e=case(client)
    job=action(client,e,'optimize','dispute',max_queries=1,max_rounds=1,target_score=100)
    assert wait(client,job)['status']=='complete'
    data=client.get('/api/v1/experiments/'+e['id']).json()
    assert len(calls)==2 and 'grader_disagreements' not in str(calls)
    assert data['rounds'][0]['queries'][0]['status']=='review_disputed'
    assert data['rounds'][0]['queries'][0]['evaluation']['score']==100
    assert data['optimization']['best'] is None


def test_failed_outcome_review_stops_before_next_paid_batch(client,monkeypatch):
    from backend import round_review
    original_review=round_review.perform
    def fail(*args):raise ValueError('Review omitted result IDs')
    monkeypatch.setattr(round_review,'perform',fail)
    e=case(client)
    job=action(client,e,'optimize','failed-review',max_queries=20,max_rounds=3)
    assert wait(client,job)['status']=='failed'
    data=client.get('/api/v1/experiments/'+e['id']).json()
    assert len(data['rounds'])==1 and data['rounds'][0]['outcome_review_status']=='failed'
    assert data['rounds'][0]['queries'][0]['results']
    cached_ids={q['id'] for q in data['rounds'][0]['queries']}
    original_search=engine.search
    calls=[]
    def no_repeat(exp,q,i):
        assert q['id'] not in cached_ids, 'Cached evidence must not be searched again'
        calls.append(q['id'])
        return original_search(exp,q,i)
    monkeypatch.setattr(round_review,'perform',original_review)
    monkeypatch.setattr(engine,'search',no_repeat)
    resumed=action(client,data,'optimize','resume-review',max_queries=1,max_rounds=1)
    assert wait(client,resumed)['status']=='complete'
    data=client.get('/api/v1/experiments/'+e['id']).json()
    assert len(calls)==1
    assert all(r['outcome_review_status']=='complete' for r in data['rounds'])
