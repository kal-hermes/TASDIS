// TADSDI app.js: entry point and screen routing.

import { initSettings, howToAtStart, setHowToAtStart } from './settings.js?v=25';
import { initEngine, startInterview, getEngineSession } from './engine.js?v=25';
import { initExport } from './export.js?v=25';
import { initSubmission } from './submission.js?v=25';
import { loadProblems } from './problems.js?v=25';

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

async function startFromMenu() {
  let slug = selectedProblemSlug();
  if (el('problem-random').checked || !slug) {
    const available = [...problems.entries()].filter(([, p]) => p);
    if (!available.length) {
      el('menu-status').textContent = 'No problems loaded. Check the server.';
      return;
    }
    slug = available[Math.floor(Math.random() * available.length)][0];
  }
  const prefs = {
    helpMode: el('help-mode').value,
    constraintMode: el('constraint-mode').value,
    proactiveHints: el('proactive-guidance').value === 'on',
  };
  const timerMinutes = Number(el('timer-preset').value) || 0;
  el('menu-status').textContent = '';
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
  initSubmission();
  for (const button of document.querySelectorAll('#screen-nav button[data-nav]')) {
    button.addEventListener('click', () => showScreen(button.dataset.nav));
  }
  el('start-interview').addEventListener('click', startFromMenu);
  el('problem-random').addEventListener('change', () => {
    el('problem-select').disabled = el('problem-random').checked;
  });
  const syncProactive = () => {
    el('proactive-guidance').disabled = el('help-mode').value === 'testing';
  };
  el('help-mode').addEventListener('change', syncProactive);
  syncProactive();
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
