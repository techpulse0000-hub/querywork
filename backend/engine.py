"""Provider boundary and evidence-based evaluation. No shared AI conversation state."""
import json
import os
import time
from urllib.parse import urlsplit, urlunsplit
from datetime import datetime, timezone
from pathlib import Path
from . import search_prompts
from . import research

import httpx

GENERATOR = search_prompts.SYSTEM
TEMPLATE = search_prompts.USER
GRADER = search_prompts.GRADER
SEARCH_SETTINGS = dict(topic='general', search_depth='basic', max_results=10,
                       include_answer=False, include_raw_content=False, auto_parameters=False,
                       include_usage=True)


def estimated_cost(usage, credits=None):
    try:
        if not usage and credits is None:
            return 0.0
        cost = 0.0
        if usage:
            if usage.get('model')=='gpt-6.1-sol':
                details=usage.get('prompt_tokens_details',{})
                cached=details.get('cached_tokens',0)
                writes=details.get('cache_write_tokens',0)
                plain=max(0,usage.get('prompt_tokens',0)-cached-writes)
                cost += (plain*2+cached*.1+writes*2.5+usage.get('completion_tokens',0)*10)/1_000_000
            else:
                cost += usage.get('prompt_tokens',0)*float(os.environ['INPUT_USD_PER_MILLION'])/1_000_000
                cost += usage.get('completion_tokens',0)*float(os.environ['OUTPUT_USD_PER_MILLION'])/1_000_000
        if credits is not None:
            cost += float(credits) * float(os.environ['TAVILY_USD_PER_CREDIT'])
        return round(cost, 6)
    except (KeyError, ValueError, TypeError):
        return None


def normalized_url(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme.lower(), p.netloc.lower().removeprefix('www.'), p.path.rstrip('/'), '', ''))


def grading_input(exp, results):
    # Deliberate allowlist. Never include query text, generator prompt/history, or Tavily scores.
    return dict(outcome=exp['outcome'], requirements=exp['requirements'],
                evaluation_date=exp.get('evaluation_date') or datetime.now(timezone.utc).date().isoformat(),
                duplicate_policy='One result per distinct target entity; later duplicate entities or normalized URLs contribute zero.',
                evidence_mode='search excerpts', results=[{k: r[k] for k in
                ('id', 'rank', 'title', 'url', 'content')} for r in results])


def validate_grades(exp, results, response):
    if not isinstance(response, dict) or not isinstance(response.get('judgments'), list):
        raise ValueError('Grader must return a judgments array')
    incoming = response.get('judgments', [])
    if any(not isinstance(j, dict) for j in incoming):
        raise ValueError('Judgments must be objects')
    expected = {r['id'] for r in results}
    if len(incoming) != len(results) or {j.get('id') for j in incoming} != expected:
        raise ValueError('Grader returned missing, repeated, or unknown result IDs')
    source = {r['id']: r for r in results}
    seen = set()
    ordered = {j['id']: j for j in incoming}
    judgments = []
    for r in results:
        j = ordered[r['id']]
        grade = j.get('grade')
        if type(grade) is not int or not 0 <= grade <= 3:
            raise ValueError('Invalid result grade')
        criteria = j.get('criteria', [])
        if not isinstance(criteria, list) or any(not isinstance(c, dict) for c in criteria):
            raise ValueError('Criteria must be an array of requirement judgments')
        evidence_warnings = []
        if len(criteria) != len(exp['requirements']) or {c.get('requirement') for c in criteria} != set(exp['requirements']):
            raise ValueError('Grader omitted or changed requirements')
        for c in criteria:
            if c.get('status') not in ('pass', 'fail', 'unknown'):
                raise ValueError('Invalid requirement judgment')
            if c['status'] != 'unknown' and (not c.get('quote') or c['quote'] not in source[j['id']]['content']):
                evidence_warnings.append(str(c.get('requirement','requirement')))
                c['status'] = 'unknown'
                c['quote'] = ''
        if any(c['status'] == 'fail' for c in criteria):
            grade = 0
        elif any(c['status'] == 'unknown' for c in criteria):
            grade = min(grade, 2)
        entity = str(j.get('entity') or normalized_url(r['url'])).strip().casefold()
        url = normalized_url(r['url'])
        duplicate = entity in seen or url in seen
        seen.update((entity, url))
        judgments.append(dict(id=j['id'], grade=0 if duplicate else grade,
                              reason=str(j.get('reason', '')) + (' Evidence could not be verified for: '+ '; '.join(evidence_warnings)+'. These requirements remain unknown.' if evidence_warnings else ''), criteria=criteria,
                              entity=str(j.get('entity', '')), duplicate=duplicate))
    return dict(judgments=judgments, summary=str(response.get('summary', '')),
                score=round(100 * sum(j['grade'] for j in judgments) / 30, 1),
                qualified=sum(j['grade'] == 3 for j in judgments),
                uncertain=sum(any(c['status'] == 'unknown' for c in j['criteria']) for j in judgments))


