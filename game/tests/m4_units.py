"""M4 unit checks: persona registry, blip schedule, voice play calls,
and the persona prompt block in the assembler. Driven through the browser
(dynamic module import) so the real module graph runs. Offline. Run from
game/:
    uv run --with playwright python tests/m4_units.py
"""

import pathlib
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

GAME_DIR = pathlib.Path(__file__).resolve().parent.parent
PORT = 8144
BASE = f"http://127.0.0.1:{PORT}"

EXPECTED_EXPECTATION = {
    "registry": {"ids": "klingon,vulcan,pirate,cowboy,normal",
                 "fields": True},
    "blips": {"latinCount": 3, "cjkCount": 5, "durations": True,
              "pitches": True, "deterministic": True},
    "voice": {"klingonWave": "sawtooth", "vulcanWave": "sine",
              "count": True, "muted": 0},
    "prompt": {"klingon": True, "vulcan": True, "pirate": True,
               "cowboy": True, "normal": True},
    "scenes": {"sceneIds": True, "detail": True, "colors": True,
               "deterministic": True, "animated": True,
               "klingonFlash": True, "vulcanSoup": True,
               "cowboyPuff": True, "pirateFlash": True,
               "officeStapler": True, "bustSkin": True},
    "mouth": {"atlas": True, "idleClosed": True, "talkCycle": True,
              "deterministic": True},
    "speech": {"present": True, "distinct": True},
    "voiceStop": {"mutesTracked": True, "replaysAfterStop": True},
}


