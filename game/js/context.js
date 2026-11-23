// TADSDI context.js: what one interviewer call sees (DESIGN.md 7.1).
//
// The stored session always keeps the full transcript, and both graders read
// it. This module builds the interviewer context in two parts:
//
// - The head is never compressed: the interviewer prompt, the step tracker,
//   the design ledger, the source of every artifact, and the narrative of the
//   summarized turns.
// - The newest turns follow verbatim inside a character budget. The budget is
//   60 percent of the model context window, minus the head.
//
// A turn that leaves the budget is not lost. compressIfNeeded() sends the
// turns that left the window to one summarization call. The call returns a
// narrative and lines for the ledger. Game code checks the shape and applies
// it; nothing that the model returns is used as it arrives.

import { assembleInterviewerPrompt, STEPS } from './prompts/assemble.js?v=22';
import { buildSummarizeMessages } from './prompts/summarize-prompt.js?v=22';
import { extractJsonObject } from './json-reply.js?v=22';

export const DEFAULT_CONTEXT_TOKENS = 32000;
export const THRESHOLD = 0.6;
// The newest turns stay verbatim whatever the budget holds.
export const KEEP_RECENT_TURNS = 6;
// Room held for the first narrative and its ledger lines, so the window does
// not shrink by a turn right after the first compression.
const SUMMARY_RESERVE_CHARS = 2500;
// A longer narrative is refused, because the reserve above holds it.
export const NARRATIVE_MAX_CHARS = 1500;

const FENCE = { latex: 'latex', mermaid: 'mermaid', prose: 'text' };

export function estimateTokens(text) {
  return Math.ceil(text.length / 4);
}

const charCount = (messages) => messages.reduce((sum, m) => sum + m.content.length, 0);
const summarizedCount = (session) => (session.compression ? session.compression.uptoIndex : 0);

function block(title, items) {
  return items.length ? [title, ...items] : [];
}

function trackerText(session) {
  const covered = session.coveredSteps.length
    ? session.coveredSteps.join(', ')
    : 'none';
  return `Step tracker: covered steps: ${covered}. Current step: ` +
    `${session.currentStep} (${STEPS[session.currentStep - 1]}).`;
}

// Ledger lines that are not an artifact: the Artifacts block carries every
// artifact source in full, so the ledger lists only what was stated in words.
function ledgerText(session, artifactIds) {
  const led = session.ledger;
  const stated = (entries) => entries
    .filter((entry) => !artifactIds.has(entry.id))
    .map((entry) => `- ${entry.source}`);
  const out = ['Design ledger (canonical solution state):'];
  out.push(...block('Decisions stated in the conversation:', stated(led.components)));
  out.push(...block('Estimates stated in the conversation:', stated(led.estimates)));
  if (led.revealedGuidance.length) {
    out.push(`Hidden guidance already surfaced: items ${led.revealedGuidance.join(', ')}`);
  }
  out.push(...block('Open threads:', led.openThreads.map((thread) => `- ${thread}`)));
  if (out.length === 1) out.push('(nothing settled yet)');
  return out.join('\n');
}

function artifactsText(session) {
  const out = ['Artifacts submitted so far (full source, always current):'];
  for (const artifact of session.artifacts) {
    out.push(`Artifact ${artifact.id}: ${artifact.kind}, step ${artifact.step}`);
    out.push(`\`\`\`${FENCE[artifact.kind] || 'text'}\n${artifact.source}\n\`\`\``);
  }
  return out.join('\n');
}

function narrativeText(compression) {
  return 'Summary of earlier turns (the full transcript is not repeated here):\n' +
    compression.narrative;
}

// The layers that no compression ever drops.
export function headMessages(session) {
  const artifactIds = new Set(session.artifacts.map((a) => a.id));
  const head = [
    ...assembleInterviewerPrompt({
      problem: session.problem,
      helpMode: session.helpMode,
      constraintMode: session.constraintMode,
      proactiveHints: session.proactiveHints === true,
    }),
    { role: 'system', content: `${trackerText(session)}\n\n${ledgerText(session, artifactIds)}` },
  ];
  if (session.artifacts.length) {
    head.push({ role: 'system', content: artifactsText(session) });
  }
  if (session.compression) {
    head.push({ role: 'system', content: narrativeText(session.compression) });
  }
  return head;
}

// An artifact turn points at the Artifacts block instead of repeating the
// source, so the source is in the context exactly once.
function turnContent(msg, artifactsById) {
  const artifact = artifactsById.get(msg.artifactId);
  if (!artifact) return msg.text;
  return `${msg.text} (${artifact.kind}, artifact ${artifact.id}, source in the Artifacts block)`;
}

