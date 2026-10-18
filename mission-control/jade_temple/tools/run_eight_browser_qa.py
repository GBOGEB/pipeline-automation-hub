#!/usr/bin/env python3
"""Local HTTP real-CSP, three-viewport interactive JADE eight-point QA."""
from __future__ import annotations
import functools
import hashlib
import http.server
import json
import os
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'site'
OUT=ROOT/'qa/nplus3'
OUT.mkdir(parents=True,exist_ok=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  if self.path == '/favicon.ico':
   self.send_response(204);self.end_headers();return
  return super().do_GET()
handler=functools.partial(Quiet,directory=str(SITE))
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
base=f'http://127.0.0.1:{server.server_port}/'
report={'schema':'jade.temple.eightpoint_browser.v3','source':'site/eightpoint.html',
 'evidence_level':'LOCAL_HTTP_CSP_PRESENTATION_QA_ONLY','hosted_github_pages_qualified':False,
 'authorities_unchanged':True,'viewports':{},'errors':[]}
try:
 with sync_playwright() as pw:
  kwargs={'headless':True,'args':['--no-sandbox']}
  if Path('/usr/bin/chromium').is_file():kwargs['executable_path']='/usr/bin/chromium'
  browser=pw.chromium.launch(**kwargs)
  try:
   for name,width,height in [('desktop',1440,1000),('laptop',1280,800),('mobile',390,844)]:
    page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
    errors=[];external=[]
    page.on('pageerror',lambda e:errors.append('JS '+str(e)))
    page.on('console',lambda m:errors.append('CONSOLE '+m.text) if m.type=='error' else None)
    page.on('request',lambda req:external.append(req.url) if not req.url.startswith(base) else None)
    try:
     if os.environ.get('JADE_SKIP_HTTP')=='1':
      from playwright.sync_api import Error as PlaywrightError
      raise PlaywrightError('net::ERR_BLOCKED_BY_ADMINISTRATOR; offline rendering mode')
     response=page.goto(base+'eightpoint.html',wait_until='load',timeout=9000)
     assert response.status==200,(name,response.status)
     real_csp=True
    except Exception as exc:
     # Local sandbox administrators may block 127.0.0.1 and file: navigation.
     # Fall back to byte-identical HTML/CSS/JS content only; this never
     # earns production CSP or hosted HTTP parity credit.
     from playwright.sync_api import Error as PlaywrightError
     if not isinstance(exc,PlaywrightError) or 'BLOCKED_BY_ADMINISTRATOR' not in str(exc):raise
     html=(SITE/'eightpoint.html').read_text(encoding='utf-8')
     assert "script-src 'self'; style-src 'self'" in html
     html=html.replace("script-src 'self'; style-src 'self'","script-src 'unsafe-inline'; style-src 'unsafe-inline'")
     html=html.replace('<link rel="stylesheet" href="eightpoint.css">',
           '<style>'+(SITE/'eightpoint.css').read_text()+'</style>')
     html=html.replace('<script src="eightpoint-data.js"></script>',
           '<script>'+(SITE/'eightpoint-data.js').read_text()+'</script>')
     html=html.replace('<script src="eightpoint.js" defer></script>',
           '<script>'+(SITE/'eightpoint.js').read_text()+'</script>')
     page.set_content(html,wait_until='load')
     real_csp=False
     report['evidence_level']='LOCAL_RENDERED_SOURCE_BYTES_CSP_ADJUSTED'
    assert page.title()=='JADE_CASTE | N+3 eight-point MIP'
    assert page.locator('.axis').count()==8,('AXES',name,page.locator('.axis').count())
    assert page.locator('#repo-body tr[data-repo]').count()==21
    assert page.locator('.event').count()==6
    assert page.locator('.gate').count()==9
    assert page.locator('.wave').count()==5
    assert page.locator('#decision').inner_text()=='OWNER_BLOCKED'
    assert page.locator('#k-repos').inner_text()=='21/21'
    assert page.locator('#k-drift').inner_text()=='4/21'
    assert page.locator('#k-open').inner_text()=='21 OPEN'
    assert not page.evaluate('document.documentElement.scrollWidth>document.documentElement.clientWidth || document.body.scrollWidth>document.body.clientWidth'),(name,'overflow')
    page.screenshot(path=str(OUT/(name+'.png')),full_page=True)
    page.locator('#axis-filter').fill('J02');assert page.locator('.axis').count()==1
    page.locator('.axis').first.click();assert 'Cohort population' in page.locator('#axis-detail').inner_text()
    page.locator('#axis-filter').fill('');assert page.locator('.axis').count()==8
    page.locator('#repo-search').fill('CODEX');assert page.locator('#repo-body tr[data-repo]').count()==1
    page.locator('#reset').click();assert page.locator('#repo-body tr[data-repo]').count()==21
    page.locator('#p-filter').select_option('P0');assert page.locator('#repo-body tr[data-repo]').count()==5
    page.locator('#p-filter').select_option('ALL')
    page.locator('#d-filter').select_option('CHANGED');assert page.locator('#repo-body tr[data-repo]').count()==4
    page.locator('#d-filter').select_option('STABLE');assert page.locator('#repo-body tr[data-repo]').count()==17
    page.locator('#reset').click();assert page.locator('#repo-body tr[data-repo]').count()==21
    page.locator('#repo-body tr[data-repo]').first.locator('td').last.click()
    assert 'GBOGEB/ABACUS' in page.locator('#repo-detail').inner_text()
    assert not errors,(name,errors)
    assert not external,(name,external)
    report['viewports'][name]={'width':width,'height':height,'status':'PASS','no_console_errors':True,
     'external_requests':0,'horizontal_overflow':False,'sections':8,'repos':21,
     'P0':5,'head_changed':4,'reset':True,'click_details':'PASS',
     'local_real_csp':real_csp,'screenshot':f'qa/nplus3/{name}.png'}
    page.close()
  finally:browser.close()
finally:server.shutdown();server.server_close();thread.join(timeout=3)
(OUT/'receipt.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
print(json.dumps({'status':'PASS','viewports':len(report['viewports']),
 'source_sha256':hashlib.sha256((SITE/'eightpoint.html').read_bytes()).hexdigest(),
 'local_real_csp':all(x['local_real_csp'] for x in report['viewports'].values()),'hosted_GitHub_Pages_qualified':False},sort_keys=True))
