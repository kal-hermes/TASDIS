# M3 task plan: robustness, how-to-play, export, compression

Objective per PLAN.md: robustness fit for real providers and real users.

## 0. Levers

Problem: modules import each other by exact URL, so mixed `?v=` values load
one module twice (today `assemble.js` loads as v3 and v4).
Plan: `game/tools/bump_versions.py` sets one version on every non-vendor
asset URL (index.html, js modules, tests). Run it before each commit.
Vendor files stay at v1.

Problem: the crapper scores complexity and coverage, but the tests run in
Python, so the coverage of the game code was unknown.
Plan: `game/tools/js_coverage.py` runs the suites with the coverage of
Chromium on and writes `coverage/lcov.info`. The crapper then reads that
report with `--use-existing-coverage`. The dryer and the mutator do not read
plain JavaScript, so they do not run on this game.

## 1. Error handling

TDD: `tests/m3_errors.py` (units + browser).

- `providers.js`
  - Typed low-level errors: `NetworkError`, `TimeoutError`, `HttpError`.
  - Request timeout (connect and first byte) and stream idle timeout.
  - Settings validation: a missing API key, model, or Base URL names the
    Settings dialog.
  - `describeProviderError` maps each kind to a readable message with a
    next step (401 and 403 = key, 404 = Base URL or model, 429 = wait).
  - Empty reply is an error.
  - Mock fault queue: test hook that throws the same low-level errors.
- `engine.js`
  - A failed turn shows a notice with a Retry button. Retry re-runs the
    turn and does not duplicate the candidate message.
  - Briefing failure stays on the briefing screen with a retry button.
  - Wrap-up failure records a system message and moves on to grading.
  - Grading failure after the one retry keeps the retry button.
- Real adapter paths are verified with route interception against a fake
  OpenAI-compatible endpoint (abort, 401, hang, 500).

## 2. How to play

`<dialog id="howto-dialog">`, opened from the menu and from Settings.
Content per PLAN.md M3 task 2. Test: opens from both places and names
every provider role and every menu toggle.

## 3. Transcript export

`js/export.js`: `transcriptMarkdown(session)` is a pure function.
Buttons on the interview sidebar and the feedback screen download the file.
Test: unit on the pure function, browser download on the feedback screen.

## 4. Context compression (DESIGN.md 7.1)

- The stored record keeps the full transcript. Compression changes only
  the interviewer assembly. Both graders read the full transcript.
- Head layers, always uncompressed: interviewer prompt, tracker, ledger,
  full artifact sources, compression narrative.
- Verbatim window: budget = 60 percent of the context window minus the
  head. The last 6 turns stay verbatim whatever the budget. The default
  context window is 32000 tokens. Settings has a field for the text role.
- Turns that fall out of the window are summarized by one call. Output is
  strict JSON: narrative, decisions, estimates, open threads. Game code
  verifies the shape and applies it to the ledger.
- Room for the first summary is held back until the first compression, so
  the window does not shrink by a turn right after it. A second run on the
  same transcript changes nothing.
- Failure of the summarization call leaves the interview running. A
  status line says older turns were not summarized.
- Test: `tests/m3_context.py` units with a small fake context limit and
  a long mock script.

## 5. Self-play with injected failures

`tests/m3_selfplay.py`: MENU to FEEDBACK with zero console errors, then
the same script with network, timeout, HTTP, empty, and malformed replies
at several points. Every failure shows a readable notice, and every
retry path recovers without losing the session.

## 6. GitHub Pages

The game moved to its own repository, `kal-hermes/TASDIS`, which is the
submodule `TASDIS/` of `games`. GitHub publishes a project site at
`<user>.github.io/<repository>/`, so the address of the game is
`https://kal-hermes.github.io/TASDIS/`.

The workflow `.github/workflows/static.yml` in that repository deploys the
runtime files of `game/` on a push to main. The site is live and verified
(`game/tests/deployed_smoke.py` with no argument).

Three facts about this repository:

- The owner turned Pages on once in the repository settings, with GitHub
  Actions as the source. The token of a workflow run cannot do that.
- One run deployed before GitHub listed the uploaded artifact, and failed.
  The workflow now waits until the artifact is listed.
- The address keeps the capital letters of the repository name. The
  address `https://kal-hermes.github.io/tasdis/` returns 404.

## 7. Make it right

- Delete code that no caller reaches.
- Split each function with a CRAP score of 10 or more.
- Cover each function that no test executed.
- Measure again with both levers after the change.

## 8. Changes after M3, requested by the owner

