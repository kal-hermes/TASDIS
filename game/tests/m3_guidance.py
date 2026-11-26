"""Revealed guidance: the control line [[guidance: N]] of an interviewer reply
reaches the ledger. Run from game/:
    uv run --with playwright python tests/m3_guidance.py

Units: revealGuidance, parseControlLines, the problem block, and the ledger
summary. Browser: scripted replies over an intercepted endpoint (the real
adapter), then the mock provider, whose first hint reveals an item.
"""

import json
import pathlib
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from m1_e2e import Driver, GAME_DIR, PORT as M1_PORT, SESSION_KEY, SEED_SETTINGS, wait_port  # noqa: E402
from m3_errors import FAKE_API, set_text_role  # noqa: E402

PORT = M1_PORT + 9
BASE = f"http://127.0.0.1:{PORT}"
MODULES = BASE + "/"  # base URL for dynamic imports in page.evaluate

UNITS = """async (base) => {
  const state = await import(base + 'js/state.js?v=38');
  const engine = await import(base + 'js/engine.js?v=38');
  const assemble = await import(base + 'js/prompts/assemble.js?v=38');
  const context = await import(base + 'js/context.js?v=38');
  const out = {};
  const problem = { id: 'p', title: 'P', vague_prompt: 'Design X.',
    hidden_guidance: ['g1', 'g2', 'g3'] };

  // The numbers are 1-based. A number outside the list is dropped.
  const session = state.newSession(problem, { helpMode: 'learning' });
  state.revealGuidance(session, [2]);
  state.revealGuidance(session, [2, 1, 0, 4, 1.5, '2', NaN]);
  out.revealed = session.ledger.revealedGuidance.join(',');

  const good = engine.parseControlLines(
    'Hi.\\n\\n[[step: 2]]\\n[[covered: 2]]\\n[[guidance: 3]] [[guidance: 1]]');
  out.good = [good.clean, good.step, good.covered.join(','), good.guidance.join(',')].join('|');

  // A line with a bad value leaves the text and changes nothing.
  const bad = engine.parseControlLines(
    'Text [[guidance: 0]] [[guidance: 99]] [[guidance: x]] [[step: 6]] [[step: nine]] [[covered: 0]]');
  out.bad = [bad.clean, bad.step, bad.covered.join(','), bad.guidance.join(',')].join('|');

  // The problem block numbers the items and names the control line.
  const prompt = assemble.assembleInterviewerPrompt(
    { problem, helpMode: 'learning', constraintMode: 'unconstrained' });
  const text = prompt[0].content;
  out.prompt = [text.includes('1. g1'), text.includes('2. g2'), text.includes('3. g3'),
                text.includes('[[guidance: N]]')].join(',');

  // The ledger summary names the items that the interviewer surfaced.
  state.revealGuidance(session, [3]);
  const head = context.assembleContext(session, { contextTokens: 0 })
    .filter((m) => m.role === 'system').map((m) => m.content).join('\\n');
  out.ledgerLine = head.includes('Hidden guidance already surfaced: items 2, 1, 3');

  // A record without a problem has no items to reveal.
  const bare = { ledger: { revealedGuidance: [] } };
  state.revealGuidance(bare, [1]);
  out.bare = bare.ledger.revealedGuidance.length;

  // The grader receives the texts of the revealed items, in the order of
  // the ledger. The ledger itself passes as it is stored.
  const prompts = await import(base + 'js/prompts/grader-prompt.js?v=38');
  const graded = state.newSession({ ...problem, known_patterns: ['kp'], common_misses: ['cm'] });
  const input = (variant) => JSON.parse(
    prompts.buildGraderMessages(graded, variant)[1].content.split('Input:\\n\\n')[1]);
  const texts = (variant) => input(variant).hidden_guidance_revealed;
  out.graderEmpty = Array.isArray(texts('final')) && texts('final').length === 0;
  state.revealGuidance(graded, [2, 1]);
  out.graderFinal = texts('final').join('|');
  out.graderMid = texts('mid').join('|');
  out.graderLedger = input('final').design_ledger.revealedGuidance.join(',');
  out.graderRule = prompts.buildGraderMessages(graded, 'final')[0].content
    .includes('hidden_guidance_revealed lists');
  graded.ledger.revealedGuidance.push(99);  // a number that no item has
  out.graderCorrupt = texts('final').join('|');
  // A guidance list that is not a list gives the grader nothing, not a character.
  const odd = { ...graded, problem: { ...problem, hidden_guidance: 'abc' } };
  out.graderNoList = prompts.buildGraderMessages(odd, 'final')[1].content
    .includes('"hidden_guidance_revealed":[]');

  // The reveal checker: its prompt names the reply, the numbered items,
  // and what is already surfaced. Its reply validation is strict.
  const check = await import(base + 'js/prompts/check-prompt.js?v=38');
  const checkMsgs = check.buildCheckMessages(
    'Reads outnumber writes about 100 to 1.', problem, [1]);
  const checkUser = checkMsgs[1].content;
  out.checkMsgs = [
    checkMsgs.length === 2,
    checkMsgs[0].role === 'system',
    checkUser.includes('Reads outnumber writes about 100 to 1.'),
    checkUser.includes('1. g1') && checkUser.includes('3. g3'),
    checkUser.includes('Already surfaced earlier: 1.'),
  ].join(',');
  out.checkValid = check.parseCheckReply('{"revealed": [2, 1]}', 3).join(',');
  out.checkDedupe = check.parseCheckReply('{"revealed": [2, 2, 1]}', 3).join(',');
  out.checkDrops = check.parseCheckReply('{"revealed": [2, 0, 9, "3", 2.5]}', 3).join(',');
  const rejects = (text) => {
    try { check.parseCheckReply(text, 3); return false; } catch { return true; }
  };
  out.checkRejects = [rejects('no json here'), rejects('{"revealed": "no"}'),
    rejects('{"other": []}')].join(',');
  return out;
}"""

