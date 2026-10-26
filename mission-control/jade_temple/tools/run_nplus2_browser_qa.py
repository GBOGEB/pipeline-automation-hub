"""Native responsive QA for N+2 HTML/CSS/JS source bytes (offline, no server claims)."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];SITE=ROOT/'site';OUT=ROOT/'qa/nplus2'
OUT.mkdir(parents=True,exist_ok=True)
receipt={'schema':'jade.temple.nplus2.browser.v2','source':'site/burndown.html',
 'evidence_level':'LOCAL_RENDERED_SOURCE_BYTES','no_served_csp_claim':True,
 'method':'playwright.set_content with identical byte content inlined; CSP adjusted only for offline test',
 'viewports':{},'errors':[]}
html=(SITE/'burndown.html').read_text(encoding='utf-8')
css=(SITE/'burndown.css').read_text(encoding='utf-8')
data=(SITE/'burndown-data.js').read_text(encoding='utf-8')
app=(SITE/'burndown.js').read_text(encoding='utf-8')
assert 'script-src \'self\'; style-src \'self\'' in html
assert html.count('<script src="burndown-data.js"></script>')==1
assembled=html.replace("script-src 'self'; style-src 'self'","script-src 'unsafe-inline'; style-src 'unsafe-inline'")
assembled=assembled.replace('<link rel="stylesheet" href="burndown.css">','<style>'+css+'</style>')
assembled=assembled.replace('<script src="burndown-data.js"></script>','<script>'+data+'</script>')
assembled=assembled.replace('<script src="burndown.js" defer></script>','<script>'+app+'</script>')
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,args=['--no-sandbox'], **({'executable_path':'/usr/bin/chromium'} if Path('/usr/bin/chromium').is_file() else {}))
 for name,w,h in [('desktop',1440,1000),('laptop',1280,800),('mobile',390,844)]:
  page=browser.new_page(viewport={'width':w,'height':h},device_scale_factor=1)
  errors=[];requests=[]
  page.on('pageerror',lambda e:errors.append('javascript '+str(e)))
  page.on('console',lambda e:errors.append('console '+e.text) if e.type=='error' else None)
  page.on('request',lambda e:requests.append(e.url))
  page.set_content(assembled,wait_until='load')
  assert page.title()=='JADE_CASTE | N+2 Top21 convergence control',name+' title'
  assert page.locator('#repos-tbody tr[data-repo]').count()==21,name+' missing rows'
  assert page.locator('#drift').inner_text()=='3/21',name+' drift'
  assert page.locator('#heads').inner_text()=='21/21'
  assert page.locator('#stop-action').inner_text()=='REPAIR_FIRST_RED'
  assert page.locator('.gate').count()==9
  assert page.locator('.hold').inner_text()=='MERGE ADMISSION · HOLD'
  assert not page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth || document.body.scrollWidth > document.body.clientWidth'),name+' horizontal overflow'
  assert not errors and not requests,(name,errors,requests)
  page.screenshot(path=str(OUT/(name+'.png')),full_page=True)
  page.locator('#search').fill('CODEX');assert page.locator('#repos-tbody tr[data-repo]').count()==1
  page.locator('#reset').click();assert page.locator('#repos-tbody tr[data-repo]').count()==21
  page.locator('#priority').select_option('P0');assert page.locator('#repos-tbody tr[data-repo]').count()==5
  page.locator('#priority').select_option('ALL')
  page.locator('#drift-only').select_option('CHANGED');assert page.locator('#repos-tbody tr[data-repo]').count()==3
  page.locator('#drift-only').select_option('STABLE');assert page.locator('#repos-tbody tr[data-repo]').count()==18
  page.locator('#reset').click();assert page.locator('#repos-tbody tr[data-repo]').count()==21
  page.locator('#repos-tbody tr[data-repo]').first.locator('td').last.click()
  assert page.locator('#details h3').inner_text()=='GBOGEB/ABACUS'
  assert 'Next point-release TODO' in page.locator('#details').inner_text()
  assert not errors and not requests,(name,errors,requests)
  receipt['viewports'][name]={'width':w,'height':h,'status':'PASS','external_requests':len(requests),
        'errors':len(errors),'top21_rows':21,'p0_rows':5,'drift_rows':3,'filters_and_detail':'PASS',
        'horizontal_overflow':False,'screenshot':f'qa/nplus2/{name}.png'}
  page.close()
 browser.close()
(OUT/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n',encoding='utf-8',newline="\n")
print(json.dumps({'status':'PASS','viewports':len(receipt['viewports']),
     'sha256':hashlib.sha256((SITE/'burndown.html').read_bytes()).hexdigest()},sort_keys=True))
