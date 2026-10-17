#!/usr/bin/env python3
"""Offline browser QA for all W18 HTML renditions at responsive viewports."""
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from threading import Thread
from playwright.sync_api import sync_playwright

BASE=Path(__file__).resolve().parents[1]
SHOTS=BASE/'qa_screenshots';SHOTS.mkdir(exist_ok=True)
summary=[]
server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(BASE)))
Thread(target=server.serve_forever,daemon=True).start()
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path="/usr/bin/chromium",args=["--no-sandbox"])
    for view in ['index.html','cards.html','deck.html']:
        for w,h in [(1440,900),(1024,768),(768,950),(390,844)]:
            page=browser.new_page(viewport={'width':w,'height':h},device_scale_factor=1)
            errors=[]
            page.on('pageerror',lambda exc:errors.append(str(exc)))
            page.set_content((BASE/view).read_text(),wait_until='domcontentloaded',timeout=30000)
            page.wait_for_timeout(180)
            if view=='index.html':
                assert page.locator('#content .metric').count()>=4
                for tab in ['Session DOD','Global DOV','BD queue','Telemetry','Master lineage']:
                    page.get_by_role('button',name=tab).click()
                    assert page.locator('#content').inner_text().strip(),(view,tab)
                page.get_by_role('button',name='BD queue').click()
                field=page.get_by_role('searchbox',name='Filter BD queue')
                field.fill('Ariana')
                assert page.locator('#content .card').count()==1
                field.fill('')
                page.get_by_role('button',name='Overview').click()
            elif view=='cards.html':
                assert page.locator('.cards .card').count()==8
                page.get_by_role('searchbox',name='Filter BD queue').fill('Matplotlib')
                assert page.locator('.cards .card').count()==1
                page.get_by_role('searchbox',name='Filter BD queue').fill('')
            else:
                assert page.locator('.slide.active').count()==1
                page.get_by_role('button',name='Next').click()
                assert page.locator('#slide-index').inner_text()=='2 / 6'
                page.keyboard.press('ArrowRight')
                assert page.locator('#slide-index').inner_text()=='3 / 6'
                page.get_by_role('button',name='Previous').click()
                page.get_by_role('button',name='Previous').click()
            overflow=page.evaluate('document.documentElement.scrollWidth > innerWidth + 2')
            assert not overflow, (view,w,'horizontal overflow')
            assert not errors, (view,w,errors)
            if w in (1440,390):
                shot=SHOTS/f'{view.replace(".html", "")}_{w}.png'
                page.screenshot(path=str(shot),full_page=(view!='deck.html'))
            summary.append({'view':view,'width':w,'height':h,'js_errors':len(errors),'horizontal_overflow':overflow,'interactive_ok':True})
            page.close()
    browser.close()
server.shutdown()
print('BROWSER_QA_PASS',len(summary),'viewports/interactions')
for x in summary:print(x)
