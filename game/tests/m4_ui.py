"""M4 UI checks: persona picker and persistence, portrait canvas and
background, theme font and palette variables, and the blip voice wiring
against a fake AudioContext. Offline: the mock provider runs the turns.
Run from game/:
    uv run --with playwright python tests/m4_ui.py
"""

import json
import pathlib
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

GAME_DIR = pathlib.Path(__file__).resolve().parent.parent
PORT = 8145
BASE = f"http://127.0.0.1:{PORT}"
SETTINGS_KEY = "tadsdi.settings.v1"

SEED_SETTINGS = json.dumps({
    "roles": {
        "text": {"provider": "mock", "baseUrl": "", "model": "mock-interviewer",
                 "apiKey": "", "thinkingEffort": "default"},
        "vision": {"provider": "mock", "baseUrl": "", "model": "mock-vision",
                   "apiKey": "", "thinkingEffort": "default"},
        "image": {"provider": "mock", "baseUrl": "", "model": "mock-image",
                  "apiKey": "", "thinkingEffort": "default"},
    },
    "preferences": {"helpMode": "learning", "constraintMode": "unconstrained",
                    "timerMinutes": 0, "showHowToAtStart": False,
                    "persona": "normal", "voiceMuted": False},
})

# A fake AudioContext records every oscillator the game creates. Injected
# before app.js loads, so the voice wiring drives through it headlessly.
FAKE_AUDIO = """
  window.__audioLog = { waves: [], started: 0, freqs: [] };
  class FakeOsc {
    constructor(log) { this.log = log; this._type = ''; this.frequency = {
      setValueAtTime: (v) => this.log.freqs.push(v) }; }
    set type(v) { this._type = v; if (v) this.log.waves.push(v); }
    get type() { return this._type; }
    connect() {}
    start() { this.log.started += 1; }
    stop() {}
  }
  class FakeAudioContext {
    constructor() { if (!window.__audioLog.shared) window.__audioLog.shared = this; }
    get currentTime() { return 0; }
    get destination() { return {}; }
    get state() { return 'running'; }
    resume() { return Promise.resolve(); }
    createOscillator() { return new FakeOsc(window.__audioLog); }
    createGain() { return { gain: {
      setValueAtTime() {}, exponentialRampToValueAtTime() {} }, connect() {} }; }
  }
  window.AudioContext = FakeAudioContext;
"""


