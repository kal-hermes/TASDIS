// The 16-bit era interview scenes (DESIGN.md section 11). One painted,
// animated scene per persona: a large bust in the foreground and a
// persona-matching background with a scripted set piece. Everything is
// drawn with fillRect at paint time, deterministically in the frame
// number: the same scene and frame always paint the same pixels, so the
// unit suite can replay a frame through a recording context.
//
// Canvas: 256x192 logical pixels (4:3), scaled up by CSS with
// image-rendering: pixelated. The loop runs at 8 frames per second and
// every scene cycle is CYCLE frames.

export const SCENE_W = 256;
export const SCENE_H = 192;
export const CYCLE = 150;

/* ---- the paint kit ---------------------------------------------------- */

function rect(c, x, y, w, h, color) {
  c.fillStyle = color;
  c.fillRect(x, y, w, h);
}

function vGrad(c, x, y, w, h, colors) {
  const band = Math.max(1, Math.floor(h / colors.length));
  for (let i = 0; i < colors.length; i += 1) {
    const top = y + i * band;
    const tall = (i === colors.length - 1) ? (y + h - top) : band;
    rect(c, x, top, w, tall, colors[i]);
  }
}

function dither(c, x, y, w, h, c1, c2) {
  const cell = 4;
  for (let yy = y; yy < y + h; yy += cell) {
    for (let xx = x; xx < x + w; xx += cell) {
      const bw = Math.min(cell, x + w - xx);
      const bh = Math.min(cell, y + h - yy);
      const even = ((xx / cell) + (yy / cell)) % 2 === 0;
      rect(c, xx, yy, bw, bh, even ? c1 : c2);
    }
  }
}

// A filled disc made of 2px cells: the round shape of the 16-bit era.
function blob(c, cx, cy, r, color) {
  for (let dy = -r; dy <= r; dy += 2) {
    for (let dx = -r; dx <= r; dx += 2) {
      if (dx * dx + dy * dy <= r * r) rect(c, cx + dx, cy + dy, 2, 2, color);
    }
  }
}

/* ---- the bust builder --------------------------------------------------
   Busts are 32x40 character cells drawn at 3x (96x120 pixels) in the
   foreground. Each bust is built by calls, then joined into pixel-map
   rows and self-checked, so a drawing bug fails loudly at import. */

function bustRows(grid) {
  const rows = grid.map((row) => row.join(''));
  if (rows.length !== 40 || rows.some((r) => r.length !== 32)) {
    throw new Error('bust map must be 40 rows of 32 cells');
  }
  return rows;
}

function buildBust(draw) {
  const g = Array.from({ length: 40 }, () => Array(32).fill('.'));
  const put = (x, y, k) => {
    if (x >= 0 && x < 32 && y >= 0 && y < 40) g[y][x] = k;
  };
  const hline = (x0, x1, y, k) => { for (let x = x0; x <= x1; x += 1) put(x, y, k); };
  const vline = (x, y0, y1, k) => { for (let y = y0; y <= y1; y += 1) put(x, y, k); };
  const box = (x0, y0, x1, y1, k) => {
    for (let y = y0; y <= y1; y += 1) hline(x0, x1, y, k);
  };
  draw({ put, hline, vline, box });
  return bustRows(g);
}

// The shared face: skin, eyes, nose, mouth. Overlays add the persona.
function face(t, d) {
  d.box(9, 4, 22, 6, t.skin);
  d.box(8, 7, 23, 12, t.skin);
  d.hline(10, 21, 13, t.skin);
  d.hline(12, 19, 14, t.skin);
  d.hline(9, 22, 3, t.line);
  d.vline(8, 7, 13, t.line);
  d.vline(23, 7, 13, t.line);
  d.hline(11, 20, 14, t.line);
  d.box(10, 8, 11, 9, t.eyeW); d.box(12, 8, 12, 9, t.eye);
  d.box(19, 8, 20, 9, t.eyeW); d.box(21, 8, 21, 9, t.eye);
  d.box(15, 9, 16, 10, t.shade);
  d.hline(13, 18, 11, t.mouth);
  d.box(13, 16, 18, 17, t.skin);
  d.vline(13, 16, 17, t.shade);
  d.vline(18, 16, 17, t.shade);
}

