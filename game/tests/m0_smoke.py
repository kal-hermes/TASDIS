"""M0 smoke test - TADSDI scaffold, settings, provider layer.

Run from the game/ directory:
    uv run --with playwright python tests/m0_smoke.py

Starts a container-local http.server, drives headless Chromium, and checks
the M0 acceptance:
  a. page loads with zero console errors, and "How to play" opens over
     the menu on a first visit
  b. settings save to localStorage and survive a reload
  c. test connection reports success against the mock provider
  d. a mock reply renders in the placeholder chat view
"""

import json
import pathlib
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

GAME_DIR = pathlib.Path(__file__).resolve().parent.parent
PORT = 8137
BASE = f"http://127.0.0.1:{PORT}"
SETTINGS_KEY = "tadsdi.settings.v1"


def wait_port(port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


def fill_row(page, role, provider, base_url, model, api_key):
    row = page.locator(f'tr[data-role="{role}"]')
    row.locator("select.provider-id").select_option(provider)
    row.locator("input.base-url").fill(base_url)
    row.locator("input.model").fill(model)
    row.locator("input.api-key").fill(api_key)


def main():
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        cwd=GAME_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert wait_port(PORT), "http.server did not come up"
        console_errors = []
        page_errors = []
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page()
            page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: page_errors.append(str(e)))

            # a. load with zero console errors
            page.goto(f"{BASE}/index.html", wait_until="networkidle")
            assert page.title().startswith("Totally Accurate"), page.title()
            assert window_flag(page), "window.__tadsdi missing (app did not boot)"
            assert not console_errors, f"console errors: {console_errors}"
            assert not page_errors, f"pageerror: {page_errors}"
            # A first visit opens how to play over the menu.
            page.wait_for_selector("#howto-dialog[open]")
            page.click("#howto-close")
            assert not page.locator("#howto-dialog").evaluate("d => d.open"), \
                "Close did not close how to play"

            # b. settings round trip through localStorage
            page.click("#open-settings")
            assert page.locator("#settings-dialog").evaluate("d => d.open"), "settings dialog did not open"
            fill_row(page, "text", "mock", "", "mock-interviewer", "")
            fill_row(page, "vision", "openai-compatible", "https://llm.example/v1", "vision-model", "sk-test")
            fill_row(page, "image", "mock", "", "mock-image", "")
            page.click("#settings-save")
            stored = page.evaluate(f"() => localStorage.getItem('{SETTINGS_KEY}')")
            assert stored, "settings not written to localStorage"
            data = json.loads(stored)
            assert data["roles"]["vision"]["model"] == "vision-model", data
            assert data["roles"]["text"]["provider"] == "mock", data

            page.reload(wait_until="networkidle")
            # The box was not ticked, so how to play opens again.
            page.wait_for_selector("#howto-dialog[open]")
            page.click("#howto-close")
            page.click("#open-settings")
            vision_model = page.locator('tr[data-role="vision"] input.model').input_value()
            assert vision_model == "vision-model", f"reload lost model: {vision_model!r}"
            text_provider = page.locator('tr[data-role="text"] select.provider-id').input_value()
            assert text_provider == "mock", f"reload lost provider: {text_provider!r}"

            # c. test connection against the mock provider
            page.locator('tr[data-role="text"] button.test-connection').click()
            page.wait_for_selector('tr[data-role="text"] .test-result.ok', timeout=5000)
            result_text = page.locator('tr[data-role="text"] .test-result').inner_text()
            assert "ok" in result_text.lower(), result_text

            # d. mock reply renders in the chat view via a real interview start
            page.click("#settings-close")
            page.wait_for_selector("#problem-select option:not([disabled])", state="attached", timeout=10000)
            page.click("#start-interview")
            page.wait_for_selector("#chat-log .chat-message.interviewer", timeout=15000)
            reply = page.locator("#chat-log .chat-message.interviewer").last.inner_text()
            assert len(reply) > 0, "mock reply rendered empty"
            assert not console_errors, f"console errors after interactions: {console_errors}"
            assert not page_errors, f"pageerror after interactions: {page_errors}"

            browser.close()

        print("M0 SMOKE: PASS (a,b,c,d green, zero console errors)")
        return 0
    finally:
        server.terminate()
        server.wait(timeout=5)


def window_flag(page):
    return page.evaluate("() => Boolean(window.__tadsdi && window.__tadsdi.showScreen)")


if __name__ == "__main__":
    sys.exit(main())
