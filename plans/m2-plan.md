# M2 implementation plan - grading and feedback

Objective per PLAN.md: an end-of-interview grade with structured feedback,
plus mid-interview progress grading in learning mode.

## Module map

- `js/prompts/grader-prompt.js`: DIAGNOSTIC_ROWS (the eight rows from the
  system-design skill Quick Diagnostic, with question, if-no risk, and
  action), rubric block, JSON schemas for the final and mid variants,
  `buildGraderMessages(session, variant)`. Reuses ESTIMATION_REFERENCE for
  the realism rules.
- `js/grader.js`: `gradeSession(session, options)`: one call over the full
  transcript plus ledger plus artifacts plus known_patterns plus
  common_misses. `parseGradeJson(text)` strips fences and preamble.
  Malformed output retries exactly once (second LLM call). Score derived as
  `round(passed / 8 * 10)`. Shape validation after parse.
- `js/providers.js` (edit) - mock purposes `grade` and `grade_mid`,
  a
  grader reply queue (`setMockGraderQueue`) so tests script malformed then
  valid replies. `resetMockState` clears the queue.
- `js/prompts/mock-script.json` (edit) - `grade` (valid rubric JSON for the
  scripted interview), `grade_bad` (prose, unparseable), `midgrade`
  (progress shape, no score).
- `js/engine.js` (edit) - wrapup now lands in GRADING, renders a grading
  indicator, runs the grader, stores `session.grade`, and moves to FEEDBACK.
  Grader failure leaves the session intact and offers a retry button.
  `requestMidGrade()` for learning mode: snapshot into
  `session.midInterviewGrades`, never touches the transcript. Testing mode
  hides the button. Busy flag pauses the timer during grading calls.
- `js/app.js` (edit) - `renderFeedback(session)`: score, process coverage,
  eight rows with pass or fail and fixes, realism judgments, missing list,
  per-artifact comments, in-character closing. Resume into FEEDBACK renders
  the stored grade,
  resume into GRADING with no stored grade reruns the
  grader.
- `index.html`, `css/main.css` (edit) - grading indicator, feedback
  sections, mid-grade button with token cost note, snapshots list.

## Grader JSON contract (final)

```
{"process_coverage": [ints 1-5], "rows": [{"name", "pass", "fix"} x8],
 "realism": [{"claim", "verdict", "note"}],
 "missing": [strings], "artifact_comments": [{"artifact_id", "comment"}],
 "closing": "string"}
```

Score is computed by game code from rows, never trusted from the model.

Mid variant: `{"solid_steps", "passing_rows", "obvious_gaps", "note"}`,
no score, states the interview is still open.

## Task order

1. Plan + diagnostic rows extraction (done here).
2. grader-prompt.js + grader.js with unit tests first (parse, retry, score).
3. Mock script entries + queue.
4. Engine wiring + resume-into-FEEDBACK.
5. Feedback and grading UI + snapshots.
6. m2_units.py + m2_e2e.py green,
  full suite re-run,
  bump ?v= on edits.

## Verification

- m2_e2e: scripted interview ends in a parsed grade,
  feedback renders every
  section,
  malformed grader reply triggers exactly one retry (queue has
  grade_bad then grade),
  mid-interview request returns progress, stores a
  snapshot, appends nothing to the transcript,
  testing mode hides the
  button,
  zero console errors,
  localStorage assertions throughout.