1. The game opens "How to play" at the start. The dialog has a box, "Do
   not show automatically in the future". When the dialog closes with the
   box ticked, the next load opens no dialog. A box that is not ticked
   opens it again. The game keeps the choice in the settings, in the local
   storage, where the game keeps all of its data. The game uses no
   cookies. The dialog opens over the screen that a resume selected.
2. The dialog opens at its top. Today its only focusable element is the
   Close button at the end, so the browser scrolls to that button.

Test: `game/tests/m3_howto.py`, written first. The older suites seed the
new setting as off, so that the dialog stays out of their way.
3. The last row of "How to play" stays visible while the text scrolls.
   The dialog is a column: the text that scrolls, with the title, and
   then the row with the box and Close. On some systems the scrollbar is
   invisible, so the row is the sign that the text continues.
4. The game wires `revealGuidance`. The problem block numbers the hidden
   guidance items. The interviewer adds the control line `[[guidance: N]]`
   to a reply that reveals item N. Game code records N in the ledger and
   never shows the line. A number outside the list of the problem is
   dropped. The ledger summary names the items that the interviewer
   already surfaced.

Tests: `game/tests/m3_howto.py` gains the last row. `game/tests/m3_guidance.py`
is new and written first: the units, then a browser run with scripted
replies over an intercepted endpoint.
5. The grader receives the texts of the revealed hidden guidance items,
   in the field `hidden_guidance_revealed` of its input. The ledger keeps
   the numbers. The grader judges the design against these constraints.
   They are not estimates of the candidate. The grader does not receive
   the items that the interviewer never revealed.

Test: the units of `game/tests/m3_guidance.py`, written first.

6. The API key of a provider row is optional. When it is empty, the game
   makes the call without an auth header: no `Authorization` for the
   OpenAI shapes, no `x-api-key` for Anthropic. The model name and, for
   openai-compatible, the base URL stay required. A 401 or 403 error
   points at the key in Settings. It also says an endpoint that needs
   no key takes an empty one.

Test: the units and the keyless sections of `game/tests/m3_errors.py`,
written first: an empty key and a set key over an intercepted endpoint,
for both adapters, with the auth headers captured.

7. The interviewer gets a directing protocol and a closed world. The
   process block gives each of the five steps a job, runs them in order,
   and forbids opening a later step's material early. Bottleneck depth
   waits for step 4, or for the candidate opening that door. Learning
   mode says out loud what it parks. Testing mode announces nothing
   about structure and aims its next question at the current step's job.
   The problem block closes the world: the vague statement and the
   hidden list are the only requirements. The interviewer never invents
   a constraint. When the list does not cover an ask, it says to assume
   anything reasonable. A tracker-truth rule demands the `[[guidance:
   N]]` line whenever a reply states an item, and `[[step: N]]` with any
   step named in words. The per-turn tracker line of the interviewer
   context states the current step's job, so the anchor survives
   compression. The end control is available on every candidate turn.
   The reason: a live interview showed a real model leaving steps
   unmarked, which used to hide the end button for the whole session.

Test: the prompt flags of `game/tests/m1_units.py` and the end-control
section of `game/tests/m3_ui.py`, both written first and red on the
missing rules.

8. The ledger does not depend on the model emitting control lines. A
   live interview showed a real model stating items in bold prose while
   the ledger stayed at three of six. A tracker-truth prompt rule was
   written after that session, but a rule cannot force a model's
   bookkeeping. After every interviewer reply the game now sends a
   second, small checker call. It reads the reply against the numbered
   hidden guidance list and returns the items the reply stated. Game
   code inspects the shape, drops numbers outside the list, and
   records the rest through the same revealGuidance path as the control
   lines. A failed checker names itself on the engine status and loses
   nothing. The checker runs inside the turn, so the timer stays paused
   and the ledger is consistent before the next candidate turn.

Test: the checker units and the intercepted-endpoint sections of
`game/tests/m3_guidance.py`, written first and red. Red cases: a prose
reveal with no control line reaches the ledger through the scripted
checker reply. A failed checker names itself and loses nothing. The
mock path records from the checker queue.

