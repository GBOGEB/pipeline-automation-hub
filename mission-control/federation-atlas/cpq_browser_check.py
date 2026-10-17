#!/usr/bin/env python3
"""Native Playwright positive/seeded-negative CPQ 003 smoke on generated pages.

Screenshots and runtime observations are presentation evidence only.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

VIEWPORTS=[('desktop',1440,1000),('laptop',1280,800),('mobile',390,844)]

def verify(page, *, kind):
    if kind=='atlas':
        if page.locator('svg#dag').count()!=1: raise AssertionError('CPQ003_MISSING_SVG_DAG')
        if page.locator('#queue tr').count()<9: raise AssertionError('CPQ003_MISSING_BD_ROWS')
        if page.locator('#gates').count()!=1: raise AssertionError('CPQ003_MISSING_GATE_LEDGER')
        if page.locator('svg#dag *').count()<2: raise AssertionError('CPQ003_UNRENDERED_DAG')
    else:
        if page.locator('#search').count()!=1 or page.locator('#status').count()!=1:
            raise AssertionError('CPQ003_MISSING_REVIEW_CONTROLS')
        if page.locator('#items tr').count()!=9: raise AssertionError('CPQ003_INCORRECT_OPEN_DENOMINATOR')
        if 'WITHHELD' not in page.locator('#top7').inner_text():
            raise AssertionError('CPQ011_FALSE_COMPARABLE_SOURCE')
    width=page.evaluate('({scroll:document.documentElement.scrollWidth,inner:window.innerWidth})')
    if width['scroll']>width['inner']+2: raise AssertionError('CPQ003_BODY_OVERFLOW')
    return width

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--atlas',type=Path,required=True)
    p.add_argument('--cpq',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(argv)
    atlas=args.atlas.read_text(encoding='utf-8');cpq=args.cpq.read_text(encoding='utf-8')
    args.out.mkdir(parents=True,exist_ok=True)
    out={'schema':'missioncontrol.code_purple.cpq_browser_check.v1', 'checks':[],
         'seeded_negatives':[],'admission':'HOLD','authority_transfer':False}
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
                width=verify(page,kind=kind)
                if errors:raise AssertionError(f'{label}/{kind} JavaScript errors: {errors[:3]}')
                if kind=='cpq':
                    # Search intentionally includes title, evidence and route text.
                    # CPQ-013 references CPQ-010: a substring query is NOT an
                    # exact-ID selector and can legitimately yield two rows.
                    page.locator('#search').fill('CPQ-010')
                    page.wait_for_function("document.querySelectorAll('#items tr').length > 0 && document.querySelectorAll('#items tr').length < 9",timeout=3500)
                    matched=page.locator('#items tr').all_inner_texts()
                    if not any(row.strip().startswith('CPQ-010') for row in matched):
                        raise AssertionError('search control omitted exact target')
                    page.locator('#search').fill('CPQ-UNMATCHED-SEED')
                    page.wait_for_function("document.querySelectorAll('#items tr').length === 0")
                    page.locator('#search').fill('')
                    page.wait_for_function("document.querySelectorAll('#items tr').length === 9")
                    page.locator('#status').select_option('DONE')
                    page.wait_for_function("document.querySelectorAll('#items tr').length === 9")
                    page.locator('#status').select_option('ACTIVE')
                    page.wait_for_function("document.querySelectorAll('#items tr').length === 2")
                    page.locator('#status').select_option('OPEN')
                    page.wait_for_function("document.querySelectorAll('#items tr').length === 9")
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
            try:verify(page,kind=kind)
            except AssertionError as e:
                if signature not in str(e):raise
                out['seeded_negatives'].append({'kind':kind,'status':'EXPECTED_FAIL','root':signature})
            else:raise AssertionError(f'false-green seed did not fail: {kind}')
        browser.close()
    if len(out['checks'])!=6 or len(out['seeded_negatives'])!=2:raise AssertionError('incomplete browser QA')
    (args.out/'browser_receipt.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print('CPQ003_BROWSER=PASS; VIEWPORT_CHECKS=6; SEEDED_FALSE_GREEN_REJECTIONS=2')

if __name__=='__main__':main()