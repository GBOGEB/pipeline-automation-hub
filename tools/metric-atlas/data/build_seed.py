"""Generate reproducible, evidence-qualified seed ledger from local native artifact + reported snapshots."""
import json, zipfile, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ZIP=ROOT/'evidence/method_atlas_11964700323.zip'
with zipfile.ZipFile(ZIP) as z:
    assert z.testzip() is None
    hist=json.loads(z.read('code-purple.json'))
    lane=json.loads(z.read('lane-process.json'))
    wave=json.loads(z.read('federation-wave-metrics.json'))
    archive_members={i.filename:i.file_size for i in z.infolist()}
sha256=hashlib.sha256(ZIP.read_bytes()).hexdigest()
records=[]

def add(id, label, scope, metric,step, *, value=None,numerator=None,denominator=None,
        unit='count',repo='GBOGEB/ABACUS',state='REPORTED_HISTORICAL',metric_type='count',
        population_key=None,sha=None,source=None,pr=None,at='2026-10-17',note=None):
    r={'id':id,'label':label,'scope_id':scope,'metric':metric,'step':step,
       'unit':unit,'repo':repo,'state':state,'metric_type':metric_type,'observed_at':at,
       'source':source,'sha':sha,'pr':pr,'population_key':population_key,'note':note}
    if value is not None:r['value']=value
    if numerator is not None:r['numerator']=numerator
    if denominator is not None:r['denominator']=denominator
    records.append(r)

