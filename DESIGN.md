# DESIGN - Totally Accurate System Design Interview Simulator

This document is the authoritative design for the game. It is self-contained:
an implementer needs no other conversation history to build from it. The
build sequence lives in `PLAN.md` in this directory.

## 1. Purpose and scope

The game simulates a system design job interview. An LLM plays the
interviewer, and the user plays the candidate. The interviewer picks a problem
from a problem bank and states it in vague terms. The user then asks
clarifying questions, estimates, draws diagrams, and walks through a design.
At the end, a grader pass scores the work and gives feedback.

The canonical interview process is this five-step merge of the System Design
Primer and Hired in Tech processes:

1. Ask questions to understand constraints and use cases.
2. Produce an abstract, high-level design.
3. Design the core components.
4. Identify bottlenecks.
5. Scale the design.

Revisiting steps is normal iterative engineering, so the game tracks step
coverage, not step order.

### MVP scope (milestones M0 to M3 in PLAN.md)

- Text chat interview loop with a step tracker.
- Problem bank with eight to ten classic problems.
- Calculations submitted as LaTeX, rendered with KaTeX, or as prose.
- Diagrams submitted as Mermaid.js source, rendered live, or as prose.
- Learning mode (hints on request) and testing mode (no help).
- Constrained mode (pinned stack) and unconstrained mode.
- Settings dialog for LLM providers, models, and API keys.
- A how-to-play section covering provider setup (one required text model,
  vision and image rows reserved for phase 2), the menu toggles, and key
  storage. It lands in M3. Until the player ticks its box, "Do not show
  automatically in the future", the game opens the section at each load.
- End-of-interview grading with a 0 to 10 score and structured feedback.
- One normal tech interviewer persona.

### Phase 2 scope (milestones M4 and M5 in PLAN.md)

- Five personas with distinct art, backgrounds, speech style, and gibberish
  voice. The personas are: a Klingon captain or commander, a Vulcan captain
  or commander, a pirate ship captain, a Texan ranch owner, and a normal
  tech interviewer. All three fictional personas wear command authority on
  their sleeve: uniform, bearing, and voice of someone in charge.
- Handwritten calculations and hand-drawn diagrams as image uploads, with a
  vision-model transcription the user corrects before submission.
- Gibberish speech synthesis through the Web Audio API.
- UI localization in six locales: English, French, Japanese, Simplified
  Chinese (Putonghua), Traditional Chinese (Cantonese written form), and
  Traditional Chinese (Taiwanese Mandarin). Interviewer dialogue language is
  a prompt parameter, so all locales work without recorded speech.
- Cited-source verification through a small fetch proxy hosted on the
  owner's VPS.

### Explicitly dropped

Image-editing feedback on uploaded pictures is dropped. Models annotate
pictures badly. Diagram feedback happens in Mermaid source or prose instead.

## 2. Decision record

These decisions are settled. Do not reopen them without new information.

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | No-build static SPA, all libraries vendored | Works offline, matches the host-side `http.server` plus browser verification workflow, no package registry dependency |
| D2 | Browser-only LLM calls behind one provider interface | No server for MVP. One interface keeps a later Bifrost router swap cheap |
| D3 | Mermaid.js for diagrams | Text form is natively readable by LLMs and renders in the browser |
| D4 | LaTeX (KaTeX) for calculations | All major LLMs read LaTeX reliably, KaTeX renders in the browser |
| D5 | Five-step process above, coverage not order | Owner's merge of two known processes, agreed in the 004 exchange |
| D6 | Grader is a separate call over the transcript | Grades the record, not the interviewer's live memory |
| D7 | Estimation realism judged by order of magnitude | Vendor throughput numbers change over time, exact-figure rubrics rot |
| D8 | Problem bank written by us, classic problems only | No licensing questions |
| D9 | API keys in localStorage, never sent anywhere but the provider | GitHub Pages first, no backend for MVP |
| D10 | Deployment target is GitHub Pages | Static app. The phase 2 fetch proxy goes on the owner's VPS |
| D11 | Game name is fixed | "Totally Accurate System Design Interview Simulator", tongue-in-cheek by intent |
| D12 | MVP ship bar decided after M2 | Owner reviews a playable loop before polish work |