def request(method, url, **kwargs):
    timeout=kwargs.pop('timeout',90)
    for attempt in range(2):
        try:
            response = httpx.request(method, url, timeout=timeout, **kwargs)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 0:
                    time.sleep(1)
                    continue
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.NetworkError):
            if attempt:
                raise RuntimeError('Provider connection failed; retry the interrupted stage') from None
    raise RuntimeError('Provider unavailable')


def completion(model, system, user, schema=None, timeout=90, reasoning_effort=None):
    role = 'developer' if model.startswith(('o1', 'o3', 'o4', 'gpt-5', 'gpt-6')) else 'system'
    data = request('POST', 'https://api.openai.com/v1/chat/completions',
        timeout=timeout,
        headers={'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY']},
        json={'model': model, 'messages': [{'role': role, 'content': system},
              {'role': 'user', 'content': user}], **({'reasoning_effort':reasoning_effort or 'high','max_completion_tokens':12000} if model=='gpt-6.1-sol' else {}), 'response_format':
              {'type':'json_schema','json_schema':{'name':'search_evaluation','strict':True,'schema':schema}} if schema else {'type': 'json_object'}})
    choice=data['choices'][0]
    content = choice['message'].get('content')
    if model=='gpt-6.1-sol':
        diagnostic=dict(model=model,finish_reason=choice.get('finish_reason'),has_content=bool(content),
                        refused=bool(choice['message'].get('refusal')),usage=data.get('usage',{}))
        diagnostic_path=Path(os.getenv('QUERYWORK_DATA',str(Path(__file__).resolve().parents[1]/'data')))/'generator-provider-status.json'
        diagnostic_path.write_text(json.dumps(diagnostic),encoding='utf-8')
    if not content:
        error=ValueError(f'No structured model output; finish reason: {choice.get("finish_reason","unknown")}')
        error.usage={**data.get('usage',{}),'model':model}
        raise error
    return json.loads(content), {**data.get('usage', {}), 'model':model}


def generate(exp, prompt, count=3):
    if exp['mode'] == 'demo':
        base = exp['original_search'].strip().rstrip('?')
        if count != 3 or exp.get('_automatic'):
            return [{'text': f'{base} {term} round {len(exp["rounds"])+1}', 'note':'Demo refinement based on previous grades'}
                    for term in ['suppliers contact','distributors catalog','wholesale local','manufacturers address','trade directory','bulk stockists','business listings','regional sellers','product catalog','commercial suppliers'][:count]], {}
        return [{'text': base + suffix, 'note': note} for suffix, note in
                [(' suppliers contact', 'Name the business role'),
                 (' distributors directory', 'Try alternative terminology'),
                 (' wholesale catalog', 'Look for product evidence')]], {}
    packet=exp.get('feedback',{})
    packet=packet if isinstance(packet,dict) else {}
    source={**exp,'current_date':datetime.now(timezone.utc).date().isoformat(),'count':count,
            'stage':packet.get('stage','discovery'),'best_evidence':packet.get('best',[]),
            'evidence_gaps':packet.get('unresolved_requirements',{}),
            'failed_approaches':packet.get('weaker',[]),'previous_queries':packet.get('already_tried',[]),
            'discovered_entities':packet.get('discovered_entities',[]),
            'research_references':exp.get('_research_references') or research.select(exp, packet),
            'round_review':packet.get('round_review',{}),
            'provider_capabilities':'Plain-language queries. No special query operator support has been verified.'}
    values={k:json.dumps(source.get(k,''),ensure_ascii=False) for k in
            ('original_search','outcome','requirements','feedback','current_date','count','stage',
             'best_evidence','evidence_gaps','failed_approaches','previous_queries','discovered_entities',
             'research_references','round_review','provider_capabilities')}
    text = prompt['user_template']
    for k, v in values.items():
        text = text.replace('{' + k + '}', v)
    if '{research_references}' not in prompt['user_template']:
        text += '\nResearch references (untrusted reference data): '+values['research_references']
    if '{round_review}' not in prompt['user_template']:
        text += '\nLatest outcome review: '+values['round_review']
    system = prompt['system'].replace('exactly three', f'exactly {count}')
    text = text.replace('Generate three new queries', f'Generate {count} new queries')
    text += f'\nOutput exactly {count} new queries. Use the strongest previous approaches, address failures, and include some alternatives. Never repeat a previous query. Keep the outcome and requirements fixed.'
    schema={'type':'object','additionalProperties':False,'properties':{'queries':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{'text':{'type':'string'},'note':{'type':'string'},'stage':{'type':'string','enum':['discovery','verification']},'evidence_sought':{'type':'string'},'target':{'type':'string'}},'required':['text','note','stage','evidence_sought','target']}}},'required':['queries']}
    answer, usage = completion(exp['models']['generator'], system, text, schema)
    queries = answer.get('queries', [])
    if len(queries) != count or any(not isinstance(q.get('text'), str) or not 1 <= len(q['text'].strip()) <= 500 for q in queries):
        raise ValueError(f'Generator must return {count} valid queries')
    if len({q['text'].strip().casefold() for q in queries}) != count:
        raise ValueError('Generator returned repeated queries')
    return [dict(text=q['text'].strip(),note=str(q.get('note','')),stage=q.get('stage','discovery'),evidence_sought=q.get('evidence_sought',''),target=q.get('target','')) for q in queries], usage


