"""Smoke test of a deployed copy of the game. Run from game/:
    uv run --with playwright python tests/deployed_smoke.py <base URL>
    uv run --with playwright python tests/deployed_smoke.py     # the live site

The base URL is the directory that holds index.html, for example the
project subpath of a GitHub Pages site. The script opens the page in a
fresh browser, so it runs on the default settings: the mock provider. It
checks four things: every file the game loads arrives, nothing logs an
error, one interview plays from the menu to its grade, and "How to play"
opens at the start until its box is ticked.
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
        # A new browser opens "How to play" at the start of the game. While
        # its box is not ticked, it opens again at the next load.
        page.wait_for_selector("#howto-dialog[open]")
        assert page.evaluate("() => document.getElementById('howto-dialog').matches(':modal')"), \
            "how to play is not a modal dialog"
        page.click("#howto-close")
        page.reload(wait_until="networkidle")
        page.wait_for_selector("#howto-dialog[open]")
        page.click("#howto-close")
        # The session starts on this page. A new load would open the dialog
        # again, so the steps of Driver.start_session stand here without
        # the navigation.
        page.evaluate("() => localStorage.removeItem('tadsdi.session.v1')")
        page.select_option("#problem-select", "url-shortener")
        page.select_option("#help-mode", "learning")
        page.select_option("#constraint-mode", "unconstrained")
        page.select_option("#timer-preset", "0")
        page.click("#start-interview")
        page.wait_for_selector("#chat-log .chat-message.interviewer", timeout=15000)
        page.wait_for_function(
            "() => document.getElementById('send-btn').disabled === false")
        assert page.locator("#timer-hud").is_hidden(), "timer shows with the timer option off"
        d.send("About ten million writes per day, as a ballpark.")
        # The first hint of the mock script reveals hidden guidance item 2.
        # The game records it in the ledger and shows no control line.
        d.send("I am stuck, please give me a hint.")
        assert d.stored_session()["ledger"]["revealedGuidance"] == [2], \
            "a hint that reveals guidance did not reach the ledger"
        assert "[[" not in page.locator("#chat-log").inner_text()
        d.send("Estimate first.\n$$QPS = 1160$$")
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

        # The box in how to play is remembered: the next load opens no dialog.
        page.click("#open-settings")
        page.click("#open-howto-settings")
        page.wait_for_selector("#howto-dialog[open]")
        page.check("#howto-skip")
        page.click("#howto-close")
        page.keyboard.press("Escape")  # closes Settings
        page.reload(wait_until="networkidle")
        page.wait_for_function("() => Boolean(window.__tadsdi)")  # the game booted
        assert page.evaluate("() => document.getElementById('howto-dialog').open") is False, \
            "how to play opened at the start with the box ticked"
        browser.close()

    assert not failures, f"files that did not load:\n  " + "\n  ".join(failures)
    assert not errors, f"console or page errors:\n  " + "\n  ".join(errors)
    print(f"DEPLOYED SMOKE: PASS ({base})")
    print(f"  {files} files loaded, zero errors, one interview to its grade ({score}),"
          " how to play opens at the start until its box is ticked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
