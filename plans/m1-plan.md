# M1 implementation plan - core interview loop

Objective per PLAN.md: a playable interview from problem pick to in-character
chat with artifacts and a step tracker.

## Module map (new files unless noted)

- `js/problems/*.json` (8 problems) + `js/problems.js` loader.
- `js/prompts/estimation.js`: estimation reference table as a module string.
- `js/prompts/assemble.js`: six prompt blocks per DESIGN.md 7. returns
  system messages. Inputs: problem, settings (mode, constraints), persona.
- `js/state.js`: session record per DESIGN.md 5.3/5.4 in
  localStorage `tadsdi.session.v1`. create/start/append/step coverage/
  ledger updates/artifacts. save after each mutation.
- `js/context.js`: assembly per 7.1: system blocks + ledger + artifacts +
  step state verbatim, recency window of turns, token estimate chars/4;
  summarization trigger stub (inert until M3).
- `js/providers.js` (edit) - add `completeStream(role, messages, onChunk,
  options)`. openai + openai-compatible SSE, anthropic SSE, mock word-chunked
  delay. mock reads an `interview` sequence with per-reply `covered` step
  data from mock-script.json.
- `js/engine.js`: BRIEFING and INTERVIEW loop: send turn, streaming reveal,
  step tag parsing (`[[step: n]]`, `[[covered: n]]` control lines stripped
  from display), help ladder detection (learning: purpose hint ladder;
  testing: refusal), timer (ticks only while send enabled, persists
  remaining_ms, expiry wraps up into GRADING).
- `js/render-latex.js`, `js/render-mermaid.js`: KaTeX/Mermaid wrappers.
- `js/submission.js`: three tabs, live previews, inserts artifact message
  tagged with the current step. deterministic ledger updates.
- `js/app.js`, `index.html` (edit) - MENU picker (problem list, random,
  learning/testing, constrained/unconstrained, timer presets), interview
  screen with tracker sidebar + submission panel + timer HUD.
- `tests/m1_e2e.py`, `tests/m1_units.py`: Playwright + node-less module
  checks driven through the browser.

## Task order

1. Plan + delegation of problem bank (this file. problems via subagent).
2. estimation.js + assemble.js (pure functions. check in browser console).
3. providers.js streaming + mock interview script (offline deterministic).
4. state.js session + ledger (unit-checked through browser evaluate).
5. engine.js loop + tracker + ladder + timer (mock-driven).
6. render wrappers + submission panel + UI wiring.
7. context.js recency assembly wired into engine.
8. tests: m1 units then e2e. fix until green. bump ?v= on every edit.

## Key contracts

- Step control lines: interviewer replies may contain `[[step: N]]` (current
  step) and `[[covered: N]]` (mark covered). Engine strips them from display
  text and updates coverage (coverage, not order).
- Ledger: artifact submission appends `{artifactId, step, kind, status:
  'proposed'}` to the matching ledger section. prose extraction lands in M2.
- Timer: `remaining_ms` in session. tick only while candidate turn active;
  expiry fires between turns. wrap-up then GRADING (placeholder until M2).
- GRADING and FEEDBACK screens stay placeholders in M1. interview end marks
  the session `ended` and shows the GRADING placeholder.

## Verification

- m1_e2e.py: menu -> briefing renders -> scripted turns advance all five
  steps -> artifact submission appears in chat -> reload resumes transcript
  and remaining_ms -> expiry auto-transitions to GRADING placeholder. zero
  console errors. assert localStorage side effects, not just UI.
- All assets versioned `?v=N`. bumps on every edit.
