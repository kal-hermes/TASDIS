# PLAN - Totally Accurate System Design Interview Simulator

This document is the authoritative build plan. It is self-contained: an
implementer needs no other conversation history to execute it. Read
`DESIGN.md` in this directory first. It holds the architecture, data schemas,
prompt design, and settled decisions D1 to D12.

Goal: build the MVP (milestones M0 to M3) of the system design interview
simulation game, then phase 2 (M4 to M5).

## Ground rules for the implementer

- Stack: no-build static SPA per DESIGN.md section 3. No bundler, no npm,
  every library vendored with its license.
- Version every asset URL as `?v=N` in `index.html` and bump on every edit,
  including ES module sub-imports. A stale cached asset looks exactly like a
  fix that did not work.
- Work milestone by milestone. Commit after each verified task with
  descriptive messages, using the environment default git identity. Never
  pass `-c user.name` or `-c user.email` overrides.
- Verify behavior in headless Chromium through container-side Playwright
  (`uv run --with playwright python <script>.py`) against a container-local
  `python3 -m http.server <port> --bind 127.0.0.1` in the game directory.
  Capture console and pageerror events in every run.
- The mock provider (DESIGN.md section 10) must exist before any real
  provider test, so the loop, state machine, and grader parsing tests run
  offline and deterministically.
- The user can also serve host-side for Camofox sessions on request. The
  container's localhost is not reachable from Camofox, so only host-side
  serving works there.
- Write a task-level implementation plan for the current milestone before
  coding it, then work the tasks in order with tests first where practical.

## M0 - Scaffold, settings, provider layer

Objective: a loading page with a working settings dialog and a provider
layer proven by a mock provider round trip.

Tasks:

1. Scaffold the directory layout from DESIGN.md section 4, `index.html` with
   versioned asset URLs, and a boot screen that routes to placeholder
   screens.
2. Vendor Mermaid and KaTeX plus licenses into `js/vendor/`.
3. Settings dialog: provider rows for `text`, `vision`, and `image` roles,
   each with provider id, base URL, model, API key, and a test connection
   button. Persist to localStorage.
4. Provider layer: `complete(role, messages, options)` with `openai`,
   `anthropic`, `openai-compatible`, and `mock` adapters. OpenAI adapter
   sets its browser-access flag, Anthropic adapter sets its direct-browser
   access flag. CORS failures produce a clear error naming the provider.
5. Mock provider returns scripted replies from a JSON script file.
6. Playwright smoke test: page loads with zero console errors, settings
   save and reload from localStorage, a mock reply renders in a placeholder
   chat view.

Acceptance: smoke test passes, a page reload preserves settings, and the
test connection button reports success against the mock provider.

## M1 - Core interview loop

Objective: a playable interview from problem pick to in-character chat with
artifacts and a step tracker.

Tasks:

1. Problem bank: JSON schema per DESIGN.md section 5.1, loader, and the
   first eight problem files (URL shortener, rate limiter, news feed, chat,
   autocomplete, web crawler, unique ID generator, notification system).
2. Problem picker screen on `MENU`.
3. Prompt assembly module: the six blocks from DESIGN.md section 7,
   including the estimation reference numbers embedded from the
   `system-design` skill reference table.
4. Interviewer engine: conversation loop with streaming, in-character
   replies, step tagging of interviewer turns, and the step tracker sidebar
   (coverage, not order).
5. Learning mode help ladder and testing mode refusal behavior.
6. Constrained mode pinned stack from `constrained_variant`, and
   unconstrained free choice.
7. Submission panel: LaTeX tab with live KaTeX preview, Mermaid tab with
   live rendered preview, and prose tab. Submission inserts the artifact
   into the chat, tagged with the current step.
8. Session persistence: transcript, artifacts, ledger, timer state, and
   process state to localStorage, with resume after reload.
9. Design ledger per DESIGN.md section 5.4: structure, deterministic
   updates from artifact submissions, and storage in the session record.
   The interviewer marks a revealed hidden-guidance item with the control
   line `[[guidance: N]]`. The game records the item (DESIGN.md section 7).
10. Context assembly per DESIGN.md section 7.1: layered assembly with the
    recency window. The summarization trigger itself lands in M3.
11. Optional timer per DESIGN.md section 6: setup at `MENU`, off by
    default, with presets. The HUD shows a countdown with a late-game
    color change. The clock ticks only while the send button is enabled,
    persists as `remaining_ms`, and expiry runs the wrap-up into
    `GRADING`.
12. Playwright tests with the mock provider: briefing message renders, a
    scripted multi-turn interview advances the step tracker, an artifact
    submission appears in the chat, and a reload resumes the session. The
    clock pauses while a mock reply streams. Expiry auto-transitions to
    `GRADING` through the wrap-up. A reload preserves `remaining_ms`.

Acceptance: a scripted end-to-end interview runs from `MENU` through all
five steps to interview close with zero console errors. A mid-interview
reload resumes without losing messages. With the timer on, a reload
preserves the remaining time.

## M2 - Grading and feedback

Objective: an end-of-interview grade with structured feedback.

Tasks:

1. Grader prompt: separate system prompt per DESIGN.md section 9, fed
   transcript, design ledger, artifacts, `known_patterns`, and
   `common_misses`. The texts of the revealed hidden guidance items were
   added later (`hidden_guidance_revealed`, `plans/m3-plan.md` item 8.5).
   Process comes from the transcript, and the solution
   comes from the ledger plus artifacts.
