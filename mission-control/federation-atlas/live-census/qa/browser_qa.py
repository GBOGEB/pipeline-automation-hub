"""Visible Playwright user-I/O and responsive audit with screenshots."""
from __future__ import annotations
import json
import re
import sys
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'source'))
import serve

def audit():
  report={'viewports':{},'tests':0,'passed':0,'errors':[],'screenshots':[],'browser_mode':'HTTP_NAVIGATION'}
  def check(ok,tag):
    report['tests']+=1
    if not ok:report['errors'].append(tag)
    else:report['passed']+=1
  with serve.Server(('127.0.0.1',0),serve.Handler,ROOT/'output',ROOT/'view') as host:
    thread=threading.Thread(target=host.serve_forever,daemon=True);thread.start()
    try:
      with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        try:
          for name,w,h in [('desktop',1440,1000),('laptop',1280,800),('mobile',390,844)]:
            page=browser.new_page(viewport={'width':w,'height':h},device_scale_factor=1)
            errors=[];page.on('pageerror',lambda e:errors.append('page:'+str(e)))
            page.on('console',lambda m:errors.append('console:'+m.text) if m.type=='error' else None)
            try:
              page.goto('http://127.0.0.1:'+str(host.server_port)+'/',wait_until='load',timeout=12000)
            except Exception as nav_error:
              if 'ERR_BLOCKED_BY_ADMINISTRATOR' not in str(nav_error):raise
              # Browser's managed policy prohibits localhost. Test DOM/controls
              # using an in-memory fixture; HTTP endpoints are separately unittest-tested.
              report['browser_mode']='IN_MEMORY_FIXTURE_HTTP_NAVIGATION_BLOCKED'
              html=(ROOT/'view/index.html').read_text()
              css=(ROOT/'view/styles.css').read_text()
              js=(ROOT/'view/app.js').read_text()
              fixture=(ROOT/'output/snapshot.json').read_text()
              html=re.sub(r'<meta http-equiv="Content-Security-Policy"[^>]*>', '', html)
              html=html.replace('<link rel="stylesheet" href="styles.css">','<style>'+css+'</style>')
              html=html.replace('<script src="app.js" defer></script>', '')
              html=html.replace('</body>', '<script>window.EventSource=undefined;window.fetch=async()=>({ok:true,json:async()=>JSON.parse('+json.dumps(fixture)+')});</script><script>'+js+'</script></body>')
              page.close()
              page=browser.new_page(viewport={'width':w,'height':h},device_scale_factor=1)
              errors=[];page.on('pageerror',lambda e:errors.append('page:'+str(e)))
              page.on('console',lambda m:errors.append('console:'+m.text) if m.type=='error' else None)
              page.set_content(html,wait_until='load')
            page.wait_for_function("document.getElementById('repoCount').textContent==='5'",timeout=15000)
            check(page.locator('#prCount').inner_text()=='14',name+': PR count')
            check(page.locator('#nodeCount').inner_text()=='33 / 44',name+': node edge count')
            check('UNKNOWN' in page.locator('#closures').inner_text(),name+': closure is unknown')
            check('FROZEN' in page.locator('#feedState').inner_text(),name+': no false live claim')
            check(len(page.locator('#prRows tr').all())==14,name+': all PRs')
            page.locator('#query').fill('2059')
            check(len(page.locator('#prRows tr').all())==1,name+': text filtering')
            page.locator('#query').fill('')
            page.locator('#disposition').select_option('MERGED_INTERMEDIATE_NOT_MAIN')
            check(len(page.locator('#prRows tr').all())==1,name+': intermediate filter')
            check('2060' in page.locator('#prRows').inner_text(),name+': branch not main')
            page.locator('#disposition').select_option('ALL')
            page.get_by_role('button',name='Nodes & edges').click()
            check(page.locator('#graphEdges').inner_text()=='44',name+': graph state')
            page.locator('#graphType').select_option('STACKED_PARENT')
            check(len(page.locator('#edgeRows tr').all())>=4,name+': stacked graph edges')
            page.get_by_role('button',name='Intervening events').click()
            check(len(page.locator('#eventRows li').all())==9,name+': event generation')
            page.get_by_role('button',name='Diagnostics / Docker').click()
            check('READ-ONLY API' in page.locator('#transport').inner_text(),name+': diagnostics transport')
            check('NOT PROBED' in page.locator('#pane-diagnostics').inner_text(),name+': Docker honesty')
            page.locator('#theme').click()
            check(page.locator('html').get_attribute('data-theme')=='light',name+': theme toggle')
            page.locator('#theme').click()
            check(page.locator('html').get_attribute('data-theme')=='dark',name+': theme restore')
            page.locator('#reload').click()
            page.wait_for_timeout(220)
            check(page.locator('#prCount').inner_text()=='14',name+': manual reload')
            bad=page.evaluate("""() => {let x=JSON.parse(JSON.stringify(state.snapshot));x.authority.root_closures_verified=1;try{validate(x);return false}catch(e){return true}}""")
            check(bad,name+': UI rejects forged closure')
            overflow=page.evaluate("Math.max(0,document.documentElement.scrollWidth - document.documentElement.clientWidth)")
            check(overflow==0,name+': no body horizontal overflow ('+str(overflow)+')')
            check(len(page.locator('img').all())==0,name+': no broken images')
            page.get_by_role('button',name='PR / branch leaves').click()
            shot=str(ROOT/'qa/screenshots'/(name+'.png'));page.screenshot(path=shot,full_page=True)
            report['screenshots'].append('qa/screenshots/'+name+'.png')
            page.wait_for_timeout(200)
            check(not errors,name+': console and page errors: '+repr(errors[:2]))
            report['viewports'][name]={'width':w,'height':h,'overflow_px':overflow,'errors':errors}
            page.close()
        finally:browser.close()
    finally:host.shutdown();thread.join(timeout=2)
  (ROOT/'qa/browser_qa_receipt.json').write_text(json.dumps(report,indent=2)+'\n')
  print(json.dumps({'passed':report['passed'],'total':report['tests'],'errors':report['errors']}))
  if report['errors']:raise SystemExit(1)
if __name__=='__main__':audit()
