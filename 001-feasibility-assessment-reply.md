## Weak or risky parts

1. **Image-editing feedback.** Agreed. Let's drop image editing. The LLM may translate the hand-drawn diagram into Mermaid.js and add comments there, I guess?

2. **Browser-only LLM calls.** No problem. Stick with browser-only LLM calls for now. We can switch to using a locally-run Bifrost LLM router later, if we encounter any CORS-related problem.

3. **Grader hallucination.** That is a real issue. In addition, services and hardware may have updated performance numbers that no longer match whatever real numbers we tabulate in advance or whatever training cutoff date of the LLM. E.g. S3 may become faster next year; in fact, it could even become slower simply at the whim of AWS. Is it OK if the user can justify the numbers by supplying a source (e.g. links to blog posts or official documentation). Of course some blogs are more trust-worthy than others. There could also bias or cherry-picking of bad numbers if a blog post is written by someone working for a competitor. What if the game could fetch URLs and feed them to the LLM to verify the user's claims. Would that work?

4. **Four steps vs five steps.** Yes, I'm aware of that. This is because I have studied system design from multiple sources. Donne Martin's [System Design Primer](https://github.com/donnemartin/system-design-primer/tree/master#how-to-approach-a-system-design-interview-question) has four steps very similar to what you have in the `system-design` skill; whereas the [Hired in Tech website](https://www.hiredintech.com/system-design/the-system-design-process/) has a step 3 that is different. The main difference is that the former lumps the bottleneck identification into step 4, whereas the latter has bottleneck identification as a separate step, but loses the "design core components" step. I thought it is important to explicitly have all those steps, so I merged the two methods into a 5-step process.

5. **i18n is two problems.** You are right, we should have these language settings:
  - English
  - French
  - Japanese
  - Simplified Chinese (Putonghua)
  - Traditional Chinese (Cantonese)
  - Traditional Chinese (Taiwanese Mandarin)

## Suggested phasing

OK

## BTW

For the gibberish sound effects, do we need to generate them as sound files ahead of time? Or is there some kind of web audio API that you can drive to create arbitrary waveforms?
