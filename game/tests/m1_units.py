"""M1 unit checks for state.js and context.js, driven through the browser
(dynamic module import) so the real module graph runs. Offline: no provider
calls. Run from game/:
    uv run --with playwright python tests/m1_units.py
"""

import json
import pathlib
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

GAME_DIR = pathlib.Path(__file__).resolve().parent.parent
PORT = 8139
BASE = f"http://127.0.0.1:{PORT}"


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
        assert wait_port(PORT), "http.server did not come up"
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page()
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"{BASE}/index.html", wait_until="networkidle")

            result = page.evaluate("""async () => {
              const state = await import('./js/state.js?v=22');
              const context = await import('./js/context.js?v=22');
              const assemble = await import('./js/prompts/assemble.js?v=22');
              const out = {};

              const problem = {
                id: 'p1', title: 'P1', vague_prompt: 'Design X.',
                hidden_guidance: ['g0', 'g1'],
                constrained_variant: 'AWS, MySQL',
              };
              const session = state.newSession(problem, {helpMode: 'testing'});
              out.newSession = {
                state: session.state,
                ledgerKeys: Object.keys(session.ledger).sort().join(','),
                helpMode: session.helpMode,
                proactiveHints: session.proactiveHints,
                showTracker: session.showTracker,
              };

              const a1 = state.addArtifact(session, {kind: 'latex', source: 'QPS = 5800', step: 1});
              const a2 = state.addArtifact(session, {kind: 'mermaid', source: 'graph LR; A-->B', step: 2});
              out.ledger = {
                estimates: session.ledger.estimates.length,
                components: session.ledger.components.length,
                transcriptArtifacts: session.transcript.filter(m => m.artifactId).length,
              };

              state.coverStep(session, 3);
              state.coverStep(session, 1);
              state.coverStep(session, 3);
              out.coverage = session.coveredSteps.join(',');

              state.revealGuidance(session, [1]);
              state.revealGuidance(session, [1, 0]);
              out.guidance = session.ledger.revealedGuidance.join(',');

              out.currentStep = (() => { state.setCurrentStep(session, 9); return session.currentStep; })();

              const prompt = assemble.assembleInterviewerPrompt(
                {problem, helpMode: 'testing', constraintMode: 'constrained'});
              out.prompt = {
                messages: prompt.length,
                hasPersona: /senior systems engineer/.test(prompt[0].content),
                hasVague: prompt[0].content.includes('Design X.'),
                hasHidden: prompt[0].content.includes('g0'),
                hasEstimation: prompt[0].content.includes('Jeff Dean'),
                hasTestingRefusal: /Refuse all help/.test(prompt[0].content),
                hasPinned: prompt[0].content.includes('AWS, MySQL'),
                hasNoSolicit: /Never solicit an\s+estimate/.test(prompt[0].content),
                hasNoVolunteer: prompt[0].content.includes('Never volunteer process guidance'),
              };
              const learn = assemble.assembleInterviewerPrompt(
                {problem, helpMode: 'learning', constraintMode: 'unconstrained'});
              out.promptLearning = /Mode: learning/.test(learn[0].content);
              out.promptFreeChoice = /any technologies/.test(learn[0].content);
              out.learningPassive = learn[0].content.includes('do not volunteer');
              out.learningDefaultNoPointer = !learn[0].content.includes('ONE gentle pointer');
              const learnPro = assemble.assembleInterviewerPrompt(
                {problem, helpMode: 'learning', constraintMode: 'unconstrained', proactiveHints: true});
              out.learningProactive = learnPro[0].content.includes('ONE gentle pointer');

              const briefing = assemble.assembleBriefingMessages({problem});
              out.briefingTurns = briefing.length;

              // context assembly: a head that is never compressed, then the
              // newest turns inside the window of the model context
              for (let i = 0; i < 30; i++) {
                state.addMessage(session, 'candidate', `filler message ${i} ` + 'x'.repeat(100));
                state.addMessage(session, 'interviewer', `reply ${i}`);
              }
              const ctxBig = context.assembleContext(session);
              const ctx = context.assembleContext(session, {contextTokens: 2000});
              const firstTurn = ctx.find(m => m.role !== 'system');
              out.context = {
                systemBlocks: ctxBig.filter(m => m.role === 'system').length,
                hasLedger: ctxBig.some(m => m.content.includes('Design ledger')),
                hasTracker: ctxBig.some(m => m.content.includes('Step tracker')),
                hasArtifactFence: ctxBig.some(m => m.content.includes('```mermaid\\ngraph LR')),
                bigKeepsOldest: ctxBig.some(m => m.content.includes('filler message 0 ')),
                smallWindowKeepsLatest: ctx[ctx.length - 1].role,
                smallWindowTurns: ctx.filter(m => m.role !== 'system').length,
                smallWindowDropsArtifacts: !firstTurn.content.includes('artifact'),
              };
              out.tokens = context.estimateTokens('x'.repeat(400));
              out.summarization = context.summarizationNeeded(session, 2000);

              out.artifactIds = [a1.id, a2.id].every(id => /^a\\d+-\\d+$/.test(id));
              return out;
            }""")

            exp = {
                "newSession": {"state": "MENU", "ledgerKeys": "components,estimates,openThreads,revealedGuidance", "helpMode": "testing", "proactiveHints": False, "showTracker": True},
                "ledger": {"estimates": 1, "components": 1, "transcriptArtifacts": 2},
                "coverage": "1,3",
                "guidance": "1,0",
                "currentStep": 1,
                "prompt": {"messages": 1, "hasPersona": True, "hasVague": True, "hasHidden": True,
                           "hasEstimation": True, "hasTestingRefusal": True, "hasPinned": True,
                           "hasNoSolicit": True, "hasNoVolunteer": True},
                "promptLearning": True,
                "promptFreeChoice": True,
                "learningPassive": True,
                "learningDefaultNoPointer": True,
                "learningProactive": True,
                "briefingTurns": 2,
                "context": {"systemBlocks": 3, "hasLedger": True, "hasTracker": True,
                            "hasArtifactFence": True, "bigKeepsOldest": True,
                            "smallWindowKeepsLatest": "assistant", "smallWindowTurns": 6,
                            "smallWindowDropsArtifacts": True},
                "tokens": 100,
                "summarization": True,
                "artifactIds": True,
            }
            assert result == exp, f"unit mismatch:\n got {json.dumps(result, indent=1)}\n want {json.dumps(exp, indent=1)}"
            assert not errors, f"console/page errors: {errors}"
            browser.close()
        print("M1 UNITS: PASS (state, ledger, prompt blocks, context window)")
        return 0
    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