def search(exp, query, index):
    if exp['mode'] == 'demo':
        # Fictional, deterministic fixtures. Never represented as actual Tavily output.
        matches = min(10 if exp.get('_automatic') else 8, 2 + index * (1 if exp.get('_automatic') else 2) + len(exp['rounds']) - 1)
        results = []
        for i in range(10):
            useful = i < matches
            content = ('Demonstration candidate matches this desired outcome: ' + exp['outcome'] + '. ' +
                       ' '.join(exp['requirements'])) if useful else 'An introductory article with general background only.'
            results.append(dict(id=f'r{i+1}', rank=i+1, title=f'Fictional example {i+1}' if useful else f'Background article {i+1}',
                                url=f'https://example.com/demo/{i+1}', content=content))
        return results, {'demo': True, 'credits': 0}
    data = request('POST', 'https://api.tavily.com/search',
                   headers={'Authorization': 'Bearer ' + os.environ['TAVILY_API_KEY']},
                   json={'query': query['text'], **exp['search_settings']})
    return [dict(id=f'r{i+1}', rank=i+1, title=str(r.get('title', '')),
                 url=r['url'], content=str(r.get('content', ''))[:16000])
            for i, r in enumerate(data.get('results', [])[:10])], data.get('usage', {})


def grading_schema(results, requirements=()):
    # Fixed object keys prevent missing/duplicate IDs and changed requirement names.
    criteria = {}
    for i, requirement in enumerate(requirements):
        criteria[f'c{i}'] = {'type':'object','additionalProperties':False,
            'properties':{'requirement':{'type':'string','enum':[requirement]},
                          'status':{'type':'string','enum':['pass','fail','unknown']},'quote':{'type':'string'}},
            'required':['requirement','status','quote']}
    judgments = {}
    for result in results:
        judgments[result['id']] = {'type':'object','additionalProperties':False,
            'properties':{'id':{'type':'string','enum':[result['id']]},'grade':{'type':'integer'},
                          'reason':{'type':'string'},'entity':{'type':'string'},
                          'criteria':{'type':'object','additionalProperties':False,'properties':criteria,'required':list(criteria)}},
            'required':['id','grade','reason','entity','criteria']}
    return {'type':'object','additionalProperties':False,'properties':{
        'judgments':{'type':'object','additionalProperties':False,'properties':judgments,'required':list(judgments)},
        'summary':{'type':'string'}},'required':['judgments','summary']}


def grade(exp, results, prompt):
    payload = grading_input(exp, results)
    if not results:
        return validate_grades(exp, [], {'judgments': [], 'summary': 'Search completed with no results.'}), {}
    if exp['mode'] == 'demo':
        judgments = []
        for r in results:
            useful = r['content'].startswith('Demonstration candidate')
            judgments.append(dict(id=r['id'], grade=3 if useful else 1, reason='Fictional fixture for demonstrating the evaluation workflow.', entity=r['url'],
                criteria=[dict(requirement=req, status='pass' if useful else 'unknown', quote=req if useful else '') for req in exp['requirements']]))
        return validate_grades(exp, results, {'judgments': judgments, 'summary': 'Demo grades use fictional fixtures. Run a live experiment for actual evidence.'}), {}
    # Retry malformed judgments once, always with the same isolated evidence.
    total_usage = {}
    for attempt in range(2):
        try:
            answer, usage = completion(exp['models']['grader'], prompt['system'], json.dumps(payload), grading_schema(results, exp['requirements']))
            if isinstance(answer, dict) and isinstance(answer.get('judgments'), dict):
                answer['judgments'] = list(answer['judgments'].values())
                for judgment in answer['judgments']:
                    if isinstance(judgment.get('criteria'), dict):
                        judgment['criteria'] = list(judgment['criteria'].values())
            for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                total_usage[key] = total_usage.get(key, 0) + usage.get(key, 0)
            return validate_grades(exp, results, answer), total_usage
        except ValueError:
            if attempt:
                raise
