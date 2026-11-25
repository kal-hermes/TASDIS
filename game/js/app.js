// TADSDI app.js: entry point and screen routing.

import { initSettings, howToAtStart, setHowToAtStart, loadSettings,
  saveSettings } from './settings.js?v=34';
import { initEngine, startInterview, getEngineSession } from './engine.js?v=34';
import { initExport } from './export.js?v=34';
import { loadProblems } from './problems.js?v=34';
import { PERSONA_IDS, PERSONAS } from './personas.js?v=34';
import { applyPersona, startPortraitLoop, stopPortraitLoop } from './persona-art.js?v=34';
import { BlipVoice, setBlipVoice } from './audio.js?v=34';

const SCREENS = ['menu', 'briefing', 'interview', 'grading', 'feedback'];

function showScreen(name) {
  if (!SCREENS.includes(name)) {
    throw new Error(`unknown screen: ${name}`);
  }
  document.body.dataset.screen = name;
  for (const section of document.querySelectorAll('section[data-screen-name]')) {
    section.hidden = section.dataset.screenName !== name;
  }
  // Modules that show session state render again on every screen change.
  document.dispatchEvent(new CustomEvent('tadsdi:screen', { detail: name }));
}

function el(id) { return document.getElementById(id); }

// ---- feedback --------------------------------------------------------

function fillList(id, items) {
  const ul = el(id);
  ul.innerHTML = '';
  for (const text of items) {
    const li = document.createElement('li');
    li.textContent = text;
    ul.appendChild(li);
  }
}

function renderFeedback(session) {
  const grade = session.grade;
  if (!grade) return;
  const passed = grade.rows.filter((r) => r.pass).length;
  el('feedback-score').textContent =
    `Score: ${grade.score} / 10 (${passed} of 8 diagnostic rows pass)`;
  el('feedback-coverage').textContent =
    `Steps with transcript evidence: ${grade.process_coverage.join(', ')}`;

  const tbody = el('feedback-rows').querySelector('tbody');
  tbody.innerHTML = '';
  for (const row of grade.rows) {
    const tr = document.createElement('tr');
    tr.className = row.pass ? 'row-pass' : 'row-fail';
    const name = document.createElement('td');
    name.textContent = row.name;
    const verdict = document.createElement('td');
    verdict.textContent = row.pass ? 'pass' : 'fail';
    const fix = document.createElement('td');
    fix.textContent = row.fix || '';
    tr.appendChild(name);
    tr.appendChild(verdict);
    tr.appendChild(fix);
    tbody.appendChild(tr);
  }

  fillList('feedback-realism',
    grade.realism.map((r) => `${r.claim}: ${r.verdict} (${r.note})`));
  fillList('feedback-missing', grade.missing);
  fillList('feedback-artifacts',
    grade.artifact_comments.map((c) => `${c.artifact_id}: ${c.comment}`));
  el('feedback-closing').textContent = grade.closing;
}

// ---- menu ------------------------------------------------------------

let problems = new Map();

function selectedProblemSlug() {
  return el('problem-select').value;
}

function renderMenu() {
  const select = el('problem-select');
  select.innerHTML = '';
  for (const [slug, problem] of problems) {
    const opt = document.createElement('option');
    if (!problem) {
      opt.disabled = true;
      opt.textContent = `${slug} (unavailable)`;
    } else {
      opt.value = slug;
      opt.textContent = problem.title;
    }
    select.appendChild(opt);
  }
}

// Picks the slug for a new interview: the selected one, or a random one
// among the entries that loaded. Null when nothing loaded.
function pickProblemSlug(slug) {
  if (slug && !el('problem-random').checked) return slug;
  const available = [...problems.entries()].filter(([, p]) => p);
  if (!available.length) return null;
  return available[Math.floor(Math.random() * available.length)][0];
}

// ---- persona ------------------------------------------------------------

function initPersonaSelect() {
  const select = el('persona-select');
  select.innerHTML = PERSONA_IDS
    .map((id) => `<option value="${id}">${PERSONAS[id].name}</option>`)
    .join('');
  select.value = loadSettings().preferences.persona || 'normal';
  select.addEventListener('change', () => {
    const settings = loadSettings();
    settings.preferences.persona = select.value;
    saveSettings(settings);
  });
}

function savePreference(key, value) {
  const settings = loadSettings();
  settings.preferences[key] = value;
  saveSettings(settings);
}

// The voice and the portrait come up with the interview screen. The
// AudioContext is created on the start click, which is a user gesture.
let activePersona = 'normal';

