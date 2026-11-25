"""M3 task 5: self-play. Run from game/:
    uv run --with playwright python tests/m3_selfplay.py

A. A clean interview on the mock from MENU to FEEDBACK with every control:
   random problem, constrained mode, proactive guidance, timer, Enter to
   send, an empty message, LaTeX, Mermaid and prose artifacts (with the two
   render error paths), a double submit, the help ladder, a progress grade,
   both exports, and a reload on the feedback screen.
B. The same interview with provider failures at seven points. Every failure
   shows a readable notice, every retry recovers, and no message is lost.
C. Edges: the wire format of the Anthropic and OpenAI-compatible adapters,
   the Settings dialog (connection test, context window round trip), a
   problem bank that fails to load, a reload in the GRADING state, and
   screens opened without a session.
"""

import json
import pathlib
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from m1_e2e import Driver, GAME_DIR, MERMAID_SOURCE, PORT as M1_PORT, SEED_SETTINGS  # noqa: E402
from m3_errors import notice_text, set_text_role  # noqa: E402

PORT = M1_PORT + 6
BASE = f"http://127.0.0.1:{PORT}"
MODULES = BASE + "/"  # base URL for dynamic imports in page.evaluate
SETTINGS_KEY = "tadsdi.settings.v1"
SESSION_KEY = "tadsdi.session.v1"
SLUGS = ["url-shortener", "rate-limiter", "news-feed", "chat", "autocomplete",
         "web-crawler", "unique-id-generator", "notification-system"]
ANTHROPIC_API = "**/anthropic/v1/messages"
OPENAI_API = "**/fake/v1/chat/completions"


def queue_faults(page, faults):
    page.evaluate(
        """async ([base, faults]) => {
          const providers = await import(base + 'js/providers.js?v=31');
          providers.setMockFaultQueue(faults);
        }""", [MODULES, faults])


def wait_ready(page):
    page.wait_for_function(
        "() => document.getElementById('send-btn').disabled === false", timeout=20000)


def transcript(page):
    return page.evaluate(
        "key => JSON.parse(localStorage.getItem(key)).transcript", SESSION_KEY)


def speakers(page):
    return [m["speaker"] for m in transcript(page)]


def wait_interview(page):
    page.wait_for_selector("body[data-screen='interview']", timeout=20000)
    wait_ready(page)


def export_text(page, button_id):
    with page.expect_download() as download:
        page.click(f"#{button_id}")
    return pathlib.Path(download.value.path()).read_text()


def interview_ready(page):
    page.wait_for_selector("#chat-log .chat-message.interviewer", timeout=20000)
    wait_interview(page)


# ---- A. the clean self-play ---------------------------------------------

