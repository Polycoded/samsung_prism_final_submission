"""End-to-end organizer corpus and labeled benchmark UI check."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    root = Path(__file__).parents[1] / "demo" / "messy-conference"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(os.environ.get("CITEFRONTIER_TEST_URL", "http://127.0.0.1:8013"))
        page.wait_for_function("document.getElementById('connection').textContent === 'Local session'")
        assert page.locator("#organizer-score").inner_text() == "Not run"
        page.locator("#upload-open").click()
        page.locator("#corpus-files").set_input_files([str(root / "Prism_Summit_2026.md"), str(root / "Partner_Expo_Notes.txt")])
        page.locator("#benchmark-file").set_input_files(str(root / "benchmark.json"))
        page.locator("#upload-apply").click()
        page.wait_for_function("document.getElementById('corpus-title').textContent === 'Organizer corpus'", timeout=60_000)
        page.locator("#upload-open").click()
        page.locator("#benchmark-run").click()
        page.wait_for_function("document.getElementById('organizer-score').textContent.includes('/')", timeout=60_000)
        assert page.locator("#organizer-score").inner_text() == "6/10"
        assert "0 fabricated IDs" in page.locator("#organizer-score-note").inner_text()
        assert page.locator(".benchmark-row").count() == 10
        assert page.locator(".benchmark-row.fail").count() == 4
        assert not errors, errors
        browser.close()
    print("Organizer benchmark browser QA PASS: 6/10, four visible failures, zero fabricated IDs")


if __name__ == "__main__":
    main()
