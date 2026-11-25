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
              const state = await import('./js/state.js?v=34');
              const context = await import('./js/context.js?v=34');
              const assemble = await import('./js/prompts/assemble.js?v=34');
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
                hasStepJobs: prompt[0].content.includes('4: name bottlenecks'),
                hasDirecting: prompt[0].content.includes("do not open a later step's material early"),
                hasDrillRule: prompt[0].content.includes('only in step 4'),
                hasClosedWorld: /the ONLY requirements of\s+this interview/.test(prompt[0].content),
                hasNoInvent: /assume\s+anything reasonable/.test(prompt[0].content),
                hasEmitDiscipline: prompt[0].content.includes('MUST end with that item'),
                hasTrackerTruth: prompt[0].content.includes('Keep the tracker truthful'),
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

              // ---- interviewer brief: validation, block, gates, probe lines
              const briefMod = await import('./js/prompts/brief.js?v=34');
              const engineMod = await import('./js/engine.js?v=34');
              const pack = await (await fetch('./js/problems/url-shortener.json?v=34')).json();
              out.briefValidates = (() => {
                try { briefMod.validateBrief(pack); return true; } catch (e) { return 'threw: ' + e.message; }
              })();
              const briefErr = (mut) => {
                const p = JSON.parse(JSON.stringify(pack));
                mut(p);
                try { briefMod.validateBrief(p); return 'no-throw'; } catch (e) { return e.message; }
              };
              out.briefGistErr = briefErr((p) => { p.interviewer_brief.gist = '   '; });
              out.briefDimsErr = briefErr((p) => { delete p.interviewer_brief.dimensions['5']; });
              out.briefAnchorsErr = briefErr((p) => { delete p.interviewer_brief.anchors['6']; });
              out.briefProbesErr = briefErr((p) => { p.interviewer_brief.probes = p.interviewer_brief.probes.slice(0, 5); });
              out.briefProbeStepErr = briefErr((p) => { p.interviewer_brief.probes[0].step = 6; });
              out.briefProbeQErr = briefErr((p) => { p.interviewer_brief.probes[0].q = '  '; });

              const bargs = (over) => Object.assign(
                { problem: pack, currentStep: 4, revealed: [2], helpMode: 'learning',
                  probeCap: 2, probesAsked: 0 }, over);
              const b4 = briefMod.briefBlock(bargs({}));
              out.briefBlock = {
                hasGist: b4.includes('read-heavy key-value service'),
                hasStepDim: b4.includes('Hot key: one viral link'),
                noOtherStepDim: !b4.includes('Geo: serving redirects'),
                hidesRevealedAnchor: !b4.includes('Hearing the imbalance'),
                keepsUnrevealedAnchor: b4.includes('Hearing the target'),
                hasProbeRule: b4.includes('[[probe: N]]'),
                hasProbes: b4.includes('viral on live television'),
                hasBudget: b4.includes('at most 2 more'),
              };
              out.briefGates = {
                capZero: !briefMod.briefBlock(bargs({probeCap: 0})).includes('viral on live television'),
                testing: !briefMod.briefBlock(bargs({helpMode: 'testing'})).includes('viral on live television'),
                usedUp: briefMod.briefBlock(bargs({probesAsked: 2})).includes('used up'),
                noBrief: briefMod.briefBlock(bargs({problem: {id: 'x'}})) === '',
              };
              const withBrief = assemble.assembleInterviewerPrompt(Object.assign(
                bargs({}), { constraintMode: 'unconstrained' }));
              out.promptBrief = withBrief[0].content.includes('Interviewer brief');
              out.promptNoBrief = !assemble.assembleInterviewerPrompt(
                {problem, helpMode: 'learning', constraintMode: 'unconstrained'})[0].content
                .includes('Interviewer brief');

              const parsedProbe = engineMod.parseControlLines(
                'A viral link. [[step: 4]]\\n[[probe: 5]]\\n[[probe: 5]]');
              out.probeLines = {
                probes: parsedProbe.probes.join(','),
                stripped: !parsedProbe.clean.includes('[[probe'),
                step: parsedProbe.step,
              };
              const ps = state.newSession(pack, {helpMode: 'learning'});
              ps.currentStep = 4;
              state.countProbe(ps, 5);
              state.countProbe(ps, 0);
              state.countProbe(ps, 99);
              state.countProbe(ps, 5);
              out.probeCount = JSON.stringify(ps.probesUsed);

              // every bank problem carries a valid prep pack on the
              // template floor: five dimensions, one anchor per hidden
              // item, at least six probes
              const bankSlugs = ['url-shortener', 'rate-limiter', 'news-feed',
                'chat', 'autocomplete', 'web-crawler', 'unique-id-generator',
                'notification-system'];
              const packs = {};
              const packErrs = {};
              for (const slug of bankSlugs) {
                const resp = await fetch(`./js/problems/${slug}.json?v=34`);
                const pb = await resp.json();
                const brief = pb.interviewer_brief;
                let valid = false;
                let err = '';
                try {
                  briefMod.validateBrief(pb);
                  valid = true;
                } catch (e) {
                  err = String(e.message);
                }
                const floor = !!brief && valid
                  && Object.keys(brief.dimensions || {}).length === 5
                  && Object.keys(brief.anchors || {}).length === 6
                  && (brief.probes || []).length >= 6;
                packs[slug] = floor;
                if (!floor) packErrs[slug] = err || 'below the floor';
              }
              out.packs = packs;
              out.packErrs = packErrs;

              // one turn = prose, $$latex$$, and ```mermaid fences in any
              // combination; parseTurn splits it into ordered segments
              const tp = await import('./js/turn-parse.js?v=34');
              const p1 = tp.parseTurn('Just a plain answer.');
              const p2 = tp.parseTurn('The answer:\\n$$Q = 100 \\cdot 86400$$\\nThat is the rate.');
              const p3 = tp.parseTurn('Sketch:\\n```mermaid\\ngraph LR\\nA-->B\\n```\\nIt flows.');
              const p4 = tp.parseTurn('$$x^2$$');
              const p5 = tp.parseTurn('```mermaid\\ngraph TD\\nB-->A\\n```');
              const p6 = tp.parseTurn('Intro\\n```mermaid\\ngraph LR\\nA-->B\\n```\\nMid\\n$$y = 2x$$\\nOut');
              const p7 = tp.parseTurn('```mermaid\\ngraph LR\\nA-->B');
              const p8 = tp.parseTurn('The value $$x^2 is big');
              const p9 = tp.parseTurn('   \\n  ');
              const types = (r) => JSON.stringify(r.segments.map((s) => s.type));
              out.turnParse = {
                proseOnly: types(p1) === '["prose"]' && p1.segments[0].text === 'Just a plain answer.',
                prosePlusLatex: types(p2) === '["prose","latex","prose"]',
                latexSource: p2.segments[1].source === 'Q = 100 \\cdot 86400',
                prosePlusMermaid: types(p3) === '["prose","mermaid","prose"]',
                mermaidSource: p3.segments[1].source === 'graph LR\\nA-->B',
                latexOnly: types(p4) === '["latex"]',
                mermaidOnly: types(p5) === '["mermaid"]',
                orderKept: types(p6) === '["prose","mermaid","prose","latex","prose"]',
                unclosedFenceProse: types(p7) === '["prose"]',
                unbalancedDollarProse: types(p8) === '["prose"]',
                blank: p9.segments.length === 0,
              };

              // the thinking-effort setting maps to request parameters in
              // game code (DESIGN.md 5.2): reasoning_effort for OpenAI-style
              // calls, a thinking budget for Anthropic-style calls, nothing
              // for the mock
              const prov = await import('./js/providers.js?v=34');
              const tp2 = (cfg) => prov.thinkingParams(cfg);
              // off = reasoning disabled (none), default = omit the field
              // (provider picks; defaults are model-dependent). Ladder
              // values pass through verbatim on OpenAI-style calls and map
              // to budgets on Anthropic-style calls.
              out.thinking = {
                mockAll: ['off', 'default', 'minimal', 'low', 'medium', 'high',
                  'xhigh', 'max', 'ultra', '']
                    .every((e) => JSON.stringify(
                      tp2({ provider: 'mock', thinkingEffort: e })) === '{}'),
                openaiNone: JSON.stringify(tp2({ provider: 'openai', thinkingEffort: 'off' }))
                  === JSON.stringify({ reasoning_effort: 'none' }),
                openaiDefault: JSON.stringify(tp2({ provider: 'openai', thinkingEffort: 'default' })) === '{}',
                openaiBlank: JSON.stringify(tp2({ provider: 'openai', thinkingEffort: '' })) === '{}',
                openaiLadder: ['minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra']
                  .every((e) => JSON.stringify(tp2({ provider: 'openai', thinkingEffort: e }))
                    === JSON.stringify({ reasoning_effort: e })),
                openaiCompatPass: JSON.stringify(tp2({ provider: 'openai-compatible', thinkingEffort: 'xhigh' }))
                  === JSON.stringify({ reasoning_effort: 'xhigh' }),
                anthropicOff: JSON.stringify(tp2({ provider: 'anthropic', thinkingEffort: 'off' })) === '{}',
                anthropicDefault: JSON.stringify(tp2({ provider: 'anthropic', thinkingEffort: 'default' })) === '{}',
                anthropicBlank: JSON.stringify(tp2({ provider: 'anthropic', thinkingEffort: '' })) === '{}',
                anthropicLadder: ['minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra']
                  .every((e) => {
                    const got = tp2({ provider: 'anthropic', thinkingEffort: e });
                    const want = { minimal: 1024, low: 2048, medium: 8192, high: 16384,
                      xhigh: 32768, max: 65536, ultra: 131072 }[e];
                    return got.thinking
                      && got.thinking.type === 'enabled'
                      && got.thinking.budget_tokens === want
                      && got.max_tokens === want + 1024;
                  }),
              };

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
                anchorInstruction: ctxBig.some(m => m.content.includes('later step waits for its step')),
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
                "guidance": "1",
                "currentStep": 1,
                "prompt": {"messages": 1, "hasPersona": True, "hasVague": True, "hasHidden": True,
                           "hasEstimation": True, "hasTestingRefusal": True, "hasPinned": True,
                           "hasNoSolicit": True, "hasNoVolunteer": True,
                           "hasStepJobs": True, "hasDirecting": True, "hasDrillRule": True,
                           "hasClosedWorld": True, "hasNoInvent": True,
                           "hasEmitDiscipline": True, "hasTrackerTruth": True},
                "promptLearning": True,
                "promptFreeChoice": True,
                "learningPassive": True,
                "learningDefaultNoPointer": True,
                "learningProactive": True,
                "briefValidates": True,
                "briefGistErr": "problem url-shortener: interviewer_brief gist needs text",
                "briefDimsErr": "problem url-shortener: interviewer_brief dimensions needs keys 1 to 5",
                "briefAnchorsErr": "problem url-shortener: interviewer_brief anchors needs one entry per hidden item",
                "briefProbesErr": "problem url-shortener: interviewer_brief needs at least 6 probes (template floor)",
                "briefProbeStepErr": "problem url-shortener: interviewer_brief probe 1 needs step 1 to 5",
                "briefProbeQErr": "problem url-shortener: interviewer_brief probe 1 needs text",
                "briefBlock": {"hasGist": True, "hasStepDim": True, "noOtherStepDim": True,
                               "hidesRevealedAnchor": True, "keepsUnrevealedAnchor": True,
                               "hasProbeRule": True, "hasProbes": True, "hasBudget": True},
                "briefGates": {"capZero": True, "testing": True, "usedUp": True, "noBrief": True},
                "promptBrief": True,
                "promptNoBrief": True,
                "probeLines": {"probes": "5,5", "stripped": True, "step": 4},
                "probeCount": '{"4":2}',
                "packs": {"url-shortener": True, "rate-limiter": True,
                          "news-feed": True, "chat": True, "autocomplete": True,
                          "web-crawler": True, "unique-id-generator": True,
                          "notification-system": True},
                "packErrs": {},
                "thinking": {"mockAll": True, "openaiNone": True,
                             "openaiDefault": True, "openaiBlank": True,
                             "openaiLadder": True, "openaiCompatPass": True,
                             "anthropicOff": True, "anthropicDefault": True,
                             "anthropicBlank": True, "anthropicLadder": True},
                "turnParse": {"proseOnly": True, "prosePlusLatex": True,
                              "latexSource": True, "prosePlusMermaid": True,
                              "mermaidSource": True, "latexOnly": True,
                              "mermaidOnly": True, "orderKept": True,
                              "unclosedFenceProse": True,
                              "unbalancedDollarProse": True, "blank": True},
                "briefingTurns": 2,
                "context": {"systemBlocks": 3, "hasLedger": True, "hasTracker": True,
                            "anchorInstruction": True,
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
