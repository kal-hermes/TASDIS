"""M3 task 4: context compression (DESIGN.md 7.1). Units on a long session
with the real window math, then browser runs: a real compression during a
mock interview, and a summarization call that fails without stopping the
interview. Run from game/:
    uv run --with playwright python tests/m3_context.py
"""

import json
import pathlib
import subprocess
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from m1_e2e import Driver, GAME_DIR, PORT as M1_PORT, SEED_SETTINGS  # noqa: E402

PORT = M1_PORT + 5
BASE = f"http://127.0.0.1:{PORT}"
MODULES = BASE + "/"  # base URL for dynamic imports in page.evaluate
SETTINGS_KEY = "tadsdi.settings.v1"
SMALL_CONTEXT = 4000  # tokens: a fake limit that leaves room for only a few long turns
FILLER = "design reasoning " * 90  # about 1500 characters per candidate message


def set_text_role(page, **fields):
    page.evaluate(
        """([key, fields]) => {
          const s = JSON.parse(localStorage.getItem(key));
          s.roles.text = { ...s.roles.text, ...fields };
          localStorage.setItem(key, JSON.stringify(s));
        }""",
        [SETTINGS_KEY, fields])


UNITS = """async (base) => {
  const state = await import(base + 'js/state.js?v=29');
  const context = await import(base + 'js/context.js?v=29');
  const sum = await import(base + 'js/prompts/summarize-prompt.js?v=29');
  const prompts = await import(base + 'js/prompts/grader-prompt.js?v=29');
  const providers = await import(base + 'js/providers.js?v=29');
  const settings = await import(base + 'js/settings.js?v=29');
  const out = {};
  const CTX = 16000;  // tokens: a mid-size window that a long transcript outgrows
  const problem = { id: 'p', title: 'P', vague_prompt: 'Design X.',
    hidden_guidance: ['g0'], constrained_variant: 'AWS' };

  // interviewer opening, a LaTeX artifact, then candidate/interviewer turns
  const build = (turns, turnChars) => {
    const s = state.newSession(problem, { helpMode: 'testing' });
    state.addMessage(s, 'interviewer', 'opening');
    state.addArtifact(s, { kind: 'latex', source: 'W = 10^7 \\\\div 86400', step: 2 });
    for (let i = 0; i < turns; i += 1) {
      state.addMessage(s, 'candidate', `candidate turn ${i} ` + 'y'.repeat(turnChars));
      state.addMessage(s, 'interviewer', `interviewer answer ${i}`);
    }
    return s;
  };
  const has = (messages, needle) => messages.some((m) => m.content.includes(needle));
  const tokens = (messages) => messages.reduce((n, m) => n + context.estimateTokens(m.content), 0);
  const SUMMARY = JSON.stringify({
    narrative: 'The candidate asked about scale. The interviewer answered 100 million reads per day. '
      + 'The candidate chose one database and a read cache.',
    decisions: ['One primary database', 'A read cache in front of the database'],
    estimates: ['About 1157 reads per second'],
    open_threads: ['How the cache is invalidated'],
  });

  // 1. everything fits: the window holds the whole transcript
  const small = build(10, 100);
  out.fits = { start: context.firstVerbatimIndex(small, 0),
    needed: context.summarizationNeeded(small, 0) };

  // 2. a long transcript leaves the window
  const big = build(60, 700);
  const before = context.assembleContext(big, { contextTokens: CTX });
  out.overflow = { range: context.overflowRange(big, CTX),
    needed: context.summarizationNeeded(big, CTX), length: big.transcript.length };
  out.before = { artifactIn: has(before, 'W = 10^7'), latestIn: has(before, 'candidate turn 59 '),
    oldestOut: !has(before, 'candidate turn 0 '), narrativeIn: has(before, 'Summary of earlier turns') };

  // 3. one call distills the overflow into the ledger and a narrative
  let calls = 0;
  const input = {};
  const result = await context.compressIfNeeded(big, { contextTokens: CTX,
    summarize: async (messages) => {
      calls += 1;
      input.hasNoPrevious = has(messages, '(none yet)');
      input.hasOldest = has(messages, 'candidate turn 0 ');
      input.hasArtifact = has(messages, 'W = 10^7');
      return SUMMARY;
    } });
  const after = context.assembleContext(big, { contextTokens: CTX });
  out.compressed = { result, calls, input,
    upto: big.compression.uptoIndex, transcriptLength: big.transcript.length,
    narrativeIn: has(after, '100 million reads per day'),
    oldestOut: !has(after, 'candidate turn 0 '), latestIn: has(after, 'candidate turn 59 '),
    artifactIn: has(after, 'W = 10^7'),
    decisions: big.ledger.components.filter((c) => c.status === 'summarized').map((c) => c.source),
    estimates: big.ledger.estimates.filter((e) => e.status === 'summarized').map((e) => e.source),
    openThreads: big.ledger.openThreads,
    tokens: tokens(after), limit: CTX * context.THRESHOLD,
    neededAfter: context.summarizationNeeded(big, CTX) };

  // 4. idempotent: nothing new to summarize, and a second apply adds nothing
  const again = await context.compressIfNeeded(big, { contextTokens: CTX,
    summarize: async () => { calls += 1; return SUMMARY; } });
  out.again = { result: again, calls };
  const counts = [big.ledger.components.length, big.ledger.estimates.length, big.ledger.openThreads.length];
  context.applyCompression(big, context.parseSummary(SUMMARY), big.compression.uptoIndex);
  out.applyTwice = [big.ledger.components.length, big.ledger.estimates.length,
    big.ledger.openThreads.length].join() === counts.join();

  // 5. both graders still read the full transcript from storage
  out.graderSeesOldest = has(prompts.buildGraderMessages(big, 'final'), 'candidate turn 0 ') &&
    has(prompts.buildGraderMessages(big, 'mid'), 'candidate turn 0 ');

  // 6. a failing summarization call leaves the session as it was
  const failing = build(60, 700);
  const status = [];
  const failOptions = { contextTokens: CTX, onStatus: (text) => status.push(text) };
  out.failed = await context.compressIfNeeded(failing, { ...failOptions,
    summarize: async () => { throw new Error('HTTP 500: upstream down'); } });
  out.failedState = { compression: failing.compression === undefined,
    status: [...status], transcriptLength: failing.transcript.length,
    needed: context.summarizationNeeded(failing, CTX) };
  out.recovered = (await context.compressIfNeeded(failing, { ...failOptions,
    summarize: async () => SUMMARY })).compressed && failing.compression !== undefined;

  // 7. an invalid summary is refused, never applied
  const invalid = build(60, 700);
  const bad = ['Sure, here is a summary.', '{"narrative": "' + 'x'.repeat(40) + '"}',
    JSON.stringify({ narrative: 'x', decisions: [], estimates: [], open_threads: [] }),
    JSON.stringify({ narrative: 'x'.repeat(40), decisions: ['ok', 5], estimates: [], open_threads: [] })];
  out.invalid = [];
  for (const text of bad) {
    const r = await context.compressIfNeeded(invalid, { contextTokens: CTX,
      summarize: async () => text });
    out.invalid.push(`${r.compressed}:${r.error ? 'error' : 'no error'}`);
  }
  out.invalidApplied = invalid.compression !== undefined;

  // 8. a small context window still keeps the newest turns verbatim
  const tiny = build(20, 700);
  out.tiny = { start: context.firstVerbatimIndex(tiny, 2000), length: tiny.transcript.length,
    keeps: context.KEEP_RECENT_TURNS };

  // 9. mock faults can name the call they fail
  const msgs = [{ role: 'user', content: 'ping' }];
  const run = async (purpose) => {
    try { await providers.complete('text', msgs, { purpose }); return 'ok'; }
    catch (e) { return e.message; }
  };
  providers.setMockFaultQueue([{ kind: 'http', status: 500, purpose: 'summarize' }, 'network']);
  out.faults = [await run('interview'), await run('summarize'), await run('interview'),
    (await run('interview')).slice(0, 2)];
  providers.setMockFaultQueue([]);

  // 10. the context window is a Settings field of the text role
  out.settingsDefault = settings.loadSettings().roles.text.contextTokens;
  const saved = settings.loadSettings();
  saved.roles.text.contextTokens = 64000;
  settings.saveSettings(saved);
  out.settingsRead = providers.textContextTokens();
  saved.roles.text.contextTokens = 0;
  settings.saveSettings(saved);

  // 11. the summarizer prompt
  const system = sum.buildSummarizeMessages(big, { from: 0, to: 2 })[0].content;
  out.prompt = { json: system.includes('"narrative"') && system.includes('"open_threads"'),
    addsNothing: /Add nothing/.test(system), keepsNumbers: /unit/.test(system) };
  return out;
}"""


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
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"{BASE}/index.html", wait_until="networkidle")

            # ---- units ------------------------------------------------
            out = page.evaluate(UNITS, MODULES)

            def expect(name, condition, detail=""):
                print(f"  {'ok  ' if condition else 'FAIL'} {name}" + ("" if condition else f": {detail}"))
                assert condition, f"{name}: {detail}"

            expect("fits: whole transcript verbatim, nothing to summarize",
                   out["fits"] == {"start": 0, "needed": False}, out["fits"])
            expect("overflow: range starts at 0 and ends before the newest turns",
                   out["overflow"]["range"]["from"] == 0 and 0 < out["overflow"]["range"]["to"]
                   < out["overflow"]["length"], out["overflow"])
            expect("overflow: needed", out["overflow"]["needed"] is True)
            expect("before: artifacts in, newest in, oldest out, no narrative",
                   out["before"] == {"artifactIn": True, "latestIn": True, "oldestOut": True,
                                     "narrativeIn": False}, out["before"])
            c = out["compressed"]
            expect("compress: one call, applied", c["result"]["compressed"] is True and c["calls"] == 1, c["result"])
            expect("compress: summarizer sees the overflow turns and the artifact, no earlier summary",
                   c["input"] == {"hasNoPrevious": True, "hasOldest": True, "hasArtifact": True}, c["input"])
            expect("compress: stored transcript unchanged", c["transcriptLength"] == out["overflow"]["length"])
            expect("compress: narrative in, summarized turns out, newest and artifacts in",
                   c["narrativeIn"] and c["oldestOut"] and c["latestIn"] and c["artifactIn"], c)
            expect("compress: ledger gains summarized decisions, estimates, open threads",
                   c["decisions"] == ["One primary database", "A read cache in front of the database"]
                   and c["estimates"] == ["About 1157 reads per second"]
                   and c["openThreads"] == ["How the cache is invalidated"], c)
            expect("compress: assembly fits 60 percent of the context window (rounding allowed)",
                   c["tokens"] <= c["limit"] + 20, f"{c['tokens']} > {c['limit']}")
            expect("compress: nothing more to summarize", c["neededAfter"] is False, c)
            expect("idempotent: a second call is a no-op and a second apply adds nothing",
                   out["again"] == {"result": {"compressed": False}, "calls": 1} and out["applyTwice"],
                   out["again"])
            expect("graders read the full transcript", out["graderSeesOldest"] is True)
            f = out["failed"]
            expect("failure: reported, not applied, session intact, still needed later",
                   f["compressed"] is False and "HTTP 500" in f["error"]
                   and out["failedState"]["compression"] is True
                   and out["failedState"]["transcriptLength"] == out["overflow"]["length"]
                   and out["failedState"]["needed"] is True
                   and len(out["failedState"]["status"]) == 1
                   and "not summarized" in out["failedState"]["status"][0], out["failedState"])
            expect("failure: the next attempt succeeds", out["recovered"] is True)
            expect("invalid summary: refused with an error, never applied",
                   out["invalid"] == ["false:error"] * 4 and out["invalidApplied"] is False,
                   out["invalid"])
            expect("small context: the newest turns stay verbatim",
                   out["tiny"]["start"] == out["tiny"]["length"] - out["tiny"]["keeps"], out["tiny"])
            expect("faults: a fault can name the call it fails",
                   "HTTP 500" in out["faults"][1] and "network or CORS" in out["faults"][0]
                   and out["faults"][2] == "ok" and out["faults"][3] == "ok", out["faults"])
            expect("settings: context window defaults to 0 and reads back",
                   out["settingsDefault"] == 0 and out["settingsRead"] == 64000, out)
            expect("prompt: strict JSON, adds nothing, keeps numbers with units",
                   out["prompt"] == {"json": True, "addsNothing": True, "keepsNumbers": True}, out["prompt"])
            print("  ok   units: window, compression, idempotence, graders, failure, invalid, faults")

            # ---- browser: default settings never compress short interviews
            d = Driver(page, BASE)
            d.start_session(help_mode="learning")
            for _ in range(3):
                d.send("A short answer.")
            s = d.stored_session()
            assert "compression" not in s, "a short interview was compressed"
            assert page.locator("#engine-status").inner_text() == ""
            print("  ok   browser: a short interview is not compressed")

            # ---- browser: long turns on a small context window ----------
            # The page load in start_session seeds the default settings, so the
            # fake limit is set after it. Every call reads the settings again.
            d.start_session(help_mode="learning")
            set_text_role(page, contextTokens=SMALL_CONTEXT)
            for i in range(8):
                d.send(f"MARKER-{i} " + FILLER)
            s = d.stored_session()
            assert s.get("compression", {}).get("narrative"), "no compression recorded"
            assert "100 million reads per day" in s["compression"]["narrative"], s["compression"]
            assert len(s["transcript"]) == 17, len(s["transcript"])
            assert any(e["status"] == "summarized" for e in s["ledger"]["estimates"]), s["ledger"]
            assert page.locator("#engine-status").inner_text() == "", "status shows a failure"
            assembly = page.evaluate("""async ([base, session, tokens]) => {
              const context = await import(base + 'js/context.js?v=29');
              return context.assembleContext(session, { contextTokens: tokens })
                .map((m) => m.content);
            }""", [MODULES, s, SMALL_CONTEXT])
            joined = "\n".join(assembly)
            assert "MARKER-0 " not in joined, "the summarized turn is still in the assembly"
            assert "MARKER-7 " in joined, "the newest turn left the assembly"
            assert "Summary of earlier turns" in joined and "100 million reads per day" in joined
            assert len(d.stored_session()["transcript"]) == 17, "the stored transcript shrank"
            print("  ok   browser: long turns compress into narrative and ledger")

            # ---- browser: a failing summary call does not stop the interview
            d.start_session(help_mode="learning")
            set_text_role(page, contextTokens=SMALL_CONTEXT)
            page.evaluate("""async ([base, n]) => {
              const providers = await import(base + 'js/providers.js?v=29');
              providers.setMockFaultQueue(Array.from({ length: n }, () => (
                { kind: 'http', status: 500, purpose: 'summarize' })));
            }""", [MODULES, 5])
            for i in range(8):
                d.send(f"RETRY-MARKER-{i} " + FILLER)
                assert page.locator("#send-btn").is_enabled(), f"turn {i}: the interview stopped"
            s = d.stored_session()
            assert "compression" not in s, "a failed summary was recorded"
            assert len(s["transcript"]) == 17, len(s["transcript"])
            status = page.locator("#engine-status").inner_text()
            assert "not summarized" in status and "HTTP 500" in status, status
            d.send("RETRY-MARKER-8 " + FILLER)
            s = d.stored_session()
            assert s.get("compression", {}).get("narrative"), "no compression after the failures ended"
            assert page.locator("#engine-status").inner_text() == "", "status not cleared after success"
            assert len(s["transcript"]) == 19, len(s["transcript"])
            print("  ok   browser: failed summary calls leave the interview running, then recover")

            assert not errors, f"console/page errors: {errors}"
            browser.close()
        print("M3 CONTEXT: PASS (window, compression, idempotence, graders, failure, faults, browser)")
        return 0
    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
