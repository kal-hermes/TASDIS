# M4 plan: personas, art, and sound

Objective: the five personas from DESIGN.md section 11 with art and voice.

## Task 1: persona registry in `js/personas.js`

One exported registry with five personas: `klingon`, `vulcan`, `pirate`,
`cowboy`, `normal`. Each entry carries:

- `name`: display name for the menu.
- `promptBlock`: the speech-style block the assembler embeds (DESIGN.md
  section 11 voices: brusque Klingon captain, precise Vulcan commander,
  colorful pirate captain, weathered Texan rancher, plain modern
  interviewer).
- `palette`: the sprite palette and the theme accent colors.
- `timbre`: waveform id for the blip synth (raspy sawtooth, smooth sine,
  square, triangle, soft sine) plus the pitch range in Hz.
- `sprite`: pixel map frames for the portrait canvas.
- `background`: the id of the themed backdrop.

Test (m4_units, red first): the registry exposes exactly five personas,
each with all fields, palettes non-empty, and the prompt blocks name
their style keywords.

## Task 2: blip synth in `js/audio.js`

`scheduleBlips(text, persona)` returns the blip schedule: one entry per
syllable, where a syllable is a vowel-group count of the word and CJK
text counts one blip per character. Each blip lasts 50 to 100 ms. The
pitch comes from the character code inside the persona range. The
schedule is deterministic for the same text and persona. `BlipVoice`
plays a schedule, one WebAudio oscillator per blip with the persona
waveform. It takes the AudioContext constructor as a parameter, so tests
inject a fake. A mute toggle gates playback and persists in preferences.

Test (m4_units, red first): schedule count, duration bounds, pitch
bounds, determinism, and the per-persona waveform in the play calls
against a fake context. The mute gate stops creation.

## Task 3: persona prompt block in the assembler

`assemble.js` embeds `persona.promptBlock` in the interviewer system
prompt. A persona other than `normal` switches the speech style.
`normal` keeps the current plain-interviewer voice. The block rides the
never-compressed head through `context.js`.

Test (m4_units, red first): assembled messages contain the persona
style keywords per persona and nothing extra for `normal`.

## Task 4: persona picker on MENU, persisted

A select next to the problem picker with the five personas. The choice
persists in `settings.preferences.persona` and rides the session record.
Changing it mid-interview is allowed and takes effect on the next turn.

Test (m4_ui, red first): select exists with five options, choice
persists to localStorage, session record carries it.

## Task 5: sprite and background rendering

`js/persona-art.js` draws the sprite pixel maps onto the portrait canvas
(two frames, idle bob, `image-rendering: pixelated`). It also applies
the persona background class to the interview screen. The portrait sits
next to the interviewer name in the chat header.

Test (m4_ui, red first): the canvas holds non-transparent pixels after
start. The frame toggles over time. Switching persona changes the canvas
palette and the screen background class.

## Task 6: UI theme pass

Vendor Press Start 2P (OFL license file alongside) as
`game/fonts/`. CSS custom properties per persona palette drive the
accent colors. Restyle buttons, inputs, panels, chat log, step tracker,
and timer HUD with chunky borders, hard shadows, and one palette per
persona. Latin text uses the pixel font. CJK falls back to sans-serif.

Test (m4_ui, red first): the font face loads. The body font family
includes it. The persona CSS variables change on switch. The hard
shadow and the border width are present on the primary controls.

## Task 7: voice wiring in the engine

During streaming, feed the landed text delta to the blip voice. Blips
fire only for newly landed characters. The mute toggle lives near the
timer HUD. Headless runs keep audio muted by default in tests.

Test (m4_ui, red first): with a fake AudioContext, a streamed mock turn
creates oscillators matching the landed text. The mute toggle stops
creation and persists.

## Task 8: closing round

Full suite loop, vendor probe, coverage, crapper, deployed smoke, bump,
commits, push, and live verify. Make sure that the deployed copy passes
before the push.

## Test placement

- `game/tests/m4_units.py`: registry, blip schedule, prompt block.
- `game/tests/m4_ui.py`: picker, art, theme, voice wiring.
- `game/tests/deployed_smoke.py` gains one persona-switch case after
  the existing flow. The round-end loop makes sure that the live copy
  passes it.
