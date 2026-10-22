"""Evidence-bound metrics and temporal analysis (standard library only)."""
from __future__ import annotations
from collections import defaultdict
from statistics import mean, median, pstdev
from math import isfinite


class LedgerError(ValueError):
    pass


def validate(data):
    seen = set()
    for r in data['measurements']:
        rid = r.get('id')
        if not rid or rid in seen:
            raise LedgerError('missing/duplicate measurement id: ' + str(rid))
        seen.add(rid)
        if r.get('state') not in ('OBSERVED_NATIVE', 'REPORTED_HISTORICAL', 'DERIVED', 'SIMULATED'):
            raise LedgerError('invalid observation state: ' + rid)
        if not r.get('scope_id') or not r.get('metric'):
            raise LedgerError('missing scope/metric: ' + rid)
        n, d = r.get('numerator'), r.get('denominator')
        if n is not None and (not isinstance(n, (int, float)) or not isfinite(n) or n < 0):
            raise LedgerError('invalid numerator: ' + rid)
        if d is not None and (not isinstance(d, (int, float)) or not isfinite(d) or d <= 0):
            raise LedgerError('invalid denominator: ' + rid)
        if n is not None and d is not None and n > d:
            raise LedgerError('numerator exceeds denominator: ' + rid)
        if r.get('value') is not None and not isinstance(r['value'], (int, float)):
            raise LedgerError('non-numeric value: ' + rid)
        if not isinstance(r.get('step'), int):
            raise LedgerError('missing step: ' + rid)
        if r.get('state') == 'SIMULATED' and r.get('claimed_native'):
            raise LedgerError('simulated result claimed native: ' + rid)
    return True


def measure(r):
    n, d = r.get('numerator'), r.get('denominator')
    if n is not None and d is not None:
        return n / d if r.get('metric_type') == 'ratio' else n
    return r.get('value')


def arithmetic_slope(a, b):
    dx = b['step'] - a['step']
    if dx <= 0:
        return None
    y0, y1 = measure(a), measure(b)
    return (y1 - y0) / dx if y0 is not None and y1 is not None else None


def history_stats(items):
    items = sorted(items, key=lambda r: r['step'])
    latest = items[-1]
    pts = [(r['step'], measure(r)) for r in items if measure(r) is not None and r.get('state') != 'SIMULATED']
    baseline = pts[0][1] if pts else None
    latest_val = pts[-1][1] if pts else None
    slopes = [(y1-y0)/(x1-x0) for (x0,y0),(x1,y1) in zip(pts,pts[1:]) if x1>x0]
    slope = slopes[-1] if slopes else None
    acceleration = slopes[-1]-slopes[-2] if len(slopes)>=2 else None
    normalized = [{'n': x-pts[-1][0], 'index': round(y/baseline*100,4) if baseline else None,
                   'raw': y} for x,y in pts]
    rolling20 = mean(y for _,y in pts[-20:]) if len(pts)>=20 else None
    stability_cv = pstdev(slopes)/abs(mean(slopes)) if len(slopes)>=5 and mean(slopes) else None
    return {'observations':len(pts), 'latest':latest_val, 'baseline':baseline,
            'change': latest_val-baseline if latest_val is not None and baseline is not None and len(pts)>1 else None,
            'pct_change': (latest_val/baseline-1)*100 if baseline not in (None,0) and latest_val is not None and len(pts)>1 else None,
            'slope_per_pulse':slope, 'acceleration_per_pulse2':acceleration,
            'rolling_n20':rolling20, 'slope_cv':stability_cv,
            'normalized_timeline':normalized,
            'history_sufficient_for_n20':len(pts)>=20,
            'comparable_coverage_populations': (len({r.get('population_key') for r in items})==1 and
                                               None not in {r.get('population_key') for r in items}) if latest.get('metric_type')=='ratio' else None}


def analyze(data):
    validate(data)
    groups = defaultdict(list)
    for r in data['measurements']:
        if r['state']!='SIMULATED':
            groups[(r['scope_id'],r['metric'])].append(r)
    histories = {}
    for (scope,metric),items in groups.items():
        histories[scope+'::'+metric] = dict(history_stats(items),scope_id=scope,metric=metric,
            repo=items[-1].get('repo'),unit=items[-1].get('unit'),state=items[-1].get('state'),
            population_key=items[-1].get('population_key'))
    test_candidates=[dict(id=k,scope_id=v['scope_id'],growth_pct=v['pct_change'],
                          increment=v['change'],slope=v['slope_per_pulse'],
                          label=next((r.get('label') for r in reversed(data['measurements'])
                                      if r['scope_id']==v['scope_id'] and r['metric']==v['metric']),k))
       for k,v in histories.items() if v['metric']=='tests_passed' and v['pct_change'] is not None]
    growth_rank=sorted(test_candidates,key=lambda x:x['growth_pct'],reverse=True)
    native_count=sum(r['state']=='OBSERVED_NATIVE' for r in data['measurements'])
    return {'schema':'codepurple.metric_atlas.analysis.v1',
            'input_measurements':len(data['measurements']), 'native_measurements':native_count,
            'histories':histories,'rankings':{'relative_test_growth':growth_rank},
            'sources':data.get('sources',[]), 'limitations':data.get('limitations',[]),
            'interpretation':{'rank_winner':growth_rank[0]['label'] if growth_rank else None,
                'yield_winner':None,'stability_winner':None,
                'reason':'Yield requires comparable resource denominators; stability requires >=6 comparable points.'}}


def simulate(hist, extra_pulses=3):
    if not 1<=extra_pulses<=20:
        raise ValueError('pulses must be 1..20')
    pts=hist['normalized_timeline']
    if len(pts)<2 or hist['slope_per_pulse'] is None:
        return {'state':'UNAVAILABLE','reason':'Requires at least two observations with N steps'}
    # Linear scenario only: deliberately no assertion of forecast confidence.
    result=[]
    current=pts[-1]['raw']
    slope=hist['slope_per_pulse']
    for i in range(1,extra_pulses+1):
        result.append({'N':f'N+{i}','value':round(max(0,current+i*slope),4),
                       'state':'SIMULATED_UNCERTIFIED'})
    return {'state':'SIMULATED_UNCERTIFIED','assumption':'last observed slope persists, floor at 0',
            'scenario':result}


def matched_comparison(first, second):
    """Reject coverage comparisons absent identical population/config fingerprints."""
    if first['scope_id'] != second['scope_id'] or not first.get('population_key') or first.get('population_key') != second.get('population_key'):
        return {'status':'UNMATCHED_POPULATION','delta':None}
    a,b=measure(first),measure(second)
    return {'status':'MATCHED' if a is not None and b is not None else 'UNKNOWN',
            'delta': b-a if a is not None and b is not None else None}
