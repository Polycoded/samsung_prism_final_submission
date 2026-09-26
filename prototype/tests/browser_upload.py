"""Organizer upload and gate score separation through the actual UI."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(os.environ.get('CITEFRONTIER_TEST_URL','http://127.0.0.1:8013'))
        page.wait_for_function("document.getElementById('connection').textContent==='Local session'")
        page.locator('#scorecard').click()
        page.wait_for_selector('#validation-dialog[open]')
        assert '37/40 (92.5%)' in page.locator('#validation-content').inner_text()
        assert '15/15 (100.0%)' in page.locator('#validation-content').inner_text()
        assert '90/90 (100.0%); 0 fabricated IDs' in page.locator('#validation-content').inner_text()
        page.screenshot(path='prototype/reports/g2-g4-dashboard.png',full_page=True)
        page.locator('#close-validation').click()
        page.locator('#upload-open').click()
        page.locator('#corpus-files').set_input_files({'name':'train.json','mimeType':'application/json','buffer':b'[{"tokens":["hello"],"labels":[0]}]'})
        page.locator('#upload-apply').click()
        page.wait_for_function("document.getElementById('upload-status').textContent.includes('not accepted')")
        assert page.locator('#corpus-title').inner_text()=='LumaHome control corpus'
        page.locator('#corpus-files').set_input_files({'name':'Conference_Hall.md','mimeType':'text/markdown','buffer':b'# Conference Hall\n\n## Capacity.1\nThe Conference Hall capacity is 30 people.\n'})
        page.locator('#upload-apply').click()
        page.wait_for_function("!document.getElementById('upload-dialog').open",timeout=60000)
        assert page.locator('#corpus-footer').inner_text()=='Organizer corpus · not benchmarked'
        assert page.locator('#replay').is_disabled()
        page.locator('#question').fill('What is the Conference Hall capacity?')
        page.locator('#commit').click()
        page.wait_for_selector('.citation')
        assert page.locator('.citation').inner_text()=='Conference_Hall §Capacity.1'
        page.locator('.citation').click()
        assert '30 people' in page.locator('.quote').inner_text()
        page.locator('#scorecard').click()
        page.wait_for_selector('#validation-dialog[open]')
        assert 'Your uploaded corpus has not been benchmarked' in page.locator('#validation-content').inner_text()
        page.locator('#close-validation').click()
        for width in (390,768,1440):
            page.set_viewport_size({'width':width,'height':900})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
        page.screenshot(path='prototype/reports/organizer-upload.png',full_page=True)
        page.locator('#reset').click()
        page.wait_for_function("document.getElementById('connection').textContent==='Local session'")
        assert page.locator('#corpus-title').inner_text()=='LumaHome control corpus'
        assert not errors,errors
        Path('prototype/reports/upload-browser-qa.json').write_text(json.dumps({'status':'PASS','checks':['G2-G4 scores','reject training data','upload conference Markdown','retrieve uploaded citations','score isolation','reset to bundled corpus','responsive layout'],'javascript_errors':errors},indent=2),encoding='utf-8')
        browser.close()


if __name__=='__main__':main()