url533='https://github.com/GBOGEB/pipeline-automation-hub/pull/533'
url2080='https://github.com/GBOGEB/ABACUS/pull/2080'
url1997='https://github.com/GBOGEB/ABACUS/pull/1997'
add('mc-branch-66','MC four Python modules','MC:4-PY-MODULES','branch_coverage',0,numerator=52,denominator=66,metric_type='ratio',unit='fraction',repo='GBOGEB/pipeline-automation-hub',population_key='MC:4-python-modules:historic-config',source='prior conversation baseline',note='Not federation coverage; local module set and exact file list unavailable.')
add('abac-fred-branch','ABACUS first-red source','ABACUS:FIRST_RED','branch_coverage',0,numerator=36,denominator=36,metric_type='ratio',unit='fraction',population_key='ABACUS:first_red:30ec74',sha='30ec74cc3cb86d1168b714cc112f2886605517eb',pr=2080,source=url2080)
add('abac-fred-stmt','ABACUS first-red source','ABACUS:FIRST_RED','statement_coverage',0,numerator=137,denominator=137,metric_type='ratio',unit='fraction',population_key='ABACUS:first_red:30ec74',sha='30ec74cc3cb86d1168b714cc112f2886605517eb',pr=2080,source=url2080)
add('abac-root-branch','ABACUS root-leverage source','ABACUS:ROOT_LEVERAGE','branch_coverage',0,numerator=34,denominator=34,metric_type='ratio',unit='fraction',population_key='ABACUS:root_leverage:30ec74',sha='30ec74cc3cb86d1168b714cc112f2886605517eb',pr=2080,source=url2080)
add('abac-root-stmt','ABACUS root-leverage source','ABACUS:ROOT_LEVERAGE','statement_coverage',0,numerator=76,denominator=76,metric_type='ratio',unit='fraction',population_key='ABACUS:root_leverage:30ec74',sha='30ec74cc3cb86d1168b714cc112f2886605517eb',pr=2080,source=url2080)
add('w70-br','ABACUS W70 metrics','ABACUS:W70_METRICS','branch_coverage',0,numerator=17,denominator=18,metric_type='ratio',unit='fraction',source=url1997,pr=1997,population_key='ABACUS:W70:1997')
add('w70-st','ABACUS W70 metrics','ABACUS:W70_METRICS','statement_coverage',0,numerator=133,denominator=133,metric_type='ratio',unit='fraction',source=url1997,pr=1997,population_key='ABACUS:W70:1997')
add('w70-trans-br','ABACUS workflow transitions','ABACUS:W70_TRANSITIONS','branch_coverage',0,numerator=14,denominator=16,metric_type='ratio',unit='fraction',source=url1997,pr=1997,population_key='ABACUS:W70trans:1997')
add('w70-trans-st','ABACUS workflow transitions','ABACUS:W70_TRANSITIONS','statement_coverage',0,numerator=29,denominator=31,metric_type='ratio',unit='fraction',source=url1997,pr=1997,population_key='ABACUS:W70trans:1997')
add('broad-pre-stat','ABACUS broad statement census','ABACUS:PY312_BROAD','statement_coverage',-1,numerator=30987-13668,denominator=30987,metric_type='ratio',unit='fraction',population_key='ABACUS:broader:HEAD_PRE',pr=2080,source=url2080,sha='c179c91a5f8e39b7a9486e039030ac2c8ce8204a',note='Numerator derived total - missing; unmatched population vs next head')
add('broad-new-stat','ABACUS broad statement census','ABACUS:PY312_BROAD','statement_coverage',0,numerator=31028-13657,denominator=31028,metric_type='ratio',unit='fraction',population_key='ABACUS:broader:HEAD_NEW',pr=2080,source=url2080,sha='30ec74cc3cb86d1168b714cc112f2886605517eb',note='Numerator derived total - missing; population and tool config not matched')
add('broad-new-branch','ABACUS broad branch opportunities','ABACUS:PY312_BROAD','branch_coverage',0,denominator=8394,metric_type='ratio',unit='fraction',population_key='ABACUS:broader:HEAD_NEW',pr=2080,source=url2080,note='Covered branch numerator UNKNOWN')
add('broad-pre-branch','ABACUS broad branch opportunities','ABACUS:PY312_BROAD','branch_opportunities',-1,value=8370,unit='branches',pr=2080,source=url2080)
add('broad-new-op','ABACUS broad branch opportunities','ABACUS:PY312_BROAD','branch_opportunities',0,value=8394,unit='branches',pr=2080,source=url2080)
add('abac-diffcov','ABACUS changed lines','ABACUS:DIFF_HEAD_30EC','changed_line_coverage',0,numerator=213,denominator=213,metric_type='ratio',unit='fraction',population_key='ABACUS:diff:HEAD_NEW',pr=2080,source=url2080)
add('test-abac-old','ABACUS Python 3.12 suite','ABACUS:PY312_SUITE','tests_passed',-1,value=2243,pr=2080,sha='c179c91a5f8e39b7a9486e039030ac2c8ce8204a',source=url2080)
add('test-abac-new','ABACUS Python 3.12 suite','ABACUS:PY312_SUITE','tests_passed',0,value=2257,pr=2080,sha='30ec74cc3cb86d1168b714cc112f2886605517eb',source=url2080)
add('test-method-old','Mission Control Method Atlas','MC:METHOD_ATLAS','tests_passed',-1,value=53,repo='GBOGEB/pipeline-automation-hub',source=url533,sha='04e6bde112592993e2d026c42b4aa5c3b747f2f1')
add('test-method-new','Mission Control Method Atlas','MC:METHOD_ATLAS','tests_passed',0,value=74,repo='GBOGEB/pipeline-automation-hub',source=url533,sha='bf9383bc39bedf645175184049bdb2013379041d')
add('lint-17','ABACUS Markdown debt','ABACUS:MD_LINT','markdown_failures',-1,value=17,pr=2080,source=url2080,sha='c179c91a5f8e39b7a9486e039030ac2c8ce8204a',unit='errors')
add('lint-1','ABACUS Markdown debt','ABACUS:MD_LINT','markdown_failures',0,value=1,pr=2080,source=url2080,sha='30ec74cc3cb86d1168b714cc112f2886605517eb',unit='errors')
add('fp-5','Shared Matplotlib fingerprint','ABACUS:MATPLOTLIB_FAMILY','fingerprint_pr_occurrences',-1,value=5,unit='prs',source='previously reported historical cohort',note='Not deduplicated root ID')
add('fp-7','Shared Matplotlib fingerprint','ABACUS:MATPLOTLIB_FAMILY','fingerprint_pr_occurrences',0,value=7,unit='prs',source='previously reported historical cohort',note='Not proven root closure')
# Four genuine (historical, artifact-bound) evolution records.
for i,e in enumerate(hist['series']):
    metric=e['metrics'];ref=e['refs'][0] if e.get('refs') else url533
    for kind,key in [('bd_completed','bd_complete'),('bd_inventory','bd_total')]:
        add('series-'+kind+'-'+str(i),'CODE PURPLE history', 'MC:CODE_PURPLE_SERIES',kind,i,
            value=metric[key],repo='GBOGEB/pipeline-automation-hub',state='OBSERVED_NATIVE',unit='items',
            source=ref,at='sequence:'+e['key'],note='historical source snapshot embedded in #533 native artifact')
    add('series-cov-'+str(i),'CODE PURPLE historical cohort', 'MC:HISTORIC_COVERAGE_BREADTH','measured_coverage_breadth',i,
        numerator=metric['coverage_rows_measured'],denominator=metric['coverage_rows_total'],
        metric_type='ratio',unit='fraction',repo='GBOGEB/pipeline-automation-hub',state='OBSERVED_NATIVE',
        population_key='MC:top21:2026-09-27',source=ref,at='sequence:'+e['key'])
    add('series-bdpercent-'+str(i),'CODE PURPLE backlog completion', 'MC:CODE_PURPLE_SERIES', 'bd_completion_fraction',i,
        numerator=metric['bd_complete'],denominator=metric['bd_total'],metric_type='ratio',unit='fraction',
        repo='GBOGEB/pipeline-automation-hub',state='OBSERVED_NATIVE',population_key='MC:historical-bd-interval-'+str(i),
        source=ref,at='sequence:'+e['key'],note='denominator changes: preserve numerator and denominator explicitly')
