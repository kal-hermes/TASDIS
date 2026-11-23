# 003 - Design and Plan for the System Design Interview Game

This document turns GOAL.md and the agreed decisions in 001 and 002 into a
concrete design and a phased build plan. Each milestone gets its own detailed
implementation plan at start time. This document stays at the level of
architecture, data schemas, prompts, and milestone scope.

## 1. Architecture overview

The game is a no-build static SPA: plain `index.html`, `js/`, `css/`, and JSON
data files, with every library vendored as a local file. No bundler, no
package registry, works offline except for the LLM calls. This matches the
host-side `http.server` plus Camofox verification topology we already use.

Key decisions carried over from 001 and 002:

- Browser-only LLM calls behind one provider interface. Bifrost stays a later
  escape hatch, and the interface keeps that swap cheap.
- Diagrams in Mermaid.js, calculations in LaTeX rendered by KaTeX.
- Image-editing feedback is dropped. Hand-drawn diagrams get transcribed to
  Mermaid by a vision model, and the user corrects the transcription before
  grading (phase 2).
- The canonical interview process is k_sze's five-step merge from 001 reply:
  (1) clarifying questions, (2) abstract design, (3) core components,
  (4) bottlenecks, (5) scaling.
- Source verification is phase 2 and needs a small fetch proxy.

## 2. Directory layout

```
system-design/game/
  index.html
  css/
    main.css
  js/
    app.js            entry point, screen routing
    state.js          session state machine and persistence
    engine.js         interviewer conversation loop, step tracker
    grader.js         end-of-interview grading pass
    providers.js      provider interface, adapters, mock provider
    settings.js       settings dialog, localStorage persistence
    render-latex.js   KaTeX wrapper
    render-mermaid.js Mermaid wrapper, diagram editor
    audio.js          gibberish blip synth (phase 2)
    i18n.js           UI strings (phase 2)
    vendor/           mermaid, katex, and their licenses
    prompts/          prompt template modules
    problems/         problem bank JSON files
  assets/             pixel art sprites and backgrounds
  tests/              Playwright drivers and fixtures
```

## 3. Data schemas

### 3.1 Problem bank entry (`js/problems/<slug>.json`)

- `id`, `title`: identity.
- `vague_prompt`: the one-liner the interviewer opens with, deliberately
  under-specified.
- `hidden_guidance`: constraints that the interviewer holds back until the
  user asks about them
  (expected DAU, read or write ratio, latency targets, consistency needs).
- `known_patterns`: the classic design this problem reduces to, used by the
  grader, never shown to the user.
- `common_misses`: the things candidates forget (TTL on the cache, shard key
  choice, queue for fanout), used by the grader.
- `constrained_variant`: optional pinned stack for constrained mode
  (for example "AWS, MySQL, RabbitMQ").

The bank starts with eight to ten classic problems: URL shortener, rate
limiter, news feed, chat, autocomplete, web crawler, unique ID generator, and
notification system. We write all entries ourselves, so there are no
licensing questions.

### 3.2 Settings (`localStorage`, editable in the settings dialog)

- Providers: for each of text, vision, and image roles, a provider id
  (`openai`, `anthropic`, `openai-compatible`), a base URL, a model name, and
  an API key. Keys live in localStorage and never leave the browser except in
  the Authorization header to the provider.
- Interview preferences: learning or testing mode, constrained or
  unconstrained, persona (phase 2), language (phase 2).

### 3.3 Session (localStorage, one active session)

- Transcript: ordered messages with speaker, text, and artifact references.
- Artifacts: calculations (LaTeX source plus rendering) and diagrams
  (Mermaid source), each tagged with the step it belongs to.
- Process state: which of the five steps the interviewer marked as
  covered, derived from interviewer messages.
- Grade: filled in by the grader pass at the end.

## 4. Game flow and state machine

States: `MENU`, `BRIEFING`, `INTERVIEW`, `GRADING`, `FEEDBACK`.

- `MENU`: pick a problem (or random), mode, and constraints. Then start.
- `BRIEFING`: the interviewer opens with `vague_prompt` in character.
- `INTERVIEW`: free-form chat. The engine tags interviewer messages with the
  step they belong to and drives the step tracker. The user submits
  calculations and diagrams through the submission panel, and the
  interviewer responds to each submission in the same channel.
- `GRADING`: a separate grader call over the full transcript and artifacts.
- `FEEDBACK`: score, failing diagnostic rows, missed items, and per-artifact
  comments, plus the interviewer's in-character closing.

The user can reopen earlier steps. The tracker records coverage, not order.
The tracker shows all five steps covered, and the user confirms. The engine
then ends the interview. The user can also ask to finish early.

## 5. Interviewer prompt design

The system prompt assembles from blocks, in this order:

