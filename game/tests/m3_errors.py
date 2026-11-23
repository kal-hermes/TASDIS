"""M3 task 1: error handling. Units for the error mapping and Settings
validation, then browser runs for every retry path: a failed turn, a failed
briefing, a failed wrap-up, grading that fails twice, and the real
OpenAI-compatible adapter against an intercepted endpoint (abort, 401, hang).
Run from game/:
    uv run --with playwright python tests/m3_errors.py
"""

import json
import pathlib
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from m1_e2e import Driver, GAME_DIR, PORT as M1_PORT, SEED_SETTINGS  # noqa: E402

PORT = M1_PORT + 3
BASE = f"http://127.0.0.1:{PORT}"
MODULES = BASE + "/"  # base URL for dynamic imports in page.evaluate
SETTINGS_KEY = "tadsdi.settings.v1"
FAKE_API = "**/fake/v1/chat/completions"
SSE_OK = ('data: {"choices":[{"delta":{"content":"Real reply. [[step:1]]"}}]}\n\n'
          "data: [DONE]\n\n")
STALL_PORT = PORT + 50


class StallHandler(BaseHTTPRequestHandler):
    """Answers like a provider that sends one chunk and then stops.

    The server is on another origin than the game, so it also answers the
    CORS preflight the browser sends first, like a real provider must.
    """

    CORS = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "authorization, content-type",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
    }

    def do_OPTIONS(self):
        self.send_response(204)
        for name, value in self.CORS.items():
            self.send_header(name, value)
        self.end_headers()

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        for name, value in self.CORS.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(b'data: {"choices":[{"delta":{"content":"Partial "}}]}\n\n')
        self.wfile.flush()
        time.sleep(5)

    def log_message(self, *args):
        pass


def set_text_role(page, **fields):
    page.evaluate(
        """([key, fields]) => {
          const s = JSON.parse(localStorage.getItem(key));
          s.roles.text = { ...s.roles.text, ...fields };
          localStorage.setItem(key, JSON.stringify(s));
        }""",
        [SETTINGS_KEY, fields])


def app_console_errors(errors):
    """Console errors caused by the game, not by the browser's own log line
    for a failed request to the intercepted test endpoint."""
    return [e for e in errors if not (e["text"].startswith("Failed to load resource")
                                      and "/fake/" in e["url"])]


def notice_text(page):
    page.wait_for_selector("#chat-log .notice.error", timeout=20000)
    page.wait_for_function(
        "() => document.getElementById('send-btn').disabled === false", timeout=20000)
    return page.locator("#chat-log .notice.error").last.inner_text()


def speakers(session):
    return [m["speaker"] for m in session["transcript"]]