## 3. Architecture overview

The app is a static SPA: `index.html`, `js/`, `css/`, and JSON data files,
served by any static file server. Every library is vendored as a local file
with its license. There is no bundler and no server-side code in MVP.

All LLM traffic goes through one provider module. Three provider roles exist:
`text` (interviewer and grader), `vision` (phase 2 transcription), and
`image` (reserved, unused in MVP). A mock provider returns scripted replies
so tests run offline.

The UI has five screens driven by a session state machine: menu, briefing,
interview, grading, and feedback. A sidebar shows the five-step tracker. The
candidate types each whole turn into one multi-line input. A turn mixes
prose with LaTeX blocks in `$$dollars$$`. A turn can also carry Mermaid
blocks in fenced code, in any order. The game turns each block into an
artifact and keeps the prose as chat messages.

## 4. Directory layout

```
game/
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
  assets/             pixel art sprites and backgrounds (phase 2)
  tests/              Playwright drivers and fixtures
```

Version every asset URL in `index.html` as `js/app.js?v=N` from day one.
Bump the version on every edit of that file, including ES module sub-imports.

## 5. Data schemas

### 5.1 Problem bank entry (`js/problems/<slug>.json`)

- `id`, `title`: identity.
- `vague_prompt`: the one-liner the interviewer opens with, deliberately
  under-specified.
- `hidden_guidance`: constraints that the interviewer holds back until the
  user asks about them. Examples: expected DAU, read or write ratio, latency
  targets, consistency needs.
- `known_patterns`: the classic design this problem reduces to. Used by the
  grader, never shown to the user.
- `common_misses`: things candidates forget, such as cache TTL, shard key
  choice, or a queue for fanout. Used by the grader.
- `constrained_variant`: optional pinned stack for constrained mode, for
  example "AWS, MySQL, RabbitMQ".
- `interviewer_brief`: optional author-time prep pack for the interviewer
  (section 7). Shape: `gist` (one framing paragraph). `dimensions` (keys 1
  to 5, one list per step). `anchors` (one entry per `hidden_guidance`
  item, phrased as what hearing it sounds like). `probes` (at least six,
  each with `step` 1 to 5 and a speakable question). The template floor is
  five dimensions, one anchor per item, and six probes. Game code inspects
  the shape at bank load time. A malformed pack fails the load loudly.

The bank starts with eight to ten classics: URL shortener, rate limiter, news
feed, chat, autocomplete, web crawler, unique ID generator, and notification
system.

### 5.2 Settings (localStorage, edited in the settings dialog)

- Providers, one row per role (`text`, `vision`, `image`): provider id
  (`openai`, `anthropic`, or `openai-compatible`), base URL, model name,
  API key, and thinking effort. The effort is `default` by default, or
  `off`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, or `ultra`.
  The key is optional: an endpoint that needs no key (a gateway, a local
  model server) gets its call without an auth header. A set key stays in
  localStorage and rides only in the auth header to the provider. The
  thinking effort maps to request parameters in game code. `default`
  omits the reasoning field, so the provider picks. Those defaults are
  model-dependent. `off` asks for no reasoning: OpenAI-style calls carry
  `reasoning_effort: "none"`, Anthropic-style calls leave thinking out
  (thinking there is opt-in). The ladder values pass through verbatim as
  `reasoning_effort` on OpenAI-style calls, so a model that lacks a value
  rejects the request. Anthropic-style calls carry a thinking budget
  instead: 1024, 2048, 8192, 16384, 32768, 65536, and 131072 tokens from
  `minimal` to `ultra`, with `max_tokens` just above the budget. The mock
  provider carries nothing. The field applies to the text and vision
  roles. The image role ignores it.
- Interview preferences: learning or testing mode, constrained or
  unconstrained mode, persona (phase 2), language (phase 2). The menu also
  offers a proactive-guidance preference (learning mode only, off by
  default, stored in the session record). The step tracker visibility is a
  learning-mode toggle stored in the session record. Testing mode hides
  the step tracker entirely.