const BUSTS = {
  klingon: buildBust((d) => {
    const t = {
      line: 'O', skin: 'S', shade: 's', hair: 'H', cloth: 'C', cloth2: 'c',
      accent: 'A', accent2: 'a', eyeW: 'W', eye: 'E', mouth: 'M', ridge: 'G',
    };
    face(t, d);
    // the ridge crest over the crown, and forehead ridge lines
    d.box(12, 1, 19, 2, t.ridge);
    d.hline(10, 21, 3, t.ridge);
    d.vline(13, 4, 6, t.ridge);
    d.vline(16, 4, 6, t.ridge);
    d.vline(19, 4, 6, t.ridge);
    // heavy angled brows
    d.hline(9, 13, 7, t.hair);
    d.hline(18, 22, 7, t.hair);
    d.put(14, 8, t.hair); d.put(17, 8, t.hair);
    // shaved sides and the goatee
    d.box(8, 4, 9, 13, t.hair);
    d.box(22, 4, 23, 13, t.hair);
    d.box(12, 12, 19, 15, t.hair);
    d.hline(14, 17, 12, t.mouth);
    d.hline(14, 17, 16, t.hair);
    // armor: pauldrons, chest, sash
    d.box(2, 18, 29, 22, t.cloth);
    d.hline(2, 29, 18, t.line);
    d.hline(2, 29, 22, t.cloth2);
    d.put(3, 17, t.cloth); d.put(28, 17, t.cloth);
    d.box(4, 23, 27, 39, t.cloth);
    d.hline(4, 27, 23, t.line);
    d.box(20, 30, 27, 39, t.cloth2);
    for (let y = 23; y <= 39; y += 1) {
      const cx = 9 + Math.floor(((y - 23) * 13) / 16);
      d.hline(cx - 1, cx + 1, y, y % 3 === 2 ? t.accent2 : t.accent);
    }
    d.hline(4, 27, 37, t.accent2);
  }),

  vulcan: buildBust((d) => {
    const t = {
      line: 'O', skin: 'S', shade: 's', hair: 'H', cloth: 'C', cloth2: 'c',
      accent: 'A', accent2: 'a', eyeW: 'W', eye: 'E', mouth: 'M',
    };
    face(t, d);
    // the straight bowl cut with side locks down past the jaw
    d.box(7, 1, 24, 5, t.hair);
    d.hline(7, 24, 6, t.line);
    d.vline(7, 6, 16, t.hair);
    d.vline(24, 6, 16, t.hair);
    d.put(6, 9, t.skin); d.put(25, 9, t.skin);
    // level brows, calm mouth
    d.hline(9, 13, 7, t.hair);
    d.hline(18, 22, 7, t.hair);
    d.hline(14, 17, 12, t.mouth);
    // the high collar with the idic badge
    d.box(2, 17, 29, 20, t.cloth);
    d.hline(2, 29, 17, t.line);
    d.put(4, 16, t.cloth); d.put(27, 16, t.cloth);
    d.box(14, 18, 17, 19, t.accent);
    d.box(4, 21, 27, 39, t.cloth);
    d.hline(4, 27, 21, t.line);
    d.vline(15, 21, 39, t.cloth2);
    d.vline(16, 21, 39, t.cloth2);
    d.box(23, 24, 25, 26, t.accent2);
  }),

  pirate: buildBust((d) => {
    const t = {
      line: 'O', skin: 'S', shade: 's', hair: 'H', cloth: 'C', cloth2: 'c',
      accent: 'A', accent2: 'a', eyeW: 'W', eye: 'E', mouth: 'M', gold: 'G',
    };
    face(t, d);
    // the tricorn: crown, gold trim, upturned brim corners
    d.box(10, 1, 21, 4, t.hair);
    d.hline(10, 21, 1, t.gold);
    d.box(4, 4, 7, 6, t.hair);
    d.box(24, 4, 27, 6, t.hair);
    d.hline(8, 23, 5, t.hair);
    d.hline(4, 27, 6, t.line);
    // the eyepatch and its strap
    d.hline(8, 22, 7, t.line);
    d.box(18, 8, 21, 9, t.line);
    // beard, mustache
    d.box(11, 12, 20, 17, t.hair);
    d.hline(12, 19, 11, t.hair);
    d.hline(14, 17, 13, t.mouth);
    // the coat: lapels, shirt, gold buttons
    d.box(2, 18, 29, 22, t.cloth);
    d.hline(2, 29, 18, t.line);
    d.box(4, 23, 27, 39, t.cloth);
    d.hline(4, 27, 23, t.line);
    d.vline(11, 23, 32, t.gold);
    d.vline(20, 23, 32, t.gold);
    d.box(13, 23, 18, 30, t.cloth2);
    d.put(15, 25, t.gold); d.put(16, 27, t.gold); d.put(15, 29, t.gold);
    d.hline(13, 18, 32, t.accent2);
  }),

  cowboy: buildBust((d) => {
    const t = {
      line: 'O', skin: 'S', shade: 's', hair: 'H', cloth: 'C', cloth2: 'c',
      accent: 'A', accent2: 'a', eyeW: 'W', eye: 'E', mouth: 'M',
    };
    face(t, d);
    // the hat: creased crown, wide brim with a shaded edge
    d.box(11, 1, 20, 5, t.hair);
    d.vline(15, 1, 5, t.accent2);
    d.hline(4, 27, 6, t.hair);
    d.hline(4, 27, 7, t.accent2);
    // squint, sun shade across the cheeks, mustache
    d.hline(9, 12, 7, t.hair);
    d.hline(19, 22, 7, t.hair);
    d.hline(9, 11, 10, t.shade);
    d.hline(20, 22, 10, t.shade);
    d.hline(12, 19, 11, t.hair);
    d.hline(14, 17, 12, t.mouth);
    // the bandana over the neck
    d.box(11, 15, 20, 17, t.accent);
    d.box(13, 18, 18, 18, t.accent);
    d.box(14, 19, 17, 20, t.accent2);
    // cream shirt, brown vest both sides
    d.box(4, 21, 27, 39, t.cloth);
    d.hline(4, 27, 21, t.line);
    d.box(4, 21, 9, 39, t.cloth2);
    d.box(22, 21, 27, 39, t.cloth2);
    d.put(14, 23, t.accent2); d.put(14, 27, t.accent2); d.put(14, 31, t.accent2);
  }),

  normal: buildBust((d) => {
    const t = {
      line: 'O', skin: 'S', shade: 's', hair: 'H', cloth: 'C', cloth2: 'c',
      accent: 'A', accent2: 'a', eyeW: 'W', eye: 'E', mouth: 'M', frame: 'F',
    };
    face(t, d);
    // thinning hair on the sides only
    d.box(8, 3, 10, 6, t.hair);
    d.box(21, 3, 23, 6, t.hair);
    // glasses: two frames and the bridge
    d.hline(9, 13, 7, t.frame);
    d.hline(9, 13, 9, t.frame);
    d.vline(9, 7, 9, t.frame);
    d.vline(13, 7, 9, t.frame);
    d.hline(18, 22, 7, t.frame);
    d.hline(18, 22, 9, t.frame);
    d.vline(18, 7, 9, t.frame);
    d.vline(22, 7, 9, t.frame);
    d.hline(13, 18, 8, t.frame);
    d.hline(13, 18, 12, t.mouth);
    // shirt and collar, tie, suspenders
    d.box(4, 18, 27, 39, t.cloth);
    d.hline(4, 27, 18, t.line);
    d.hline(12, 19, 17, t.cloth2);
    d.box(15, 17, 17, 18, t.accent);
    d.box(15, 19, 17, 27, t.accent);
    d.box(16, 28, 16, 29, t.accent);
    d.box(9, 19, 10, 39, t.accent2);
    d.box(21, 19, 22, 39, t.accent2);
    // the coffee mug in the breast pocket
    d.box(22, 26, 25, 29, t.eyeW);
    d.vline(22, 26, 29, t.cloth2);
    d.hline(23, 24, 27, t.mouth);
  }),
};

