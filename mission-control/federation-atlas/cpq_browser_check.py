#!/usr/bin/env python3
"""Native Playwright positive/seeded-negative CPQ 003 smoke on generated pages.

Screenshots and runtime observations are presentation evidence only.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from playwright.sync_api import expect, sync_playwright

VIEWPORTS=[('desktop',1440,1000),('laptop',1280,800),('mobile',390,844)]

def census_counts(report):
    """Source-bound comparison; never assume that the open queue has a fixed size."""
    if report.get('schema') != 'missioncontrol.code_purple.cpq_convergence_n5.v1':
        raise AssertionError('CPQ003_REPORT_SCHEMA_MISMATCH')
    if report.get('admission') != 'HOLD' or report.get('formal_credit_delta') != 0:
        raise AssertionError('CPQ003_REPORT_AUTHORITY_ESCALATION')
    m = report.get('metrics') or {}
    names = ('open', 'done', 'active', 'canonical_rows')
    if any(type(m.get(k)) is not int or m[k] < 0 for k in names):
        raise AssertionError('CPQ003_MISSING_CENSUS_COUNTS')
    if m['open'] == 0 or m['open'] + m['done'] != m['canonical_rows'] or m['active'] > m['open']:
        raise AssertionError('CPQ003_INCONSISTENT_CENSUS_COUNTS')
    return {k: m[k] for k in names}


def verify(page, *, kind, expected):
    if kind=='atlas':
        if page.locator('svg#dag').count()!=1: raise AssertionError('CPQ003_MISSING_SVG_DAG')
        if page.locator('#queue tr').count()<9: raise AssertionError('CPQ003_MISSING_BD_ROWS')
        if page.locator('#gates').count()!=1: raise AssertionError('CPQ003_MISSING_GATE_LEDGER')
        if page.locator('svg#dag *').count()<2: raise AssertionError('CPQ003_UNRENDERED_DAG')
        if page.locator('#sources tr').count()!=6: raise AssertionError('CPQ005_SOURCE_CENSUS_MISSING')
        if 'UNKNOWN' not in page.locator('#sources').inner_text():
            raise AssertionError('CPQ005_FALSE_FRESHNESS_WITHOUT_OBSERVED_CLOCK')
    else:
        if page.locator('#search').count()!=1 or page.locator('#status').count()!=1:
            raise AssertionError('CPQ003_MISSING_REVIEW_CONTROLS')
        if page.locator('#items tr').count()!=expected['open']: raise AssertionError('CPQ003_INCORRECT_OPEN_DENOMINATOR')
        if 'WITHHELD' not in page.locator('#top7').inner_text():
            raise AssertionError('CPQ011_FALSE_COMPARABLE_SOURCE')
    width=page.evaluate('({scroll:document.documentElement.scrollWidth,inner:window.innerWidth})')
    if width['scroll']>width['inner']+2: raise AssertionError('CPQ003_BODY_OVERFLOW')
    return width

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--atlas',type=Path,required=True)
    p.add_argument('--cpq',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True,help='Same-run cpq-n5.json; source of expected denominators')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--report',type=Path,help='cpq-n5.json; default: sibling of --cpq')
    args=p.parse_args(argv)
    from playwright.sync_api import sync_playwright
    report_path=args.report or args.cpq.with_name('cpq-n5.json')
    exp=expectations(json.loads(report_path.read_text(encoding='utf-8')))
    atlas=args.atlas.read_text(encoding='utf-8');cpq=args.cpq.read_text(encoding='utf-8')
    report=json.loads(args.report.read_text(encoding='utf-8'))
    expected=census_counts(report)
    source_sha=(report.get('source') or {}).get('exact_master_sha')
    if not isinstance(source_sha,str) or len(source_sha)!=40 or source_sha not in cpq:
        raise AssertionError('CPQ003_REPORT_HTML_SOURCE_MISMATCH')
    args.out.mkdir(parents=True,exist_ok=True)
    out={'schema':'missioncontrol.code_purple.cpq_browser_check.v1', 'checks':[],
         'seeded_negatives':[],'admission':'HOLD','authority_transfer':False,
         'expected_counts':expected,'source_sha':source_sha}
    with sync_playwright() as pw:
        exe=os.environ.get('CHROMIUM_EXECUTABLE_PATH')
        browser=pw.chromium.launch(headless=True,executable_path=exe or None,
                                  args=['--no-sandbox'])
        for label,w,h in VIEWPORTS:
            context=browser.new_context(viewport={'width':w,'height':h})
            # Generated page loads only local render code. External fonts are optional.
            context.route('https://fonts.googleapis.com/**',lambda r:r.fulfill(status=200,content_type='text/css',body=''))
            context.route('https://fonts.gstatic.com/**',lambda r:r.fulfill(status=200,content_type='font/woff2',body=''))
            for kind,content in [('atlas',atlas),('cpq',cpq)]:
                page=context.new_page()
                errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
                page.set_content(content,wait_until='load')
                width=verify(page,kind=kind,expected=expected)
                if errors:raise AssertionError(f'{label}/{kind} JavaScript errors: {errors[:3]}')
                if kind=='cpq':
                    # Search intentionally includes title, evidence and route text.
                    # CPQ-013 references CPQ-010: a substring query is NOT an
                    # exact-ID selector and can legitimately yield two rows.
                    page.locator('#search').fill('CPQ-010')
                    page.locator('#items tr').first.wait_for(timeout=3500)
                    matched=page.locator('#items tr').all_inner_texts()
                    if not 0<len(matched)<expected['open']:
                        raise AssertionError('CPQ003_SEARCH_DENOMINATOR_MISMATCH')
                    if not any(row.strip().startswith('CPQ-010') for row in matched):
                        raise AssertionError('search control omitted exact target')
                    page.locator('#search').fill('CPQ-UNMATCHED-SEED')
                    expect(page.locator('#items tr')).to_have_count(0)
                    page.locator('#search').fill('')
                    expect(page.locator('#items tr')).to_have_count(expected['open'])
                    page.locator('#status').select_option('DONE')
                    expect(page.locator('#items tr')).to_have_count(expected['done'])
                    page.locator('#status').select_option('ACTIVE')
                    expect(page.locator('#items tr')).to_have_count(expected['active'])
                    page.locator('#status').select_option('OPEN')
                    expect(page.locator('#items tr')).to_have_count(expected['open'])
                path=args.out/f'{label}_{kind}.png';page.screenshot(path=str(path),full_page=True)
                out['checks'].append({'viewport':label,'kind':kind,'status':'PASS',**width,
                                      'screenshot':path.name})
                page.close()
            context.close()
        page=browser.new_page(viewport={'width':1280,'height':800})
        # Positive corpus must detect mutated missing SVG and missing root table.
        for kind,content,broken,signature in [
            ('atlas',atlas,atlas.replace('<svg id="dag"','<div id="dag"',1),'CPQ003_MISSING_SVG_DAG'),
            ('cpq',cpq,cpq.replace('id="items"','id="broken-items"',1),'CPQ003_INCORRECT_OPEN_DENOMINATOR')
        ]:
            if broken==content:raise AssertionError(f'seed injection did not apply for {kind}')
            page.set_content(broken,wait_until='load')
            try:verify(page,kind=kind,expected=expected)
            except AssertionError as e:
                if signature not in str(e):raise
                out['seeded_negatives'].append({'kind':kind,'status':'EXPECTED_FAIL','root':signature})
            else:raise AssertionError(f'false-green seed did not fail: {kind}')
        browser.close()
    if len(out['checks'])!=6 or len(out['seeded_negatives'])!=2:raise AssertionError('incomplete browser QA')
    out['expected_rows']=exp
    (args.out/'browser_receipt.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print('CPQ003_BROWSER=PASS; VIEWPORT_CHECKS=6; SEEDED_FALSE_GREEN_REJECTIONS=2')

if __name__=='__main__':main()