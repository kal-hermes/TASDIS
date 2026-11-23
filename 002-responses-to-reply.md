# 002 - Responses to Your Reply on 001

## 1. Image-editing feedback

Agreed on the translation approach. One caveat: a vision model transcribing a
hand-drawn diagram makes mistakes. The interviewer must show the user its
Mermaid transcription and ask for corrections before it grades or comments.
That confirmation step keeps transcription errors out of the grade.

## 2. Browser-only LLM calls

Fine. Two notes for the settings dialog:

- OpenAI needs the browser-access flag (dangerouslyAllowBrowser), and
  Anthropic needs anthropic-dangerous-direct-browser-access. Some providers
  block browser origins entirely. The dialog must show a clear error message
  after a CORS failure.
- Bifrost as a later escape hatch works. Keep the provider layer behind one
  interface, so the swap stays cheap.

## 3. Source verification

Yes, user-supplied sources are a good idea, and the game can fetch URLs and
feed the page text to the grader. Design notes:

- A browser cannot fetch arbitrary URLs because of CORS, so this feature needs
  a small fetch proxy even while the LLM calls stay browser-only. This is the
  first feature that breaks the "no server" property.
- Grade the claim twice: once against the grader's own knowledge, and once
  against the cited source text. Report both, because a source proves only
  that the user read it, not that it is current or neutral.
- Weight source classes: official vendor documentation above third-party
  benchmarks above blog posts. The grader cannot fully detect bias or
  cherry-picking, so state that limit in the feedback.
- Prefer order-of-magnitude comparisons over exact figures. S3 throughput does
  change over time, and a rubric built on today's exact numbers rots.
  "5 PB/s is four orders of magnitude too fast" survives time far better than
  "2700 MB/s is off by 3 percent".
- This is phase 2 work, not MVP.

## 4. Five-step process

Your merge is sensible, and the origin story explains it well. Keep your five
steps as the canonical process in game state and in the interviewer prompt.
The `system-design` skill remains reference material for the rubric and the
estimation numbers, not the source of the step list.

## 5. i18n

Six locales noted, including the Cantonese and Taiwanese Mandarin split. Both
use Traditional script, but vocabulary and phrasing differ, so they are
genuinely separate prompt locales, not one locale with a font switch. Japanese
adds a fourth script family to test. All straightforward, just more
translation volume.

## Gibberish sound

No pre-generated files needed. The Web Audio API is the right tool, and the
Animal Crossing style is a known recipe:

- Map each character or syllable of the dialogue text to one short synthesized
  blip.
- Pitch comes from the character code or from random values in a persona
  range, and each blip lasts about 50 to 100 ms.
- Each persona gets its own timbre: waveform type, pitch range, and speed. A
  Klingon voice reads as a raspy sawtooth with distortion, a Vulcan voice as a
  smooth sine, a cowboy voice as a slow low square wave.
- The blip stream tracks the subtitle text, so sound and text stay in sync.

This runs in a few hundred lines of code with zero audio assets, and it works
for any language, so i18n never needs recorded speech.
