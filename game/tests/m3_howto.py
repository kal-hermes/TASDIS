"""How to play in the browser. Run from game/:
    uv run --with playwright python tests/m3_howto.py

a. A new browser opens "How to play" when the game loads.
b. The dialog opens at its top, with the title focused.
c. The box "Do not show automatically in the future" acts when the dialog
   closes, and the game remembers it.
Every section starts from a new browser, which is the state of a first
visit.
"""

import pathlib
import subprocess
import sys

from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from m1_e2e import GAME_DIR, PORT as M1_PORT, wait_port  # noqa: E402

PORT = M1_PORT + 8
BASE = f"http://127.0.0.1:{PORT}"
SETTINGS_KEY = "tadsdi.settings.v1"
BOX = "#howto-skip"

# Where the dialog is and what it shows.
STATE = """() => {
  const dialog = document.getElementById('howto-dialog');
  const scroller = document.getElementById('howto-body');
  const title = document.getElementById('howto-title');
  const box = document.getElementById('howto-skip');
  const close = document.getElementById('howto-close');
  const d = dialog.getBoundingClientRect();
  const t = title.getBoundingClientRect();
  const b = box.getBoundingClientRect();
  const c = close.getBoundingClientRect();
  const inside = (r) => r.top >= d.top - 1 && r.bottom <= d.bottom + 1
    && r.left >= d.left - 1 && r.right <= d.right + 1;
  return {
    open: dialog.open,
    modal: dialog.matches(':modal'),
    scrollTop: Math.round(scroller.scrollTop),
    scrollHeight: scroller.scrollHeight,
    clientHeight: scroller.clientHeight,
    focus: document.activeElement ? document.activeElement.id : '',
    titleInView: t.top >= d.top - 1 && t.bottom <= d.bottom + 1,
    boxInView: inside(b),
    closeInView: inside(c),
    screen: document.body.dataset.screen,
    boxChecked: box ? box.checked : null,
    boxLabel: box ? box.closest('label').innerText.trim() : null,
  };
}"""


def state(page):
    return page.evaluate(STATE)


def is_open(page):
    return page.evaluate("() => document.getElementById('howto-dialog').open")


def remembered(page):
    """The stored setting. None: nothing is stored yet."""
    return page.evaluate(
        """key => {
          const s = JSON.parse(localStorage.getItem(key) || '{}');
          return s.preferences ? s.preferences.showHowToAtStart : null;
        }""", SETTINGS_KEY)


def takes_click(page, selector):
    """True when a click on the element would reach it."""
    try:
        page.locator(selector).click(trial=True, timeout=1500)
        return True
    except PlaywrightTimeoutError:
        return False


def fresh_page(browser, errors):
    """A page in a new browser context: no settings, no session."""
    page = browser.new_page()
    page.set_default_timeout(20000)
    # A low window, so that the text of the dialog scrolls.
    page.set_viewport_size({"width": 1280, "height": 600})
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{BASE}/index.html", wait_until="networkidle")
    page.wait_for_selector("#start-interview", state="visible")
    return page


def load(page):
    page.goto(f"{BASE}/index.html", wait_until="networkidle")
    page.wait_for_selector("#start-interview", state="visible")


def start_interview(page):
    page.select_option("#problem-select", "url-shortener")
    page.click("#start-interview")
    page.wait_for_selector("#chat-log .chat-message.interviewer", timeout=15000)
    page.wait_for_function(
        "() => document.getElementById('send-btn').disabled === false")


def open_from_settings(page):
    page.click("#open-settings")
    page.wait_for_selector("#settings-dialog[open]")
    page.click("#open-howto-settings")
    page.wait_for_selector("#howto-dialog[open]")