9. The url-shortener problem carries an `interviewer_brief` prep pack
   (`gist`, five `dimensions`, six `anchors`, six step-gated `probes`).
   The pack is the interviewer's author-time mental model, written once
   instead of improvised per session. Game code inspects the pack shape
   at bank load time. The template floor: five dimensions, one anchor per
   hidden item, at least six probes. A malformed pack fails the load
   loudly. The pack reaches only the interviewer's context. The brief
   block holds the gist, the dimension list of the current step, the
   anchors of the not-yet-surfaced items, and the current step's probes.
   Probes exist in learning mode only. The player caps them per step
   (`maxProbesPerStep`, 0 to 5, default 2, menu select, frozen in testing
   mode). Each asked probe carries a `[[probe: N]]` control line. The
   per-step counts ride the session (`probesUsed`) and the never-
   compressed head as a budget line. The other seven problems follow the
   same pattern on this template floor.

   Shipped: all eight problems carry a pack. The seven drafts sit in
   `plans/prep-pack-<slug>.json` next to the url-shortener draft. Each
   pack's arithmetic was computed, not quoted. The load-bearing numbers:
   the 200 follower fan-out lands near 231 thousand feed inserts per
   second. Chat flows at about 579 thousand messages per second.
   Autocomplete answers about 926 thousand keystroke requests per second.
   The crawler needs 386 parallel hosts at the politeness ceiling. Twelve
   sequence bits give 4096 IDs per millisecond per machine. Notification
   backoff runs about 31 seconds before a dead letter. The bank load
   inspects every pack, so a malformed one fails the menu loudly.

10. The candidate types each whole turn into one multi-line input
    (`#candidate-input`, a textarea). Enter sends. Shift+Enter makes a
    newline. A turn is any combination: prose only, prose with `$$latex$$`
    blocks, prose with Mermaid fences, equations only, diagrams only, or
    all of it at once. The three-tab submission panel is gone. The parser
    (`js/turn-parse.js`) splits the text into ordered segments. Only
    closed fences and balanced `$$` pairs become artifacts. An unclosed
    fence or a lone `$$` stays prose, so a half-typed block never swallows
    the rest of the turn. Each block lands in the ledger through the
    normal artifact path, renders inline in the chat, and the interviewer
    responds once per turn. Help detection reads the prose only, so a
    diagram alone never triggers the hint ladder. A source the renderers
    reject shows the render error inside the artifact box, and the chat
    never breaks. Image attachments join the same segment model in
    phase 2.

Test: the parse units of `game/tests/m1_units.py` cover all
combinations, ordering, the unclosed fence, the lone `$$`, and the blank
input. The unified-turn section of `game/tests/m3_ui.py` covers the
textarea, the gone panel, one mixed turn, and the recorded artifacts.
The typed-turn flows of `game/tests/m1_e2e.py`,
`game/tests/m3_selfplay.py`, and `game/tests/deployed_smoke.py` cover
the rest. All were written first and red.

11. The settings table carries a Thinking effort select per role. The
    old "Context window of the text model" number field is gone. The
    vocabulary is provider-neutral: `off`, `default`, `minimal`, `low`,
    `medium`, `high`, `xhigh`, `max`, `ultra`. `default` is the select's
    initial value. It omits the reasoning field, so the provider picks.
    Provider defaults differ per model. `off` asks for no reasoning.
    OpenAI-style calls receive the value `none`. Anthropic-style calls
    leave thinking out, because thinking there is opt-in. The ladder
    values ride OpenAI-style calls verbatim as `reasoning_effort`, so a
    model that lacks a value rejects the request. Anthropic-style calls
    carry a thinking budget instead: 1024, 2048, 8192, 16384, 32768,
    65536, and 131072 tokens from `minimal` to `ultra`, with `max_tokens`
    just above the budget. Game code owns the mapping
    (`thinkingParams` in `js/providers.js`). The mock carries nothing.
    The field applies to the text and vision roles. Wire capture proves
    the parameter rides the request and drops out at `default`.

Test: the mapping units of `game/tests/m1_units.py` cover all providers
and all nine values plus the blank string. The settings section of
`game/tests/m3_ui.py` covers the nine options, the `default` initial
value, and persistence. The wire captures of `game/tests/m3_selfplay.py`
prove the rest. `xhigh` rides the wire verbatim. `off` becomes `none`
on OpenAI-style calls. `default` omits the field. The Anthropic budgets
land. All were written first and red.

Test: the brief units of `game/tests/m1_units.py` (validation, block
assembly, mode and cap gates, probe lines). Also the probe-cap section
of `game/tests/m3_ui.py`, the budget-anchor section of
`game/tests/m3_context.py`, and the probe-line section of
`game/tests/m3_guidance.py`. All were written first and red. Red cases:
a valid pack passes. Malformed packs throw with the problem id. The
block holds the current step's material only. Cap 0 and testing mode
remove the probes. A probe line counts once per step.
