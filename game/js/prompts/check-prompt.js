// TADSDI check-prompt.js: the reveal checker. After an interviewer reply,
// a second, small call reads that reply against the numbered hidden
// guidance list and returns the items the reply stated. A live interview
// showed a real model stating items in prose without their [[guidance: N]]
// line, so the ledger cannot depend on the model's bookkeeping alone.
// Game code inspects the checker reply's shape before anything reaches
// the ledger.

import { extractJsonObject } from '../json-reply.js?v=38';

const CHECK_RULES = `You audit one reply from a technical interviewer. The
reply may have stated some of the hidden guidance items listed below. Decide
which items the reply states to the candidate, in substance. A paraphrase
counts. A partial statement counts when the substance of the constraint is
there. Judge only this reply: do not carry over items from earlier turns.

Answer with ONLY a JSON object, no markdown fences, no commentary:
{"revealed": [item numbers]}`;

export function buildCheckMessages(replyText, problem, alreadyRevealed) {
  const items = (problem.hidden_guidance || [])
    .map((g, i) => `${i + 1}. ${g}`)
    .join('\n');
  const surfaced = Array.isArray(alreadyRevealed) && alreadyRevealed.length
    ? `Already surfaced earlier: ${alreadyRevealed.join(', ')}.`
    : 'Already surfaced earlier: none.';
  return [
    { role: 'system', content: CHECK_RULES },
    {
      role: 'user',
      content: `Reply:\n\n${replyText}\n\nHidden guidance items:\n${items}\n\n${surfaced}`,
    },
  ];
}

// The checker's reply must be one JSON object with a "revealed" list of
// item numbers. Anything else is a checker failure. Duplicates, non-integers,
// and numbers outside the item list are dropped here, so the ledger never
// sees them.
export function parseCheckReply(text, itemCount) {
  const data = extractJsonObject(text, 'reveal check');
  if (!Array.isArray(data.revealed)) {
    throw new Error('the reveal check needs "revealed" as a list');
  }
  const out = [];
  for (const n of data.revealed) {
    if (typeof n === 'number' && Number.isInteger(n)
        && n >= 1 && n <= itemCount && !out.includes(n)) {
      out.push(n);
    }
  }
  return out;
}
