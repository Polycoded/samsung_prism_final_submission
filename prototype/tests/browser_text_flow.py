"""Real browser + real retrieval; no microphone or answer stubs."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    out = Path('prototype/reports')
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, permissions=['clipboard-read', 'clipboard-write'])
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(os.environ.get('CITEFRONTIER_TEST_URL', 'http://127.0.0.1:8011'))
        page.wait_for_function("document.getElementById('connection').textContent==='Local session'")
        assert page.locator('#voice').count() == 0
        assert page.locator('body').evaluate("e=>e.classList.contains('focus-mode')")
        page.locator('#question').fill('LumaPad S1 warranty period, sorry I meant S2')
        page.locator('#question').press('Control+Enter')
        page.wait_for_function("document.getElementById('answer').textContent.includes('36-month')")
        assert page.locator('#transcript-change').inner_text() == 'Understood as: LumaPad S2 warranty period'
        assert not page.locator('.evidence-pane').is_visible()
        page.locator('.citation').click()
        assert page.locator('.quote').is_visible()
        page.locator('#copy-answer').click()
        page.wait_for_function("document.getElementById('copy-answer').textContent==='Copied with citations'")
        assert 'LumaPad_S2 §Warranty.1' in page.evaluate('navigator.clipboard.readText()')
        page.locator('#view-toggle').click()
        page.locator('[data-scenario="refinement"]').click()
        page.locator('#replay').click()
        page.wait_for_function("document.getElementById('version-history').textContent.includes('1 preserved')", timeout=60000)
        page.wait_for_function("!document.getElementById('replay').disabled")
        assert page.locator('.claim-diff').count() == 1
        page.locator('.claim-diff summary').click()
        assert '24-month' in page.locator('.claim-diff p').inner_text()
        assert 'Unchanged' in page.locator('#answer').inner_text()
        before = page.locator('#session-stats').inner_text()
        page.locator('#bullets').click()
        page.wait_for_function("document.getElementById('input-state').textContent==='Retrieval suppressed'")
        assert before == page.locator('#session-stats').inner_text()
        page.locator('#view-toggle').click()
        page.screenshot(path=str(out/'text-flow-desktop.png'), full_page=True)
        for width in (390, 768, 1440):
            page.set_viewport_size({'width': width, 'height': 900})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), width
        page.set_viewport_size({'width': 390, 'height': 844})
        page.screenshot(path=str(out/'text-flow-mobile.png'), full_page=True)
        page.locator('#reset').click()
        page.wait_for_function("document.getElementById('connection').textContent==='Local session'")
        assert page.locator('#question').input_value() == ''
        assert not page.locator('#transcript-change').is_visible()
        assert not page.locator('.evidence-pane').is_visible()
        # A new typed follow-up must stream even after a finalized turn.
        page.locator('#question').fill('LumaPad S1 warranty period')
        page.locator('#commit').click()
        page.wait_for_function("!document.getElementById('commit').disabled")
        page.locator('#question').fill('What about warranty liquid damage exclusions?')
        page.wait_for_timeout(900)
        page.wait_for_function("document.getElementById('input-state').textContent!=='Final transcript committed'")
        page.locator('#commit').click()
        page.wait_for_function("document.getElementById('answer').textContent.includes('liquid damage')")
        page.locator('#question').fill('For LumaPad S1, what is the warranty period? What receipt opens a repair?')
        page.locator('#commit').click()
        page.wait_for_function("!document.getElementById('commit').disabled")
        assert page.locator('#intents .intent').count() == 2
        assert page.locator('#intents').is_visible()
        assert page.locator('.citation').count() == 2
        page.locator('#question').fill('What is the warranty for LumaPad S1 and LumaPad S2 and where can they be repaired?')
        page.locator('#commit').click()
        page.wait_for_function("document.getElementById('input-state').textContent==='Clarification needed'")
        assert 'more than one product' in page.locator('#error').inner_text()
        assert not errors, errors
        (out/'text-flow-qa.json').write_text(json.dumps({'status': 'PASS', 'checks': ['no voice controls', 'text correction', 'source inspection', 'copy with citations', 'refinement diff', 'unchanged claim', 'format suppression', 'responsive layout', 'session reset', 'follow-up streaming', 'visible multi-intent splitting', 'ambiguous product clarification'], 'javascript_errors': errors}, indent=2), encoding='utf-8')
        browser.close()


if __name__ == '__main__':
    main()
