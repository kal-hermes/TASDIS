// TADSDI engine.js: interviewer conversation loop, step tracker, timer.
// Per DESIGN.md 6: the clock ticks only while the send button is enabled
// (the candidate's turn); it pauses while the LLM streams, during GRADING
// and FEEDBACK, and after a reload until the user's next turn. Only game
// code ends the interview.

import {
  loadSession, saveSession, newSession,
  addMessage, addArtifact, coverStep, setCurrentStep, revealGuidance,
  countProbe,
} from './state.js?v=30';
import { STEPS, assembleBriefingMessages } from './prompts/assemble.js?v=30';
import { buildCheckMessages, parseCheckReply } from './prompts/check-prompt.js?v=30';
import { assembleContext, compressIfNeeded } from './context.js?v=30';
import { completeStream, complete, resetMockState, textContextTokens } from './providers.js?v=30';
import { gradeSession, graderTokenEstimate } from './grader.js?v=30';
import { renderLatex } from './render-latex.js?v=30';
import { renderMermaid } from './render-mermaid.js?v=30';

let session = null;
let busy = false;
let showScreenFn = null;
let renderFeedbackFn = null;
let helpStage = 0;
let tickInterval = null;

const STEP_RE = /\[\[step:\s*([1-5])\]\]/g;
const COVERED_RE = /\[\[covered:\s*([1-5])\]\]/g;
const GUIDANCE_RE = /\[\[guidance:\s*(\d+)\]\]/g;
const PROBE_RE = /\[\[probe:\s*(\d+)\]\]/g;
// Every control line leaves the text, also one with a value out of range:
// the candidate never sees a line of the protocol.
const CONTROL_LINE_RE = /\[\[(?:step|covered|guidance|probe):[^\]\n]*\]\]/g;

