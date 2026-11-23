# 001 - Feasibility Assessment of GOAL.md

## Verdict

The core idea is feasible, and the hard parts are content quality, not technology.
The one real risk is scope: the document bundles a solid MVP with a pile of
expensive extras, and a few of those extras are weak ideas on their own merits.

## Strong parts

1. **Interview loop.** The flow (problem bank, clarifying questions, estimates,
   diagrams, grading) maps directly onto chat plus prompt engineering. The
   `system-design` skill already provides the material an interviewer LLM needs:
   the process steps, estimation numbers, building blocks, and an eight-row
   diagnostic that works as a grading rubric. You do not need to write the
   domain content from scratch.

2. **Mermaid.js for diagrams.** Right choice. It is text, so the LLM reads and
   writes it natively, and it renders in the browser with no server work. The
   instinct that "rendered nicely but also parseable" matters is correct, and
   Mermaid satisfies both.

3. **Calculations.** LaTeX is the practical answer. Every major LLM reads LaTeX
   reliably, and KaTeX renders it in the browser. Prose remains a valid
   fallback. Handwritten images depend on a good user-configured vision model.
   Grading of hand-drawn diagrams is noisier than grading of text diagrams.

4. **Game modes and settings.** Learning vs testing mode, constrained vs
   unconstrained, and process tracking (did the user visit all five steps) are
   all just game state plus prompt parameters. Cheap.

5. **Presentation.** Pixel art interviewer, themed backgrounds, and gibberish
   Animal Crossing-style speech are asset work, not research. Doable, but each
   persona is real art and sound production time.

## Weak or risky parts

1. **Image-editing feedback.** Image editing models are bad at annotating
   diagrams. Overlaying graded comments onto a hand-drawn sketch will look
   messy and will misplace labels. Marking up a Mermaid diagram is easy because
   it is text. Recommendation: drop image-editing feedback. Give diagram
   feedback in prose or by editing the Mermaid source.

2. **Browser-only LLM calls.** Two walls: CORS blocks some providers from
   browser origins, and the API key lives in the user's browser. It works for
   OpenAI and Anthropic with explicit browser-access flags, but a tiny proxy
   server removes both problems. Plan for this early, because it shapes
   deployment.

3. **Grader hallucination.** The grader itself can invent hardware numbers, so
   the "realistic claims only" rule cuts both ways. Anchoring the interviewer
   prompt to the skill's estimation reference table (real latency and
   throughput figures) makes grading much more trustworthy.

4. **Four steps vs five steps.** The `system-design` skill teaches a four-step
   process. GOAL.md specifies five. Worth reconciling before step tracking gets
   baked into game state.

5. **i18n is two problems.** UI strings in four languages are routine.
   Interviewer dialogue is LLM output, so language is a prompt parameter. That
   part is easy. But written Cantonese is a distinct written form from Standard
   Written Chinese. Decide: Cantonese written form or Taiwanese Mandarin. They
   are not the same prompt.

## Suggested phasing

**MVP (weekend-to-week scale):** text chat interviewer with the rubric, LaTeX
calculations, Mermaid diagrams, learning and testing modes, provider settings
dialog.

**Later (month-scale with the assets):** vision input, personas with art and
sound, image/diagram display area, i18n.
