// TADSDI turn-parse.js: one candidate turn is one input holding prose,
// $$latex$$ blocks, and ```mermaid / ```latex fenced blocks in any
// combination (DESIGN.md 8). parseTurn splits the text into ordered
// segments: prose keeps its place between the blocks, and each block
// becomes an artifact.
//
// Deterministic rules: only CLOSED fences and BALANCED $$ pairs become
// artifacts. An unclosed fence or a lone $$ stays prose, so a half-typed
// block can never swallow the rest of the turn.

const FENCE_RE = /```(mermaid|latex)[ \t]*\n([\s\S]*?)```/g;
const DOLLAR_RE = /\$\$([\s\S]+?)\$\$/g;

function collectTokens(text) {
  const tokens = [];
  for (const match of text.matchAll(FENCE_RE)) {
    tokens.push({ start: match.index, end: match.index + match[0].length,
      type: match[1], source: match[2].trim() });
  }
  for (const match of text.matchAll(DOLLAR_RE)) {
    const overlapping = tokens.some((t) => match.index < t.end
      && match.index + match[0].length > t.start);
    if (!overlapping) {
      tokens.push({ start: match.index, end: match.index + match[0].length,
        type: 'latex', source: match[1].trim() });
    }
  }
  tokens.sort((a, b) => a.start - b.start);
  return tokens;
}

export function parseTurn(text) {
  const tokens = collectTokens(String(text || ''));
  const segments = [];
  let cursor = 0;
  for (const token of tokens) {
    const before = text.slice(cursor, token.start).trim();
    if (before) segments.push({ type: 'prose', text: before });
    segments.push({ type: token.type, source: token.source });
    cursor = token.end;
  }
  const tail = text.slice(cursor).trim();
  if (tail) segments.push({ type: 'prose', text: tail });
  return { segments };
}
