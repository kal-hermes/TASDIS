# Prep pack draft: url-shortener (for owner style review)

This file is a draft, not shipped code. The owner reviews the style of
this one pack. The same pattern then produces the other seven, and the
pack object lands inside each problem JSON. Nothing here is wired into
the game yet.

The artifact under review is the JSON next to this file:
`plans/prep-pack-url-shortener.json`. It shows the `interviewer_brief`
object in the shape it takes inside `js/problems/url-shortener.json`.

## What the pack is for

The pack is the interviewer's author-time preparation, the runtime
"mental model" the owner asked for, made deterministic. It is written
once into the problem JSON instead of improvised by the model each
session. It gives the interviewer a stable understanding of the
problem, so it directs from that understanding instead of drifting.

It is aligned with the grader's `known_patterns` and `common_misses`,
so the interviewer listens for what the grader scores.

The guardrail that will ship with it: the brief reaches only the
interviewer's context. Its contents reach the candidate only through
the candidate's own asks or the candidate's own work. The brief is
listen-for material, never say-material. Revealing a hidden item stays
governed by the closed-world rule and the reveal rules, and the reveal
checker audits every reply.

## Numbers the interviewer may grade against

All computed, all within an order of magnitude of what a candidate can
reach.

- 10 billion redirects per day is about 116 thousand per second.
- 100 million new links per day is about 1.2 thousand per second.
- The ratio lands at 100 to 1.
- Seven-character Base62 holds about 3.52 trillion codes. At 100
  million new links per day that is about 96 years.
- Five years of links is about 182 billion rows, about 91 TB at 500
  bytes per row before replication.

## How the fields map to the machinery

- `gist` frames the whole session. It is the model's stable mental
  model, the thing improvisation used to replace.
- `dimensions` keys 1 to 5 match `STEPS` in `assemble.js`. The
  directing block tells the interviewer to work one step at a time.
  The dimension lists tell it what working that step means for this
  problem. Every line traces to `known_patterns` or `common_misses`.
  The interviewer therefore never praises a pattern that the grader
  scores as a miss.
- `anchors` key 1 to 6 match `hidden_guidance` 1 to 6. Each anchor
  describes what hearing the item sounds like. The interviewer credits
  the candidate's own words instead of re-stating the item, which
  leaks it.
- `probes` are speakable questions. Each carries the step where it is
  legal. The bottleneck probes wait for step 4, and the geo probe
  waits for step 5, exactly as the directing block requires. They came
  out of the real interview session: the mutability, edit-versus-TTL,
  hot key, and geo lines were the probes the live model invented and
  the owner's session proved worth keeping.

## Open questions for the owner

All four answered by the owner. The style stands as drafted.

1. `gist` voice: approved as drafted.
2. `dimensions` can paraphrase `hidden_guidance`: approved as safe.
3. Probe cap: configurable in the game, 0 to 5 per step (menu select,
   default 2). Implemented as a learning-mode-only control. Testing mode
   never sees a probe list.
4. Five dimensions, six anchors, six probes are the template floor for
   every problem pack.
