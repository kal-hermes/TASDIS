"""M2 unit checks: grader parsing, score math, retry-once, mid shape.
Run from game/:
    uv run --with playwright python tests/m2_units.py
"""

import json
import pathlib
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

GAME_DIR = pathlib.Path(__file__).resolve().parent.parent
PORT = 8142
BASE = f"http://127.0.0.1:{PORT}"

SEED = json.dumps({"roles": {
    "text": {"provider": "mock", "baseUrl": "", "model": "m", "apiKey": ""},
    "vision": {"provider": "mock", "baseUrl": "", "model": "v", "apiKey": ""},
    "image": {"provider": "mock", "baseUrl": "", "model": "i", "apiKey": ""}},
    "preferences": {"showHowToAtStart": False}})


def wait_port(port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


def main():
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
        cwd=GAME_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    errors = []
    try:
        assert wait_port(PORT)
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page()
            page.add_init_script(
                f"window.localStorage.setItem('tadsdi.settings.v1', {json.dumps(SEED)})")
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"{BASE}/index.html", wait_until="networkidle")

            result = page.evaluate("""async () => {
              const grader = await import('./js/grader.js?v=28');
              const prompts = await import('./js/prompts/grader-prompt.js?v=28');
              const providers = await import('./js/providers.js?v=28');
              const state = await import('./js/state.js?v=28');
              const out = {};

              // parse: plain, fenced, preamble junk (full valid 8-row grade)
              const valid = {rows: prompts.DIAGNOSTIC_ROWS.map(r => (
                {name: r.name, pass: true, fix: ''}))};
              out.parsePlain = Boolean(grader.parseGradeJson(JSON.stringify(valid)));
              out.parseFenced = Boolean(grader.parseGradeJson(
                '```json\\n' + JSON.stringify(valid) + '\\n```'));
              out.parseJunk = Boolean(grader.parseGradeJson(
                'Sure! Here is my assessment:\\n' + JSON.stringify(valid) + '\\nHope it helps.'));
              let threw = false;
              try { grader.parseGradeJson('not json at all'); } catch { threw = true; }
              out.parseThrows = threw;

              // row validation
              let badRows = false;
              try {
                grader.parseGradeJson(JSON.stringify({rows: [{name: 'requirements', pass: true, fix: ''}]}));
              } catch { badRows = true; }
              out.badRowsThrow = badRows;

              // score math
              const mk = (n) => Array.from({length: 8}, (_, i) => (
                {name: prompts.DIAGNOSTIC_ROWS[i].name, pass: i < n, fix: ''}));
              out.score = [grader.computeScore(mk(8)), grader.computeScore(mk(4)), grader.computeScore(mk(0))].join(',');

              // prompt shape
              const problem = {id: 'p', title: 'P', vague_prompt: 'Design.',
                hidden_guidance: [], known_patterns: ['kp1'], common_misses: ['cm1'],
                constrained_variant: null};
              const session = state.newSession(problem, {});
              state.addMessage(session, 'candidate', 'hello transcript');
              session.ledger.estimates.push({id: 'x', step: 1, status: 'proposed', source: 'Q=1'});
              const msgs = prompts.buildGraderMessages(session, 'final');
              const sys = msgs[0].content;
              const usr = msgs[1].content;
              out.prompt = {
                twoMessages: msgs.length === 2,
                rowCount: prompts.DIAGNOSTIC_ROWS.length,
                hasAllRows: prompts.DIAGNOSTIC_ROWS.every(r => sys.includes(r.name)),
                hasEstimation: sys.includes('Jeff Dean'),
                hasStrictJson: sys.includes('Return ONLY a JSON object'),
                hasPatterns: usr.includes('kp1'),
                hasMisses: usr.includes('cm1'),
                hasTranscript: usr.includes('hello transcript'),
                hasLedger: usr.includes('design_ledger'),
              };
              const mid = prompts.buildGraderMessages(session, 'mid');
              out.midPromptNoScore = !/PROGRESS/.test(mid[0].content) === false;

              // retry via mock queue: bad then good
              providers.resetMockState();
              providers.setMockGraderQueue(['grade_bad', 'grade']);
              const g = await grader.gradeSession(session, {variant: 'final'});
              out.retryGrade = {score: g.score, rows: g.rows.length};

              // queue exhausted with bad entries -> throws after retry
              providers.setMockGraderQueue(['grade_bad', 'grade_bad']);
              let retryThrow = false;
              try { await grader.gradeSession(session, {variant: 'final'}); } catch { retryThrow = true; }
              out.retryThrows = retryThrow;

              // mid variant shape
              providers.resetMockState();
              const m = await grader.gradeSession(session, {variant: 'mid'});
              out.mid = {
                keys: ['solid_steps','passing_rows','obvious_gaps','note'].every(k => k in m),
                noScore: !('score' in m),
                note: typeof m.note === 'string' && m.note.length > 0,
              };

              out.tokenEstimate = grader.graderTokenEstimate(session) > 0;
              return out;
            }""")

            exp = {
                "parsePlain": True, "parseFenced": True, "parseJunk": True,
                "parseThrows": True, "badRowsThrow": True,
                "score": "10,5,0",
                "prompt": {"twoMessages": True, "rowCount": 8, "hasAllRows": True,
                           "hasEstimation": True, "hasStrictJson": True, "hasPatterns": True,
                           "hasMisses": True, "hasTranscript": True, "hasLedger": True},
                "midPromptNoScore": True,
                "retryGrade": {"score": 6, "rows": 8},
                "retryThrows": True,
                "mid": {"keys": True, "noScore": True, "note": True},
                "tokenEstimate": True,
            }
            assert result == exp, f"unit mismatch:\n got {json.dumps(result, indent=1)}\n want {json.dumps(exp, indent=1)}"
            assert not errors, f"console/page errors: {errors}"
            browser.close()
        print("M2 UNITS: PASS (parse, fences, validation, score, retry-once, mid shape)")
        return 0
    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