def wait_port(port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


UNITS = """
  const personas = await import('./js/personas.js?v=38');
  const audio = await import('./js/audio.js?v=38');
  const assemble = await import('./js/prompts/assemble.js?v=38');
  const out = {};

  // ---- 1. the registry: five personas, every field present
  out.registry = {};
  const expected = ['klingon', 'vulcan', 'pirate', 'cowboy', 'normal'];
  out.registry.ids = personas.PERSONA_IDS.join(',');
  out.registry.fields = expected.every((id) => {
    const p = personas.PERSONAS[id];
    return p && typeof p.name === 'string' && p.name.length > 0
      && typeof p.promptBlock === 'string' && p.promptBlock.length > 40
      && p.palette && Object.keys(p.palette).length >= 3
      && p.timbre && typeof p.timbre.wave === 'string'
      && p.timbre.minHz > 0 && p.timbre.maxHz > p.timbre.minHz
      && typeof p.background === 'string' && p.background.length > 0;
  });

  // ---- 2. the blip schedule
  out.blips = {};
  const klingon = personas.PERSONAS.klingon;
  const latin = audio.scheduleBlips('QPS is 100.', klingon);
  out.blips.latinCount = latin.length;
  const cjk = audio.scheduleBlips('\\u3053\\u3093\\u306b\\u3061\\u306f', klingon);
  out.blips.cjkCount = cjk.length;
  out.blips.durations = latin.every((b) => b.ms >= 50 && b.ms <= 100)
    && cjk.every((b) => b.ms >= 50 && b.ms <= 100);
  out.blips.pitches = latin.every((b) => b.hz >= klingon.timbre.minHz
    && b.hz <= klingon.timbre.maxHz);
  const again = audio.scheduleBlips('QPS is 100.', klingon);
  out.blips.deterministic = JSON.stringify(latin) === JSON.stringify(again);

  // ---- 3. the voice plays the schedule with the persona waveform
  class FakeOsc {
    constructor(log) { this.log = log; this.type = ''; this.frequency = {
      setValueAtTime: (v) => this.log.freqs.push(v) }; }
    connect() {}
    start() { this.log.started += 1; }
    stop() {}
  }
  class FakeCtx {
    constructor() { this.log = { started: 0, freqs: [], waves: [] }; }
    get currentTime() { return 0; }
    get destination() { return {}; }
    createOscillator() { const o = new FakeOsc(this.log); this.log.waves.push(o); return o; }
    createGain() { return { gain: { setValueAtTime() {}, exponentialRampToValueAtTime() {} }, connect() {} }; }
  }
  out.voice = {};
  const kc = new FakeCtx();
  const kv = new audio.BlipVoice(kc, klingon, { muted: false });
  kv.play(latin);
  out.voice.klingonWave = kc.log.waves.every((o) => o.type === 'sawtooth')
    ? 'sawtooth' : 'other';
  const vc = new FakeCtx();
  const vv = new audio.BlipVoice(vc, personas.PERSONAS.vulcan, { muted: false });
  vv.play(latin);
  out.voice.vulcanWave = vc.log.waves.every((o) => o.type === 'sine')
    ? 'sine' : 'other';
  const cc = new FakeCtx();
  const cv = new audio.BlipVoice(cc, klingon, { muted: false });
  cv.play(cjk);
  out.voice.count = cc.log.started === cjk.length;
  const mc = new FakeCtx();
  const mv = new audio.BlipVoice(mc, klingon, { muted: true });
  mv.play(latin);
  out.voice.muted = mc.log.started;

  // ---- 4. the persona prompt block in the assembler
  const problem = {
    id: 'p1', title: 'P1', vague_prompt: 'Design X.',
    hidden_guidance: ['g0', 'g1'],
  };
  const marker = (id) => {
    const msgs = assemble.assembleInterviewerPrompt({
      problem, persona: id, currentStep: 1, revealedGuidance: [],
    });
    return personas.PERSONAS[id].promptBlock.split('\\n')[0];
  };
  out.prompt = {};
  for (const id of ['klingon', 'vulcan', 'pirate', 'cowboy', 'normal']) {
    const msgs = assemble.assembleInterviewerPrompt({
      problem, persona: id, currentStep: 1, revealedGuidance: [],
    });
    const sys = msgs[0].content;
    out.prompt[id] = sys.includes(personas.PERSONAS[id].promptBlock);
  }
  // ---- 5. the 16-bit scenes: one animated painted scene per persona
  const scenes = await import('./js/scenes.js?v=38');
  out.scenes = {};
  const ids = ['klingon', 'vulcan', 'pirate', 'cowboy', 'normal'];
  const record = () => {
    const ops = [];
    const fake = {
      fillStyle: '',
      fillRect(x, y, w, h) { ops.push([this.fillStyle, x, y, w, h]); },
    };
    return { fake, ops };
  };
  const paintOps = (id, frame) => {
    const r = record();
    scenes.getScene(id).paint(r.fake, frame);
    return r.ops;
  };
  const area = (ops, color) => ops
    .filter((op) => op[0] === color)
    .reduce((sum, op) => sum + op[3] * op[4], 0);
  const hasColor = (ops, color) => ops.some((op) => op[0] === color);
  out.scenes.sceneIds = ids.every((id) => {
    const s = scenes.getScene(id);
    return s && typeof s.paint === 'function' && s.palette;
  });
  const zero = {};
  for (const id of ids) zero[id] = paintOps(id, 0);
  out.scenes.detail = ids.every((id) => zero[id]
    .reduce((sum, op) => sum + op[3] * op[4], 0) >= 18000);
  out.scenes.colors = ids.every((id) => new Set(zero[id]
    .map((op) => op[0])).size >= 8);
  out.scenes.deterministic = ids.every((id) => {
    const a = paintOps(id, 97);
    const b = paintOps(id, 97);
    return JSON.stringify(a) === JSON.stringify(b);
  });
  out.scenes.animated = ids.every((id) => {
    const f97 = paintOps(id, 97);
    return JSON.stringify(zero[id]) !== JSON.stringify(f97);
  });
  out.scenes.klingonFlash = hasColor(paintOps('klingon', 74), '#ffd75e')
    && !hasColor(zero.klingon, '#ffd75e');
  out.scenes.vulcanSoup = hasColor(paintOps('vulcan', 90), '#7a4a21')
    && !hasColor(zero.vulcan, '#7a4a21');
  out.scenes.cowboyPuff = hasColor(paintOps('cowboy', 120), '#9fd26a')
    && !hasColor(zero.cowboy, '#9fd26a');
  out.scenes.pirateFlash = area(paintOps('pirate', 82), '#e8f2ff') >= 8000
    && area(zero.pirate, '#e8f2ff') === 0;
  out.scenes.officeStapler = hasColor(zero.normal, '#c81e1e');
  out.scenes.bustSkin = ids.every((id) => area(zero[id],
    scenes.getScene(id).skin) >= 30);

  // ---- 6. the mouth atlas: states, tags, and the pure frame picker
  const mouth = await import('./js/mouth.js?v=38');
  out.mouth = {};
  out.mouth.atlas = ids.every((id, i) => {
    const p = mouth.MOUTH_META.personas[id];
    return p && p.base === i * 3
      && mouth.MOUTH_META.frameW === 10
      && mouth.MOUTH_META.frameH === 7
      && mouth.MOUTH_META.talkMs === 90;
  });
  out.mouth.idleClosed = [0, 45, 500, 99999].every((ms) =>
    mouth.pickMouthFrame(false, ms) === 0);
  out.mouth.talkCycle = mouth.pickMouthFrame(true, 0) === 1
    && mouth.pickMouthFrame(true, 89) === 1
    && mouth.pickMouthFrame(true, 90) === 2
    && mouth.pickMouthFrame(true, 179) === 2
    && mouth.pickMouthFrame(true, 180) === 1;
  out.mouth.deterministic = [0, 95, 200, 777].every((ms) =>
    mouth.pickMouthFrame(true, ms) === mouth.pickMouthFrame(true, ms));

  // ---- 7. the menu preview speech: one sample paragraph per persona
  const reg = await import('./js/personas.js?v=38');
  const texts = ids.map((id) => reg.PERSONAS[id].sampleSpeech || '');
  out.speech = {};
  out.speech.present = texts.every((t) => t.length >= 40 && t.length <= 400);
  out.speech.distinct = new Set(texts).size === ids.length;

  // ---- 8. BlipVoice.stop mutes the tracked blips and stays usable
  const audioMod = await import('./js/audio.js?v=38');
  let cancelled = 0;
  const mkOsc = () => ({ connect() {}, start() {}, stop() {},
    frequency: { setValueAtTime() {} }, onended: null });
  const fakeCtx = { currentTime: 0, destination: {},
    createOscillator: mkOsc,
    createGain: () => ({ connect() {}, gain: {
      setValueAtTime() {}, exponentialRampToValueAtTime() {},
      cancelScheduledValues() { cancelled += 1; } } }) };
  const p = { timbre: { wave: 'sine', minHz: 140, maxHz: 300 } };
  const voice = new audioMod.BlipVoice(fakeCtx, p, {});
  const made = voice.play([{ ms: 60, hz: 200 }, { ms: 60, hz: 220 }]);
  voice.stop();
  const replayed = voice.play([{ ms: 60, hz: 210 }]);
  out.voiceStop = {};
  out.voiceStop.mutesTracked = made === 2 && cancelled >= 2;
  out.voiceStop.replaysAfterStop = replayed === 1;
  return out;
"""


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
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"{BASE}/index.html", wait_until="networkidle")

            out = page.evaluate(f"async () => {{\n{UNITS}\n}}")
            ok = True
            for group, want in EXPECTED_EXPECTATION.items():
                got = out.get(group, {})
                for key, value in want.items():
                    good = got.get(key) == value
                    if not good:
                        print(f"  FAIL {group}.{key}: want {value!r} got {got.get(key)!r}")
                    ok = ok and good
            if errors:
                ok = False
                print("  console/page errors:", errors[:5])
            assert ok, "m4 units mismatch"
            print("M4 UNITS: PASS (registry, blip schedule, voice waves, prompt blocks)")
            browser.close()
            return 0
    finally:
        server.terminate()


if __name__ == "__main__":
    sys.exit(main())
