"""Playwright responsive/interactive QA for the single-file generated review site."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright
BASE=Path(__file__).resolve().parents[1]
page_source=(BASE/'out'/'index.html').read_text(encoding='utf-8')
results={"schema":"missioncontrol.flightdeck.browser-qa.v1","viewports":[],"filter_and_export":"PENDING"}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    for name,width,height in [('desktop',1440,1000),('laptop',1280,800),('mobile',390,844)]:
        page=browser.new_page(viewport={'width':width,'height':height},accept_downloads=True)
        errors=[];console=[]
        page.on('pageerror',lambda x:errors.append(str(x)))
        page.on('console',lambda x:console.append(x.text) if x.type=='error' else None)
        page.set_content(page_source,wait_until='load')
        page.locator('#evidence-table tbody tr').first.wait_for()
        before=page.locator('#evidence-table tbody tr:visible').count()
        page.get_by_role('button',name='Show 36 missing').click()
        only_missing=page.locator('#evidence-table tbody tr:visible').count()
        page.locator('#repoFilter').select_option('GBOGEB/CODEX')
        filtered=page.locator('#evidence-table tbody tr:visible').count()
        page.get_by_role('button',name='Reset filters').click()
        reset=page.locator('#evidence-table tbody tr:visible').count()
        page.locator('#find').fill('G4-GG_MATH-MATH_MODEL')
        searched=page.locator('#evidence-table tbody tr:visible').count()
        page.locator('#find').fill('')
        page.locator('#reviewNotes').fill('Local-only proof review; not GitHub authority')
        with page.expect_download() as download:
            page.get_by_role('button',name='Export selected rows + notes').click()
        dl=download.value;assert dl.suggested_filename=='flightdeck_review_notes.json'
        overflow=page.evaluate('document.documentElement.scrollWidth>window.innerWidth')
        missing_links=page.evaluate("""() => Array.from(document.querySelectorAll('a[href]')).filter(a => { const u=a.getAttribute('href'); if(!u || !u.endsWith('.html') && !u.endsWith('.svg') && !u.endsWith('.xlsx') && !u.endsWith('.docx') && !u.endsWith('.pptx') && !u.endsWith('.pdf') && !u.endsWith('.json') && !u.endsWith('.md')) return false;return !document.body.textContent; }).length""")
        page.screenshot(path=str(BASE/'qa'/f'{name}.png'),full_page=True)
        assert before==42,(name,'before',before)
        assert only_missing==36,(name,'missing',only_missing)
        assert filtered==7,(name,'CODEX unknown',filtered)
        assert reset==42,(name,'reset',reset)
        assert searched==1,(name,'search',searched)
        assert not overflow,(name,'overflow')
        assert not errors,(name,'pageerror',errors)
        assert not console,(name,'console',console)
        assert page.locator('a[href="mission_brief.pptx"]').count()==0
        assert page.locator('a[href="linked_evidence_book.pdf"]').count()==0
        results['viewports'].append({'name':name,'width':width,'height':height,'initial_visible_rows':before,'missing_only':only_missing,'codex_unknown_rows':filtered,'search_hits':searched,'horiz_overflow':overflow,'errors':errors,'console_errors':console,'screenshot':f'qa/{name}.png','status':'PASS'})
        page.close()
    browser.close()
results['filter_and_export']='PASS'
(BASE/'qa'/'browser_qa.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'PASS','viewports':len(results['viewports']),'interactions':'search/filter/reset/notes/download','visible_rows':42,'missing':36},sort_keys=True))