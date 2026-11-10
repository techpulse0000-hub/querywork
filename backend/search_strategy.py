"""Keep the incumbent search family while testing controlled nearby variations."""
from urllib.parse import urlsplit


def plan(candidates, stagnant_rounds, count):
    if not candidates:
        return dict(strategy='initial_discovery',focus=None,
                    allocation=dict(local_variations=0,nearby_exploration=count),
                    directions=['Discover distinct useful search approaches for the fixed goal.'])
    anchor=candidates[0]
    judgments={j['id']:j for j in anchor['evaluation'].get('judgments',[])}
    sources=[]
    gaps={}
    for judgment in judgments.values():
        for criterion in judgment.get('criteria',[]):
            if criterion['status']!='pass':
                key=criterion['requirement'];gaps[key]=gaps.get(key,0)+1
    for result in anchor.get('results',[]):
        judgment=judgments.get(result['id'],{})
        sources.append(dict(title=result['title'],url=result['url'],
                            domain=urlsplit(result['url']).netloc,excerpt=result['content'][:900],
                            grade=judgment.get('grade'),criteria=judgment.get('criteria',[])))
    sources.sort(key=lambda s:s['grade'] if s['grade'] is not None else -1,reverse=True)
    # A new winner gets a whole local batch. A tie or loss retains the anchor;
    # only the nearby exploration share grows, never a wholesale unrelated pivot.
    nearby=0 if stagnant_rounds==0 else (max(1,count//5) if stagnant_rounds==1 else max(2,count*2//5))
    local=count-nearby
    strategy='exploit_winner' if nearby==0 else 'broaden_near_winner'
    return dict(strategy=strategy,
        focus=dict(query_id=anchor['id'],query=anchor['text'],score=anchor['evaluation']['score'],
                   evaluation=anchor['evaluation'],unresolved_requirements=gaps,
                   strongest_sources=sources[:6],lowest_scoring_sources=list(reversed(sources))[:2]),
        allocation=dict(local_variations=local,nearby_exploration=nearby),
        directions=[
            f'First {local} queries: investigate and vary the incumbent query within its successful source/topic family.',
            'Explain the winning evidence and the remaining gaps before choosing changes; do not assume score proves a match.',
            'Preserve useful site restrictions, named competition, season and source type. Change one retrieval component per local query: keyword, phrase, operator, date precision, or scope.',
            'Use language from the strongest source titles and excerpts; remove restrictions only to address an identified evidence gap.',
            f'Last {nearby} queries: nearby exploration only, combining the winning pattern with a supported runner-up, an adjacent relevant official source, or a related source phrase.',
            'On a tie or loss, keep the same incumbent and try new untried variations. Replace the anchor only when an independently graded query beats it.',
            'Never switch to an unrelated sport, industry, source family or intent simply because the latest batch regressed.'
        ])
