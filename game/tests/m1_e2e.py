"""M1 end-to-end test: scripted mock interview from MENU through all five
steps to close, artifact submission, reload resume, timer behavior, expiry,
and mode behavior. Run from game/:
    uv run --with playwright python tests/m1_e2e.py
"""

import json
import pathlib
import re
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

GAME_DIR = pathlib.Path(__file__).resolve().parent.parent
PORT = 8140
BASE = f"http://127.0.0.1:{PORT}"
SESSION_KEY = "tadsdi.session.v1"

SEED_SETTINGS = json.dumps({
    "roles": {
        "text": {"provider": "mock", "baseUrl": "", "model": "mock-interviewer", "apiKey": ""},
        "vision": {"provider": "mock", "baseUrl": "", "model": "mock-vision", "apiKey": ""},
        "image": {"provider": "mock", "baseUrl": "", "model": "mock-image", "apiKey": ""},
    },
    "preferences": {"helpMode": "learning", "constraintMode": "unconstrained", "timerMinutes": 0,
                    # These suites do not test the start of the game, so how to
                    # play must stay closed there. tests/m3_howto.py covers it.
                    "showHowToAtStart": False},
})

MERMAID_SOURCE = "graph LR; Client-->LB; LB-->App; App-->DB;"


def wait_port(port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


def seconds(text):
    """Seconds in a timer readout like '14:59'."""
    minutes, secs = text.split(":")
    return int(minutes) * 60 + int(secs)


class Driver:
    def __init__(self, page, base=BASE):
        self.page = page
        self.base = base

    def open_menu(self):
        """Drop any stored session and load the menu."""
        # A same-origin static file allows the storage access without
        # running the game, which would resume the old session first.
        self.page.goto(f"{self.base}/css/main.css")
        self.page.evaluate("() => localStorage.removeItem('tadsdi.session.v1')")
        self.page.goto(f"{self.base}/index.html", wait_until="networkidle")
        self.page.wait_for_selector("#start-interview", state="visible")

    def start_session(self, problem="url-shortener", help_mode="learning",
                      constraint="unconstrained", timer="0", probe_cap=None):
        page = self.page
        page.evaluate("slug => localStorage.removeItem('tadsdi.session.v1')", None)
        page.goto(f"{self.base}/index.html", wait_until="networkidle")
        page.select_option("#problem-select", problem)
        page.select_option("#help-mode", help_mode)
        page.select_option("#constraint-mode", constraint)
        page.select_option("#timer-preset", timer)
        if probe_cap is not None:
            page.select_option("#probe-cap", probe_cap)
        page.click("#start-interview")
        page.wait_for_selector("#chat-log .chat-message.interviewer", timeout=15000)
        page.wait_for_selector("#interview-busy", state="hidden", timeout=15000)

    def send(self, text):
        self.page.fill("#candidate-input", text)
        self.page.click("#send-btn")
        self.wait_reply()

    def wait_reply(self):
        # send becomes disabled while busy, then re-enabled after the reply
        self.page.wait_for_function(
            "() => document.getElementById('send-btn').disabled === true", timeout=5000)
        self.page.wait_for_function(
            "() => document.getElementById('send-btn').disabled === false", timeout=20000)

    def submit_mermaid(self):
        page = self.page
        page.click("#tab-btn-mermaid")
        page.fill("#artifact-source", MERMAID_SOURCE)
        page.wait_for_selector("#artifact-preview svg", timeout=10000)
        page.click("#artifact-submit")
        page.wait_for_selector("#chat-log .chat-message.artifact", timeout=10000)
        self.wait_reply()

    def stored_session(self):
        raw = self.page.evaluate(f"() => localStorage.getItem('{SESSION_KEY}')")
        return json.loads(raw)

    def screen(self):
        return self.page.evaluate("() => document.body.dataset.screen")


def main():
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        cwd=GAME_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    errors = []
    try:
        assert wait_port(PORT), "http.server did not come up"
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            context = browser.new_context()
            page = context.new_page()
            page.add_init_script(f"window.localStorage.setItem('tadsdi.settings.v1', {json.dumps(SEED_SETTINGS)})")
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"{BASE}/index.html", wait_until="networkidle")
            d = Driver(page)

            # menu shows the bank
            slugs = page.evaluate("() => window.__tadsdi.getProblemSlugs()")
            assert len(slugs) == 8, f"expected 8 problems, got {slugs}"
            options = page.locator("#problem-select option:not([disabled])").count()
            assert options == 8, f"menu options: {options}"

            # A. scripted multi-turn interview advances the tracker
            d.start_session(help_mode="learning")
            for i in range(6):
                d.send("Let me ask about scale and constraints." if i == 0 else "Proceeding with the next part.")
            tracker = page.evaluate("""() => [...document.querySelectorAll('#step-tracker li.covered')].map(li => li.dataset.step)""")
            assert tracker == ["1", "2", "3", "4", "5"], f"tracker coverage: {tracker}"

            # artifact submission appears in chat + ledger side effect
            d.submit_mermaid()
            s = d.stored_session()
            assert len(s["ledger"]["components"]) == 1, s["ledger"]
            assert s["artifacts"][0]["kind"] == "mermaid", s["artifacts"]
            assert s["artifacts"][0]["step"] == s["currentStep"], s

            # end button after coverage, wrap-up -> grading -> FEEDBACK (M2)
            assert page.locator("#end-interview-btn").is_visible()
            page.click("#end-interview-btn")
            page.wait_for_selector("body[data-screen='feedback']", timeout=30000)
            s = d.stored_session()
            assert s["ended"], s["state"]
            assert s["grade"] and s["grade"]["score"] >= 0, s.get("grade")
            wrap_msgs = [m for m in s["transcript"] if m["speaker"] == "interviewer"]
            assert "wrap" in wrap_msgs[-1]["text"].lower(), wrap_msgs[-1]

            # E. testing mode refuses help and hides the step tracker entirely
            d.start_session(help_mode="testing")
            assert page.locator("#tracker-block").is_hidden(), "tracker visible in testing mode"
            assert page.locator("#toggle-tracker").is_hidden(), "tracker toggle visible in testing mode"
            d.send("Can I have a hint please?")
            last = page.evaluate("() => [...document.querySelectorAll('#chat-log .chat-message.interviewer')].at(-1).textContent")
            assert "testing mode" in last.lower(), last

            # F. learning mode: tracker visible with a working toggle
            d.start_session(help_mode="learning")
            assert page.locator("#tracker-block").is_visible(), "tracker hidden in learning mode"
            page.click("#toggle-tracker")
            assert page.locator("#tracker-block").is_hidden(), "toggle did not hide tracker"
            page.reload(wait_until="networkidle")
            page.wait_for_selector("body[data-screen='interview']", timeout=10000)
            assert page.locator("#tracker-block").is_hidden(), "tracker visibility lost on reload"
            s = d.stored_session()
            assert s["showTracker"] is False, s["showTracker"]
            page.click("#toggle-tracker")
            assert page.locator("#tracker-block").is_visible(), "toggle did not re-show tracker"

            # learning mode ladder: hint -> fuller -> walkthrough
            d.send("I am stuck, give me a hint")
            h1 = page.evaluate("() => [...document.querySelectorAll('#chat-log .chat-message.interviewer')].at(-1).textContent")
            assert "Hint:" in h1, h1
            d.send("still stuck")
            h2 = page.evaluate("() => [...document.querySelectorAll('#chat-log .chat-message.interviewer')].at(-1).textContent")
            assert "Fuller answer" in h2, h2
            d.send("hint again please")
            h3 = page.evaluate("() => [...document.querySelectorAll('#chat-log .chat-message.interviewer')].at(-1).textContent")
            assert "Walkthrough" in h3, h3

            # B. reload resumes the session (transcript restored, input enabled)
            d.start_session()
            d.send("First turn.")
            count_before = page.locator("#chat-log .chat-message").count()
            page.reload(wait_until="networkidle")
            page.wait_for_selector("body[data-screen='interview']", timeout=10000)
            count_after = page.locator("#chat-log .chat-message").count()
            assert count_after == count_before, f"transcript lost on reload: {count_before} -> {count_after}"
            assert page.locator("#send-btn").is_enabled(), "send disabled after resume"
            s = d.stored_session()
            assert len(s["transcript"]) == 3, s["transcript"]

            # C. timer: visible, preserved by reload, paused until next turn
            d.start_session(timer="15")
            hud = page.locator("#timer-hud")
            assert hud.is_visible()
            assert re.match(r"^\d+:\d\d$", hud.inner_text()), hud.inner_text()
            v1 = hud.inner_text()
            page.reload(wait_until="networkidle")
            page.wait_for_selector("body[data-screen='interview']", timeout=10000)
            v2 = page.locator("#timer-hud").inner_text()
            # The clock runs until the page unloads, so a slow reload can cost
            # a few ticks. The remaining time must be preserved within that.
            assert seconds(v1) - 5 <= seconds(v2) <= seconds(v1), \
                f"timer not preserved: {v1} -> {v2}"
            time.sleep(2.5)
            v3 = page.locator("#timer-hud").inner_text()
            assert v3 == v2, f"timer ticked while paused: {v2} -> {v3}"
            d.send("Resuming after reload.")
            time.sleep(2.5)
            v4 = page.locator("#timer-hud").inner_text()
            assert v4 != v1, f"timer did not resume: {v1} -> {v4}"
            s = d.stored_session()
            assert s["timer"]["remainingMs"] < 15 * 60000, s["timer"]

            # D. expiry runs the wrap-up and lands in graded FEEDBACK (M2)
            #    The live page saves its own clock on every tick, so the edit
            #    also blocks later saves of the session until the reload.
            page.evaluate(f"""() => {{
              const s = JSON.parse(localStorage.getItem('{SESSION_KEY}'));
              s.timer.remainingMs = 1500;
              localStorage.setItem('{SESSION_KEY}', JSON.stringify(s));
              // From here the live page cannot overwrite the edited session.
              const setItem = Storage.prototype.setItem;
              Storage.prototype.setItem = function (key, value) {{
                if (key === '{SESSION_KEY}') return;
                return setItem.call(this, key, value);
              }};
            }}""")
            page.reload(wait_until="networkidle")
            page.wait_for_selector("body[data-screen='interview']", timeout=10000)
            d.send("Almost done here.")
            try:
                page.wait_for_selector("body[data-screen='feedback']", timeout=30000)
            except Exception:
                stuck = d.stored_session()
                print("EXPIRY STUCK:", page.get_attribute("body", "data-screen"),
                      stuck["state"], stuck["timer"],
                      [(m["speaker"], m["text"][:50]) for m in stuck["transcript"]][-4:],
                      page.locator("#chat-log .notice.error").all_inner_texts())
                raise
            s = d.stored_session()
            assert s["timer"]["remainingMs"] == 0, s["timer"]
            assert s["state"] == "FEEDBACK" and s["grade"], s["state"]
            system_msgs = [m for m in s["transcript"] if m["speaker"] == "system"]
            assert any("Time is up" in m["text"] for m in system_msgs), system_msgs
            wrap = [m for m in s["transcript"] if m["speaker"] == "interviewer"][-1]["text"].lower()
            assert "wrap" in wrap, wrap

            assert not errors, f"console/page errors: {errors}"
            browser.close()
        print("M1 E2E: PASS (menu->5 steps->close, artifact, resume, timer, expiry, modes; zero console errors)")
        return 0
    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
