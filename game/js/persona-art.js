// Draws the persona interview scene onto the scene canvas and applies the
// persona backdrop class and palette variables to the interview screen.
// The canvas is a 256x192 logical pixel 4:3 scene, scaled up with
// image-rendering: pixelated in CSS. Three independent timelines run
// here: the background painters redraw on the scene tick, the body idle
// bob is part of the painted bust on the same fixed period, and the
// mouth overlay blits Aseprite-authored states only while the
// interviewer's speech streams (engine.js flips the talking flag).
// The loop follows the interview screen: app.js stops it on every other
// screen, so no timer outlives it.

import { getPersona } from './personas.js?v=37';
import { getScene, SCENE_W, SCENE_H, CYCLE, bustBobOffset } from './scenes.js?v=37';
import { loadMouthSheet, pickMouthFrame, drawMouth } from './mouth.js?v=37';

let frameTimer = null;
let frame = 0;
let talking = false;
let mouthElapsed = 0;

// The patch origin matches scenes.js paintBust: bust at (12, 66), cells
// at 3x, mouth patch window at bust-local (11, 9).
const MOUTH_X = 12 + 11 * 3;
const MOUTH_Y = 66 + 9 * 3;

export function drawScene(canvas, personaId, frameIndex = 0) {
  const scene = getScene(personaId);
  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  scene.paint(ctx, ((frameIndex % CYCLE) + CYCLE) % CYCLE);
}

export function applyPersona(screenEl, personaId) {
  const persona = getPersona(personaId);
  screenEl.className = screenEl.className
    .replace(/persona-[a-z]+/g, '').trim();
  screenEl.classList.add(`persona-${personaId === 'normal' ? 'normal' : personaId}`);
  screenEl.style.setProperty('--accent', persona.palette.accent);
  screenEl.style.setProperty('--panel-bg', persona.palette.bg);
  screenEl.style.setProperty('--panel-ink', persona.palette.ink);
  return persona;
}

// The engine sets the flag when an interviewer stream starts and clears
// it in its finally block, next to the existing blip feed. The hook
// updates here too, so a reader between scene ticks sees the transition
// instead of the previous tick's state.
export function setTalking(value) {
  talking = value === true;
  if (!talking) mouthElapsed = 0;
  window.__mouth = { talking, frame: pickMouthFrame(talking, mouthElapsed) };
}

export function startSceneLoop(canvas, personaId, fps = 8) {
  stopSceneLoop();
  frame = 0;
  talking = false;
  mouthElapsed = 0;
  let sheet = null;
  loadMouthSheet().then((img) => {
    sheet = img;
    if (frameTimer) tickScene(canvas, personaId, sheet);
  }).catch(() => {});
  const tickMs = Math.round(1000 / fps);
  const drawTick = () => tickScene(canvas, personaId, sheet);
  drawTick();
  frameTimer = setInterval(() => {
    frame = (frame + 1) % CYCLE;
    if (talking) mouthElapsed += tickMs;
    drawTick();
  }, tickMs);
}

function tickScene(canvas, personaId, sheet) {
  drawScene(canvas, personaId, frame);
  const state = pickMouthFrame(talking, mouthElapsed);
  if (sheet && state > 0) {
    drawMouth(canvas.getContext('2d'), sheet, personaId, state,
      MOUTH_X, MOUTH_Y + bustBobOffset(frame));
  }
  window.__mouth = { talking, frame: state };
}

export function stopSceneLoop() {
  if (frameTimer) {
    clearInterval(frameTimer);
    frameTimer = null;
  }
}

export { SCENE_W, SCENE_H };