- Whether the game opens the how-to-play section at each load. On is the
  default. The section has a box, "Do not show automatically in the
  future". A tick on that box sets the setting to off. A box without a
  tick sets it back on. The closing of the section stores the setting.
  The last row of the section, with the box and the Close button, stays
  visible while the text scrolls.
- Optional interview timer with presets such as 45 minutes, to match a real
  interview. Off by default, and configured at `MENU`.
- A test connection button per provider row.

### 5.3 Session (localStorage, one active session)

- Transcript: ordered messages with speaker, text, and artifact references.
- Artifacts: calculations (LaTeX source plus rendering) and diagrams
  (Mermaid source), each tagged with the step it belongs to.
- Process state: which of the five steps the interviewer marked as covered,
  derived from interviewer messages.
- Grade: filled in by the grader pass at the end.
- Mid-interview grading snapshots: results of grading requests made during
  the interview, oldest first, so the user can watch progress across
  attempts.
- Design ledger: the cleaned-up solution state per section 5.4.
- Timer state: remaining milliseconds and a running flag. Present only in
  sessions with the optional timer on.
- Probe budget: the cap the player chose for prepared probes per step
  (`maxProbesPerStep`, 0 to 5, default 2) and the counts of asked probes
  (`probesUsed`, keyed by step). Learning mode only. The counts come from
  the `[[probe: N]]` control lines.

### 5.4 Design ledger (the cleaned-up solution)

The ledger is the canonical, structured form of the candidate's solution,
kept separate from chat noise:

- Components and decisions: each settled choice with its parameters, for
  example "cache: Redis, cache-aside, TTL 60 seconds" or "sharding: hash on
  user_id".
- Accepted estimates: the numbers the interviewer accepted, with values and
  units.
- Revealed guidance: which `hidden_guidance` items the user already
  surfaced. The flag lives here, so context compression cannot make the
  interviewer re-reveal a constraint or forget one.
- Open threads: questions asked but not yet answered.

Artifact submissions update the ledger deterministically. Decisions stated
in prose enter it through a small extraction pass. The pass runs before
grading or compression, not after every turn.

## 6. Game flow and state machine

States: `MENU`, `BRIEFING`, `INTERVIEW`, `GRADING`, `FEEDBACK`.

- `MENU`: pick a problem (or random), mode, and constraints. Then start.
- `BRIEFING`: the interviewer opens with `vague_prompt` in character.
- `INTERVIEW`: free-form chat. The engine tags interviewer messages with the
  step they belong to and drives the step tracker. The candidate types one
  turn at a time into a multi-line input. A turn is any combination: prose
  only, prose with equations or diagrams, equations only, or diagrams only.
  Each equation or diagram becomes an artifact tagged with the current
  step, and the interviewer responds once per turn in the same channel. In
  learning mode, the user can request a mid-interview grade at any time
  (section 9.1).
- `GRADING`: a separate grader call over the full transcript and artifacts.
- `FEEDBACK`: score, failing diagnostic rows, missed items, and per-artifact
  comments, plus the interviewer's in-character closing.

The user can reopen earlier steps. The tracker records coverage, not order.
The tracker shows all five steps covered, and the user agrees to end. The
engine then ends the interview. The user can also ask to finish early. The
end control is available on every candidate turn, whatever the tracker
shows: ending is the user's call, never something the model's bookkeeping
can take away. An interview ended with steps unmarked grades honestly on
the missing rows.

An optional timer can bound the interview. It uses accumulated active time:
`remaining_ms` ticks down only while the send button is enabled, which is
exactly the candidate's turn. It pauses while the LLM streams, while a
grading request runs, and during `GRADING` and `FEEDBACK`, so provider
latency never consumes the candidate's budget. Expiry fires from engine
code between turns, never mid-stream. On expiry the engine injects a
time-is-up signal, the interviewer delivers a short in-character wrap-up,
and the game moves to `GRADING`. An unfinished design grades badly on the
missing rows, which is the honest outcome. A reload restores
`remaining_ms` with the clock paused until the user's next turn.

