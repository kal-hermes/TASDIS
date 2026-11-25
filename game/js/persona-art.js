// Draws the persona sprite pixel maps onto the portrait canvas and applies
// the persona backdrop class and palette variables to the interview screen.
// The canvas is 16x16 game pixels, scaled up with image-rendering: pixelated
// in CSS. The idle bob alternates the two frames on an interval.

import { getPersona } from './personas.js?v=34';

let frameTimer = null;
let frame = 0;

export function drawSprite(canvas, personaId, frameIndex = 0) {
  const persona = getPersona(personaId);
  const map = persona.sprite[frameIndex % persona.sprite.length];
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  for (let y = 0; y < map.length; y += 1) {
    const row = map[y];
    for (let x = 0; x < row.length; x += 1) {
      const key = row[x];
      if (key === '.') continue;
      ctx.fillStyle = persona.palette[key] || persona.palette.uniform;
      ctx.fillRect(x, y, 1, 1);
    }
  }
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

export function startPortraitLoop(canvas, personaId, intervalMs = 600) {
  stopPortraitLoop();
  frame = 0;
  drawSprite(canvas, personaId, frame);
  frameTimer = setInterval(() => {
    frame = (frame + 1) % 2;
    drawSprite(canvas, personaId, frame);
  }, intervalMs);
}

export function stopPortraitLoop() {
  if (frameTimer) {
    clearInterval(frameTimer);
    frameTimer = null;
  }
}