// The interviewer ends a reply with control lines. The game reads them and
// shows the rest. A value out of range changes nothing: a step stays as it
// was, and revealGuidance checks a guidance number against the problem.
export function parseControlLines(text) {
  const covered = [];
  const guidance = [];
  const probes = [];
  let m;
  COVERED_RE.lastIndex = 0;
  while ((m = COVERED_RE.exec(text)) !== null) covered.push(Number(m[1]));
  GUIDANCE_RE.lastIndex = 0;
  while ((m = GUIDANCE_RE.exec(text)) !== null) guidance.push(Number(m[1]));
  PROBE_RE.lastIndex = 0;
  while ((m = PROBE_RE.exec(text)) !== null) probes.push(Number(m[1]));
  STEP_RE.lastIndex = 0;
  let step = null;
  while ((m = STEP_RE.exec(text)) !== null) step = Number(m[1]);
  const clean = text.replace(CONTROL_LINE_RE, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  return { clean, step, covered, guidance, probes };
}

// ---- DOM helpers -----------------------------------------------------

function el(id) { return document.getElementById(id); }

function chatMessageEl(speaker, text) {
  const div = document.createElement('div');
  div.className = `chat-message ${speaker}`;
  div.textContent = text;
  el('chat-log').appendChild(div);
  div.scrollIntoView({ behavior: 'auto', block: 'end' });
  return div;
}

function streamingEl() {
  return chatMessageEl('interviewer', '');
}

// A failed provider call shows one notice with a Retry button. The notice
// lives in the chat view only: the stored transcript never records it, and
// Retry runs the same turn again without a new candidate message.
function showError(message, retry) {
  const box = document.createElement('div');
  box.className = 'notice error';
  const text = document.createElement('div');
  text.className = 'notice-text';
  text.textContent = message;
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'retry-btn';
  button.textContent = 'Retry';
  button.addEventListener('click', async () => {
    if (busy) return;
    box.remove();
    await retry();
  });
  box.appendChild(text);
  box.appendChild(button);
  el('chat-log').appendChild(box);
  box.scrollIntoView({ behavior: 'auto', block: 'end' });
  return box;
}

function renderArtifact(artifact) {
  const div = document.createElement('div');
  div.className = 'chat-message candidate artifact';
  const head = document.createElement('div');
  head.className = 'artifact-head';
  head.textContent = `${artifact.kind.toUpperCase()} artifact (step ${artifact.step})`;
  const body = document.createElement('div');
  body.className = 'artifact-body';
  if (artifact.kind === 'latex') {
    renderLatex(body, artifact.source);
  } else if (artifact.kind === 'mermaid') {
    renderMermaid(body, artifact.source);
  } else {
    body.textContent = artifact.source;
  }
  const source = document.createElement('details');
  const sum = document.createElement('summary');
  sum.textContent = 'source';
  const pre = document.createElement('pre');
  pre.textContent = artifact.source;
  source.appendChild(sum);
  source.appendChild(pre);
  div.appendChild(head);
  div.appendChild(body);
  div.appendChild(source);
  el('chat-log').appendChild(div);
  div.scrollIntoView({ behavior: 'auto', block: 'end' });
  return div;
}

function renderChatFromSession() {
  el('chat-log').innerHTML = '';
  const byId = new Map(session.artifacts.map((a) => [a.id, a]));
  for (const msg of session.transcript) {
    if (msg.artifactId && byId.has(msg.artifactId)) {
      renderArtifact(byId.get(msg.artifactId));
    } else {
      chatMessageEl(msg.speaker, msg.text);
    }
  }
}

function renderTracker() {
  const learning = session && session.helpMode === 'learning';
  const visible = learning && session.showTracker !== false;
  el('tracker-block').hidden = !learning || !visible;
  const toggle = el('toggle-tracker');
  toggle.hidden = !learning;
  toggle.textContent = visible ? 'Hide step tracker' : 'Show step tracker';
  const list = el('step-tracker');
  list.innerHTML = '';
  STEPS.forEach((name, i) => {
    const li = document.createElement('li');
    li.textContent = name;
    li.dataset.step = String(i + 1);
    if (session && session.coveredSteps.includes(i + 1)) {
      li.classList.add('covered');
    }
    if (session && session.currentStep === i + 1) {
      li.classList.add('current');
    }
    list.appendChild(li);
  });
}

function renderTimer() {
  const hud = el('timer-hud');
  if (!session || !session.timer || !session.timer.enabled) {
    hud.hidden = true;
    return;
  }
  hud.hidden = false;
  const minutes = Math.floor(session.timer.remainingMs / 60000);
  const seconds = Math.floor((session.timer.remainingMs % 60000) / 1000);
  hud.textContent = `${minutes}:${String(seconds).padStart(2, '0')}`;
  const late = session.timer.remainingMs < session.timer.presetMs * 0.2;
  hud.classList.toggle('late', late);
}

// True while an interview is on, and true while the candidate may act: no
// provider call runs. The clock and every control use these two.
const interviewOpen = () => Boolean(session) && session.state === 'INTERVIEW';
const candidateTurn = () => interviewOpen() && !busy;

function renderControls() {
  const turn = candidateTurn();
  el('send-btn').disabled = !turn;
  el('candidate-input').disabled = !turn;
  el('interview-busy').hidden = !busy;
  el('end-interview-btn').hidden = !turn;
  const midButton = el('request-midgrade');
  midButton.hidden = !interviewOpen() || session.helpMode !== 'learning';
  midButton.textContent = session
    ? `Request progress grade (~${graderTokenEstimate(session)} tokens in + out)`
    : 'Request progress grade';
}

// ---- timer -----------------------------------------------------------

function clockRunning() {
  return candidateTurn() && Boolean(session.timer && session.timer.enabled) &&
    !session.clockPaused;
}

function tick() {
  if (!clockRunning()) return;
  session.timer.remainingMs -= 1000;
  renderTimer();
  if (session.timer.remainingMs <= 0) {
    session.timer.remainingMs = 0;
    onTimerExpired();
  } else {
    saveSession(session);
  }
}

async function onTimerExpired() {
  saveSession(session);
  addMessage(session, 'system', 'Time is up. The interview moves to wrap-up.');
  await wrapup('The time for this interview is over.');
}

function startTicker() {
  if (tickInterval) clearInterval(tickInterval);
  tickInterval = setInterval(tick, 1000);
}

// ---- turns -----------------------------------------------------------

// What the interviewer sees: the head and the newest turns. Turns that left
// the window are summarized first, so nothing that was settled is lost.
async function interviewerContext() {
  const contextTokens = textContextTokens();
  await compressIfNeeded(session, {
    contextTokens,
    summarize: (messages) => complete('text', messages, { purpose: 'summarize' }),
    onStatus: (message) => {
      el('engine-status').textContent = message;
    },
  });
  return assembleContext(session, { contextTokens });
}

// Runs one interviewer call (briefing, interview turn, or help). Returns
// false when the provider failed; the caller's message is already stored, so
// a retry only repeats this call.

// The reveal checker: the ledger cannot depend on the model's control
// lines, so every interviewer reply is audited against the hidden list.
// A failed checker degrades to the engine status; the reply is safe.
async function runRevealCheck(session, replyText) {
  const status = el('engine-status');
  try {
    const audit = await complete('text',
      buildCheckMessages(replyText, session.problem, session.ledger.revealedGuidance),
      { purpose: 'check_reveals' });
    revealGuidance(session,
      parseCheckReply(audit, (session.problem.hidden_guidance || []).length));
    // The engine status carries other subsystem notes (compression, for
    // one). Only the checker's own failure message is cleared here.
    if (status.textContent.startsWith('The reveal check failed')) {
      status.textContent = '';
    }
  } catch (checkErr) {
    status.textContent =
      `The reveal check failed on the last reply (${checkErr.message}). ` +
      'The ledger may be missing an item the reply stated.';
  }
}

// Applies the control lines of one interviewer reply to the session: the
// step move, the coverage marks, the ledger reveals, and the probe counts.
// A value out of range changes nothing; the parsers already dropped junk.
function applyControlLines(session, lines) {
  const { step, covered, guidance, probes } = lines;
  if (step) setCurrentStep(session, step);
  for (const c of covered) coverStep(session, c);
  revealGuidance(session, guidance);
  for (const p of probes) countProbe(session, p);
}

export async function runLlmTurn({ purpose, helpRequest }) {
  busy = true;
  renderControls();
  const streamEl = streamingEl();
  let ok = true;
  try {
    let messages;
    const options = { purpose, helpRequest };
    if (purpose === 'briefing') {
      messages = assembleBriefingMessages({
        problem: session.problem,
        helpMode: session.helpMode,
        constraintMode: session.constraintMode,
        proactiveHints: session.proactiveHints === true,
      });
    } else {
      messages = await interviewerContext();
    }
    const raw = await completeStream('text', messages, (chunk) => {
      streamEl.textContent += chunk;
      streamEl.scrollIntoView({ behavior: 'auto', block: 'end' });
    }, options);
    const { clean, step, covered, guidance, probes } = parseControlLines(raw);
    streamEl.textContent = clean;
    addMessage(session, 'interviewer', clean, {
      step: step || session.currentStep,
      ...(purpose === 'help' ? { helpReply: true } : {}),
    });
    if (purpose !== 'help') helpStage = 0;
    applyControlLines(session, { step, covered, guidance, probes });
    await runRevealCheck(session, clean);
  } catch (err) {
    ok = false;
    streamEl.remove();
    if (purpose === 'briefing') {
      el('briefing-status').textContent = `The briefing failed: ${err.message}`;
      el('briefing-retry').hidden = false;
    } else {
      showError(`The interviewer could not answer: ${err.message}`, () =>
        runLlmTurn({ purpose, helpRequest }));
    }
  } finally {
    busy = false;
    session.clockPaused = false;
    saveSession(session);
    renderTracker();
    renderControls();
    renderTimer();
  }
  return ok;
}

async function startInterview(problem, prefs, timerMinutes) {
  resetMockState();
  helpStage = 0;
  session = newSession(problem, prefs);
  if (timerMinutes > 0) {
    session.timer = {
      enabled: true,
      presetMs: timerMinutes * 60000,
      remainingMs: timerMinutes * 60000,
    };
  }
  session.state = 'BRIEFING';
  saveSession(session);
  showScreenFn('briefing');
  await runBriefing();
}

async function runBriefing() {
  // Idempotent: a crash after the briefing already stored leaves the
  // transcript non-empty, so a reload resumes into INTERVIEW instead of
  // duplicating the greeting.
  if (session.transcript.length > 0) {
    session.state = 'INTERVIEW';
    saveSession(session);
    enterInterviewScreen();
    return;
  }
  const ok = await runLlmTurn({ purpose: 'briefing' });
  if (!ok) return;
  el('briefing-status').textContent = '';
  el('briefing-retry').hidden = true;
  session.state = 'INTERVIEW';
  saveSession(session);
  enterInterviewScreen();
}

function enterInterviewScreen() {
  showScreenFn('interview');
  renderChatFromSession();
  renderTracker();
  renderControls();
  renderTimer();
}

async function sendTurn(text) {
  if (!candidateTurn()) return;
  const trimmed = text.trim();
  if (!trimmed) return;
  addMessage(session, 'candidate', trimmed);
  saveSession(session);
  chatMessageEl('candidate', trimmed);
  const help = /\b(hint|help|stuck|clue|what would you (do|look))\b/i.test(trimmed);
  if (help) {
    if (session.helpMode === 'testing') {
      await runLlmTurn({ purpose: 'help', helpRequest: 'refusal' });
    } else {
      await runLlmTurn({ purpose: 'help', helpRequest: 'ladder' });
    }
  } else {
    await runLlmTurn({ purpose: 'interview' });
  }
}

async function submitArtifact(kind, source) {
  if (!candidateTurn()) return null;
  const artifact = addArtifact(session, { kind, source, step: session.currentStep });
  saveSession(session);
  renderArtifact(artifact);
  await runLlmTurn({ purpose: 'interview' });
  return artifact;
}

async function wrapup(timeUpNote) {
  busy = true;
  renderControls();
  if (timeUpNote) chatMessageEl('system', timeUpNote);
  const streamEl = streamingEl();
  try {
    const raw = await completeStream('text', await interviewerContext(), (chunk) => {
      streamEl.textContent += chunk;
    }, { purpose: 'wrapup' });
    const { clean } = parseControlLines(raw);
    streamEl.textContent = clean;
    addMessage(session, 'interviewer', clean);
  } catch (err) {
    // The wrap-up is a courtesy line. A failure here must not block the
    // grade, which is a separate call over the stored transcript.
    streamEl.remove();
    addMessage(session, 'system', `Wrap-up skipped: ${err.message}`);
  }
  session.state = 'GRADING';
  session.ended = true;
  saveSession(session);
  busy = false;
  showScreenFn('grading');
  el('grading-status').textContent = 'Grading your interview...';
  el('grading-retry').hidden = true;
  await runGrading();
}

async function runGrading() {
  try {
    const grade = await gradeSession(session, { variant: 'final' });
    session.grade = grade;
    session.state = 'FEEDBACK';
    saveSession(session);
    renderFeedbackFn(session);
    showScreenFn('feedback');
  } catch (err) {
    el('grading-status').textContent =
      `Grading failed after one retry: ${err.message}. Your session is saved.`;
    el('grading-retry').hidden = false;
  }
}

async function requestMidGrade() {
  // The button is hidden in testing mode. The check here is the guarantee.
  if (!candidateTurn() || session.helpMode !== 'learning') return;
  busy = true;
  renderControls();
  el('midgrade-status').textContent =
    'Grading in progress... (the clock is paused)';
  try {
    const result = await gradeSession(session, { variant: 'mid' });
    session.midInterviewGrades.push({ ts: Date.now(), result });
    el('midgrade-status').textContent = '';
    saveSession(session);
    renderMidGrades();
  } catch (err) {
    el('midgrade-status').textContent = `Progress grading failed: ${err.message}`;
  } finally {
    busy = false;
    session.clockPaused = false;
    saveSession(session);
    renderControls();
    renderTimer();
  }
}

function renderMidGrades() {
  const list = el('midgrade-snapshots');
  list.innerHTML = '';
  (session.midInterviewGrades || []).forEach((snap, i) => {
    const li = document.createElement('li');
    const time = new Date(snap.ts).toLocaleTimeString();
    li.textContent = `#${i + 1} at ${time}: ${snap.result.solid_steps.length} solid step(s), ` +
      `${snap.result.passing_rows.length} row(s) pass. ${snap.result.note}`;
    list.appendChild(li);
  });
}

// ---- resume ----------------------------------------------------------

function showStoredFeedback() {
  renderFeedbackFn(session);
  showScreenFn('feedback');
}

// A reload in GRADING, or in FEEDBACK without a stored grade, grades again.
function gradeAgain() {
  showScreenFn('grading');
  el('grading-status').textContent = 'Grading your interview...';
  el('grading-retry').hidden = true;
  return runGrading();
}

// What a reload does for each stored state.
const ON_RESUME = {
  BRIEFING: () => runBriefing(),
  INTERVIEW: () => {
    session.clockPaused = true;
    saveSession(session);
    enterInterviewScreen();
    renderMidGrades();
  },
  FEEDBACK: () => (session.grade ? showStoredFeedback() : gradeAgain()),
  GRADING: () => gradeAgain(),
};

function resumeSession() {
  const stored = loadSession();
  const resume = stored && ON_RESUME[stored.state];
  if (!resume) return false;
  session = stored;
  resume();
  return true;
}

// ---- event handlers --------------------------------------------------

function onSendClicked() {
  const input = el('candidate-input');
  const text = input.value;
  input.value = '';
  return sendTurn(text);
}

function onInputKeydown(event) {
  if (event.key === 'Enter' && !el('send-btn').disabled) {
    el('send-btn').click();
  }
}

function onEndClicked() {
  if (!busy) wrapup(null);
}

function onMidGradeClicked() {
  if (!busy) requestMidGrade();
}

function onToggleTracker() {
  if (!session) return;
  session.showTracker = session.showTracker === false;
  saveSession(session);
  renderTracker();
}

function onGradingRetry() {
  if (!busy) runGrading();
}

function onBriefingRetry() {
  if (!busy) runBriefing();
}

function renderSidebar() {
  renderTracker();
  renderControls();
  renderTimer();
}

// ---- public init -----------------------------------------------------

export function initEngine(showScreen, renderFeedback) {
  showScreenFn = showScreen;
  renderFeedbackFn = renderFeedback;
  el('send-btn').addEventListener('click', onSendClicked);
  el('candidate-input').addEventListener('keydown', onInputKeydown);
  el('end-interview-btn').addEventListener('click', onEndClicked);
  el('request-midgrade').addEventListener('click', onMidGradeClicked);
  el('toggle-tracker').addEventListener('click', onToggleTracker);
  el('grading-retry').addEventListener('click', onGradingRetry);
  el('briefing-retry').addEventListener('click', onBriefingRetry);
  // The nav buttons open any screen at any time, so the sidebar renders
  // again on every screen change, with or without a session.
  document.addEventListener('tadsdi:screen', renderSidebar);
  startTicker();
  return resumeSession();
}

export function getEngineSession() {
  return session;
}

export { startInterview, submitArtifact };
