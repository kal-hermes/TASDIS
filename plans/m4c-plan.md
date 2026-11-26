# M4c plan: sprite mouth animation with decoupled timelines

## Goal

The interviewer's mouth moves while the speech text streams on the page.
When the stream ends, the mouth stops. The background animation runs on
its own clock. It never depends on the speech state. The mouth states
are authored pixel art in Aseprite through the pixel-plugin skills. They
ship as a spritesheet plus atlas metadata.

## Design

The interview screen runs three independent timelines:

1. Background set pieces. The existing deterministic painters in
   `js/scenes.js` redraw on the scene tick. No speech awareness.
2. Body idle bob. Part of the painted bust, same tick, fixed period.
3. Mouth. An Aseprite-authored spritesheet holds three states per
   persona: closed, half, and open. A pure function `pickMouthFrame`
   takes the talking flag and the elapsed milliseconds. Idle returns the
   closed state. Talking cycles half and open at the tagged durations.
   When the interviewer stream starts, the engine sets the talking flag.
   The engine clears the flag in its finally block after the stream.
   The flag sits next to the existing blip feed.

Why the backgrounds stay procedural: the Aseprite MCP server has no
image import tool. A 256x192 frame is about 49,000 pixels. Drawing ten
frames of five backgrounds pixel by pixel through tool calls is not
practical. The painters are already deterministic and reviewed. The
mouth states are small at 10x7 cells per state, so they are practical to
author, and they are the genuinely new art.

## Tasks

1. Probe and record the Aseprite server topology. Sources land in the
   host cache. Exports land in the repo. Record source paths in
   `game/art/manifest.json`.
2. RED tests. `tests/m4_units.py` gains the mouth group: the atlas shape
   for five personas, and `pickMouthFrame` behavior. Idle returns the
   closed state. Talking cycles the pair. The result is deterministic in
   the elapsed time. `tests/m4_ui.py` gains the sync section on a slow
   intercepted stream. The mouth pixels change while busy. The mouth
   pixels stay put while idle. The background lamp region keeps changing
   while idle. `tests/deployed_smoke.py` asserts the same on the live
   site.
3. Author `mouth-states.aseprite`. Fifteen frames of 10x7. Five personas
   in order, three states each. Indexed palette built from the scene
   palettes. Tag the closed frame and the talk pair. Export a horizontal
   spritesheet with JSON to `game/img/mouth-states.png`.
4. Runtime. `js/mouth.js` holds the atlas constants and the pure frame
   picker. `js/persona-art.js` blits the patch over the painted bust at
   3x with the same bob offset the bust uses. Engine wraps both
   interviewer streams with the talking signal.
5. `.github/workflows/static.yml` stages `img/` and triggers on it.
6. Bump to v36. The sheet fetch URL in `js/mouth.js` carries the version.
7. Closing loop. Every suite, the vendor probe, coverage, crapper, and
   the bump report. Then docs in DESIGN section 11, commit, push, CI,
   live verify, and the deployed smoke with the mouth assert.

## Palette note

The patch underlay copies the exact bust cells it covers. The sheet
palette is therefore the union of the five bust palettes over the covered
region plus the mouth colors. Indexed mode snaps colors at draw time.