## 7. Interviewer prompt design

The system prompt assembles from blocks in this order:

1. Persona and style block. MVP ships only the normal tech interviewer.
2. Problem block: `vague_prompt`, plus `hidden_guidance` marked as
   hold-back-until-asked, with a number on each item. The block closes the
   world: the vague statement and the hidden list are the only requirements
   of the interview. The interviewer never invents or implies a
   requirement, constraint, scale number, or SLA from its general
   knowledge. When the candidate asks about something the list does not
   cover, the interviewer says to assume anything reasonable instead of
   supplying a number.
3. Interviewer brief block: the problem's `interviewer_brief` prep pack
   (section 5.1). A problem without a pack skips this block.
   It holds the gist. It holds the dimension list of the current step. It
   holds the anchors of the items that are not surfaced yet, and the
   prepared probes of the current step. The probes appear in learning mode
   only, within the per-step cap the player set. Each asked probe carries
   a `[[probe: N]]` control line. The brief is listen-for material. Its
   contents reach the candidate only through the candidate's own asks or
   the candidate's own work.
4. Process block: the five steps, each with its job. Step 1 collects
   requirements and constraints. Step 2 gets an end-to-end sketch that
   stays at the big picture. Step 3 works the core components in depth.
   Step 4 names bottlenecks and what fixes them. Step 5 addresses scaling.
   The interviewer runs the steps in order and does not open a later
   step's material early. When feedback on the current step touches
   material from a later step, the interviewer says so in one short line.
   Then it returns to the current step's job. It drills into bottlenecks
   and optimization in step 4. When the candidate opens that door first,
   it also drills there. In learning mode it says out loud what it
   parks. In testing mode it announces nothing about structure, and its
   next question aims at the current step's job instead. The process
   block also carries the tracker-truth rule. A reply that states a
   hidden guidance item ends with that item's `[[guidance: N]]` line.
   That holds every time, also for an item already surfaced. A step is
   announced in words only together with its `[[step: N]]` line. The
   block tags each turn with the current step.
   It instructs the interviewer to grade every volunteered number against
   the estimation table instead of accepting hand-waving. The
   interviewer never solicits an estimate the candidate has not offered,
   and never suggests that the candidate run calculations. The
   interviewer accepts aggressive rounding and ballpark figures. It
   treats false precision (four significant digits) as a stylistic
   flaw, not a merit. The interviewer can suggest wrapping up in
   character, but it must never declare the interview over. Only game
   code ends the interview.
   Control lines end each reply. `[[step: N]]` names the step, and
   `[[covered: N]]` marks a step as covered. `[[guidance: N]]` marks a
   hidden guidance item that the reply reveals, with the number of that
   item in the problem block. A hint can carry that line too. Game code
   reads the lines. It records each revealed item in the ledger (section
   5). It shows no line to the candidate. A number outside the list of
   the problem is dropped.
   The ledger does not depend on those lines arriving. After every
   interviewer reply the game sends a second, small checker call. That
   call reads the reply against the numbered hidden guidance list and
   reports the items the reply states. Game code inspects the checker
   reply's shape, drops numbers outside the list, and records the rest through
   the same ledger path as the control lines. A failed checker names
   itself on the engine status and records nothing. The checker runs
   inside the turn, so the clock stays paused and the ledger is
   consistent before the next candidate turn. The briefing and the
   wrap-up are not checked.
5. Estimation reference block: the latency, throughput, and availability
   table from the `system-design` skill (reference file
   `references/estimation-numbers.md`). The interviewer grades claims against
   this table instead of its own memory, which removes most grader
   hallucination about hardware numbers. The table's lineage is the standard
   ballpark sources: the powers-of-two and latency tables in the System
   Design Primer, and the original Jeff Dean latency gists (jboner/2841832
   and hellerbarde/2843375). A user who learned from those sources finds the
   same numbers here.