def run_clean(d, page):
    d.open_menu()
    page.check("#problem-random")
    assert page.locator("#problem-select").is_disabled(), "random problem leaves the select on"
    page.select_option("#help-mode", "learning")
    page.select_option("#constraint-mode", "constrained")
    page.select_option("#proactive-guidance", "on")
    page.select_option("#timer-preset", "30")
    page.click("#start-interview")
    interview_ready(page)
    s = d.stored_session()
    assert s["problemId"] in SLUGS, s["problemId"]
    assert s["constraintMode"] == "constrained" and s["proactiveHints"] is True, s
    assert s["timer"]["enabled"] and s["timer"]["presetMs"] == 30 * 60000, s["timer"]
    assert page.locator("#timer-hud").is_visible()

    # Enter sends (page.type fires a keydown per character); an empty
    # message does nothing
    page.type("#candidate-input", "What scale should I plan for?", delay=5)
    page.press("#candidate-input", "Enter")
    d.wait_reply()
    assert speakers(page)[-1] == "interviewer", speakers(page)

    # clicks that arrive while the interviewer responds are ignored
    before = len(transcript(page))
    page.fill("#candidate-input", "Second point of the design.")
    page.click("#send-btn")
    page.evaluate("""() => {
      for (const id of ['end-interview-btn', 'request-midgrade',
                       'grading-retry', 'briefing-retry']) {
        document.getElementById(id).click();
      }
    }""")
    d.wait_reply()
    s = d.stored_session()
    assert s["state"] == "INTERVIEW" and len(s["transcript"]) == before + 2, s["state"]
    assert s["midInterviewGrades"] == [], "a click during a reply started a progress grade"

    before = len(transcript(page))
    page.fill("#candidate-input", "   ")
    page.click("#send-btn")
    time.sleep(0.5)
    assert len(transcript(page)) == before, "an empty message reached the transcript"
    assert page.locator("#send-btn").is_enabled()

    # LaTeX: live preview, KaTeX in the chat, and the render error path
    page.click("#tab-btn-latex")
    page.fill("#artifact-source", "QPS = 1160")
    page.wait_for_selector("#artifact-preview .katex", timeout=10000)
    page.click("#artifact-submit")
    page.wait_for_selector("#chat-log .chat-message.artifact .katex", timeout=10000)
    d.wait_reply()
    page.fill("#artifact-source", "\\frac{")
    page.wait_for_selector("#artifact-preview .render-error", timeout=10000)
    assert "KaTeX error" in page.locator("#artifact-preview .render-error").inner_text()
    page.click("#artifact-submit")
    page.wait_for_selector("#chat-log .chat-message.artifact .render-error", timeout=10000)
    d.wait_reply()

    # Mermaid: render error path, then a diagram; a double submit adds one artifact
    page.click("#tab-btn-mermaid")
    page.fill("#artifact-source", "banana")
    page.wait_for_selector("#artifact-preview .render-error", timeout=10000)
    page.fill("#artifact-source", MERMAID_SOURCE)
    page.wait_for_selector("#artifact-preview svg", timeout=10000)
    artifacts_before = len(d.stored_session()["artifacts"])
    page.click("#artifact-submit")
    page.evaluate("() => document.getElementById('artifact-submit').click()")
    page.wait_for_selector("#chat-log .chat-message.artifact svg", timeout=10000)
    d.wait_reply()
    assert len(d.stored_session()["artifacts"]) == artifacts_before + 1, "a double submit added two artifacts"

    # Prose
    page.click("#tab-btn-prose")
    page.fill("#artifact-source", "Decision: one primary database.")
    page.click("#artifact-submit")
    d.wait_reply()
    s = d.stored_session()
    kinds = sorted(a["kind"] for a in s["artifacts"])
    assert kinds == ["latex", "latex", "mermaid", "prose"], kinds
    assert s["ledger"]["estimates"] and s["ledger"]["components"], s["ledger"]

    # Help ladder: two requests, two different replies, both marked as help
    d.send("I am stuck, please give me a hint.")
    d.send("A hint again please.")
    s = d.stored_session()
    helps = [m["text"] for m in s["transcript"] if m.get("helpReply")]
    assert len(helps) == 2 and helps[0] != helps[1], helps

    # On to the end of the process
    for _ in range(5):
        d.send("Proceeding with the next part.")
    page.wait_for_selector("#end-interview-btn", state="visible", timeout=20000)
    page.click("#request-midgrade")
    page.wait_for_selector("#midgrade-snapshots li", timeout=20000)
    mid = export_text(page, "export-transcript")
    for fence in ["```latex", "```mermaid", "```text"]:
        assert fence in mid, f"mid-interview export lacks {fence}"
    assert "## Progress reports" in mid and "## Grade" not in mid

    page.click("#end-interview-btn")
    page.wait_for_selector("body[data-screen='feedback']", timeout=30000)
    score = page.locator("#feedback-score").inner_text()
    assert "6 / 10" in score, score
    final = export_text(page, "export-feedback")
    assert "Score: 6 / 10" in final and "## Progress reports" in final
    page.reload(wait_until="networkidle")
    page.wait_for_selector("body[data-screen='feedback']", timeout=10000)
    assert page.locator("#feedback-score").inner_text() == score, "feedback changed after reload"
    s = d.stored_session()
    assert s["state"] == "FEEDBACK" and sorted(s["coveredSteps"]) == [1, 2, 3, 4, 5], s["coveredSteps"]
    print("  ok   A: clean self-play from MENU to FEEDBACK with every control")


# ---- B. the same interview with provider failures ------------------------

