"""Smoke test of a deployed copy of the game. Run from game/:
    uv run --with playwright python tests/deployed_smoke.py <base URL>
    uv run --with playwright python tests/deployed_smoke.py     # the live site

The base URL is the directory that holds index.html, for example the
project subpath of a GitHub Pages site. The script opens the page in a
fresh browser, so it runs on the default settings: the mock provider. It
checks three things: every file the game loads arrives, nothing logs an
error, and one interview plays from the menu to its grade.
"""

import pathlib
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from m1_e2e import Driver  # noqa: E402

# GitHub publishes a project site at <user>.github.io/<repository>/. The
# address follows the repository name, so change this line when the game
# moves to another repository.
LIVE = "https://kal-hermes.github.io/TASDIS/"


def main():
    base = (sys.argv[1] if len(sys.argv) > 1 else LIVE).rstrip("/")
    failures = []  # a file the game asked for that did not arrive
    errors = []    # a console error or an uncaught exception

    def missing_file(response):
        # A browser asks for /favicon.ico on its own; the game has none.
        if response.status >= 400 and not response.url.endswith("/favicon.ico"):
            failures.append(f"HTTP {response.status} {response.url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page()
        page.set_default_timeout(30000)
        page.on("response", missing_file)
        page.on("requestfailed", lambda r: failures.append(f"FAILED {r.url} {r.failure}"))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(f"{base}/index.html", wait_until="networkidle")
        page.wait_for_selector("#start-interview", state="visible")
        loaded = page.evaluate(
            "() => performance.getEntriesByType('resource').map((e) => e.name)")
        assert loaded, "the page loaded no files besides index.html"
        assert all(url.startswith(base + "/") for url in loaded), \
            [url for url in loaded if not url.startswith(base + "/")]

        d = Driver(page, base)
        d.start_session(help_mode="learning")
        assert page.locator("#timer-hud").is_hidden(), "timer shows with the timer option off"
        d.send("About ten million writes per day, as a ballpark.")
        page.click("#tab-btn-latex")
        page.fill("#artifact-source", "QPS = 1160")
        page.wait_for_selector("#artifact-preview .katex")
        page.click("#artifact-submit")
        page.wait_for_selector("#chat-log .chat-message.artifact .katex")
        d.wait_reply()
        d.submit_mermaid()
        page.wait_for_selector("#chat-log .chat-message.artifact svg")
        for _ in range(5):
            d.send("Proceeding with the next part.")
        page.wait_for_selector("#end-interview-btn", state="visible")
        with page.expect_download() as download:
            page.click("#export-transcript")
        exported = pathlib.Path(download.value.path()).read_text()
        assert "```latex" in exported and "```mermaid" in exported, "the export lacks the artifacts"
        page.click("#end-interview-btn")
        page.wait_for_selector("body[data-screen='feedback']")
        score = page.locator("#feedback-score").inner_text()
        assert "6 / 10" in score, score
        files = page.evaluate("() => performance.getEntriesByType('resource').length")
        browser.close()

    assert not failures, f"files that did not load:\n  " + "\n  ".join(failures)
    assert not errors, f"console or page errors:\n  " + "\n  ".join(errors)
    print(f"DEPLOYED SMOKE: PASS ({base})")
    print(f"  {files} files loaded, zero errors, one interview to its grade ({score})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
