"""Outcome self-checks that never change independent grades."""
import json
from datetime import datetime, timezone
from . import engine, research, search_prompts

VERSION = 'outcome-review-v1'


def perform(exp, round_, incumbent, references, prompt=None):
    queries = [q for q in round_['queries'] if q.get('status') == 'complete']
    evidence = [dict(query_id=q['id'], query=q['text'], evaluation=q['evaluation'],
                     results=[{**r, 'content':r['content'][:4000]} for r in q.get('results',[])]) for q in queries]
    report = dict(version=VERSION, evidence_scope='Search excerpts only; each content capped at 4000 characters. No pages opened.',
                  per_query_checks=[], winner_diagnosis='', grader_disagreements=[], next_tests=[], stop_summary='',evidence_warnings=[])
    if exp['mode'] == 'demo':
        report.update(winner_diagnosis='Fictional demo evidence reviewed; no real prospects verified.',
                      next_tests=['Target unresolved requirements with controlled variations.'],
                      stop_summary='Demo only; real evidence requires live search.')
        for q in queries:
            judgments={j['id']:j for j in q['evaluation'].get('judgments',[])}
            report['per_query_checks'].append(dict(query_id=q['id'], conclusion='Reviewed fictional returned evidence.',
                result_checks=[dict(result_id=r['id'],assessment='match' if judgments.get(r['id'],{}).get('grade')==3 else 'incomplete',
                                    evidence_quotes=[],missing_requirements=[]) for r in q.get('results',[])]))
        if exp.get('_continuation_allowed') is False:
            report['suggested_future_tests']=report['next_tests'];report['next_tests']=[]
        return report, {}

    string={'type':'string'}
    def obj(properties):
        return dict(type='object',additionalProperties=False,properties=properties,required=list(properties))
    def array(item):return dict(type='array',items=item)
    requirement_codes={f'c{i}':req for i,req in enumerate(exp['requirements'])}
    checks={}
    for q in queries:
        results={r['id']:obj(dict(assessment={'type':'string','enum':['match','incomplete','background','failure','duplicate']},
                                 evidence_quotes=array(string),missing_requirements=array({'type':'string','enum':list(requirement_codes)} if requirement_codes else string))) for r in q.get('results',[])}
        checks[q['id']]=obj(dict(conclusion=string,result_checks=obj(results)))
    schema=obj(dict(per_query_checks=obj(checks),winner_diagnosis=string,
        grader_disagreements=array(obj(dict(query_id=string,result_id=string,requirement=string,
            expected_status={'type':'string','enum':['pass','fail','unknown']},reason=string,quote=string))),
        next_tests=array(string),stop_summary=string))
    payload=dict(evaluation_date=exp.get('evaluation_date') or datetime.now(timezone.utc).date().isoformat(),
                 outcome=exp['outcome'],requirements=exp['requirements'],round_id=round_['id'],
                 evidence_scope=report['evidence_scope'],queries=evidence,incumbent=incumbent,
                 references=references,requirement_codes=requirement_codes,remaining_search_budget=exp.get('_remaining_search_budget'),
                 continuation_allowed=exp.get('_continuation_allowed',True))
    answer,usage=engine.completion(exp['models']['generator'], prompt or search_prompts.REVIEWER,
        json.dumps(payload,ensure_ascii=False)+'\nUse the supplied JSON schema: checks are keyed by query/result ID. Use requirement_codes (c0, c1, etc.) in missing_requirements. Cite source document/page when using a research technique. Keep conclusions under 30 words and use at most one short quote per result. Do not repeat result content.',schema,timeout=240,reasoning_effort='medium')
    round_.setdefault('review_attempts',[]).append(dict(usage=usage,response=answer,reasoning_effort='medium'))
    if set(answer.get('per_query_checks',{})) != {q['id'] for q in queries}:
        raise ValueError('Outcome review omitted query IDs')
    sources={q['query_id']:{r['id']:r['content'] for r in q['results']} for q in evidence}
    for qid,check in answer['per_query_checks'].items():
        if set(check['result_checks']) != set(sources[qid]):
            raise ValueError('Outcome review omitted result IDs')
        rows=[]
        for rid,row in check['result_checks'].items():
            row['missing_requirements']=[requirement_codes.get(req,req) for req in row['missing_requirements']]
            valid=[quote for quote in row['evidence_quotes'] if quote and quote in sources[qid][rid]]
            if len(valid)!=len(row['evidence_quotes']):
                report['evidence_warnings'].append(dict(query_id=qid,result_id=rid,reason='Unsupported review quotation removed; claim remains unverified.'))
                row['assessment']='incomplete'
                row['missing_requirements']=list(exp['requirements'])
            row['evidence_quotes']=valid
            if row['assessment']=='match' and not row['evidence_quotes']:
                row['assessment']='incomplete'
                row['missing_requirements']=list(exp['requirements'])
                report['evidence_warnings'].append(dict(query_id=qid,result_id=rid,reason='Unquoted match downgraded to incomplete.'))
            if any(req not in exp['requirements'] for req in row['missing_requirements']):
                raise ValueError('Outcome review changed requirements')
            rows.append(dict(result_id=rid,**row))
        report['per_query_checks'].append(dict(query_id=qid,conclusion=check['conclusion'],result_checks=rows))
    valid_disputes=[]
    for dispute in answer['grader_disagreements']:
        source=sources.get(dispute['query_id'],{}).get(dispute['result_id'],'')
        if not dispute['quote'] or dispute['quote'] not in source or dispute['requirement'] not in exp['requirements']:
            report['evidence_warnings'].append(dict(query_id=dispute['query_id'],result_id=dispute['result_id'],reason='Unsupported grading disagreement ignored.'))
            continue
        valid_disputes.append(dispute)
    report['grader_disagreements']=valid_disputes
    for key in ('winner_diagnosis','next_tests','stop_summary'):
        report[key]=answer[key]
    if exp.get('_continuation_allowed') is False:
        report['suggested_future_tests']=report['next_tests']
        report['next_tests']=[]
    return report,usage