# Read-only archived evidence integrity record and historical breadth.
add('native-method-zip-bytes','Method Atlas ZIP artifact','MC:ARTIFACT_11964700323','archive_zip_bytes',0,
    value=ZIP.stat().st_size,repo='GBOGEB/pipeline-automation-hub',state='OBSERVED_NATIVE',
    unit='bytes',source=url533,note='sha256='+sha256)
add('producer-breadth','Historical producer breadth','MC:HISTORIC_PRODUCER','producer_breadth',0,
    numerator=wave['producer_breadth']['observed'],denominator=wave['producer_breadth']['eligible'],
    metric_type='ratio',unit='fraction',repo='GBOGEB/pipeline-automation-hub',state='OBSERVED_NATIVE',
    population_key='MC:producer-five:Oct15',source=url533,at='2026-10-15',note='Not a live federation-wide census')
add('meascov-breadth','Historical measured coverage breadth','MC:HISTORIC_PRODUCER','measured_coverage_breadth',0,
    numerator=wave['measured_coverage_breadth']['observed'],denominator=wave['measured_coverage_breadth']['eligible'],
    metric_type='ratio',unit='fraction',repo='GBOGEB/pipeline-automation-hub',state='OBSERVED_NATIVE',
    population_key='MC:producer-five:Oct15',source=url533,at='2026-10-15',note='Not a live federation-wide census')

ledger={'schema':'codepurple.metric_ledger.v1','as_of':'2026-10-17','origin':'prior-session reported measurements + independently checked native #533 historical ZIP',
        'native_archive':{'filename':ZIP.name,'sha256':sha256,'bytes':ZIP.stat().st_size,
            'members':archive_members,'method_atlas_artifact_id':11964700323,
            'valid_zip_integrity':True,'historical_source_not_live':True,
            'lane_process_16_cases':'reported successful in preceding pulse; not recounted from these JSON bytes',
            'lane_count':len(lane['contract']['lanes']) if isinstance(lane['contract']['lanes'],list) else None},
        'sources':[{'type':'native_archive','repo':'GBOGEB/pipeline-automation-hub','pr':533,'url':url533,'sha256':sha256},
                   {'type':'conversation_report','repo':'GBOGEB/ABACUS','pr':2080,'url':url2080},
                   {'type':'conversation_report','repo':'GBOGEB/ABACUS','pr':1997,'url':url1997}],
        'measurements':records,
        'limitations':['No live 90-repo census; five-repo producer measurement is historical and separate.',
                       'No worker-hours denominators; no credible yield/time winner.',
                       'Coverage populations are not global; do not average their percentages.',
                       'Source reports are distinct from the independently verified historical #533 ZIP.',
                       'History has fewer than 20 points; N20 mean is UNKNOWN.',
                       'Native source ZIP contents do not alone prove that current GitHub branch protection or mergeability changed.',
                       'PCA/Bradley-Terry readiness cannot be inferred from incomplete repeated/scope data.']}
(ROOT/'data/observations.json').write_text(json.dumps(ledger,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('wrote',len(records),'measurements','native zip',sha256)
