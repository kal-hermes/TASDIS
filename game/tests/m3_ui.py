"""M3 tasks 2 and 3 in the browser: the how-to-play section and the
transcript export. Run from game/:
    uv run --with playwright python tests/m3_ui.py
"""

import json
import pathlib
import re
import subprocess
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from m1_e2e import Driver, GAME_DIR, PORT as M1_PORT, SEED_SETTINGS  # noqa: E402

PORT = M1_PORT + 4
BASE = f"http://127.0.0.1:{PORT}"
MODULES = BASE + "/"  # base URL for dynamic imports in page.evaluate
SETTINGS_KEY = "tadsdi.settings.v1"

# What the how-to-play text has to name: every provider role and every
# menu toggle, with the facts a first-time player needs for each.
HOWTO_TERMS = [
    "text", "vision", "image",             # the three Settings rows
    "Help mode", "Learning", "Testing", "step tracker",
    "Constraints", "Unconstrained", "Constrained",
    "Proactive guidance", "Off",
    "Timer",
    "local storage",                       # where API keys live
]


def is_open(page, dialog_id):
    return page.evaluate(
        "id => document.getElementById(id).open", dialog_id)


def main():
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        cwd=GAME_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page()
            page.set_default_timeout(20000)
            page.add_init_script(
                f"window.localStorage.setItem('{SETTINGS_KEY}', {json.dumps(SEED_SETTINGS)})")
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            d = Driver(page, BASE)
            d.open_menu()

            # ---- A. how to play, opened from the menu ------------------
            page.click("#open-howto")
            page.wait_for_selector("#howto-dialog[open]")
            text = page.locator("#howto-dialog").inner_text()
            missing = [term for term in HOWTO_TERMS if term not in text]
            assert not missing, f"how-to-play lacks {missing}"
            assert "Test connection" in text, "how-to-play does not name the connection test"
            page.click("#howto-close")
            assert not is_open(page, "howto-dialog"), "Close did not close how to play"

            # ---- B. how to play, opened from Settings ------------------
            page.click("#open-settings")
            page.wait_for_selector("#settings-dialog[open]")
            page.click("#open-howto-settings")
            page.wait_for_selector("#howto-dialog[open]")
            assert is_open(page, "settings-dialog"), "Settings closed under how to play"
            # Escape closes the top dialog only
            page.keyboard.press("Escape")
            assert not is_open(page, "howto-dialog"), "Escape did not close how to play"
            assert is_open(page, "settings-dialog"), "Escape also closed Settings"
            page.keyboard.press("Escape")
            assert not is_open(page, "settings-dialog"), "Escape did not close Settings"
            print("  ok   how to play: opens from menu and Settings, names every row and toggle")

            # ---- C. export: the pure function on a built session -------
            out = page.evaluate("""async (base) => {
              const state = await import(base + 'js/state.js?v=24');
              const exp = await import(base + 'js/export.js?v=24');
              const problem = { id: 'url-shortener', title: 'URL Shortener',
                vague_prompt: 'Design a URL shortening service like bit.ly.' };
              const s = state.newSession(problem, { helpMode: 'learning',
                constraintMode: 'unconstrained' });
              state.addMessage(s, 'interviewer', 'Hi, welcome.');
              state.addMessage(s, 'candidate', 'Thanks. Ten million writes per day.');
              state.addArtifact(s, { kind: 'latex',
                source: '10^7 \\\\div 86400 \\\\approx 116', step: 2 });
              state.addArtifact(s, { kind: 'mermaid', source: 'graph LR; Client-->API;', step: 3 });
              state.addMessage(s, 'system', 'Time is up.');
              s.timer = { enabled: true, presetMs: 900000, remainingMs: 0 };
              s.midInterviewGrades.push({ ts: 1700000000000, result: { solid_steps: [1],
                passing_rows: ['requirements'], obvious_gaps: ['caching'],
                note: 'the interview is still open' } });
              s.grade = { score: 5, process_coverage: [1, 2], rows: [
                { name: 'requirements', pass: true, fix: '' },
                { name: 'caching', pass: false, fix: 'Add a cache.' }],
                realism: [{ claim: '116 writes per second', verdict: 'realistic', note: 'fine' }],
                missing: ['a queue for events'],
                artifact_comments: [{ artifact_id: s.artifacts[0].id, comment: 'Clear estimate.' }],
                closing: 'Good work today.' };
              return { md: exp.transcriptMarkdown(s), again: exp.transcriptMarkdown(s),
                name: exp.exportFileName(s), firstId: s.artifacts[0].id,
                secondId: s.artifacts[1].id };
            }""", MODULES)
            md = out["md"]
            assert md == out["again"], "transcriptMarkdown is not deterministic"
            assert md.startswith("# System design interview: URL Shortener\n"), md[:60]
            assert re.search(r"^tadsdi-url-shortener-\d{8}-\d{4}\.md$", out["name"]), out["name"]
            expected = [
                "**Interviewer:** Hi, welcome.",      # speakers keep their role
                "**Candidate:** Thanks. Ten million writes per day.",
                "**System:** Time is up.",
                "```latex\n10^7 \\div 86400 \\approx 116\n```",   # artifacts keep their source
                "```mermaid\ngraph LR; Client-->API;\n```",
                "- Help mode: learning", "- Constraints: unconstrained", "- Timer: 15 minutes",
                "| Row | Verdict | Fix |", "| requirements | pass |  |", "| caching | fail | Add a cache. |",
                "116 writes per second: realistic (fine)", "- a queue for events",
                f"{out['firstId']}: Clear estimate.",
                "> Good work today.", "- Score: 5 / 10",
                "the interview is still open",
            ]
            missing = [e for e in expected if e not in md]
            assert not missing, f"export lacks {missing}"
            print("  ok   export unit: speakers, artifacts, options, grade, deterministic")

            # ---- D. export: the download buttons in the browser -------
            d.start_session(help_mode="learning")
            d.send("Let me start with scale.")
            d.submit_mermaid()
            with page.expect_download() as mid:
                page.click("#export-transcript")
            mid_text = pathlib.Path(mid.value.path()).read_text()
            assert mid.value.suggested_filename.startswith("tadsdi-url-shortener-"), \
                mid.value.suggested_filename
            assert mid.value.suggested_filename.endswith(".md")
            for needle in ["# System design interview: URL Shortener", "**Interviewer:**",
                           "**Candidate:** Let me start with scale.", "```mermaid"]:
                assert needle in mid_text, f"mid-interview export lacks {needle!r}"
            assert "## Grade" not in mid_text, "mid-interview export has a grade section"
            for _ in range(5):
                d.send("Proceeding.")
            assert page.locator("#end-interview-btn").is_visible()
            page.click("#end-interview-btn")
            page.wait_for_selector("body[data-screen='feedback']", timeout=30000)
            with page.expect_download() as final:
                page.click("#export-feedback")
            final_text = pathlib.Path(final.value.path()).read_text()
            assert "Score: 6 / 10" in final_text, "final export lacks the score"
            assert "```mermaid" in final_text, "final export lacks the artifact"
            print("  ok   export browser: mid-interview and feedback downloads are valid Markdown")

            assert not errors, f"console/page errors: {errors}"
            browser.close()
        print("M3 UI: PASS (how to play, transcript export)")
        return 0
    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