def wait_port(port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


def game_errors(errors):
    return [e for e in errors
            if "/fake/" not in e.get("url", "")
            and "Failed to load resource" not in e["text"]]


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
            page.add_init_script(
                f"window.localStorage.setItem('{SETTINGS_KEY}', {json.dumps(SEED_SETTINGS)})")
            page.add_init_script(FAKE_AUDIO)
            page.on("console", lambda m: errors.append(
                {"text": m.text, "url": m.location.get("url", "")}) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append({"text": str(e), "url": ""}))
            page.goto(f"{BASE}/index.html", wait_until="networkidle")
            ok = True

            def expect(name, condition, detail=""):
                nonlocal ok
                if not condition:
                    print(f"  FAIL {name}: {detail}")
                    ok = False

            # ---- A. the picker: five options, default normal, persists
            page.select_option("#persona-select", "klingon")
            page.click("#start-interview")
            page.wait_for_selector("#chat-log .chat-message.interviewer", timeout=15000)
            page.wait_for_selector("#interview-busy", state="hidden", timeout=15000)
            stored = page.evaluate(
                f"key => JSON.parse(localStorage.getItem(key)).preferences", SETTINGS_KEY)
            expect("picker persists klingon", stored.get("persona") == "klingon", stored)

            # ---- B. the scene panel and the backdrop
            pixels = page.evaluate("""() => {
              const c = document.getElementById('persona-scene');
              const ctx = c.getContext('2d');
              const d = ctx.getImageData(0, 0, c.width, c.height).data;
              let painted = 0;
              const seen = new Set();
              for (let i = 0; i < d.length; i += 4) {
                if (d[i + 3] > 0) {
                  painted += 1;
                  seen.add(d[i] + ',' + d[i + 1] + ',' + d[i + 2]);
                }
              }
              return { painted, w: c.width, h: c.height, colors: seen.size };
            }""")
            expect("scene painted", pixels["painted"] > 3000, pixels)
            expect("scene 256x192", pixels["w"] == 256 and pixels["h"] == 192, pixels)
            expect("scene detail colors", pixels["colors"] >= 24, pixels)
            name = page.text_content("#persona-name")
            expect("persona name shown", "Klingon" in (name or ""), name)
            bg_class = page.evaluate(
                "() => document.getElementById('screen-interview').className")
            expect("background class", "persona-klingon" in bg_class, bg_class)
            accent = page.evaluate(
                "() => getComputedStyle(document.getElementById('screen-interview'))"
                ".getPropertyValue('--accent').trim()")
            expect("accent variable", accent == "#d4a017", accent)

            # the scene panel is at least as tall as the text box
            heights = page.evaluate("""() => {
              const scene = document.getElementById('persona-scene')
                .getBoundingClientRect();
              const log = document.getElementById('chat-log')
                .getBoundingClientRect();
              return { scene: scene.height, log: log.height };
            }""")
            expect("scene taller than the text box",
                   heights["scene"] >= heights["log"], heights)

            # ---- B2. contrast and list bounds (owner playtest findings)
            steps = page.evaluate("""() => {
              const screen = document.getElementById('screen-interview')
                .getBoundingClientRect();
              const list = document.getElementById('step-tracker')
                .getBoundingClientRect();
              return { screenL: screen.left, listL: list.left };
            }""")
            expect("step numbers inside the screen",
                   steps["listL"] >= steps["screenL"] - 1, steps)

            contrast = page.evaluate("""() => {
              const lum = (r, g, b) => {
                const ch = (v) => {
                  const s = v / 255;
                  return s <= 0.04 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
                };
                return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b);
              };
              const parts = (css) => css.match(/[\\d.]+/g).slice(0, 3).map(Number);
              const ratio = (a, b) => {
                const la = lum(...parts(a));
                const lb = lum(...parts(b));
                return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
              };
              const bubble = document.querySelector('.chat-message.interviewer');
              const bubbleStyle = getComputedStyle(bubble);
              const step = document.querySelector('#step-tracker li.current');
              const stepStyle = getComputedStyle(step);
              return {
                bubbleInk: bubbleStyle.color,
                bubbleBg: bubbleStyle.backgroundColor,
                bubbleRatio: ratio(bubbleStyle.color, bubbleStyle.backgroundColor),
                stepInk: stepStyle.color,
                stepBg: stepStyle.backgroundColor,
                stepRatio: ratio(stepStyle.color,
                  stepStyle.backgroundColor === 'rgba(0, 0, 0, 0)'
                    ? 'rgb(43, 15, 15)' : stepStyle.backgroundColor),
              };
            }""")
            expect("bubble ink is cream", contrast["bubbleInk"]
                   == "rgb(244, 227, 194)", contrast)
            expect("bubble panel is dark", contrast["bubbleBg"]
                   == "rgb(29, 24, 38)", contrast)
            expect("bubble contrast ok", contrast["bubbleRatio"] >= 4.5, contrast)
            expect("current step ink is gold", contrast["stepInk"]
                   == "rgb(255, 217, 122)", contrast)
            expect("current step contrast ok", contrast["stepRatio"] >= 4.5, contrast)

            # ---- C. the scene animates: the pixels change over time
            frame1 = page.evaluate("""() => {
              const c = document.getElementById('persona-scene');
              return c.getContext('2d').getImageData(0, 0, 256, 192).data.join(',');
            }""")
            page.wait_for_timeout(700)
            frame2 = page.evaluate("""() => {
              const c = document.getElementById('persona-scene');
              return c.getContext('2d').getImageData(0, 0, 256, 192).data.join(',');
            }""")
            expect("scene animates", frame1 != frame2, "frames identical")

            # ---- D. the theme: pixel font, hard shadow, chunky border
            font_ok = page.evaluate(
                "() => document.fonts.check('12px \\'Press Start 2P\\'')")
            expect("pixel font loaded", font_ok, "not loaded")
            body_font = page.evaluate("() => getComputedStyle(document.body).fontFamily")
            expect("body uses the font", "Press Start 2P" in body_font, body_font)
            border = page.evaluate(
                "() => parseFloat(getComputedStyle(document.getElementById('send-btn'))"
                ".borderWidth)")
            expect("chunky border", border >= 2, border)
            shadow = page.evaluate(
                "() => getComputedStyle(document.getElementById('send-btn')).boxShadow")
            expect("hard shadow", "0px 0px 0px" in shadow or "px 0px 0px" in shadow, shadow)

            # ---- E. the voice: one streamed turn drives the fake context
            page.evaluate("() => { window.__audioLog.started = 0; }")
            page.fill("#candidate-input", "I will start with the users.")
            page.click("#send-btn")
            page.wait_for_selector("#interview-busy", state="hidden", timeout=20000)
            page.wait_for_function(
                "() => window.__audioLog.started > 0", timeout=20000)
            waves = page.evaluate("() => window.__audioLog.waves")
            expect("blip wave is klingon sawtooth",
                   waves and all(w == "sawtooth" for w in waves), waves[:4])

            # the mute toggle stops creation and persists
            page.click("#voice-mute")
            stored2 = page.evaluate(
                f"key => JSON.parse(localStorage.getItem(key)).preferences", SETTINGS_KEY)
            expect("mute persists", stored2.get("voiceMuted") is True, stored2)
            page.evaluate("() => { window.__audioLog.started = 0; }")
            page.fill("#candidate-input", "Next, the storage layer.")
            page.click("#send-btn")
            page.wait_for_selector("#interview-busy", state="hidden", timeout=20000)
            page.wait_for_timeout(500)
            started = page.evaluate("() => window.__audioLog.started")
            expect("muted turn creates no blips", started == 0, started)

            # ---- F. switching persona changes art and palette
            page.click("#screen-nav button[data-nav='menu']")
            page.evaluate("key => localStorage.removeItem(key)",
                          "tadsdi.session.v1")
            page.select_option("#persona-select", "vulcan")
            page.click("#start-interview")
            page.wait_for_selector("#chat-log .chat-message.interviewer", timeout=15000)
            page.wait_for_selector("#interview-busy", state="hidden", timeout=15000)
            bg_class2 = page.evaluate(
                "() => document.getElementById('screen-interview').className")
            expect("second persona class", "persona-vulcan" in bg_class2, bg_class2)
            accent2 = page.evaluate(
                "() => getComputedStyle(document.getElementById('screen-interview'))"
                ".getPropertyValue('--accent').trim()")
            expect("second accent", accent2 == "#8fb8d8", accent2)
            waves2 = page.evaluate("() => window.__audioLog.waves.slice(-3)")
            expect("muted stays muted", page.evaluate(
                "() => window.__audioLog.started") == 0, "audio played while muted")

            # Leave like a player would: the menu stops the portrait loop,
            # so the browser closes with no live timer.
            page.click("#screen-nav button[data-nav='menu']")
            page.wait_for_selector("#start-interview", state="visible")

            bad = game_errors(errors)
            expect("zero game errors", not bad, bad[:3])
            assert ok, "m4 ui mismatch"
            print("M4 UI: PASS (picker, portrait, backdrop, theme, voice, mute)")
            browser.close()
            return 0
    finally:
        server.terminate()


if __name__ == "__main__":
    sys.exit(main())