const PAL = {
  O: '#141018', S: '', s: '', H: '', C: '', c: '',
  A: '', a: '', W: '#e8e4d8', E: '#14141a', M: '', G: '', F: '#141018',
};

function mapColors(colors) {
  return { ...PAL, ...colors };
}

/* ---- the scenes -------------------------------------------------------- */

function paintBust(c, personaId, frame, colors, px = 3, ox = 12, oy = 66) {
  const bob = bustBobOffset(frame);
  const rows = BUSTS[personaId];
  const map = mapColors(colors);
  for (let y = 0; y < rows.length; y += 1) {
    const row = rows[y];
    for (let x = 0; x < row.length; x += 1) {
      const key = row[x];
      if (key === '.') continue;
      const color = map[key];
      if (color) rect(c, ox + x * px, oy + y * px + bob, px, px, color);
    }
  }
}

const SCENES = {
  /* Klingon captain: the bridge of a Klingon ship in battle. The viewport
     shows stars, an explosion blooms on a fixed beat and the walls shake. */
  klingon: {
    palette: {
      wall1: '#170a0f', wall2: '#2b1018', wall3: '#3a1520',
      view: '#050810', star: '#cfd8ff', frame: '#4a4a52',
      stripe1: '#5a1c1c', stripe2: '#2b1018', floor: '#200a0e',
      grate: '#160608', edge: '#4a2430', fire: '#ffd75e', fire2: '#ff9d2e',
      O: '#140a0e', S: '#c98d5e', s: '#a56d42', H: '#1d1418',
      C: '#4a4a52', c: '#33333b', A: '#7a1c1c', a: '#521212',
      M: '#8a4434', G: '#6a4530',
    },
    skin: '#c98d5e',
    paint(c, frame) {
      const p = this.palette;
      const flash = frame >= 68 && frame <= 80;
      const shake = flash ? ((Math.floor(frame / 2) % 2) * 2) : 0;
      vGrad(c, 0, shake, SCENE_W, SCENE_H - shake,
        [p.wall1, p.wall2, p.wall3]);
      // the viewport with drifting stars
      rect(c, 148, 24 + shake, 96, 76, p.frame);
      rect(c, 152, 28 + shake, 88, 68, p.view);
      for (let i = 0; i < 30; i += 1) {
        const sx = 154 + ((i * 37) % 84);
        const sy = 30 + shake + ((i * 53) % 64);
        const blink = (i + (Math.floor(frame / 3))) % 7 === 0;
        rect(c, sx, sy, 2, 2, blink ? '#6a74a0' : p.star);
      }
      // warning stripes and pipes on the wall
      dither(c, 0, 20 + shake, 26, 100, p.stripe1, p.stripe2);
      rect(c, 30, 36 + shake, 8, 90, p.frame);
      rect(c, 27, 124 + shake, 14, 6, p.frame);
      rect(c, 120, 44 + shake, 6, 74, p.frame);
      rect(c, 117, 116 + shake, 12, 6, p.frame);
      // a status console with blinking indicator lamps
      rect(c, 40, 118 + shake, 88, 26, p.frame);
      rect(c, 44, 122 + shake, 80, 18, '#12080c');
      for (let i = 0; i < 10; i += 1) {
        const lx = 48 + i * 8;
        const on = (i + Math.floor(frame / 4)) % 3;
        const lamp = on === 0 ? '#ff4a3c' : (on === 1 ? '#ffaa3c' : '#4ad24a');
        rect(c, lx, 126 + shake, 5, 5, lamp);
      }
      rect(c, 48, 134 + shake, 72, 4, '#ff8a2e');
      // the floor with grating
      rect(c, 0, 150, SCENE_W, 42, p.floor);
      rect(c, 0, 150, SCENE_W, 4, p.edge);
      for (let x = 0; x < SCENE_W; x += 16) rect(c, x, 156, 2, 36, p.grate);
      // the explosion in the viewport
      if (flash) {
        const r = (frame - 68) * 2 + 6;
        blob(c, 196, 62 + shake, r, p.fire);
        blob(c, 196, 62 + shake, Math.max(2, r - 8), p.fire2);
      }
      paintBust(c, 'klingon', frame, {
        O: p.O, S: p.S, s: p.s, H: p.H, C: p.C, c: p.c,
        A: p.A, a: p.a, W: '#e8e4d8', E: '#14141a', M: p.M, G: p.G,
      });
    },
  },

  /* Vulcan commander: the calm bridge of a Vulcan ship. A crew member
     spills plomeek soup on a console, sparks fly, the crew member wipes
     it clean and carries on as though nothing happened. */
  vulcan: {
    palette: {
      wall1: '#12233a', wall2: '#1b3252', wall3: '#24406a',
      panel: '#0e1c30', view: '#06101c', star: '#cfd8ff', frame: '#3a5a88',
      console: '#173355', consoleEdge: '#2a4a78', key1: '#4a7ab8',
      key2: '#7ac47a', crew1: '#23364e', crewSkin: '#d9b08a',
      soup: '#7a4a21', spark: '#ffe95e',
      O: '#101820', S: '#d9b08a', s: '#b08a5e', H: '#16161c',
      C: '#23364e', c: '#182a40', A: '#8fb8d8', a: '#5a7a9a',
      M: '#8a5a4a',
    },
    skin: '#d9b08a',
    paint(c, frame) {
      const p = this.palette;
      vGrad(c, 0, 0, SCENE_W, SCENE_H, [p.wall1, p.wall2, p.wall3]);
      for (let x = 0; x < SCENE_W; x += 32) rect(c, x, 20, 2, 120, p.panel);
      rect(c, 148, 24, 96, 76, p.frame);
      rect(c, 152, 28, 88, 68, p.view);
      for (let i = 0; i < 26; i += 1) {
        const sx = 154 + (((i * 41) + Math.floor(frame / 3)) % 84);
        const sy = 30 + ((i * 59) % 64);
        rect(c, sx, sy, 2, 2, p.star);
      }
      // the operations console along the front
      rect(c, 118, 140, 138, 52, p.console);
      rect(c, 118, 140, 138, 4, p.consoleEdge);
      for (let i = 0; i < 14; i += 1) {
        const kx = 126 + i * 9;
        rect(c, kx, 148, 5, 4, i % 4 === 0 ? p.key2 : p.key1);
      }
      // the crew member at the console, working
      const bob = (Math.floor(frame / 8) % 2);
      const cx = 168;
      rect(c, cx, 108 + bob, 14, 12, p.crewSkin);
      rect(c, cx + 2, 102 + bob, 10, 6, '#1a1a22');
      rect(c, cx - 2, 120 + bob, 18, 20, p.crew1);
      const wiping = frame >= 96 && frame <= 108;
      const pouring = frame >= 80 && frame <= 92;
      const armY = 124 + bob + (wiping ? -4 : 0);
      rect(c, cx + (wiping ? -8 : 12), armY, 10, 5, p.crew1);
      if (pouring) rect(c, cx + 12, 118 + bob, 8, 6, '#d8d2c0');
      // the spill: the puddle grows, sparks, then is wiped away
      if (frame >= 84 && frame <= 95) {
        const r = Math.min(11, (frame - 82) * 2);
        blob(c, 196, 140, r, p.soup);
      }
      if (frame >= 91 && frame <= 95) {
        for (let i = 0; i < 6; i += 1) {
          rect(c, 184 + ((i * 13) % 30), 126 + ((i * 7) % 12), 2, 2, p.spark);
        }
      }
      if (frame >= 96 && frame <= 108) {
        const r = Math.max(2, 22 - (frame - 96) * 2);
        blob(c, 196, 140, r, p.soup);
      }
      paintBust(c, 'vulcan', frame, {
        O: p.O, S: p.S, s: p.s, H: p.H, C: p.C, c: p.c,
        A: p.A, a: p.a, W: '#e8e4d8', E: '#14141a', M: p.M,
      });
    },
  },

  /* Texas rancher: a sunny ranch with a farmhouse, grazing stock behind
     fences, and one cow with an occasional visible problem. */
  cowboy: {
    palette: {
      sky1: '#8ec9ee', sky2: '#a9d8f2', sky3: '#c4e4f6',
      sun: '#fff3ae', sunCore: '#fffdf0', cloud: '#f4f9ff',
      house: '#7a5a3a', roof: '#5a3f28', ground: '#7ea35a',
      ground2: '#6a8f4c', fence: '#6b4a2c', cow: '#e8e4d8',
      spot: '#3a3a3a', horse: '#6b4a2c', puff: '#9fd26a', puff2: '#b8e58a',
      O: '#3a2416', S: '#d9a06b', s: '#b07e4e', H: '#5a3f28',
      C: '#e8dfc8', c: '#6b4a2c', A: '#a33327', a: '#7a241c',
      W: '#e8e4d8', E: '#14141a', M: '#8a5a4a',
    },
    skin: '#d9a06b',
    paint(c, frame) {
      const p = this.palette;
      vGrad(c, 0, 0, SCENE_W, 122, [p.sky1, p.sky2, p.sky3]);
      blob(c, 34, 28, 12, p.sun);
      blob(c, 34, 28, 7, p.sunCore);
      for (let i = 0; i < 3; i += 1) {
        const clx = ((60 + i * 90 + Math.floor(frame / 2)) % 320) - 30;
        blob(c, clx, 22 + i * 14, 10, p.cloud);
        blob(c, clx + 12, 24 + i * 14, 7, p.cloud);
      }
      // the farmhouse in the distance
      rect(c, 192, 98, 44, 24, p.house);
      rect(c, 188, 90, 52, 8, p.roof);
      rect(c, 210, 106, 8, 16, p.roof);
      rect(c, 198, 104, 8, 8, '#3a2a1c');
      // the pasture and the fences
      rect(c, 0, 122, SCENE_W, 70, p.ground);
      dither(c, 0, 160, SCENE_W, 32, p.ground, p.ground2);
      for (let x = 4; x < SCENE_W; x += 24) rect(c, x, 112, 3, 22, p.fence);
      rect(c, 0, 116, SCENE_W, 3, p.fence);
      rect(c, 0, 126, SCENE_W, 3, p.fence);
      // grazing stock
      const graze = Math.floor(frame / 16) % 2;
      rect(c, 56, 134 + graze, 26, 13, p.cow);
      rect(c, 60, 130 + graze, 10, 6, p.spot);
      rect(c, 58, 147, 4, 6, p.cow); rect(c, 74, 147, 4, 6, p.cow);
      rect(c, 50, 136 + graze, 8, 8, p.cow);
      rect(c, 140, 142 - graze, 26, 13, p.cow);
      rect(c, 148, 144 - graze, 8, 5, p.spot);
      rect(c, 142, 155, 4, 6, p.cow); rect(c, 158, 155, 4, 6, p.cow);
      rect(c, 166, 138 - graze, 8, 9, p.cow);
      rect(c, 206, 130, 22, 16, p.horse);
      rect(c, 224, 124, 6, 10, p.horse);
      rect(c, 208, 146, 4, 7, p.horse); rect(c, 222, 146, 4, 7, p.horse);
      // the one cow's occasional contribution
      if (frame >= 114 && frame <= 126) {
        const r = (frame - 112);
        blob(c, 176, 150, r, p.puff);
        blob(c, 176, 150, Math.max(2, r - 4), p.puff2);
      }
      paintBust(c, 'cowboy', frame, {
        O: p.O, S: p.S, s: p.s, H: p.H, C: p.C, c: p.c,
        A: p.A, a: p.a, W: p.W, E: p.E, M: p.M,
      });
    },
  },

  /* Pirate captain: the deck of a barque in a storm at night. Rain and
     lightning, a gentle rock, and two kraken tentacles gripping the
     bulwark. */
  pirate: {
    palette: {
      sky1: '#141a2e', sky2: '#1b2440', sky3: '#232e55',
      flash: '#e8f2ff', bolt: '#f4f9ff', sea: '#0e1c30', wave: '#1a2c48',
      rain: '#5a6b8f', deck: '#3a2a1c', plank: '#2a1c10', rail: '#4a3624',
      railEdge: '#5a4430',      tentacle: '#3f6b5a', sucker: '#6b9a84',
      O: '#14101a', S: '#d9a06b', s: '#b07e4e', H: '#2a2130',
      C: '#4a1c30', c: '#331423', A: '#c9a227', a: '#14141a',
      W: '#e8e4d8', E: '#14141a', M: '#8a5a4a', G: '#c9a227',
    },
    skin: '#d9a06b',
    paint(c, frame) {
      const p = this.palette;
      const rock = Math.floor(frame / 8) % 2;
      vGrad(c, 0, 0, SCENE_W, 122 + rock, [p.sky1, p.sky2, p.sky3]);
      rect(c, 0, 112 + rock, SCENE_W, 34, p.sea);
      for (let x = 0; x < SCENE_W; x += 16) {
        rect(c, x + (Math.floor(frame / 2) % 16), 118 + rock + (x % 32) / 8, 10, 2, p.wave);
      }
      // the lightning: the sky flashes, then a bolt
      if (frame >= 80 && frame <= 84) {
        rect(c, 0, 0, SCENE_W, 114, p.flash);
        rect(c, 60, 0, 6, 30, p.bolt);
        rect(c, 78, 30, 6, 26, p.bolt);
        rect(c, 62, 56, 6, 26, p.bolt);
        rect(c, 74, 82, 6, 30, p.bolt);
      }
      // the deck and the bulwark
      rect(c, 0, 128 + rock, SCENE_W, 14, p.rail);
      rect(c, 0, 128 + rock, SCENE_W, 3, p.railEdge);
      rect(c, 0, 142 + rock, SCENE_W, 50, p.deck);
      for (let y = 148; y < 192; y += 12) rect(c, 0, y + rock, SCENE_W, 2, p.plank);
      for (let x = 8; x < SCENE_W; x += 32) {
        rect(c, x, 128 + rock, 4, 14, p.railEdge);
      }
      // the kraken: two tentacles gripping OVER the bulwark
      const sway = Math.floor(frame / 8) % 2;
      rect(c, 216 + sway, 100, 10, 30, p.tentacle);
      rect(c, 206 + sway, 100, 14, 10, p.tentacle);
      rect(c, 200 + sway, 106, 10, 10, p.tentacle);
      rect(c, 204 + sway, 132, 12, 12, p.tentacle);
      rect(c, 234 - sway, 112, 10, 28, p.tentacle);
      rect(c, 240 - sway, 106, 12, 10, p.tentacle);
      rect(c, 238 - sway, 132, 12, 12, p.tentacle);
      rect(c, 216 + sway, 106, 3, 3, p.sucker);
      rect(c, 218 + sway, 116, 3, 3, p.sucker);
      rect(c, 240 - sway, 118, 3, 3, p.sucker);
      // the rain
      for (let i = 0; i < 36; i += 1) {
        const rx = (i * 37 + frame * 3) % SCENE_W;
        const ry = (i * 23 + frame * 9) % 150;
        rect(c, rx, ry, 1, 7, p.rain);
      }
      paintBust(c, 'pirate', frame, {
        O: p.O, S: p.S, s: p.s, H: p.H, C: p.C, c: p.c,
        A: p.A, a: p.a, W: p.W, E: p.E, M: p.M, G: p.G,
      });
    },
  },

  /* Tech interviewer: a 90s cubicle office. The manager in the foreground;
     in his cubicle the quiet colleague keeps his red stapler close and
     pats it now and then. */
  normal: {
    palette: {
      wall: '#d8cfb8', trim: '#c4b89c', base: '#a89a78', ceil: '#efe9d8',
      light: '#fffbe6', lightEdge: '#d8d2be', part: '#8a94a8',
      partEdge: '#9aa4b8', desk: '#7a6a4a', crt: '#3a3f4a',
      screen: '#7ac47a', keyb: '#4a4f5a', paper: '#f4f0e0',
      miltonHair: '#6b4a2c', miltonBody: '#8a6a4a', miltonSkin: '#e8b88a',
      stapler: '#c81e1e', staplerTop: '#e8443c', chair: '#2a2e38',
      O: '#4a4038', S: '#eab98c', s: '#c4946a', H: '#5a4a3a',
      C: '#f0eee6', c: '#c4b89c', A: '#4a5a8a', a: '#8a3030',
      W: '#e8e4d8', E: '#14141a', M: '#8a5a4a', F: '#14141a',
    },
    skin: '#eab98c',
    paint(c, frame) {
      const p = this.palette;
      rect(c, 0, 0, SCENE_W, SCENE_H, p.wall);
      rect(c, 0, 0, SCENE_W, 10, p.ceil);
      rect(c, 0, 6, 70, 8, p.light);
      rect(c, 150, 6, 70, 8, p.light);
      rect(c, 0, 6, 70, 2, p.lightEdge);
      rect(c, 150, 6, 70, 2, p.lightEdge);
      rect(c, 0, 44, SCENE_W, 2, p.trim);
      rect(c, 0, 148, SCENE_W, 6, p.base);
      // the cubicle partitions
      rect(c, 96, 56, 10, 122, p.part);
      rect(c, 96, 56, 10, 4, p.partEdge);
      rect(c, 168, 80, 10, 98, p.part);
      rect(c, 168, 80, 10, 4, p.partEdge);
      rect(c, 0, 60, 10, 118, p.part);
      // the first desk with a CRT
      rect(c, 24, 116, 58, 10, p.desk);
      rect(c, 38, 90, 32, 26, p.crt);
      rect(c, 42, 94, 24, 17, p.screen);
      rect(c, 40, 118, 30, 5, p.keyb);
      rect(c, 86, 106, 14, 10, p.paper);
      const chairBob = Math.floor(frame / 16) % 2;
      rect(c, 20, 132 + chairBob, 18, 20, p.chair);
      // the quiet colleague's booth: desk, CRT, and the red stapler
      rect(c, 186, 122, 62, 10, p.desk);
      rect(c, 196, 100, 26, 22, p.crt);
      rect(c, 200, 104, 18, 14, p.screen);
      rect(c, 232, 112, 6, 10, p.miltonSkin);
      rect(c, 228, 106, 12, 8, p.miltonHair);
      rect(c, 226, 96, 16, 10, p.miltonSkin);
      rect(c, 229, 99, 10, 3, '#3a3f4a');
      rect(c, 228, 92, 14, 6, p.miltonHair);
      rect(c, 224, 106, 18, 16, p.miltonBody);
      const pat = frame >= 96 && frame <= 106;
      rect(c, 236, pat ? 114 : 112, 8, 4, p.miltonSkin);
      rect(c, 208, 114, 12, 6, p.stapler);
      rect(c, 210, 112, 8, 3, p.staplerTop);
      if (pat) rect(c, 209, 113, 2, 5, p.staplerTop);
      rect(c, 244, 116, 10, 6, p.paper);
      rect(c, 190, 136, 16, 22, p.chair);
      paintBust(c, 'normal', frame, {
        O: p.O, S: p.S, s: p.s, H: p.H, C: p.C, c: p.c,
        A: p.A, a: p.a, W: p.W, E: p.E, M: p.M, F: p.F,
      });
    },
  },
};

const IDS = Object.keys(SCENES);

// The bust grids and the bob offset are shared with the mouth patch
// blit (persona-art.js) and the Aseprite authoring generator: the patch
// must cover and move with exactly the cells the bust paints.
export { BUSTS };

export function bustBobOffset(frame) {
  return (Math.floor(frame / 8) % 2) * 2;
}

export function getScene(personaId) {
  const scene = SCENES[personaId];
  if (!scene) throw new Error(`no scene for persona ${personaId}`);
  return scene;
}

export const SCENE_IDS = IDS;