EXPECTED = {
    "revealed": "2,1",
    "good": "Hi.|2|2|3,1",
    "bad": "Text|||0,99",
    "prompt": "true,true,true,true",
    "ledgerLine": True,
    "bare": 0,
    "graderEmpty": True,
    "graderFinal": "g2|g1",
    "graderMid": "g2|g1",
    "graderLedger": "2,1",
    "graderRule": True,
    "graderCorrupt": "g2|g1",
    "graderNoList": True,
    "checkMsgs": "true,true,true,true,true",
    "checkValid": "2,1",
    "checkDedupe": "2,1",
    "checkDrops": "2",
    "checkRejects": "true,true,true",
}


def sse(text):
    """One streamed reply in the shape of an OpenAI-compatible endpoint."""
    delta = json.dumps({"choices": [{"delta": {"content": text}}]})
    return f"data: {delta}\n\ndata: [DONE]\n\n"


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
            page.set_default_timeout(20000)
            page.on("console", lambda m: errors.append(
                {"text": m.text, "url": m.location.get("url", "")}) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))

            # ---- units ------------------------------------------------
            page.goto(f"{BASE}/index.html", wait_until="networkidle")
            out = page.evaluate(UNITS, MODULES)
            bad = {key: (out.get(key), value) for key, value in EXPECTED.items()
                   if out.get(key) != value}
            assert not bad, f"units: {bad}"
            print("  ok   units: revealGuidance, parseControlLines, problem block, ledger summary, grader input")

            # ---- browser: scripted replies over an intercepted endpoint
            replies = []  # the next replies of the endpoint, in order
            checks = []   # the next checker replies, in order
            fail_check = {"on": False}

            def endpoint(route):
                # A provider takes a moment. An answer at once can end before
                # Driver.wait_reply sees the busy state of the game.
                time.sleep(0.2)
                body = route.request.post_data_json or {}
                if not body.get("stream"):
                    # The reveal checker: a plain JSON completion.
                    if fail_check["on"]:
                        route.fulfill(status=500, body="checker down")
                        return
                    payload = checks.pop(0) if checks else '{"revealed": []}'
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(
                        {"choices": [{"message": {"content": payload}}]}))
                    return
                route.fulfill(status=200, content_type="text/event-stream",
                              body=sse(replies.pop(0) if replies else "Fallback."))

            page.add_init_script(
                f"window.localStorage.setItem('tadsdi.settings.v1', {json.dumps(SEED_SETTINGS)})")
            page.route(FAKE_API, endpoint)
            d = Driver(page, BASE)
            d.open_menu()
            # The init script seeds the mock settings on every page load, so
            # the real adapter is selected after the load.
            set_text_role(page, provider="openai-compatible", baseUrl=f"{BASE}/fake/v1",
                          model="fake-model", apiKey="k")

            def stored():
                return d.stored_session()

            def revealed():
                return stored()["ledger"]["revealedGuidance"]

            def reply():
                return stored()["transcript"][-1]["text"]

            def turn(answer, said="Over to you."):
                replies.append(answer)
                page.fill("#candidate-input", said)
                page.click("#send-btn")
                d.wait_reply()
                return reply()

            replies.append("Welcome to the interview. [[step: 1]]")
            page.select_option("#problem-select", "url-shortener")  # six hidden items
            page.select_option("#help-mode", "learning")
            page.click("#start-interview")
            page.wait_for_selector("body[data-screen='interview']", timeout=20000)
            page.wait_for_function(
                "() => document.getElementById('send-btn').disabled === false", timeout=20000)
            assert revealed() == [], "guidance was revealed before the first turn"

            # 1. a reply that reveals item 2
            shown = turn("Reads dominate here. [[step: 1]] [[guidance: 2]]")
            assert shown == "Reads dominate here.", f"the reply shows a control line: {shown!r}"
            assert revealed() == [2], revealed()
            # 2. the same item again is not repeated; item 1 joins
            turn("More. [[guidance: 2]] [[guidance: 1]]")
            assert revealed() == [2, 1], revealed()
            # 3. a bad number changes nothing and never reaches the chat
            shown = turn("Odd lines. [[guidance: 0]] [[guidance: 7]] [[guidance: x]] [[step: 6]]")
            assert shown == "Odd lines.", f"the reply shows a control line: {shown!r}"
            assert revealed() == [2, 1], revealed()
            assert stored()["currentStep"] == 1, "a step number out of range moved the step"
            assert "[[" not in page.locator("#chat-log").inner_text()
            print("  ok   browser: a reply records its item; a repeat and a bad number change nothing")

            # 4. a hint reveals an item too
            replies.append("Hint: the latency target is 50 ms. [[guidance: 3]]")
            page.fill("#candidate-input", "I am stuck, give me a hint")
            page.click("#send-btn")
            d.wait_reply()
            assert revealed() == [2, 1, 3], revealed()
            assert stored()["transcript"][-1].get("helpReply") is True
            print("  ok   browser: a hint records its item")

            # 5. the interviewer is told what it already surfaced
            head = page.evaluate("""async ([base, key]) => {
              const context = await import(base + 'js/context.js?v=38');
              const session = JSON.parse(localStorage.getItem(key));
              return context.assembleContext(session, { contextTokens: 0 })
                .filter((m) => m.role === 'system').map((m) => m.content).join('\\n');
            }""", [MODULES, SESSION_KEY])
            assert "Hidden guidance already surfaced: items 2, 1, 3" in head, head[-600:]

            # 6. a reload keeps the record
            page.reload(wait_until="networkidle")
            page.wait_for_function(
                "() => document.getElementById('send-btn').disabled === false", timeout=20000)
            assert revealed() == [2, 1, 3], revealed()
            print("  ok   browser: the ledger summary names the items; a reload keeps them")

            # 7. the grader input of that stored session names the three items
            graded = page.evaluate("""async ([base, key]) => {
              const prompts = await import(base + 'js/prompts/grader-prompt.js?v=38');
              const session = JSON.parse(localStorage.getItem(key));
              const user = prompts.buildGraderMessages(session, 'final')[1].content;
              const input = JSON.parse(user.split('Input:\\n\\n')[1]);
              return { texts: input.hidden_guidance_revealed,
                       numbers: input.design_ledger.revealedGuidance,
                       items: session.problem.hidden_guidance };
            }""", [MODULES, SESSION_KEY])
            with open(GAME_DIR / "js" / "problems" / "url-shortener.json", encoding="utf-8") as f:
                items = json.load(f)["hidden_guidance"]
            assert graded["items"] == items, "the stored problem differs from the problem file"
            assert graded["numbers"] == [2, 1, 3], graded["numbers"]
            assert graded["texts"] == [items[1], items[0], items[2]], graded["texts"]
            print("  ok   browser: the grader input carries the texts of items 2, 1 and 3 of the real problem")

            # ---- 8. a prose reveal reaches the ledger through the checker
            # Section 6's reload re-seeded the mock settings; the intercepted
            # adapter is selected again (settings are read on every call).
            set_text_role(page, provider="openai-compatible", baseUrl=f"{BASE}/fake/v1",
                          model="fake-model", apiKey="k")
            checks.clear()
            checks.append('{"revealed": [5, 99, "x", 5, 5]}')
            turn("Reads outnumber writes by about a hundred to one.")
            status = page.locator("#engine-status").inner_text()
            notice = page.locator("#chat-log .notice.error").last.inner_text() \
                if page.locator("#chat-log .notice.error").count() else "(none)"
            last_reply = page.locator("#chat-log .chat-message.interviewer").last.inner_text()
            assert revealed() == [2, 1, 3, 5], \
                f"{revealed()} status={status!r} notice={notice!r} reply={last_reply!r}"
            print("  ok   checker: a prose reveal is recorded; the checker's numbers are inspected")

            # ---- 9. a failed checker is degradation, not a lost reply ----
            checks.clear()
            fail_check["on"] = True
            turn("Vanity codes are reserved for exactly one paying owner.")
            assert "Vanity codes are reserved" in reply()
            assert revealed() == [2, 1, 3, 5], revealed()
            status = page.locator("#engine-status").inner_text()
            assert "reveal check failed" in status, status
            fail_check["on"] = False
            print("  ok   checker failure: the reply stays, the ledger waits, the failure is named")

            # ---- 10. the next clean checker clears the failure flag -----
            checks.append('{"revealed": [1]}')
            turn("Still about the ratio.")
            assert revealed() == [2, 1, 3, 5], revealed()
            assert page.locator("#engine-status").inner_text() == ""
            print("  ok   checker recovery: the next clean checker clears the status")

            # ---- 11. a [[probe: N]] line counts one ask into the session
            checks.clear()
            replies.append('One link goes viral on live television. '
                           'What breaks first? [[step: 4]]\n[[probe: 5]]')
            turn('Hmm, scaling.')
            used = page.evaluate(
                "key => JSON.parse(localStorage.getItem(key)).probesUsed", SESSION_KEY)
            assert used == {"4": 1}, used
            print("  ok   probe line: [[probe: 5]] counts one ask in step 4")

            # ---- browser: the mock provider ---------------------------
            mock = browser.new_page()
            mock.set_default_timeout(20000)
            mock.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            mock.on("pageerror", lambda e: errors.append(str(e)))
            mock.add_init_script(
                f"window.localStorage.setItem('tadsdi.settings.v1', {json.dumps(SEED_SETTINGS)})")
            dm = Driver(mock, BASE)
            dm.open_menu()  # a page that never navigated has no local storage
            dm.start_session()
            dm.send("I am stuck, give me a hint")
            assert dm.stored_session()["ledger"]["revealedGuidance"] == [2], \
                "the first hint of the mock script does not reveal item 2"
            assert "[[" not in mock.locator("#chat-log").inner_text()

            # The checker runs on the mock path too: a scripted checker reply
            # records an item, and the status stays clean.
            mock.evaluate("""async (base) => {
              const providers = await import(base + 'js/providers.js?v=38');
              providers.setMockCheckerQueue(['{"revealed": [3]}']);
            }""", MODULES)
            dm.send("Another hint, please")
            assert dm.stored_session()["ledger"]["revealedGuidance"][:2] == [2, 3], \
                dm.stored_session()["ledger"]["revealedGuidance"]
            assert mock.locator("#engine-status").inner_text() == ""
            print("  ok   mock: the checker queue records a stated item; the status stays clean")
            browser.close()

        real = [e for e in errors
                if not (isinstance(e, dict) and e["text"].startswith("Failed to load resource")
                        and "/fake/" in e["url"])]
        assert not real, "console or page errors:\n  " + "\n  ".join(str(e) for e in real)
        print("M3 GUIDANCE: PASS (the [[guidance: N]] line and the checker reach the ledger; bad numbers are dropped)")
        return 0
    finally:
        server.terminate()


if __name__ == "__main__":
    sys.exit(main())
