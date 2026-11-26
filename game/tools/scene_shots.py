"""Screenshot the persona scene canvas for all five personas."""
import json
import pathlib
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

GAME_DIR = pathlib.Path(__file__).resolve().parent.parent
PORT = 8147
BASE = f"http://127.0.0.1:{PORT}"

SETTINGS_KEY = "tadsdi.settings.v1"
SESSION_KEY = "tadsdi.session.v1"
BASE_PREFS = {"helpMode": "learning", "showHowToAtStart": False}
TEXT = {"adapter": "openai", "baseUrl": "http://127.0.0.1:9/v1",
        "model": "mock", "apiKey": "", "thinkingEffort": "default"}


def wait_port(port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


def seed_script(persona_id):
    data = {
        "providers": {"text": TEXT,
                      "vision": {"adapter": "openai", "baseUrl": "",
                                 "model": "", "apiKey": ""},
                      "image": {"adapter": "openai", "baseUrl": "",
                                "model": "", "apiKey": ""}},
        "preferences": {**BASE_PREFS, "persona": persona_id},
    }
    settings = json.dumps(json.dumps(data))
    return ("window.localStorage.setItem('tadsdi.settings.v1', "
            + settings + "); "
            + "window.localStorage.removeItem('tadsdi.session.v1');")


def main():
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        cwd=GAME_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert wait_port(PORT)
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            for pid in ["klingon", "vulcan", "pirate", "cowboy", "normal"]:
                page.add_init_script(seed_script(pid))
                page.goto(f"{BASE}/index.html", wait_until="networkidle")
                if page.locator("#howto-dialog").is_visible():
                    page.click("#howto-close")
                page.click("#start-interview")
                page.wait_for_selector("#chat-log .chat-message.interviewer",
                                       timeout=15000)
                page.wait_for_timeout(1400)
                page.locator("#scene-frame").screenshot(
                    path=f"/tmp/scene_{pid}.png")
                print(f"saved /tmp/scene_{pid}.png")
            browser.close()
    finally:
        server.terminate()


if __name__ == "__main__":
    sys.exit(main())
