"""Browser QA for the vendored GSAP enhancement layer."""
import os
from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(os.environ.get("CITEFRONTIER_TEST_URL", "http://127.0.0.1:8013"))
        page.wait_for_function("document.getElementById('connection').textContent === 'Local session'")
        assert page.evaluate("typeof gsap === 'object' && gsap.version === '3.13.0'")
        assert page.evaluate("typeof CiteMotion === 'object'")
        page.locator("#replay").click()
        page.wait_for_function("document.querySelectorAll('.claim').length === 3", timeout=60_000)
        assert "Understood as:" in page.locator("#transcript-change").inner_text()
        assert "umm" not in page.locator("#transcript-change").inner_text().lower()
        assert "BERT" in page.locator("#bert-score").inner_text()
        assert "0 fallback" in page.locator("#bert-score-note").inner_text()
        page.locator(".citation").first.click()
        assert page.locator(".quote").is_visible()
        page.locator("#view-toggle").click()
        page.locator("#scorecard").click()
        page.wait_for_selector("#validation-dialog[open]")
        page.locator("#close-validation").click()
        assert not errors, errors

        page.emulate_media(reduced_motion="reduce")
        page.reload()
        page.wait_for_function("document.getElementById('connection').textContent === 'Local session'")
        assert page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches")
        assert not errors, errors
        browser.close()
    print("GSAP browser QA PASS: replay, claims, citation, inspector, dialog, reduced motion, no JS errors")


if __name__ == "__main__":
    main()
