"""Three-viewport QA: identical HTML/CSS/JS byte content assembled inline when local browser HTTP is blocked."""
import hashlib,json
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];SITE=ROOT/'site';OUT=ROOT/'qa/nplus1';OUT.mkdir(parents=True,exist_ok=True)
receipt={'schema':'jade.temple.browser.qa.v1','source':'site/green.html','evidence_level':'LOCAL_REPRODUCIBILITY','no_github_ci_claim':True,'no_hosted_pages_claim':True,'method':'playwright.set_content, exact HTML/CSS/JS asset bytes inlined for admin-blocked HTTP browser; CSP adjusted to permit inline execution; actual URL/CSP deployment untested','viewports':{},'failures':[]}
css=(SITE/'jade.css').read_text();data=(SITE/'jade_data.js').read_text();app=(SITE/'jade.js').read_text();html=(SITE/'green.html').read_text()
assert '<link rel="stylesheet" href="jade.css">' in html
assert '<script src="jade_data.js"></script>' in html and '<script src="jade.js" defer></script>' in html
assembled=html.replace("script-src 'self'; style-src 'self'", "script-src 'unsafe-inline'; style-src 'unsafe-inline'")
assembled=assembled.replace('<link rel="stylesheet" href="jade.css">','<style>'+css+'</style>')
assembled=assembled.replace('<script src="jade_data.js"></script>','<script>'+data+'</script>')
assembled=assembled.replace('<script src="jade.js" defer></script>','<script>'+app+'</script>')
try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True,args=['--no-sandbox'], **({'executable_path':'/usr/bin/chromium'} if Path('/usr/bin/chromium').is_file() else {}))
   for name,width,height in [('desktop',1440,1000),('laptop',1280,800),('mobile',390,844)]:
    page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
    errors=[];requests=[];http_errors=[]
    page.on('pageerror',lambda e:errors.append('js '+str(e)))
    page.on('console',lambda m:errors.append('console '+m.text) if m.type=='error' else None)
    page.on('request',lambda req:requests.append(req.url))
    page.on('response',lambda resp:http_errors.append(str(resp.status)+' '+resp.url) if resp.status>=400 else None)
    page.set_content(assembled,wait_until='load')
    assert page.title()=='JADE_CASTE · GoGREEN | Top21 release observatory'
    assert page.locator('#repo-body tr[data-repo]').count()==21
    assert page.locator('#metric-positive').inner_text()=='9/13'
    assert page.locator('#metric-overlap').inner_text()=='13/21'
    assert page.locator('#n11-only span').count()==8
    assert page.locator('#green-only span').count()==8
    assert not page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth || document.body.scrollWidth > document.body.clientWidth'),name+' overflow'
    page.screenshot(path=str(OUT/(name+'.png')),full_page=True)
    page.locator('#q').fill('CODEX')
    assert page.locator('#repo-body tr[data-repo]').count()==1
    page.locator('#clear').click()
    assert page.locator('#repo-body tr[data-repo]').count()==21
    page.locator('#priority').select_option('P0')
    assert page.locator('#repo-body tr[data-repo]').count()==5
    page.locator('#priority').select_option('ALL')
    page.locator('#signal').select_option('COHORT_NOT_SAMPLED')
    assert page.locator('#repo-body tr[data-repo]').count()==8
    page.locator('#signal').select_option('ALL')
    page.locator('#repo-body tr[data-repo]').first.locator('td').nth(5).click()
    assert page.locator('#repo-details h3').inner_text()=='GBOGEB/ABACUS'
    assert 'OWNER TECHNICAL TODO' in page.locator('#repo-details').inner_text()
    page.locator('#clear').click()
    assert 'GoGREEN / Evidence' in page.locator('.main-nav').inner_text()
    assert not errors and not http_errors,(errors,http_errors)
    assert not requests, 'Unexpected external asset requests '+str(requests)
    page.set_content((SITE/'index.html').read_text(),wait_until='load')
    assert page.locator('a[href="green.html"]').count()==1
    assert not page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth'),name+' old overflow'
    receipt['viewports'][name]={'width':width,'height':height,'errors':len(errors),'external_requests':0,'http_errors':len(http_errors),'horizontal_overflow':False,'search_reset_priority_green_filter_detail':'PASS','screenshot':f'qa/nplus1/{name}.png'}
    page.close()
   browser.close()
finally:pass
(OUT/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
print(json.dumps({'status':'PASS','viewports':len(receipt['viewports']),'source_sha256':hashlib.sha256((SITE/'green.html').read_bytes()).hexdigest()},indent=2))
