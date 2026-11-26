// The interviewer mouth states, authored in Aseprite (the pixel-plugin
// skills) and exported as one horizontal spritesheet: 15 frames of 10x7,
// five personas in registry order, three states each (closed, half,
// open). The closed state draws nothing; the runtime blits the half and
// open cells over the painted bust only while the interviewer's speech
// text is streaming. This module keeps the atlas constants and the pure
// frame selection, so tests replay the state machine without a canvas.

export const MOUTH_META = {
  frameW: 10,
  frameH: 7,
  talkMs: 90,
  scale: 3,
  personas: {
    klingon: { base: 0 },
    vulcan: { base: 3 },
    pirate: { base: 6 },
    cowboy: { base: 9 },
    normal: { base: 12 },
  },
};

// Idle always shows the closed state. Talking cycles half and open on
// the tagged duration, deterministically in the elapsed milliseconds.
export function pickMouthFrame(talking, elapsedMs) {
  if (!talking) return 0;
  return 1 + (Math.floor(elapsedMs / MOUTH_META.talkMs) % 2);
}

let sheetPromise = null;

export function loadMouthSheet(base = '.') {
  if (!sheetPromise) {
    sheetPromise = new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = `${base}/img/mouth-states.png?v=37`;
    });
  }
  return sheetPromise;
}

export function drawMouth(ctx, sheet, personaId, stateIndex, ox, oy) {
  const persona = MOUTH_META.personas[personaId];
  if (!persona || stateIndex <= 0) return;
  const s = MOUTH_META.scale;
  ctx.drawImage(sheet,
    (persona.base + stateIndex) * MOUTH_META.frameW, 0,
    MOUTH_META.frameW, MOUTH_META.frameH,
    ox, oy, MOUTH_META.frameW * s, MOUTH_META.frameH * s);
}