def main():
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        cwd=GAME_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    errors = []
    try:
        assert wait_port(PORT), "http.server did not come up"
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])

            # ---- a. a new browser opens how to play when the game loads
            page = fresh_page(browser, errors)
            s = state(page)
            assert s["open"] and s["modal"], f"a first visit does not open how to play: {s}"
            assert s["screen"] == "menu", f"the first screen is {s['screen']}, not the menu"
            assert s["scrollHeight"] > s["clientHeight"], "the dialog does not scroll in this window"
            assert not takes_click(page, "#start-interview"), \
                "the menu behind how to play takes a click"

            # ---- b. it opens at its top, with the title focused
            assert s["scrollTop"] == 0 and s["titleInView"], \
                f"how to play does not open at its top: {s}"
            assert s["focus"] == "howto-title", f"the focus is on '{s['focus']}', not on the title"
            # the last row is visible from the start
            assert s["boxInView"] and s["closeInView"], \
                f"the last row is not visible at the top of the dialog: {s}"
            print("  ok   a, b: a first visit opens how to play, at its top, over the menu")

            # ---- c. the box is off by default. Close without a tick keeps the start.
            assert s["boxChecked"] is False, f"the box is not off by default: {s}"
            assert s["boxLabel"] == "Do not show automatically in the future", s["boxLabel"]
            page.click("#howto-close")
            assert not is_open(page), "Close did not close how to play"
            page.reload(wait_until="networkidle")
            page.wait_for_selector("#howto-dialog[open]")
            print("  ok   c: the box is off by default; Close with the box off keeps the start")

            # ---- d. a tick and then Close: the next load opens no dialog
            page.check(BOX)
            page.click("#howto-close")
            assert remembered(page) is False, f"the setting is {remembered(page)}, not False"
            page.reload(wait_until="networkidle")
            page.wait_for_selector("#start-interview", state="visible")
            assert not is_open(page), "how to play opened at the start with the box ticked"
            start_interview(page)
            print("  ok   d: a tick and Close stops the start; the menu works")

            # ---- e. Save in Settings keeps the choice
            page.click("#open-settings")
            page.wait_for_selector("#settings-dialog[open]")
            page.click("#settings-save")
            page.click("#settings-close")
            assert remembered(page) is False, "Save in Settings reset the choice"
            page.reload(wait_until="networkidle")
            page.wait_for_selector("#chat-log .chat-message.interviewer")
            assert not is_open(page), "how to play opened after Save in Settings"
            print("  ok   e: Save in Settings keeps the choice")

            # ---- f. the way back: the box shows the stored choice
            open_from_settings(page)
            s = state(page)
            assert s["boxChecked"] is True, f"the box does not show the stored choice: {s}"
            page.uncheck(BOX)
            page.click("#howto-close")
            page.keyboard.press("Escape")  # closes Settings, which is still open
            assert remembered(page) is True, "a box that is not ticked did not turn the start on"
            page.reload(wait_until="networkidle")
            page.wait_for_selector("#howto-dialog[open]")
            assert state(page)["screen"] == "interview", "how to play hid the resumed interview"
            print("  ok   f: the box shows the stored choice; an unticked box turns the start on")

            # ---- g. a reopen starts at its top again
            body = "#howto-body"
            page.evaluate(
                "sel => { document.querySelector(sel).scrollTop = 1e6; }", body)
            assert state(page)["scrollTop"] > 0, "the dialog did not scroll to its end"
            page.click("#howto-close")
            open_from_settings(page)
            s = state(page)
            assert s["scrollTop"] == 0 and s["focus"] == "howto-title", \
                f"a reopen does not start at the top: {s}"
            page.keyboard.press("Escape")  # how to play
            page.keyboard.press("Escape")  # Settings
            print("  ok   g: a reopen starts at the top, with the title focused")

            # ---- k. the last row stays visible while the text scrolls
            open_from_settings(page)
            page.evaluate(
                "sel => { const b = document.querySelector(sel);"
                " b.scrollTop = (b.scrollHeight - b.clientHeight) / 2; }", body)
            s = state(page)
            assert 0 < s["scrollTop"] < s["scrollHeight"] - s["clientHeight"], \
                f"the text did not scroll to its middle: {s}"
            assert s["boxInView"] and s["closeInView"], f"the last row left the view: {s}"
            page.evaluate("sel => { document.querySelector(sel).scrollTop = 1e6; }", body)
            s = state(page)
            assert s["scrollTop"] > 0 and s["boxInView"] and s["closeInView"], \
                f"the last row left the view at the end: {s}"
            # The keyboard scrolls the text: the title has the focus and sits
            # inside the text.
            page.evaluate("sel => { document.querySelector(sel).scrollTop = 0; }", body)
            page.keyboard.press("PageDown")
            page.wait_for_function("sel => document.querySelector(sel).scrollTop > 0",
                                   arg=body, timeout=5000)
            page.keyboard.press("Escape")  # how to play
            page.keyboard.press("Escape")  # Settings
            print("  ok   k: the last row stays visible while the text scrolls, by wheel or by key")

            # ---- h. Escape remembers the box too
            open_from_settings(page)
            page.check(BOX)
            page.keyboard.press("Escape")
            assert not is_open(page), "Escape did not close how to play"
            assert remembered(page) is False, "Escape did not remember the box"
            page.keyboard.press("Escape")  # Settings
            page.reload(wait_until="networkidle")
            page.wait_for_selector("#chat-log .chat-message.interviewer")
            assert not is_open(page), "how to play opened after Escape with the box ticked"
            print("  ok   h: Escape remembers the box")

            # ---- i. over a resumed interview, and then the interview goes on
            page = fresh_page(browser, errors)
            page.click("#howto-close")  # no tick, so the start stays on
            start_interview(page)
            page.reload(wait_until="networkidle")
            page.wait_for_selector("#howto-dialog[open]")
            assert state(page)["screen"] == "interview", "the resume did not reach the interview"
            assert not takes_click(page, "#send-btn"), \
                "the interview takes a click under how to play"
            page.click("#howto-close")
            page.wait_for_function(
                "() => document.getElementById('send-btn').disabled === false")
            before = page.locator("#chat-log .chat-message").count()
            page.fill("#candidate-input", "One more turn after the dialog.")
            page.press("#candidate-input", "Enter")
            page.wait_for_function(
                "() => document.getElementById('send-btn').disabled === true")
            page.wait_for_function(
                "() => document.getElementById('send-btn').disabled === false")
            after = page.locator("#chat-log .chat-message").count()
            assert after == before + 2, f"the interview did not go on: {before} -> {after}"
            print("  ok   i: how to play opens over a resumed interview, and the interview goes on")

            # ---- j. only the value false stops the start
            page = fresh_page(browser, errors)
            page.evaluate(
                """([key, value]) => {
                  const s = { roles: {}, preferences: { showHowToAtStart: value } };
                  localStorage.setItem(key, JSON.stringify(s));
                }""", [SETTINGS_KEY, "false"])
            page.reload(wait_until="networkidle")
            page.wait_for_selector("#howto-dialog[open]")
            print("  ok   j: a stored value that is not the value false does not stop the start")
            browser.close()

        assert not errors, "console or page errors:\n  " + "\n  ".join(errors)
        print("M3 HOWTO: PASS (opens at the start, at its top; the box is remembered)")
        return 0
    finally:
        server.terminate()


if __name__ == "__main__":
    sys.exit(main())
