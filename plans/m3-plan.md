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
runtime files of `game/` on a push to main. `game/tests/deployed_smoke.py`
checks a deployed copy and takes the base URL as its argument.

## 7. Make it right

- Delete code that no caller reaches.
- Split each function with a CRAP score of 10 or more.
- Cover each function that no test executed.
- Measure again with both levers after the change.
