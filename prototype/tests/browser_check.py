"""End-to-end browser QA; uses an installed Chrome, no test answer stubs."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    out=Path('prototype/reports');out.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(os.environ.get('CITEFRONTIER_TEST_URL','http://127.0.0.1:8000/'));page.wait_for_function("document.getElementById('connection').textContent==='Local session'")
        page.locator('#replay').click();page.wait_for_function("document.querySelectorAll('.claim').length===3",timeout=60000)
        page.wait_for_function("!document.getElementById('replay').disabled")
        assert page.locator('.citation').count()==3
        page.locator('.citation').first.click();assert page.locator('.quote').inner_text()
        page.locator('#view-toggle').click()
        page.screenshot(path=str(out/'dashboard-desktop.png'),full_page=True)
        page.locator('#bullets').click();page.wait_for_function("document.getElementById('input-state').textContent==='Retrieval suppressed'")
        assert page.locator('.claim').count()==3
        page.locator('[data-scenario="refinement"]').click();page.locator('#replay').click()
        page.wait_for_function("document.getElementById('version-history').textContent.includes('1 preserved')",timeout=60000)
        page.wait_for_function("!document.getElementById('replay').disabled")
        assert 'liquid damage' in page.locator('#answer').inner_text().lower()
        assert 'receipt' in page.locator('#answer').inner_text().lower()
        page.screenshot(path=str(out/'dashboard-refinement.png'),full_page=True)
        page.locator('[data-scenario="correction"]').click();page.locator('#replay').click()
        page.wait_for_function("document.getElementById('answer').textContent.includes('36-month')",timeout=60000)
        page.wait_for_function("!document.getElementById('replay').disabled")
        assert 'LumaPad_S2' in page.locator('.citation').inner_text()
        page.locator('[data-scenario="unknown"]').click();page.locator('#replay').click()
        page.wait_for_function("document.querySelectorAll('.claim.uncertain').length===1",timeout=60000)
        page.wait_for_function("!document.getElementById('replay').disabled")
        assert page.locator('.citation').count()==0
        page.locator('#scorecard').click();page.wait_for_selector('#validation-dialog[open]');page.locator('#close-validation').click()
        page.locator('#browse').click();page.wait_for_selector('#corpus-dialog[open]');assert page.locator('.corpus-row').count()==30;page.locator('#close-corpus').click()
        with page.expect_download() as download:
            page.locator('#export').click()
        download.value.save_as(str(out/'browser-audit.json'))
        for width in [390,768,1440]:
            page.set_viewport_size({'width':width,'height':900})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'Horizontal overflow at {width}'
        page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(out/'dashboard-mobile.png'),full_page=True)
        page.emulate_media(reduced_motion='reduce')
        assert page.locator('.claim').evaluate("e=>getComputedStyle(e).animationName")=='none'
        assert not errors,errors
        (out/'browser-qa.json').write_text(json.dumps({'status':'PASS','checks':['compound replay','source inspector','format suppression','natural refinement','ASR correction','uncertainty','scorecard','corpus browser','audit download','390/768/1440 overflow','reduced motion','no JS errors'],'javascript_errors':errors},indent=2),encoding='utf-8')
        browser.close()


if __name__=='__main__':main()