2. Strict JSON grader output: process coverage, eight diagnostic rows with
   pass or fail and a fix each, realism judgments per claimed number,
   missing list, per-artifact comments. Parser retries once on malformed
   output.
3. `GRADING` and `FEEDBACK` states: score 0 to 10 by
   `round(passed / 8 x 10)`, failing rows with fixes, missing list,
   artifact comments, and the interviewer's in-character closing message.
4. Mid-interview grading per DESIGN.md section 9.1: request button in
   `INTERVIEW`, learning mode only. The grader runs with the mid-interview
   prompt variant and returns progress-shaped output with no final score.
   Results accumulate in the snapshot history, and the button carries a
   token cost note. Testing mode refuses the request.
5. Parser retries once on malformed grader output.
6. Playwright tests with the mock provider: a scripted full interview ends
   in a parsed grade, and the feedback screen renders every section. A
   malformed grader reply triggers exactly one retry. A mid-interview
   grading request returns a progress report, stores a snapshot, and
   appends nothing to the interviewer's message list.

Acceptance: `MENU` to `FEEDBACK` runs end to end on mock scripts with zero
console errors.

Decision point: after M2 the owner plays a real session against a real
provider and decides whether M3 polish blocks the first playable release.

## M3 - MVP polish

Objective: robustness fit for real providers and real users.

Tasks:

1. Error handling: provider failures, CORS errors, and network timeouts
   surface as readable messages with a retry path. Malformed grader output
   retries once, then shows a plain error without losing the session.
2. How-to-play section reachable from `MENU` and from the settings dialog.
   The game also opens it at each load, at its top. Its box, "Do not show
   automatically in the future", stops that at the next load (section 8 of
   `plans/m3-plan.md`). The last row of the section stays visible while the
   text scrolls.
   Provider setup: the text model runs the interviewer and the grader, so
   it is the one required row. The vision and image rows stay unused until
   phase 2. M5 adds vision transcription, and the image role is reserved.
   It explains each menu toggle. Help mode: learning gives hints on
   request, testing gives no help and hides the step tracker.
   Constraints: free choice versus a pinned stack. Proactive guidance is
   learning mode only and off by default. Also covered: the optional
   timer, the submission panel (LaTeX, Mermaid, prose), the step tracker
   toggle, and mid-interview progress grading. It states that API keys
   live in this browser's localStorage and go only to the provider.
3. Transcript export to a Markdown download.
4. Context compression per DESIGN.md section 7.1: the character estimate
   crossing the threshold runs the summarization call, distills older turns
   into the ledger, and drops them from later assemblies. Test with a long
   mock script and a small fake context limit.
5. Full self-play test: mock-scripted interview from `MENU` to `FEEDBACK`
   with zero console errors, plus a run of the same script with injected
   provider failures.
6. GitHub Pages deployment of the static build, and a live verification of
   the published URL.

Acceptance: error paths verified in the browser. The how-to-play section
covers every provider row and every menu toggle. Until its box is ticked,
it opens at each load, at its top. Export produces valid
Markdown. The GitHub Pages URL loads and plays with the user's real API
key.

## M4 - Personas, art, and sound (phase 2)

Objective: the four personas from DESIGN.md section 11 with art and voice.

Tasks:

1. Pixel art sprite and background per persona in the 8-bit or 16-bit
   style, animated. The Klingon and Vulcan wear captain or commander
   uniforms, the pirate is a pirate ship captain, and all three must look
   like people in command.
2. Persona prompt blocks with matching speech style per persona.
3. UI theme pass: restyle every screen with one consistent 8-bit or 16-bit
   console pixel art theme. Vendor a pixel webfont with its license for
   Latin text. Style the buttons, inputs, panels, chat log, step tracker,
   and timer HUD with that theme: chunky borders, hard shadows, and one
   palette that matches the persona art. If no suitable pixel font exists
   for Chinese or Japanese, those locales use a normal sans-serif font
   instead.
4. Gibberish blip synth in `audio.js` per DESIGN.md section 11: blip per
   syllable, persona timbre, subtitle sync, with a mute toggle.
5. Persona selection on `MENU`, persisted in settings.
6. Playwright tests: persona switch changes prompt block, sprite,
   background, and theme palette, and the audio engine drives without
   errors (muted asserts only, headless audio has no output device).

## M5 - Vision, i18n, source verification (phase 2)

Objective: the remaining GOAL features.

Tasks:

1. Image submission tab: upload, vision-model Mermaid transcription,
   user correction step, then submission (DESIGN.md section 8).
2. Six UI locales and locale files per DESIGN.md section 12, with a
   language picker persisted in settings, and interviewer language as a
   prompt parameter.
3. VPS fetch proxy for cited-source verification (DESIGN.md section 13),
   dual grading in the grader prompt, and source-class weighting in
   feedback.
4. Playwright tests: image tab transcription loop, locale switch covering
   every translated key, and dual judgment appearing in feedback for a
   cited claim.

## Environment notes

- The game is the repository `kal-hermes/TASDIS`, which is the submodule
  `TASDIS/` of `games`. Game source lives at
  `/workspace/projects/games/TASDIS/game/`.
- The `system-design` skill (rubric, diagnostic rows, estimation numbers)
  is at `/workspace/projects/games/.hermes/skills/system-design/`. Read
  `references/estimation-numbers.md` for the table embedded into prompt
  block 4.
- Serve only over a local `http.server` during development. API keys are
  the user's own and live in their browser localStorage only.