6. Mode block. Learning mode: on request, give a hint first, then a fuller
   explanation, then a walkthrough. A proactive-guidance preference (off by
   default) additionally allows the interviewer to end a turn with one
   gentle pointer toward an unexplored area. Without that preference the
   interviewer answers only what is asked. Testing mode: refuse all help
   requests. The testing interviewer never volunteers guidance of any
   kind. It gives no pointers to unexplored areas. It names no techniques
   or terms the candidate has not used, for example QPS, caching, or
   sharding. It never asks the candidate to run numbers, and it never
   signals that a step is missing or incomplete.
7. Constraint block: pinned stack in constrained mode, free choice otherwise.

The interviewer reads artifacts from structured blocks in the conversation.
It marks up a diagram by emitting a corrected or commented Mermaid source
block in its reply.

### 7.1 Context assembly and compression

The stored session record always keeps the full transcript. Compression
applies only to what the game assembles into an LLM call, never to what is
kept on disk. Mid-interview grading always reads the full transcript from
storage.

The assembled interviewer context has layers:

- Always uncompressed: the system prompt blocks, the design ledger, all
  artifacts, the step tracker state, and the most recent window of turns
  verbatim.
- Compressed on trigger: when a character-based token estimate crosses
  about 60 to 70 percent of the model context, a summarization call
  distills the older turns. The distillation lands in the ledger and a
  short narrative of settled questions, and those turns drop out of later
  assemblies.
- Token estimate: characters divided by 4, good enough for a trigger.
- Testing-mode safety: the ledger preserves every settled decision, so a
  compressed interviewer still holds the candidate to them.

Assembly with the recency window lands in M1. The summarization trigger
lands in M3.

## 8. Turn input and rendering

One multi-line input holds a whole candidate turn (DESIGN.md 6). The parser
splits it into ordered segments: prose, LaTeX blocks in `$$dollars$$`, and
Mermaid or LaTeX blocks in fenced code. Only closed fences and balanced
`$$` pairs become artifacts. An unclosed fence or a lone `$$` stays prose,
so a half-typed block never swallows the rest of the turn. Each artifact
renders in the chat as math or a drawing, tagged with the current step,
and the interviewer responds once per turn. Prose keeps its place between
the blocks. Phase 2 adds image attachments as a further segment type. The
picture goes to the vision model and the Mermaid transcription comes back.
The user corrects the transcription, so vision errors stay out of the
grade.

## 9. Grading design

The grader is a separate call with its own system prompt. Its input is the
whole transcript, the design ledger (section 5.4), all artifacts,
`known_patterns`, and `common_misses`. It also receives
`hidden_guidance_revealed`: the texts of the hidden guidance items that the
interviewer revealed. The grader judges the design against those
constraints. It does not count them as estimates of the candidate. It does
not receive the items that the interviewer never revealed. Process
evidence comes from the
transcript, and solution quality comes from the ledger plus artifacts, so
chat noise never touches the solution judgment. It never sees the interview
live.

Rubric output:

- Process score: coverage of the five steps, revisits allowed.
- Design score: the eight-row Quick Diagnostic from the `system-design`
  skill, one pass or fail per row, with the specific fix for each failing
  row. The rows cover requirements, estimation, redundancy, database
  scaling, caching, queues, monitoring, and deployment.
- Estimation realism: every claimed number gets an order-of-magnitude
  judgment against the estimation reference table. A claim like 5 PB/s of
  storage throughput fails as four orders of magnitude too fast. Exact
  figure pedantry is out of scope by decision D7. A ballpark answer within
  one order of magnitude passes, and rounding to friendly figures counts as
  good practice.
- Missing list: `common_misses` items never addressed.

The final score is 0 to 10, derived from the diagnostic row count
(`score = round(passed / 8 x 10)`), matching the skill's scoring rule. The
feedback screen shows the score, each failing row with its fix, the missing
list, and per-artifact comments. The grader returns strict JSON, and the
parser retries once on malformed output.

### 9.1 Mid-interview grading (learning mode only)

During `INTERVIEW`, the user can request a mid-interview grade at any time
in learning mode. The request runs the grader module over the current
transcript with a mid-interview prompt variant. Testing mode refuses these
requests, exactly as it refuses hints.

