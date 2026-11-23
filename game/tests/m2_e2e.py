"""M2 end-to-end: full interview -> parsed grade -> feedback render; one
retry on malformed grader output; mid-interview snapshots; testing-mode
refusal of the button; reload resume into FEEDBACK. Run from game/:
    uv run --with playwright python tests/m2_e2e.py
"""

import json
import pathlib
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from m1_e2e import Driver, GAME_DIR, PORT, BASE, SESSION_KEY, SEED_SETTINGS, wait_port


def main():
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        cwd=GAME_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    errors = []
    try:
        assert wait_port(PORT), "http.server did not come up"
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page()
            page.add_init_script(
                f"window.localStorage.setItem('tadsdi.settings.v1', {json.dumps(json.dumps(SEED_SETTINGS))})")
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"{BASE}/index.html", wait_until="networkidle")
            d = Driver(page)

            # A. learning mode: mid-interview progress grade stores a snapshot
            #    and appends nothing to the transcript
            d.start_session(help_mode="learning")
            assert page.locator("#request-midgrade").is_visible(), "midgrade button hidden in learning mode"
            d.send("Let me ask about scale.")
            d.send("Proceeding.")
            transcript_len = len(d.stored_session()["transcript"])
            page.click("#request-midgrade")
            page.wait_for_selector("#midgrade-snapshots li", timeout=20000)
            time.sleep(0.5)
            assert len(d.stored_session()["transcript"]) == transcript_len, \
                "mid-grade appended to the transcript"
            s = d.stored_session()
            assert len(s["midInterviewGrades"]) == 1, s["midInterviewGrades"]
            snap = s["midInterviewGrades"][0]["result"]
            assert "score" not in snap, "mid grade carried a score"
            assert snap["solid_steps"] == [1], snap
            snapshot_text = page.locator("#midgrade-snapshots li").first.inner_text()
            assert "still open" in snapshot_text, snapshot_text

            # B. full interview ends in a parsed grade with feedback sections
            for i in range(4):
                d.send("Proceeding with the next part.")
            assert page.locator("#end-interview-btn").is_visible()
            page.click("#end-interview-btn")
            page.wait_for_selector("body[data-screen='feedback']", timeout=30000)
            score_text = page.locator("#feedback-score").inner_text()
            assert "6 / 10" in score_text, score_text
            row_count = page.locator("#feedback-rows tbody tr").count()
            assert row_count == 8, f"rows rendered: {row_count}"
            fail_rows = page.locator("#feedback-rows tr.row-fail").count()
            assert fail_rows == 3, f"fail rows: {fail_rows}"
            fixes = page.locator("#feedback-rows tr.row-fail td:nth-child(3)").all_inner_texts()
            assert all(f for f in fixes), f"empty fix on a failing row: {fixes}"
            assert page.locator("#feedback-realism li").count() == 2
            assert page.locator("#feedback-missing li").count() == 2
            assert page.locator("#feedback-artifacts li").count() == 1
            closing = page.locator("#feedback-closing").inner_text()
            assert len(closing) > 10, closing
            s = d.stored_session()
            assert s["state"] == "FEEDBACK" and s["grade"]["score"] == 6, s["state"]
            coverage = page.locator("#feedback-coverage").inner_text()
            assert "1, 2, 3, 4, 5" in coverage, coverage

            # C. reload resumes into FEEDBACK with the stored grade
            page.reload(wait_until="networkidle")
            page.wait_for_selector("body[data-screen='feedback']", timeout=10000)
            assert "6 / 10" in page.locator("#feedback-score").inner_text()

            # D. malformed grader reply triggers exactly one retry: queue holds
            #    only grade_bad, so the retry (default) must succeed
            d.start_session(help_mode="learning")
            for i in range(6):
                d.send("Proceeding.")
            page.evaluate("""async () => {
              const providers = await import('./js/providers.js?v=22');
              providers.setMockGraderQueue(['grade_bad']);
            }""")
            page.click("#end-interview-btn")
            page.wait_for_selector("body[data-screen='feedback']", timeout=30000)
            assert "6 / 10" in page.locator("#feedback-score").inner_text()
            assert page.locator("#grading-retry").is_hidden(), "retry button shown without failure"

            # E. testing mode hides the mid-grade button
            d.start_session(help_mode="testing")
            assert page.locator("#request-midgrade").is_hidden(), "midgrade button visible in testing mode"

            assert not errors, f"console/page errors: {errors}"
            browser.close()
        print("M2 E2E: PASS (grade->feedback render, one retry, snapshots, resume, testing refusal)")
        return 0
    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
