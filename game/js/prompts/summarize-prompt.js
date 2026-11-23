// TADSDI summarize-prompt.js: the prompt of the context compression call
// (DESIGN.md 7.1). The call turns the turns that left the interviewer window
// into one record: a narrative and lines for the design ledger.

const FENCE = { latex: 'latex', mermaid: 'mermaid', prose: 'text' };
const SPEAKER = { interviewer: 'Interviewer', system: 'System' };

const SUMMARIZER_SYSTEM = `You keep the record of a system design interview for a later interviewer.
You receive the summary of the earlier turns and the next turns.
You return one JSON object and nothing else, with these keys:
{"narrative": "...", "decisions": ["..."], "estimates": ["..."], "open_threads": ["..."]}

- narrative: at most 150 words. State what the candidate asked, what the
  interviewer answered (requirements, scale figures, constraints), and what the
  candidate decided. Write a record in the third person.
- decisions: one short line for each design decision or technology choice that
  the candidate stated.
- estimates: one line for each number that the candidate derived, with its unit
  and the reasoning in short form.
- open_threads: questions that are still open, and areas that the candidate
  named but did not work out.
- Keep every settled answer exact. A constraint or a scale figure never changes.
- Add nothing. No evaluation, no advice, and no technique, term, or area that
  the candidate did not name. The candidate never reads this text. A later
  interviewer context does, and it must stay free of hints.`;

function turnText(msg, artifactsById) {
  const speaker = SPEAKER[msg.speaker] || 'Candidate';
  const artifact = artifactsById.get(msg.artifactId);
  if (!artifact) {
    return `${speaker}: ${msg.text}`;
  }
  return `Candidate submitted a ${artifact.kind} artifact (step ${artifact.step}):\n` +
    `\`\`\`${FENCE[artifact.kind] || 'text'}\n${artifact.source}\n\`\`\``;
}

// from and to are transcript indexes: the turns to add are [from, to).
export function buildSummarizeMessages(session, { from, to }) {
  const artifactsById = new Map(session.artifacts.map((a) => [a.id, a]));
  const previous = session.compression ? session.compression.narrative : '(none yet)';
  const turns = session.transcript
    .slice(from, to)
    .map((msg) => turnText(msg, artifactsById))
    .join('\n\n');
  return [
    { role: 'system', content: SUMMARIZER_SYSTEM },
    {
      role: 'user',
      content: `Summary of the earlier turns:\n${previous}\n\nTurns to add to the summary:\n${turns}`,
    },
  ];
}
