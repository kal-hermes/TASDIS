// Draws the persona interview scene onto the scene canvas and applies the
// persona backdrop class and palette variables to the interview screen.
// The canvas is a 256x192 logical pixel 4:3 scene, scaled up with
// image-rendering: pixelated in CSS. The scene repaints at 8 frames per
// second; the loop follows the interview screen (app.js stops it on every
// other screen).

import { getPersona } from './personas.js?v=35';
import { getScene, SCENE_W, SCENE_H, CYCLE } from './scenes.js?v=35';

let frameTimer = null;
let frame = 0;

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

export function startSceneLoop(canvas, personaId, fps = 8) {
  stopSceneLoop();
  frame = 0;
  drawScene(canvas, personaId, frame);
  frameTimer = setInterval(() => {
    frame = (frame + 1) % CYCLE;
    drawScene(canvas, personaId, frame);
  }, Math.round(1000 / fps));
}

export function stopSceneLoop() {
  if (frameTimer) {
    clearInterval(frameTimer);
    frameTimer = null;
  }
}

export { SCENE_W, SCENE_H };
