"""Bounded automatic search improvement. Generator feedback never enters grader requests."""
import time
from datetime import datetime, timezone
from . import engine
from .search_strategy import plan
from . import research, round_review, search_prompts


def optimize(e, job, checkpoint, persist, now, ident):
    opts = job['options']
    grader = job['grader_prompt']
    state = dict(id=job['id'], status='running', target=opts['target_score'],
                 batch_size=opts['batch_size'], max_rounds=opts['max_rounds'], max_queries=opts['max_queries'],
                 searches=0, new_rounds=0, best=None, comparisons=[], stop_reason=None,stagnant_rounds=0,
                 strategy_version='research_guided_v4',started=now(), models=dict(e['models']), grader_prompt=grader, generator_prompt=job['prompt'],
                 reviewer_prompt=search_prompts.REVIEWER, review_version=round_review.VERSION)
    if e.get('optimization'):
        e.setdefault('optimization_history',[]).append(e['optimization'])
    e['optimization'] = state
    context = {**e, '_automatic':True, 'evaluation_date':datetime.now(timezone.utc).date().isoformat()}
    state['evaluation_date']=context['evaluation_date']

    def update_best():
        eligible = [q for r in e['rounds'] for q in r['queries']
                    if q.get('status')=='complete' and q.get('grader_prompt',{}).get('id')==grader['id']]
        if eligible:
            q=max(eligible,key=lambda q:q['evaluation']['score'])
            state['best'] = dict(query_id=q['id'], text=q['text'], score=q['evaluation']['score'],
                                 qualified=q['evaluation']['qualified'], uncertain=q['evaluation']['uncertain'],
                                 explanation=q['evaluation']['summary'], retrieved_at=q.get('retrieved_at'))

    def stop(reason):
        update_best()
        state.update(status='finished',stop_reason=reason,finished=now())
        persist(e)

    def evaluate(r):
        r['grader_prompt']=grader
        for i,q in enumerate(r['queries']):
            checkpoint(job['id'],f'Automatic round {len(e["rounds"])} · query {i+1}/{len(r["queries"])}')
            if q.get('status')=='complete' and q.get('grader_prompt',{}).get('id')==grader['id']:
                continue
            if 'results' not in q and state['searches']>=opts['max_queries']:
                q['status']='budget_skipped'
                persist(e)
                continue
            started=time.monotonic()
            try:
                if 'results' not in q:
                    state['searches']+=1
                    persist(e)
                    q['results'],q['search_usage']=engine.search(context,q,i)
                    q.update(retrieved_at=now(),status='retrieved')
                    persist(e)
                checkpoint(job['id'],f'Automatic round {len(e["rounds"])} · independently grading query {i+1}')
                if q.get('evaluation'):
                    q.setdefault('evaluation_history',[]).append(dict(evaluation=q.pop('evaluation'),prompt=q.get('grader_prompt'),usage=q.get('grader_usage')))
                q['evaluation'],q['grader_usage']=engine.grade(context,q['results'],grader)
                q['grader_prompt']=grader
                q['status']='complete'
                q.pop('error',None)
                q['estimated_cost_usd']=0.0 if e['mode']=='demo' else engine.estimated_cost(q['grader_usage'],q.get('search_usage',{}).get('credits'))
            except InterruptedError:
                raise
            except Exception as exc:
                q.update(status='grading_failed' if 'results' in q else 'search_failed',
                         error=str(exc)[:200] if isinstance(exc,ValueError) else 'Provider operation failed; saved evidence retained')
            finally:
                q['elapsed_seconds']=round(time.monotonic()-started,2)
                update_best()
                persist(e)
        update_best()

    def comparison(r,before, new=False):
        scores=[q['evaluation']['score'] for q in r['queries'] if q.get('status')=='complete' and q.get('grader_prompt',{}).get('id')==grader['id']]
        best=max(scores) if scores else None
        state['comparisons'].append(dict(round_id=r['id'],round_number=e['rounds'].index(r)+1,
            batch_best=best,previous_best=before,improvement=round(best-before,1) if best is not None and before is not None else None,
            best_so_far=state['best']['score'] if state['best'] else None,
            completed=len(scores),failed=sum(q.get('status') in ('grading_failed','search_failed') for q in r['queries'])))
        if new:
            improved=best is not None and (before is None or best>before)
            state['comparisons'][-1]['accepted_improvement']=improved
            state['stagnant_rounds']=0 if improved else state['stagnant_rounds']+1
        persist(e)

    def review(r):
        # Reused historical rounds stay untouched unless newly evaluated in this job.
        checkpoint(job['id'], 'Checking this round against the desired outcome')
        references=research.select(context, context.get('feedback',{}))
        r['review_references']=references
        r['outcome_review_status']='running'
        context['_remaining_search_budget']=max(0,opts['max_queries']-state['searches'])
        context['_continuation_allowed']=bool(context['_remaining_search_budget'] and
            (not opts.get('max_rounds') or state['new_rounds']<opts['max_rounds']) and
            (not state['best'] or state['best']['score']<opts['target_score']))
        persist(e)
        try:
            report,usage=round_review.perform(context,r,state['best'],references,state['reviewer_prompt'])
            r.update(outcome_review=report,review_usage=usage,review_model=e['models']['generator'],
                     review_reasoning_effort='medium',
                     review_estimated_cost_usd=0.0 if e['mode']=='demo' else sum(engine.estimated_cost(a['usage']) or 0 for a in r.get('review_attempts',[{'usage':usage}])),
                     outcome_review_status='complete')
            if r.get('outcome_review_error'):
                r.setdefault('review_error_history',[]).append(r.pop('outcome_review_error'))
            # At most one isolated regrade per disputed query. No reviewer text is
            # passed to the grader; unresolved disputes remain visible and on hold.
            for q in r['queries']:
                disputes=[d for d in report['grader_disagreements'] if d['query_id']==q['id']]
                if not disputes:continue
                checkpoint(job['id'],'Independently rechecking disputed evidence')
                old=q['evaluation']
                q.setdefault('evaluation_history',[]).append(dict(evaluation=old,prompt=grader,usage=q.get('grader_usage')))
                q['evaluation'],usage=engine.grade(context,q['results'],grader)
                q['recheck_usage']=usage
                q['estimated_cost_usd']=(q.get('estimated_cost_usd') or 0)+(0.0 if e['mode']=='demo' else engine.estimated_cost(usage) or 0)
                q['review_recheck']=dict(disputes=disputes,changed=q['evaluation']!=old)
                # Preserve the independent grade, but hold acceptance while its
                # criterion judgment still disagrees with the quoted review.
                judgments={j['id']:j for j in q['evaluation']['judgments']}
                unresolved=any(not any(c['requirement']==d['requirement'] and c['status']==d['expected_status']
                                       for c in judgments.get(d['result_id'],{}).get('criteria',[])) for d in disputes)
                if unresolved:q['status']='review_disputed'
            state['best']=None
            update_best()
        except InterruptedError:
            r['outcome_review_status']='canceled'
            raise
        except Exception as exc:
            r['outcome_review_status']='failed'
            r['outcome_review_error']=str(exc)[:200] if isinstance(exc,(ValueError,RuntimeError)) else type(exc).__name__
            if getattr(exc,'usage',None):
                r.setdefault('review_attempts',[]).append(dict(usage=exc.usage,error=r['outcome_review_error']))
            r['review_estimated_cost_usd']=sum(engine.estimated_cost(a['usage']) or 0 for a in r.get('review_attempts',[]))
            raise
        finally:
            persist(e)

    try:
        # Existing evidence is judged under the frozen rubric before comparison.
        for r in e['rounds']:
            before=state['best']['score'] if state['best'] else None
            changed=any(q.get('status')!='complete' or q.get('grader_prompt',{}).get('id')!=grader['id'] for q in r['queries'])
            evaluate(r)
            if changed or r.get('outcome_review_status')!='complete':review(r)
            comparison(r,before)
        update_best()
        # No five-round handoff. Continue for the entire user-authorized search budget.
        for _ in range(opts.get('max_rounds') or opts['max_queries']):
            checkpoint(job['id'],'Reviewing the best searches and failure patterns')
            if state['best'] and state['best']['score']>=opts['target_score']:
                stop('target_reached');return
            if state['searches']>=opts['max_queries']:
                stop('query_limit');return
            candidates=[q for r in e['rounds'] for q in r['queries'] if q.get('status')=='complete' and q.get('grader_prompt',{}).get('id')==grader['id']]
            candidates.sort(key=lambda q:q['evaluation']['score'],reverse=True)
            seen={q['text'].strip().casefold() for r in e['rounds'] for q in r['queries']}
            gaps={}
            for q in candidates[:10]:
                for judgment in q['evaluation'].get('judgments',[]):
                    for criterion in judgment.get('criteria',[]):
                        if criterion['status']!='pass':
                            key=criterion['requirement']
                            gaps[key]=gaps.get(key,0)+1
            # Include recent discoveries as well as incumbents so low-scoring discovery
            # queries can seed focused verification without becoming accepted matches.
            recent=[q for r in e['rounds'][-2:] for q in r['queries'] if q.get('status')=='complete']
            discovered=[];source_urls=set()
            for q in recent+candidates[:3]:
                judgments={j['id']:j for j in q.get('evaluation',{}).get('judgments',[])}
                for result in q.get('results',[]):
                    judgment=judgments.get(result['id'],{})
                    if result['url'] in source_urls or judgment.get('grade',0)<1:continue
                    source_urls.add(result['url'])
                    discovered.append(dict(entity=judgment.get('entity',''),title=result['title'],url=result['url'],excerpt=result['content'][:700],verified_match=judgment.get('grade')==3))
            discovered=discovered[-24:]
            neighborhood=plan(candidates,state['stagnant_rounds'],opts['batch_size'])
            packet=dict(instruction='Investigate the incumbent winner and improve its query family through controlled variations. Preserve successful patterns, keep the goal fixed, and retain the same anchor after ties or losses.',
                **neighborhood,
                stagnant_rounds=state['stagnant_rounds'],unresolved_requirements=gaps,
                stage='discovery_and_verification' if discovered else 'discovery',discovered_entities=discovered,
                best=[dict(query=q['text'],evaluation=q['evaluation']) for q in candidates[:3]],
                source_examples=[dict(query=q['text'],sources=[dict(title=r['title'],url=r['url'],excerpt=r['content'][:800]) for r in q.get('results',[])[:3]]) for q in candidates[:3]],
                weaker=[dict(query=q['text'],score=q['evaluation']['score'],summary=q['evaluation']['summary']) for q in candidates[-3:]],
                round_review=next((r['outcome_review'] for r in reversed(e['rounds']) if r.get('outcome_review_status')=='complete'),{}),
                already_tried=sorted(seen), user_feedback=job['feedback'])
            before=state['best']['score'] if state['best'] else None
            context.update(rounds=e['rounds'],feedback=packet)
            context['_research_references']=research.select(context,packet)
            checkpoint(job['id'],f'Generating {opts["batch_size"]} improved search terms')
            terms,usage=engine.generate(context,job['prompt'],count=opts['batch_size'])
            terms=[q for q in terms if q['text'].strip().casefold() not in seen]
            if not terms:
                stop('no_new_terms');return
            r=dict(id=ident(),created=now(),automatic=True,optimization_id=job['id'],generator_prompt=job['prompt'],
                   anchor_query_id=neighborhood['focus']['query_id'] if neighborhood['focus'] else None,anchor_score=before,variation_allocation=neighborhood['allocation'],generator_usage=usage,generator_model=e['models']['generator'],generator_estimated_cost_usd=0.0 if e['mode']=='demo' else engine.estimated_cost(usage),feedback=packet,strategy=packet['strategy'],queries=[])
            r['research_references']=context['_research_references']
            if not e['rounds']:
                r['queries'].append(dict(id=ident(),text=e['original_search'],note='Original baseline',status='ready'))
            r['queries'].extend(dict(id=ident(),status='ready',**term) for term in terms)
            e['rounds'].append(r)
            state['new_rounds']+=1
            context['rounds']=e['rounds']
            persist(e)
            evaluate(r)
            review(r)
            comparison(r,before,new=True)
            if not any(q.get('status')=='complete' for q in r['queries']):
                stop('provider_failure');return
        stop('target_reached' if state['best'] and state['best']['score']>=opts['target_score'] else ('query_limit' if state['searches']>=opts['max_queries'] else 'round_limit'))
    except InterruptedError:
        state.update(status='canceled',stop_reason='canceled',finished=now())
        update_best();persist(e)
        raise
    except Exception:
        state.update(status='failed',stop_reason='generation_or_provider_failure',finished=now())
        update_best();persist(e)
        raise