def run_with_faults(d, page):
    d.open_menu()
    page.select_option("#help-mode", "learning")
    queue_faults(page, ["network"])
    page.click("#start-interview")
    page.wait_for_selector("#briefing-retry", state="visible", timeout=20000)
    assert "network or CORS" in page.locator("#briefing-status").inner_text()
    # A reload resumes the stored BRIEFING state and runs the briefing again.
    page.reload(wait_until="networkidle")
    interview_ready(page)
    assert len(d.stored_session()["transcript"]) == 1, "the briefing ran twice"

    # 1. a turn that times out
    queue_faults(page, ["timeout"])
    page.fill("#candidate-input", "First point of the design.")
    page.click("#send-btn")
    assert "did not answer within" in notice_text(page)
    page.locator("#chat-log .notice.error .retry-btn").click()
    wait_ready(page)
    assert speakers(page)[-2:] == ["candidate", "interviewer"], speakers(page)

    # 2. a help request that gets a server error
    queue_faults(page, ["http:500"])
    page.fill("#candidate-input", "help please")
    page.click("#send-btn")
    assert "HTTP 500" in notice_text(page)
    page.locator("#chat-log .notice.error .retry-btn").click()
    wait_ready(page)
    assert d.stored_session()["transcript"][-1].get("helpReply") is True

    # 3. an artifact submission that gets an empty reply
    page.click("#tab-btn-mermaid")
    page.fill("#artifact-source", MERMAID_SOURCE)
    queue_faults(page, ["empty"])
    page.click("#artifact-submit")
    page.wait_for_selector("#chat-log .chat-message.artifact", timeout=10000)
    assert "empty reply" in notice_text(page)
    page.locator("#chat-log .notice.error .retry-btn").click()
    wait_ready(page)
    assert len(d.stored_session()["artifacts"]) == 1

    # 4. a progress grade that is rate limited twice (the grader retries
    #    once by itself), then works on the second click
    queue_faults(page, [{"kind": "http", "status": 429, "purpose": "grade_mid"}] * 2)
    page.click("#request-midgrade")
    page.wait_for_function(
        "() => document.getElementById('midgrade-status').textContent.includes('HTTP 429')",
        timeout=20000)
    assert len(d.stored_session()["midInterviewGrades"]) == 0
    page.click("#request-midgrade")
    page.wait_for_selector("#midgrade-snapshots li", timeout=20000)

    # 5. the wrap-up loses the connection; grading still runs
    for _ in range(6):
        d.send("Proceeding.")
    page.wait_for_selector("#end-interview-btn", state="visible", timeout=20000)
    queue_faults(page, ["network"])
    page.click("#end-interview-btn")
    page.wait_for_selector("body[data-screen='feedback']", timeout=30000)
    s = d.stored_session()
    notes = [m for m in s["transcript"] if m["text"].startswith("Wrap-up skipped")]
    assert len(notes) == 1 and "network or CORS" in notes[0]["text"], notes
    assert s["grade"]["score"] == 6

    # 6. nothing was lost: every candidate message has its interviewer reply
    counts = {}
    for m in s["transcript"]:
        counts[m["speaker"]] = counts.get(m["speaker"], 0) + 1
    assert counts["interviewer"] == counts["candidate"] + 1, counts  # + briefing, - wrap-up
    assert counts.get("system", 0) == 1, counts
    assert page.locator("#chat-log .notice.error").count() == 0
    print("  ok   B: seven injected failures, every retry recovers, no message lost")


# ---- C. edges -----------------------------------------------------------

