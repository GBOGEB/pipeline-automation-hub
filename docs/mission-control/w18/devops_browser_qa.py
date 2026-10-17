#!/usr/bin/env python3
"""DevOps locator control/deep-link and clipboard tests on a local HTTP origin."""
from pathlib import Path
from functools import partial
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
SHOTS=ROOT/'qa_screenshots'
SHOTS.mkdir(exist_ok=True)
checks=[]
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  for width,height in [(1440,1000),(1280,800),(390,844)]:
   context=browser.new_context(viewport={'width':width,'height':height},permissions=['clipboard-read','clipboard-write'])
   page=context.new_page()
   page.set_default_timeout(5500)
   print('VIEW',width,'begin',flush=True)
   errors=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   print('view index',width,flush=True)
   page.set_content((ROOT/'index.html').read_text(),wait_until='domcontentloaded')
   # The screenshot's footer must navigate to the local actionable register.
   print('index loaded',width,flush=True)
   leaf=page.get_by_role('link',name='Open global BD register — 8 actionable leaves')
   assert leaf.count()==1
   assert leaf.get_attribute('href')=='cards.html#bd-register'
   # Real file navigation is blocked by policy in this runtime; assert the resolved
   # route target and load the second self-contained rendition directly.
   print('before cards',width,flush=True)
   page.set_content((ROOT/'cards.html').read_text(),wait_until='domcontentloaded')
   assert page.locator('.cards .card').count()==8
   assert page.locator('#bd-register').count()==1
   assert page.locator('#bd-register').is_visible()
   # DevOps toggle exposes exact locators and a comment composer on a leaf.
   print('cards loaded',width,flush=True)
   b=page.locator('#devops-toggle')
   assert b.get_attribute('aria-pressed')=='false'
   assert page.locator('.devops-hook-btn:visible').count()==0
   b.click()
   assert b.get_attribute('aria-pressed')=='true'
   assert page.locator('.devops-hook-btn:visible').count()>=8
   page.locator('[data-location-key="BD-W18-01"] .devops-hook-btn').click()
   assert page.locator('#devops-dialog').is_visible()
   assert 'CP-W18/bd/BD-W18-01' in page.locator('#devops-locator').inner_text()
   page.locator('#devops-observed').fill('First red is not linked to an exact owner')
   page.locator('#devops-expected').fill('Link one owner and show terminal evidence')
   page.locator('#devops-next').fill('Obtain A10 authorised disposition')
   output=page.locator('#devops-output').input_value()
   assert 'CP-W18:bd/BD-W18-01' in output
   assert 'First red is not linked' in output
   assert 'Source digest' in output
   assert 'github.com/GBOGEB/ABACUS/issues/1996' in output
   page.evaluate("Object.defineProperty(navigator, 'clipboard', {configurable:true, value:{writeText:async t => {window.__clipboardMock=t},readText:async ()=>window.__clipboardMock}})")
   print('modal opened',width,flush=True)
   page.locator('#devops-copy-comment').click()
   assert 'Copied.' in page.locator('#devops-feedback').inner_text()
   clip=page.evaluate('window.__clipboardMock')
   assert clip==page.locator('#devops-output').input_value()
   page.locator('#devops-copy-location').click()
   clipped=page.evaluate('window.__clipboardMock')
   assert 'CP-W18:bd/BD-W18-01' in clipped and 'cards.html#BD-W18-01' in clipped
   print('comment copied',width,flush=True)
   page.locator('#devops-close').click()
   assert not page.locator('#devops-dialog').is_visible()
   # A deep-link must address a specific BD card without screenshots.
   print('before cards leaf',width,flush=True)
   page.set_content((ROOT/'cards.html').read_text(),wait_until='domcontentloaded')
   page.evaluate("location.hash = '#BD-W18-06'")
   page.wait_for_timeout(200)
   assert page.locator('[data-location-key="BD-W18-06"]').count()==1
   assert 'locator-highlight' in page.locator('[data-location-key="BD-W18-06"]').get_attribute('class')
   # Dashboard route and recursive TODO view.
   print('view index',width,flush=True)
   print('before deep bd',width,flush=True)
   page.set_content((ROOT/'index.html').read_text(),wait_until='domcontentloaded')
   page.evaluate("location.hash = '#bd@BD-W18-07'")
   page.wait_for_timeout(200)
   assert page.locator('[data-location-key="BD-W18-07"]').count()==1
   assert page.locator('[data-location-key="BD-W18-07"]').is_visible()
   page.locator('button[data-view="recursiveFocus"]').click()
   assert '153 first census → 143 intermediate → 142 latest' in page.locator('#content').inner_text()
   assert '24' in page.locator('#content').inner_text()
   assert 'A10 owner approval' in page.locator('#content').inner_text()
   # Later linked DOD row should be route-addressable.
   print('view index',width,flush=True)
   print('before deep dod',width,flush=True)
   page.set_content((ROOT/'index.html').read_text(),wait_until='domcontentloaded')
   page.evaluate("location.hash = '#dod@DOD-06'")
   page.wait_for_timeout(200)
   assert page.locator('[data-location-key="DOD-06"]').count()==1
   assert 'locator-highlight' in page.locator('[data-location-key="DOD-06"]').get_attribute('class')
   assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+2'),f'overflow {width}'
   assert not errors,errors
   page.screenshot(path=str(SHOTS/f'locator_{width}.png'),full_page=False)
   print('VIEW DONE',width,flush=True)
   checks.append({'viewport':width,'modal':'PASS','clipboard':'PASS','deep_link':'PASS','recursive_bd':'PASS','errors':errors})
   context.close()
  # Deck must provide slide/diagram hooks.
  page=browser.new_page(viewport={'width':1280,'height':800})
  errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content((ROOT/'deck.html').read_text(),wait_until='domcontentloaded')
  page.evaluate("location.hash = '#slide-04'")
  page.locator('#devops-toggle').click()
  assert page.locator('.slide.active .devops-hook-btn:visible').count()>=5
  page.locator('.slide.active [data-location-key="fault-3"] .devops-hook-btn').click()
  assert 'CP-W18/deck/fault-3' in page.locator('#devops-locator').inner_text()
  assert not errors,errors
  assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+2')
  checks.append({'view':'deck','diagram_hooks':'PASS','errors':errors})
  page.close()
  browser.close()
finally:
 pass
print('DEVOPS_LOCATOR_BROWSER_PASS',len(checks),checks)