function windowBudgetChars(session, contextTokens) {
  const limit = contextTokens || DEFAULT_CONTEXT_TOKENS;
  const reserve = session.compression ? 0 : SUMMARY_RESERVE_CHARS;
  const room = limit * 4 * THRESHOLD - charCount(headMessages(session)) - reserve;
  return Math.max(Math.floor(room), 0);
}

// Index of the first transcript turn that the verbatim window holds. The
// walk goes back over every turn that is not summarized yet, while the budget
// lasts. The newest turns stay in whatever the budget holds. Turns before the
// index are summarized or wait for summarization.
export function firstVerbatimIndex(session, contextTokens = 0) {
  const transcript = session.transcript;
  const artifactsById = new Map(session.artifacts.map((a) => [a.id, a]));
  let budget = windowBudgetChars(session, contextTokens);
  let start = transcript.length;
  for (let i = transcript.length - 1; i >= summarizedCount(session); i -= 1) {
    const cost = turnContent(transcript[i], artifactsById).length;
    const forced = i >= transcript.length - KEEP_RECENT_TURNS;
    if (!forced && budget - cost < 0) break;
    budget -= cost;
    start = i;
  }
  return start;
}

export function assembleContext(session, options = {}) {
  const artifactsById = new Map(session.artifacts.map((a) => [a.id, a]));
  const turns = session.transcript
    .slice(firstVerbatimIndex(session, options.contextTokens))
    .map((msg) => ({
      role: msg.speaker === 'interviewer' ? 'assistant' : 'user',
      content: turnContent(msg, artifactsById),
    }));
  return [...headMessages(session), ...turns];
}

// ---- compression ------------------------------------------------------

// Transcript indexes of the turns that left the window and are not summarized
// yet: [from, to). Null when there is nothing to summarize.
export function overflowRange(session, contextTokens = 0) {
  const from = summarizedCount(session);
  const to = firstVerbatimIndex(session, contextTokens);
  return to > from ? { from, to } : null;
}

export function summarizationNeeded(session, contextTokens) {
  return overflowRange(session, contextTokens) !== null;
}

const LIST_KEYS = ['decisions', 'estimates', 'open_threads'];

// Strict shape: a short-enough narrative and three lists of text lines.
export function parseSummary(text) {
  const data = extractJsonObject(text, 'summarization');
  const narrative = typeof data.narrative === 'string' ? data.narrative.trim() : '';
  if (narrative.length < 20 || narrative.length > NARRATIVE_MAX_CHARS) {
    throw new Error(`the summary narrative needs 20 to ${NARRATIVE_MAX_CHARS} characters`);
  }
  const summary = { narrative };
  for (const key of LIST_KEYS) {
    const list = data[key];
    const bad = !Array.isArray(list) ||
      list.some((line) => typeof line !== 'string' || !line.trim());
    if (bad) {
      throw new Error(`the summary needs ${key} as a list of text lines`);
    }
    summary[key] = list.map((line) => line.trim());
  }
  return summary;
}

function pushLine(entries, line, id) {
  if (!entries.some((entry) => entry.source === line)) {
    entries.push({ id, step: null, status: 'summarized', kind: 'prose', source: line });
  }
}

// Puts one summary into the session. Turns before uptoIndex count as
// summarized from now on. Running it twice with the same summary changes
// nothing the second time.
export function applyCompression(session, summary, uptoIndex) {
  const led = session.ledger;
  summary.decisions.forEach((line, i) => pushLine(led.components, line, `summary-${uptoIndex}-d${i}`));
  summary.estimates.forEach((line, i) => pushLine(led.estimates, line, `summary-${uptoIndex}-e${i}`));
  for (const thread of summary.open_threads) {
    if (!led.openThreads.includes(thread)) led.openThreads.push(thread);
  }
  session.compression = {
    uptoIndex: Math.max(uptoIndex, summarizedCount(session)),
    narrative: summary.narrative,
  };
}

// Runs before each interviewer call. Summarizes the turns that left the
// window when there are any. A failed call changes nothing: the interviewer
// then works without those turns, and the next call tries again.
export async function compressIfNeeded(session, { contextTokens, summarize, onStatus }) {
  const range = overflowRange(session, contextTokens);
  if (!range) return { compressed: false };
  try {
    const reply = await summarize(buildSummarizeMessages(session, range));
    applyCompression(session, parseSummary(reply), range.to);
    session.compression.ts = Date.now();
    if (onStatus) onStatus('');
    return { compressed: true, ...range };
  } catch (err) {
    if (onStatus) {
      onStatus(`Older turns were not summarized: ${err.message}. ` +
        'The interview continues without them in the interviewer context.');
    }
    return { compressed: false, error: err.message };
  }
}