1. Persona and style block (MVP: normal tech interviewer).
2. Problem block: `vague_prompt`, plus `hidden_guidance` marked as
   reveal-on-question.
3. Process block: the five steps, instruction to tag each turn, and
   instruction to demand numbers rather than accept hand-waving.
4. Estimation reference block: the latency and throughput table from the
   `system-design` skill, so the interviewer grades against real numbers
   instead of its own memory. This directly addresses grader hallucination.
5. Mode block: learning mode help ladder (hint, then explanation, then
   walkthrough, only on request) or testing mode refusal rule.
6. Constraint block: pinned stack in constrained mode, free choice otherwise.

The interviewer reads diagrams and calculations from rendered artifact
blocks, and it marks up diagrams by emitting a corrected or commented
Mermaid source block.

## 6. Grading design

The grader is a separate call with a different system prompt, fed the whole
transcript, all artifacts, `known_patterns`, and `common_misses`. It never
sees the conversation live, so it grades the record, not its own memory of
playing interviewer.

Rubric output:

- Process score: coverage of the five steps, revisits allowed.
- Design score: the eight-row diagnostic from the `system-design` skill,
  one pass or fail per row with the specific fix for each failing row.
- Estimation realism: every claimed number gets an order-of-magnitude
  judgment against the reference table. Exact-figure pedantry is out of
  scope by agreement in 002. Source citation support lands in phase 2.
- Missing list: `common_misses` items never addressed.

Final score is 0 to 10, derived from the diagnostic row count, matching the
skill's scoring rule. Feedback shows the score, each failing row with its
fix, the missing list, and per-artifact comments.

## 7. Rendering and submission panel

One submission panel with three tabs: LaTeX (textarea plus live KaTeX
preview), Mermaid (textarea plus live rendered preview), and prose. The
panel inserts the artifact into the chat as a message. Phase 2 adds an
image tab. That tab sends the picture to the vision model and shows the
Mermaid transcription. The user corrects the transcription before
submission.

## 8. Provider layer

One interface: `complete(role, messages, options)`, where role is `text` or
`vision`. Adapters: OpenAI-compatible (covers OpenAI and any compatible
endpoint), Anthropic, and a mock provider that returns scripted replies for
offline tests. OpenAI calls set the browser-access flag, and Anthropic calls
set its direct-browser-access flag. CORS failures surface as a clear error
message naming the provider, per 002.

## 9. Verification approach

Per the SPA workflow: vendor every library, version every asset URL with
`?v=N`, and bump the version on every edit. Drive the real DOM in headless
Chromium for behavior, and keep console and pageerror capture on in every
run. The mock provider makes engine, state, and grader parsing tests
deterministic with
no network. Container-local `http.server` serves the Playwright runs. The
host-side server stays available for Camofox sessions on request.

## 10. Milestones

Each milestone ends verified in the browser and committed before the next
starts. Detailed task-level plans come as separate numbered documents at
milestone start.

### M0 - Scaffold and settings

- Scaffold the layout in section 2, `index.html` with versioned asset URLs,
  and a boot screen.
- Settings dialog with provider rows for the three roles, localStorage
  persistence, and a "test connection" button per provider.
- Mock provider and the first Playwright smoke run (page loads, settings
  save, mock reply renders).

### M1 - Core interview loop

- Problem bank loader and problem picker screen.
- Interviewer prompt assembly from the section 5 blocks.
- Chat UI with streaming, step tracker sidebar, submission panel with LaTeX
  and Mermaid tabs and live previews.
- Learning and testing mode behavior, constrained and unconstrained mode.
- Session persistence and resume after reload.

### M2 - Grading and feedback

- Grader prompt and output parsing (strict JSON output from the grader).
- FEEDBACK screen: score, diagnostic rows, missing list, artifact comments.
- In-character interviewer closing message.

### M3 - MVP polish

- Error handling: CORS failures, provider errors, malformed grader output
  with one retry.
- Interview transcript export (Markdown download).
- A full self-play test: mock-scripted interview runs end to end from MENU
  to FEEDBACK with zero console errors.

### M4 - Personas, art, and sound (phase 2)

- Pixel art interviewer sprite, background per persona, and the four
  personas from GOAL.md as prompt persona blocks.
- Gibberish Web Audio blip synth with per-persona timbre (section 8 of 002).

### M5 - Vision, i18n, source verification (phase 2)

- Image submission tab with transcription confirmation loop.
- Six UI locales and interviewer language as a prompt parameter.
- Fetch proxy for cited-source verification, with dual grading per 002.

## 11. Open questions

- The game needs a name. Every later doc and the repo want one.
- Deployment target after MVP: GitHub Pages works for the static parts, and
  the phase 2 fetch proxy then needs somewhere to run.
- MVP ship bar: M0 through M3 is the full loop. Decide after M2 whether M3
  polish blocks a first playable session for you.