def main():
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        cwd=GAME_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    stall = ThreadingHTTPServer(("127.0.0.1", STALL_PORT), StallHandler)
    threading.Thread(target=stall.serve_forever, daemon=True).start()
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

            # ---- units ------------------------------------------------
            out = page.evaluate("""async (base) => {
              const providers = await import(base + 'js/providers.js?v=25');
              const E = providers.ProviderErrors;
              const d = (err, name) => providers.describeProviderError(err, name).message;
              const out = {};
              out.network = d(new E.NetworkError('Failed to fetch'), 'OpenAI');
              out.timeout = d(new E.TimeoutError('The operation was aborted.'), 'OpenAI');
              out.http401 = d(new E.HttpError(401, 'invalid api key'), 'Anthropic');
              out.http403 = d(new E.HttpError(403, ''), 'Anthropic');
              out.http404 = d(new E.HttpError(404, 'model not found'), 'OpenAI');
              out.http429 = d(new E.HttpError(429, ''), 'OpenAI');
              out.http500 = d(new E.HttpError(500, 'upstream down'), 'OpenAI');
              out.http418 = d(new E.HttpError(418, 'short and stout'), 'OpenAI');
              out.empty = d(new E.EmptyReplyError(''), 'OpenAI');
              out.unknown = d(new Error('something odd'), 'OpenAI');
              const once = providers.describeProviderError(new E.HttpError(500, 'x'), 'OpenAI');
              out.notWrappedTwice = providers.describeProviderError(once, 'OpenAI') === once;
              out.kinds = [new E.NetworkError('a'), new E.TimeoutError('b'),
                new E.HttpError(500, 'c'), new E.EmptyReplyError('d'),
                new E.ConfigError('e')].map((e) => e.kind);
              const v = (role, config) => {
                try { providers.validateConfig(role, config); return 'ok'; }
                catch (e) { return e.message; }
              };
              out.noKey = v('text', { provider: 'openai', apiKey: '', model: 'gpt' });
              out.noModel = v('text', { provider: 'openai', apiKey: 'k', model: '' });
              out.keyOk = v('text', { provider: 'openai', apiKey: 'k', model: 'gpt' });
              out.noBase = v('vision', { provider: 'openai-compatible', apiKey: 'k',
                model: 'm', baseUrl: '' });
              out.mockOk = v('image', { provider: 'mock' });
              const msgs = [{ role: 'user', content: 'ping' }];
              const run = async () => {
                try { return 'ok:' + (await providers.complete('text', msgs,
                  { purpose: 'interview' })).slice(0, 5); }
                catch (e) { return e.message; }
              };
              providers.setMockFaultQueue(['http:429', 'timeout', 'empty']);
              out.fault1 = await run();
              out.fault2 = await run();
              out.fault3 = await run();
              out.drained = await run();
              providers.setMockFaultQueue(['network']);
              out.streamFault = await (async () => {
                try {
                  await providers.completeStream('text', msgs, () => {},
                    { purpose: 'interview' });
                  return 'no error';
                } catch (e) { return e.message; }
              })();
              providers.setMockFaultQueue([]);
              return out;
            }""", MODULES)

            def expect(name, *needles):
                missing = [n for n in needles if n not in out[name]]
                print(f"  {'ok  ' if not missing else 'FAIL'} {name}"
                      + ("" if not missing else f": {out[name]!r} lacks {missing}"))
                assert not missing, f"{name}: {out[name]!r} lacks {missing}"

            expect("network", "OpenAI", "network or CORS", "Base URL")
            expect("timeout", "OpenAI", "did not answer within", "Retry")
            expect("http401", "Anthropic", "rejected the API key", "HTTP 401", "Settings")
            expect("http403", "rejected the API key")
            expect("http404", "HTTP 404", "Base URL", "model")
            expect("http429", "HTTP 429", "Wait")
            expect("http500", "HTTP 500", "upstream down", "Retry")
            expect("http418", "HTTP 418", "short and stout")
            expect("empty", "empty reply")
            expect("unknown", "OpenAI call failed", "something odd")
            expect("noKey", "No API key set", "text", "OpenAI", "Settings")
            expect("noModel", "No model name set", "Settings")
            expect("noBase", "Base URL", "Settings")
            assert out["notWrappedTwice"], "describeProviderError wrapped an error twice"
            assert out["kinds"] == ["network", "timeout", "http", "empty", "config"], out["kinds"]
            assert out["keyOk"] == "ok" and out["mockOk"] == "ok", out
            expect("fault1", "HTTP 429")
            expect("fault2", "did not answer within")
            expect("fault3", "empty reply")
            assert out["drained"].startswith("ok:"), out["drained"]
            expect("streamFault", "network or CORS")
            print("  ok   units: mapping, validation, fault queue")

            # ---- browser: mock faults on a normal turn -----------------
            d = Driver(page, BASE)
            d.start_session(help_mode="learning")
            for fault, needle in [("network", "network or CORS"),
                                  ("timeout", "did not answer within"),
                                  ("http:500", "HTTP 500"),
                                  ("empty", "empty reply")]:
                before = len(d.stored_session()["transcript"])
                page.evaluate(
                    """async ([base, fault]) => {
                      const providers = await import(base + 'js/providers.js?v=25');
                      providers.setMockFaultQueue([fault]);
                    }""", [MODULES, fault])
                page.fill("#candidate-input", "Going fine.")
                page.click("#send-btn")
                text = notice_text(page)
                assert needle in text, f"{fault}: notice {text!r} lacks {needle!r}"
                assert "Retry" in page.locator("#chat-log .notice.error").last.inner_text()
                after = d.stored_session()["transcript"]
                assert len(after) == before + 1 and after[-1]["speaker"] == "candidate", \
                    f"{fault}: transcript changed by a failed turn: {speakers(after)}"
                page.locator("#chat-log .notice.error").last.locator(".retry-btn").click()
                page.wait_for_function(
                    "() => document.getElementById('send-btn').disabled === false", timeout=20000)
                assert page.locator("#chat-log .notice.error").count() == 0, \
                    f"{fault}: notice survived the retry"
                fixed = d.stored_session()["transcript"]
                assert len(fixed) == before + 2 and \
                    [m["speaker"] for m in fixed[-2:]] == ["candidate", "interviewer"], \
                    f"{fault}: retry duplicated a message: {fixed}"
            print("  ok   failed turn: notice, Retry, no duplicate, no loss (network, timeout, 500, empty)")

            # ---- browser: briefing failure stays on the briefing screen
            d.open_menu()
            page.evaluate(
                """async (base) => {
                  const providers = await import(base + 'js/providers.js?v=25');
                  providers.setMockFaultQueue(['network']);
                }""", MODULES)
            page.click("#start-interview")
            page.wait_for_selector("#briefing-retry", state="visible", timeout=20000)
            status = page.locator("#briefing-status").inner_text()
            assert "network or CORS" in status, status
            assert page.get_attribute("body", "data-screen") == "briefing"
            stuck = page.evaluate(
                "() => JSON.parse(localStorage.getItem('tadsdi.session.v1'))")
            assert stuck["state"] == "BRIEFING" and stuck["transcript"] == [], stuck["state"]
            page.click("#briefing-retry")
            page.wait_for_selector("body[data-screen='interview']", timeout=20000)
            page.wait_for_function(
                "() => document.getElementById('send-btn').disabled === false", timeout=20000)
            s = page.evaluate("() => JSON.parse(localStorage.getItem('tadsdi.session.v1'))")
            assert s["state"] == "INTERVIEW" and speakers(s) == ["interviewer"], speakers(s)
            assert page.locator("#briefing-retry").is_hidden()
            print("  ok   briefing failure: error and Retry on the briefing screen, then recovery")

            # ---- browser: wrap-up failure does not block grading -------
            for _ in range(6):
                d.send("Proceeding.")
            assert page.locator("#end-interview-btn").is_visible()
            page.evaluate(
                """async (base) => {
                  const providers = await import(base + 'js/providers.js?v=25');
                  providers.setMockFaultQueue(['http:500']);
                }""", MODULES)
            page.click("#end-interview-btn")
            page.wait_for_selector("body[data-screen='feedback']", timeout=30000)
            s = d.stored_session()
            wrapup_notes = [m for m in s["transcript"] if m["text"].startswith("Wrap-up skipped")]
            assert len(wrapup_notes) == 1, [m["text"] for m in s["transcript"]][-3:]
            assert "HTTP 500" in wrapup_notes[0]["text"], wrapup_notes[0]["text"]
            assert s["grade"]["score"] == 6, s["grade"]["score"]
            print("  ok   wrap-up failure: system note, grading still runs")

            # ---- browser: grading fails twice, Retry grading recovers ---
            d.start_session(help_mode="learning")
            for _ in range(6):
                d.send("Proceeding.")
            page.evaluate(
                """async (base) => {
                  const providers = await import(base + 'js/providers.js?v=25');
                  providers.setMockGraderQueue(['grade_bad', 'grade_bad']);
                }""", MODULES)
            page.click("#end-interview-btn")
            page.wait_for_selector("#grading-retry", state="visible", timeout=30000)
            status = page.locator("#grading-status").inner_text()
            assert "Grading failed after one retry" in status, status
            assert d.stored_session()["state"] == "GRADING", "session lost after failed grading"
            page.click("#grading-retry")
            page.wait_for_selector("body[data-screen='feedback']", timeout=30000)
            assert "6 / 10" in page.locator("#feedback-score").inner_text()
            print("  ok   grading failure: message after one retry, Retry grading recovers")

            # ---- browser: missing API key -----------------------------
            d.open_menu()
            set_text_role(page, provider="openai", model="gpt-test", apiKey="")
            page.click("#start-interview")
            page.wait_for_selector("#briefing-retry", state="visible", timeout=20000)
            status = page.locator("#briefing-status").inner_text()
            assert "No API key set" in status and "Settings" in status, status
            print("  ok   missing API key: named in the briefing error")

            # ---- browser: the real adapter against an intercepted endpoint
            mode = {"value": "ok"}

            def handler(route):
                if mode["value"] == "abort":
                    route.abort()
                elif mode["value"] == "hang":
                    pass  # never answer: the game's own timeout must fire
                elif mode["value"] == "401":
                    route.fulfill(status=401, body='{"error":"bad key"}')
                else:
                    route.fulfill(status=200, content_type="text/event-stream", body=SSE_OK)
            page.route(FAKE_API, handler)

            d.open_menu()
            # The init script re-seeds the mock settings on every page load,
            # so the real-adapter settings are written after the reload. The
            # reload also resets module state, so the short timeout follows it.
            set_text_role(page, provider="openai-compatible", baseUrl=f"{BASE}/fake/v1",
                          model="fake-model", apiKey="k")
            page.evaluate(
                """async (base) => {
                  const providers = await import(base + 'js/providers.js?v=25');
                  providers.setProviderTimeouts({ requestMs: 1500, idleMs: 1500 });
                }""", MODULES)
            page.click("#start-interview")
            page.wait_for_selector("body[data-screen='interview']", timeout=20000)
            page.wait_for_function(
                "() => document.getElementById('send-btn').disabled === false", timeout=20000)
            first = page.locator("#chat-log .chat-message.interviewer").first.inner_text()
            assert "Real reply." in first, first

            for value, needle in [("abort", "network or CORS"),
                                  ("401", "rejected the API key"),
                                  ("hang", "did not answer within")]:
                mode["value"] = value
                page.fill("#candidate-input", "Over to you.")
                page.click("#send-btn")
                text = notice_text(page)
                assert "OpenAI-compatible" in text and needle in text, f"{value}: {text!r}"
                mode["value"] = "ok"
                page.locator("#chat-log .notice.error").last.locator(".retry-btn").click()
                page.wait_for_function(
                    "() => document.getElementById('send-btn').disabled === false", timeout=20000)
                assert page.locator("#chat-log .notice.error").count() == 0, value
                assert speakers(d.stored_session())[-1] == "interviewer", value
            print("  ok   real adapter: abort, 401, and hang map to readable notices, Retry recovers")

            # ---- browser: a stream that starts and then stalls ----------
            before = len(d.stored_session()["transcript"])
            set_text_role(page, baseUrl=f"http://127.0.0.1:{STALL_PORT}/v1")
            page.fill("#candidate-input", "One that stalls.")
            page.click("#send-btn")
            text = notice_text(page)
            assert "did not answer within" in text, text
            after = d.stored_session()["transcript"]
            assert len(after) == before + 1 and after[-1]["speaker"] == "candidate", \
                f"stalled stream stored a partial reply: {after[-2:]}"
            assert page.locator("#chat-log .chat-message", has_text="Partial").count() == 0, \
                "the partial reply stayed in the chat view"
            print("  ok   stalled stream: idle timeout fires, the partial reply is not stored")

            mode["value"] = "ok"
            page.unroute(FAKE_API, handler)
            assert not app_console_errors(errors), f"console/page errors: {app_console_errors(errors)}"
            browser.close()
        print("M3 ERRORS: PASS (mapping, validation, turn/briefing/wrap-up/grading retries, real adapter, stalled stream)")
        return 0
    finally:
        server.terminate()
        server.wait(timeout=5)
        stall.shutdown()


if __name__ == "__main__":
    sys.exit(main())