A mid-interview grade reports progress, never a final score. It names which
of the five steps look solid, and which diagnostic rows already pass. It
lists what is obviously missing so far, and it states plainly that the
interview is still open. Each result lands in the mid-interview grading
snapshot history in the session record. The user can grade, adjust the
design, and grade again while watching progress across attempts.

Mid-interview grades never enter the interviewer's message list. The grader
is a separate call over the transcript, so the interviewer stays blind to
every verdict. Each request is a full grader call over a growing transcript,
so the request button carries a token cost note.

## 10. Provider layer

One interface: `complete(role, messages, options)`.

- Adapters: `openai` (with the browser-access flag),
  `anthropic` (with its direct-browser-access flag), `openai-compatible`
  (custom base URL), and `mock` (scripted replies for offline tests).
- CORS failures surface as a clear error message naming the provider, plus
  a pointer to the base URL field in settings.
- A later Bifrost router swap touches only this module.

## 11. Personas, art, and sound (phase 2)

Each persona is a prompt block plus art plus a voice timbre:

- Klingon: captain or commander uniform, commanding bearing, brusque speech.
- Vulcan: commander uniform, commanding bearing, precise and formal speech.
- Pirate: pirate ship captain, commanding bearing, colorful period speech.
- Cowboy: Texan, ranch owner, weathered, self-assured presence, Texan cowboy speech.
- Normal tech interviewer: business attire, plain modern speech.

Pixel art in the 8-bit or 16-bit console style, animated. Backgrounds match
the persona (starship bridge, ranch, ship deck, office). Sound is the
Animal Crossing style gibberish recipe: one short synthesized blip per
syllable or character. Pitch comes from the character code or from random
values in a persona range, and each blip lasts 50 to 100 ms. The blip stream
syncs to the subtitle text. Persona timbre comes from the waveform choice, for example a
raspy distorted sawtooth for the Klingon and a smooth sine for the Vulcan.
No audio files, no recorded speech, and it works in every locale.

The shipped shape (M4). `js/personas.js` holds the registry. The prompt
block replaces the plain interviewer voice block in the system prompt.
`normal` is that plain voice, so one source holds both. The sprite is a
16x16 pixel map per persona. `js/persona-art.js` draws it onto a canvas
portrait with a two-frame idle bob. The backdrop is a persona class on
the interview screen. The voice follows this section's recipe in
`js/audio.js`. The schedule is deterministic in text and persona. Latin
words contribute their vowel-group count with a floor of one. CJK text
contributes one blip per character. `BlipVoice` takes the AudioContext
as a parameter, so tests inject a fake. A mute toggle and the persona
choice persist in preferences.

## 12. Internationalization (phase 2)

Six UI locales: English, French, Japanese, Simplified Chinese (Putonghua),
Traditional Chinese (Cantonese written form), and Traditional Chinese
(Taiwanese Mandarin). The last two are separate locales with different
vocabulary and phrasing, not one locale with a font switch. Translated keys
hold text-only segments, so markup never lives inside a swapped element.
The interviewer's language is a prompt parameter, so dialogue needs no
recorded assets.

## 13. Cited-source verification (phase 2)

The user can attach a source URL to a claimed number. The VPS-hosted fetch
proxy retrieves the page text, because a browser cannot fetch arbitrary URLs
across origins. The grader then judges the claim twice: against its own
knowledge anchored on the estimation table, and against the fetched source
text. Feedback reports both judgments. It weighs official vendor
documentation above third-party benchmarks, and blog posts last. It states
openly that it cannot fully detect bias or cherry-picking in a cited source.

## 14. Verification approach

- Vendor every library. Version every asset URL with `?v=N`, and bump the
  version on every edit, including ES module sub-imports.
- Drive the real DOM in headless Chromium (container-side Playwright against
  a container-local `http.server`). Keep console and pageerror capture on in
  every run.
- The mock provider makes engine, state, and grader parsing tests
  deterministic with no network.
- The host-side `http.server` stays available for Camofox sessions on
  request. The container's localhost is not reachable from Camofox, so
  host-side serving is the only topology Camofox reaches.
- Assert persisted side effects (localStorage writes), not just visible UI
  state.