def run_edges(d, page, errors):
    # ---- the wire format of the Anthropic adapter ----------------------
    d.open_menu()
    anthropic_requests = []

    def anthropic_route(route):
        body = route.request.post_data_json
        anthropic_requests.append({"headers": route.request.headers, "body": body})
        if body.get("stream"):
            route.fulfill(status=200, content_type="text/event-stream", body=(
                'event: content_block_delta\n'
                'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Claude "}}\n\n'
                'event: content_block_start\n'
                'data: {"type":"content_block_start","index":0,"content_block":{"type":"text"}}\n\n'
                'event: content_block_delta\n'
                'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"here. [[step: 1]]"}}\n\n'
                'event: message_stop\n'
                'data: {"type":"message_stop"}\n\n'))
        else:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(
                {"content": [{"type": "text", "text": "pong from anthropic"}]}))
    page.route(ANTHROPIC_API, anthropic_route)

    set_text_role(page, provider="anthropic", baseUrl=f"{BASE}/anthropic",
                  model="claude-test", apiKey="k-anthropic")
    page.evaluate("key => localStorage.removeItem(key)", SESSION_KEY)
    page.click("#start-interview")
    interview_ready(page)
    first = page.locator("#chat-log .chat-message.interviewer").first.inner_text()
    assert "Claude here." in first, first
    assert "[[step:" not in first, "control line reached the chat"
    briefing, headers = anthropic_requests[0]["body"], anthropic_requests[0]["headers"]
    assert headers["x-api-key"] == "k-anthropic", headers
    assert headers["anthropic-version"] == "2023-06-01", headers
    assert "authorization" not in headers, "Anthropic request carried an Authorization header"
    assert briefing["model"] == "claude-test" and briefing["stream"] is True, briefing
    assert "senior systems engineer" in briefing["system"], "no interviewer prompt in system"
    assert [m["role"] for m in briefing["messages"] if m["role"] == "system"] == []

    # ---- Settings: connection test, key check, context window ----------
    page.click("#open-settings")
    page.wait_for_selector("#settings-dialog[open]")
    row = 'tr[data-role="text"]'

    # the Anthropic adapter without streaming, through Test connection
    page.click(f"{row} button.test-connection")
    page.wait_for_selector(f"{row} .test-result.ok", timeout=20000)
    assert "pong from anthropic" in page.locator(f"{row} .test-result.ok").inner_text()
    ping = anthropic_requests[-1]["body"]
    assert "stream" not in ping and "system" not in ping, ping
    assert ping["messages"] == [{"role": "user", "content": "ping"}], ping
    page.unroute(ANTHROPIC_API, anthropic_route)

    # An empty API key is accepted: the ping goes out with no auth header.
    page.select_option(f"{row} select.provider-id", "openai-compatible")
    page.fill(f"{row} input.base-url", f"{BASE}/fake/v1")
    page.fill(f"{row} input.model", "fake-model")
    page.fill(f"{row} input.api-key", "")
    keyless = []

    def keyless_route(route):
        keyless.append(route.request.headers)
        route.fulfill(status=200, content_type="application/json", body=json.dumps(
            {"choices": [{"message": {"content": "pong without a key"}}]}))
    page.route(OPENAI_API, keyless_route)
    page.click(f"{row} button.test-connection")
    page.wait_for_selector(f"{row} .test-result.ok", timeout=20000)
    assert "pong without a key" in page.locator(f"{row} .test-result.ok").inner_text()
    assert "authorization" not in keyless[0], f"empty key sent auth headers: {keyless[0]}"
    page.unroute(OPENAI_API, keyless_route)

    openai_requests = []

    def openai_route(route):
        body = route.request.post_data_json
        openai_requests.append({"headers": route.request.headers, "body": body})
        if body.get("stream"):
            route.fulfill(status=200, content_type="text/event-stream", body=(
                'data: {"choices":[{"delta":{"content":"OpenAI reply. [[covered: 2]]"}}]}\n\n'
                "data: [DONE]\n\n"))
        else:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(
                {"choices": [{"message": {"content": "pong from openai"}}]}))
    page.route(OPENAI_API, openai_route)
    page.select_option(f"{row} select.provider-id", "openai-compatible")
    page.fill(f"{row} input.base-url", f"{BASE}/fake/v1")
    page.fill(f"{row} input.model", "fake-model")
    page.fill(f"{row} input.api-key", "k-openai")
    page.click(f"{row} button.test-connection")
    page.wait_for_selector(f"{row} .test-result.ok", timeout=20000)
    assert "pong from openai" in page.locator(f"{row} .test-result.ok").inner_text()
    sent = openai_requests[0]
    assert sent["headers"]["authorization"] == "Bearer k-openai", sent["headers"]
    assert sent["body"]["model"] == "fake-model" and sent["body"]["stream"] is False, sent["body"]
    assert "x-api-key" not in sent["headers"]

    page.fill("#context-tokens", "64000")
    page.click("#settings-save")
    page.click("#settings-close")
    page.click("#open-settings")
    assert page.input_value("#context-tokens") == "64000", "context window not stored"
    stored = page.evaluate("key => JSON.parse(localStorage.getItem(key)).roles.text", SETTINGS_KEY)
    assert stored["contextTokens"] == 64000 and stored["apiKey"] == "k-openai", stored
    page.click("#settings-close")

    # a streamed turn through the OpenAI-compatible adapter. The menu opens
    # through the nav button: a page load would seed the default settings.
    page.click("#screen-nav button[data-nav='menu']")
    page.evaluate("key => localStorage.removeItem(key)", SESSION_KEY)
    page.click("#start-interview")
    interview_ready(page)
    page.fill("#candidate-input", "Over to you.")
    page.click("#send-btn")
    d.wait_reply()
    assert "OpenAI reply." in page.locator("#chat-log .chat-message.interviewer").last.inner_text()
    streamed = [r for r in openai_requests if r["body"].get("stream")][-1]["body"]
    assert streamed["stream"] is True and streamed["messages"][0]["role"] == "system", streamed
    assert 2 in d.stored_session()["coveredSteps"], d.stored_session()["coveredSteps"]
    page.unroute(OPENAI_API, openai_route)
    set_text_role(page, provider="mock", baseUrl="", model="mock-interviewer", apiKey="",
                  contextTokens=0)
    print("  ok   C: Anthropic and OpenAI-compatible wire formats, Settings dialog")

    # ---- the problem bank fails to load -------------------------------
    import re
    problem_json = re.compile(r"/js/problems/.*\.json")

    def refuse_problem(route):
        route.abort()
    page.route(problem_json, refuse_problem)
    d.open_menu()
    page.wait_for_function(
        "() => document.querySelectorAll('#problem-select option[disabled]').length === 8",
        timeout=10000)
    assert "(unavailable)" in page.locator("#problem-select option").first.inner_text()
    page.click("#start-interview")
    assert "No problems loaded" in page.locator("#menu-status").inner_text()
    page.unroute(problem_json, refuse_problem)

    # ---- a reload in the GRADING state grades again -------------------
    d.open_menu()
    d.start_session(help_mode="testing")
    assert page.locator("#tracker-block").is_hidden(), "tracker visible in testing mode"
    # the hidden button still refuses a programmatic click in testing mode
    page.evaluate("() => document.getElementById('request-midgrade').click()")
    assert d.stored_session()["midInterviewGrades"] == [], "progress grade ran in testing mode"
    d.send("Two answers make a session.")
    d.send("Done for now.")
    page.evaluate(f"""() => {{
      const s = JSON.parse(localStorage.getItem('{SESSION_KEY}'));
      s.state = 'GRADING'; s.ended = true;
      localStorage.setItem('{SESSION_KEY}', JSON.stringify(s));
    }}""")
    page.reload(wait_until="networkidle")
    page.wait_for_selector("body[data-screen='feedback']", timeout=30000)
    assert d.stored_session()["grade"]["score"] == 6

    # FEEDBACK without a stored grade grades again; an unknown state shows the menu
    page.evaluate(f"""() => {{
      const s = JSON.parse(localStorage.getItem('{SESSION_KEY}'));
      s.grade = null;
      localStorage.setItem('{SESSION_KEY}', JSON.stringify(s));
    }}""")
    page.reload(wait_until="networkidle")
    page.wait_for_selector("body[data-screen='feedback']", timeout=30000)
    assert d.stored_session()["grade"]["score"] == 6, "FEEDBACK without a grade did not grade again"
    page.evaluate(f"""() => {{
      const s = JSON.parse(localStorage.getItem('{SESSION_KEY}'));
      s.state = 'MENU';
      localStorage.setItem('{SESSION_KEY}', JSON.stringify(s));
    }}""")
    page.reload(wait_until="networkidle")
    assert page.get_attribute("body", "data-screen") == "menu", "an unknown state did not show the menu"

    # ---- screens without a session ------------------------------------
    d.open_menu()
    assert page.get_attribute("body", "data-screen") == "menu"
    page.click("#screen-nav button[data-nav='interview']")
    assert page.locator("#send-btn").is_disabled()
    assert page.locator("#end-interview-btn").is_hidden()
    assert page.locator("#tracker-block").is_hidden()
    assert page.locator("#timer-hud").is_hidden()
    # a programmatic click on the hidden tracker toggle is harmless
    page.evaluate("() => document.getElementById('toggle-tracker').click()")
    assert page.evaluate("key => localStorage.getItem(key)", SESSION_KEY) is None
    print("  ok   C: problem bank down, every resume state, screens without a session")


def game_errors(errors):
    """Console errors of the game. The browser's own log line for a request
    that this test refused on purpose is not a game error."""
    injected = ("/fake/", "/anthropic/", "/js/problems/")
    return [e for e in errors
            if not (e["text"].startswith("Failed to load resource") and any(p in e["url"] for p in injected))]


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
            page.on("console", lambda m: errors.append(
                {"text": m.text, "url": m.location.get("url", "")}) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append({"text": str(e), "url": ""}))
            page.goto(f"{BASE}/index.html", wait_until="networkidle")
            d = Driver(page, BASE)

            run_clean(d, page)
            run_with_faults(d, page)
            run_edges(d, page, errors)

            assert not game_errors(errors), f"console/page errors: {game_errors(errors)}"
            browser.close()
        print("M3 SELFPLAY: PASS (clean self-play, seven injected failures, adapter wire formats, edges)")
        return 0
    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
