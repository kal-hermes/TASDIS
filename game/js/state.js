// TADSDI state.js: session state machine + persistence per DESIGN.md 5.3/5.4.
// One active session in localStorage. The stored record always keeps the
// full transcript; compression (M3) applies only to LLM call assembly.

export const SESSION_KEY = 'tadsdi.session.v1';
export const STATES = ['MENU', 'BRIEFING', 'INTERVIEW', 'GRADING', 'FEEDBACK'];

export function newSession(problem, prefs = {}) {
  return {
    version: 1,
    problemId: problem.id,
    problem,
    helpMode: prefs.helpMode || 'learning',
    constraintMode: prefs.constraintMode || 'unconstrained',
    proactiveHints: prefs.proactiveHints === true && (prefs.helpMode || 'learning') === 'learning',
    showTracker: prefs.showTracker !== false,
    state: 'MENU',
    transcript: [],
    artifacts: [],
    coveredSteps: [],
    currentStep: 1,
    ledger: {
      components: [],
      estimates: [],
      revealedGuidance: [],
      openThreads: [],
    },
    grade: null,
    midInterviewGrades: [],
    timer: null,
    ended: false,
    updatedAt: Date.now(),
  };
}

export function loadSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveSession(session) {
  session.updatedAt = Date.now();
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

let artifactCounter = 0;
export function nextArtifactId() {
  artifactCounter += 1;
  return `a${Date.now()}-${artifactCounter}`;
}

export function addMessage(session, speaker, text, extra = {}) {
  const msg = { speaker, text, ts: Date.now(), ...extra };
  session.transcript.push(msg);
  return msg;
}

export function addArtifact(session, { kind, source, step }) {
  const artifact = { id: nextArtifactId(), kind, source, step };
  session.artifacts.push(artifact);
  addMessage(session, 'candidate', `submitted ${kind} artifact`, {
    artifactId: artifact.id,
  });
  // Deterministic ledger update per DESIGN.md 5.4: every submission lands in
  // the ledger as proposed; acceptance happens later (interviewer/grader).
  if (kind === 'latex') {
    session.ledger.estimates.push({
      id: artifact.id, step, status: 'proposed', source,
    });
  } else if (kind === 'mermaid') {
    session.ledger.components.push({
      id: artifact.id, step, status: 'proposed', source,
    });
  } else {
    session.ledger.components.push({
      id: artifact.id, step, status: 'proposed', kind: 'prose', source,
    });
  }
  return artifact;
}

export function coverStep(session, n) {
  if (!session.coveredSteps.includes(n)) {
    session.coveredSteps.push(n);
    session.coveredSteps.sort((a, b) => a - b);
  }
}

export function setCurrentStep(session, n) {
  if (n >= 1 && n <= 5) session.currentStep = n;
}

function guidanceCount(session) {
  const items = session.problem && session.problem.hidden_guidance;
  return Array.isArray(items) ? items.length : 0;
}

// The numbers are 1-based, like the numbers of the problem block. A number
// outside the list of the problem is a mistake of the model: the game drops it.
export function revealGuidance(session, indices) {
  const count = guidanceCount(session);
  const revealed = session.ledger.revealedGuidance;
  const valid = (i) => Number.isInteger(i) && i >= 1 && i <= count && !revealed.includes(i);
  for (const i of indices) {
    if (valid(i)) revealed.push(i);
  }
}