function setupPersonaStage(personaId) {
  activePersona = personaId;
  const screenEl = el('screen-interview');
  const persona = applyPersona(screenEl, personaId);
  el('persona-name').textContent = persona.name;
  startPortraitLoop(el('persona-portrait'), personaId);
  const muted = loadSettings().preferences.voiceMuted === true;
  el('voice-mute').textContent = muted ? 'Voice: off' : 'Voice: on';
  const Ctx = window.AudioContext;
  if (Ctx) setBlipVoice(new BlipVoice(new Ctx(), persona, { muted }));
}

function onVoiceMuteClick() {
  const muted = loadSettings().preferences.voiceMuted !== true;
  savePreference('voiceMuted', muted);
  el('voice-mute').textContent = muted ? 'Voice: off' : 'Voice: on';
  const Ctx = window.AudioContext;
  if (Ctx) {
    setBlipVoice(new BlipVoice(new Ctx(),
      PERSONAS[loadSettings().preferences.persona || 'normal'], { muted }));
  }
}

// The portrait loop runs an interval; it follows the interview screen.
// Entering the interview starts it, any other screen stops it, so no
// timer outlives the screen.
function onScreenChange(event) {
  if (event.detail === 'interview') {
    startPortraitLoop(el('persona-portrait'), activePersona);
  } else {
    stopPortraitLoop();
  }
}

function initVoiceMute() {
  el('voice-mute').addEventListener('click', onVoiceMuteClick);
  document.addEventListener('tadsdi:screen', onScreenChange);
}

async function startFromMenu() {
  const slug = pickProblemSlug(selectedProblemSlug());
  if (!slug) {
    el('menu-status').textContent = 'No problems loaded. Check the server.';
    return;
  }
  const prefs = {
    helpMode: el('help-mode').value,
    constraintMode: el('constraint-mode').value,
    proactiveHints: el('proactive-guidance').value === 'on',
    maxProbesPerStep: Number(el('probe-cap').value) || 0,
    persona: el('persona-select').value,
  };
  const timerMinutes = Number(el('timer-preset').value) || 0;
  el('menu-status').textContent = '';
  setupPersonaStage(prefs.persona);
  await startInterview(problems.get(slug), prefs, timerMinutes);
}

// ---- how to play ------------------------------------------------------

// The dialog is long, and its only button is at the end. A dialog focuses
// its first focusable element when it opens, so the view went to the end.
// The dialog now opens at its top, with the title focused.
function openHowTo() {
  const dialog = el('howto-dialog');
  el('howto-skip').checked = !howToAtStart();
  dialog.showModal();
  el('howto-body').scrollTop = 0;
  el('howto-title').focus();
}

// The box acts when the player closes the dialog. The write happens in the
// click and in the Escape key themselves: the close event of a dialog comes
// one task later, which is too late for a reload that follows at once.
function rememberHowToBox() {
  setHowToAtStart(!el('howto-skip').checked);
}

function initHowTo() {
  const dialog = el('howto-dialog');
  for (const id of ['open-howto', 'open-howto-settings']) {
    el(id).addEventListener('click', openHowTo);
  }
  el('howto-close').addEventListener('click', () => {
    rememberHowToBox();
    dialog.close();
  });
  dialog.addEventListener('cancel', rememberHowToBox);
}

// A new player reads how to play first. It opens over the screen that a
// resume selected, until the player ticks the box in the dialog.
function openHowToAtStart() {
  if (howToAtStart()) openHowTo();
}

// ---- boot ------------------------------------------------------------

export function initApp() {
  initSettings();
  initHowTo();
  showScreen('menu');
  initEngine(showScreen, renderFeedback);
  initExport(getEngineSession);
  for (const button of document.querySelectorAll('#screen-nav button[data-nav]')) {
    button.addEventListener('click', () => showScreen(button.dataset.nav));
  }
  el('start-interview').addEventListener('click', startFromMenu);
  el('problem-random').addEventListener('change', () => {
    el('problem-select').disabled = el('problem-random').checked;
  });
  const syncProactive = () => {
    el('proactive-guidance').disabled = el('help-mode').value === 'testing';
    el('probe-cap').disabled = el('help-mode').value === 'testing';
  };
  el('help-mode').addEventListener('change', syncProactive);
  syncProactive();
  initPersonaSelect();
  initVoiceMute();
  // loadProblems never rejects: an entry that fails to load is null.
  loadProblems().then((map) => {
    problems = map;
    renderMenu();
  });
  openHowToAtStart();
  window.__tadsdi = {
    showScreen,
    getProblemSlugs: () => [...problems.keys()],
  };
}

initApp();
