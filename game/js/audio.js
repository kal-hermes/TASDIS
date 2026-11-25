// The gibberish blip synth (DESIGN.md section 11): one short synthesized
// blip per syllable, pitch inside the persona range, persona waveform, no
// audio files. The schedule is a pure function of the text and the persona,
// so tests run offline against a fake AudioContext.

const VOWELS = /[aeiouy]+/i;

function isCjk(code) {
  return code >= 0x2e80;
}

function countSyllables(word) {
  const groups = word.match(/[aeiouy]+/gi);
  return groups ? groups.length : 1;
}

// One blip entry per syllable: { ms, hz, ch }. Latin words contribute a
// vowel-group count (a word with no vowels counts once); each CJK
// character contributes one blip.
export function scheduleBlips(text, persona) {
  const blips = [];
  const { minHz, maxHz } = persona.timbre;
  const span = maxHz - minHz + 1;
  let word = '';
  const flush = () => {
    if (!word) return;
    const ch = word[0];
    const code = ch.codePointAt(0);
    for (let i = 0; i < countSyllables(word); i += 1) {
      blips.push({ ms: 50 + (code % 51), hz: minHz + (code % span), ch });
    }
    word = '';
  };
  for (const ch of text) {
    const code = ch.codePointAt(0);
    if (isCjk(code)) {
      flush();
      blips.push({ ms: 50 + (code % 51), hz: minHz + (code % span), ch });
    } else if (/\s/.test(ch)) {
      flush();
    } else if (/[a-z0-9]/i.test(ch)) {
      word += ch;
    } else {
      flush();
    }
  }
  flush();
  return blips;
}

// Plays a schedule: one oscillator per blip, the persona waveform, a short
// gain envelope, scheduled ahead on the audio clock. `ctx` is injected so
// tests pass a fake.
export class BlipVoice {
  constructor(ctx, persona, { muted = false } = {}) {
    this.ctx = ctx;
    this.timbre = persona.timbre;
    this.persona = persona;
    this.muted = muted;
    this.cursor = 0;
  }

  // Returns the number of oscillators created. Blips are spaced on the
  // audio clock so a long schedule never overlaps the same slot.
  play(schedule) {
    if (this.muted) return 0;
    let t = this.ctx.currentTime;
    let made = 0;
    for (const blip of schedule) {
      const osc = this.ctx.createOscillator();
      osc.type = this.timbre.wave;
      osc.frequency.setValueAtTime(blip.hz, t);
      const gain = this.ctx.createGain();
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(0.08, t + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + blip.ms / 1000);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(t);
      osc.stop(t + blip.ms / 1000 + 0.02);
      t += blip.ms / 1000 + 0.03;
      made += 1;
    }
    return made;
  }
}

// The live voice the engine feeds: app.js installs it once the player
// gestures into the game. A null voice or a muted voice makes feedBlips a
// no-op, so headless runs stay silent unless a fake context is installed.
let liveVoice = null;

export function setBlipVoice(voice) {
  liveVoice = voice;
}

export function feedBlips(text) {
  if (!liveVoice || liveVoice.muted) return;
  liveVoice.play(scheduleBlips(text, liveVoice.persona));
}
