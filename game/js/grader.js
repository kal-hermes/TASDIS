// TADSDI grader.js: end-of-interview and mid-interview grading (DESIGN.md 9).
// One grader call over the full transcript; strict JSON; malformed output
// retries exactly once. The score derives from the row count in game code,
// never from the model.

import { complete } from './providers.js?v=33';
import { buildGraderMessages, DIAGNOSTIC_ROWS } from './prompts/grader-prompt.js?v=33';
import { extractJsonObject } from './json-reply.js?v=33';

const ROW_NAMES = DIAGNOSTIC_ROWS.map((r) => r.name);

function validateFinal(data) {
  if (!Array.isArray(data.rows) || data.rows.length !== 8) {
    throw new Error('grader output must have exactly 8 rows');
  }
  const names = data.rows.map((r) => r.name);
  for (const expected of ROW_NAMES) {
    if (!names.includes(expected)) {
      throw new Error(`grader output missing row: ${expected}`);
    }
  }
  for (const row of data.rows) {
    if (typeof row.pass !== 'boolean') {
      throw new Error(`row ${row.name} needs a boolean pass`);
    }
    if (typeof row.fix !== 'string') {
      throw new Error(`row ${row.name} needs a string fix`);
    }
  }
  return data;
}

function validateMid(data) {
  for (const key of ['solid_steps', 'passing_rows', 'obvious_gaps', 'note']) {
    if (!(key in data)) {
      throw new Error(`mid grade output missing key: ${key}`);
    }
  }
  if ('score' in data) {
    throw new Error('mid grade output must not contain a score');
  }
  return data;
}

export function computeScore(rows) {
  const passed = rows.filter((r) => r.pass).length;
  return Math.round((passed / 8) * 10);
}

export function parseGradeJson(text, variant = 'final') {
  const data = extractJsonObject(text, 'grader');
  return variant === 'mid' ? validateMid(data) : validateFinal(data);
}

async function oneGraderCall(session, variant) {
  const messages = buildGraderMessages(session, variant);
  const purpose = variant === 'mid' ? 'grade_mid' : 'grade';
  const raw = await complete('text', messages, { purpose });
  return parseGradeJson(raw, variant);
}

// variant: 'final' | 'mid'. Malformed or invalid output retries once.
export async function gradeSession(session, { variant = 'final' } = {}) {
  let firstError = null;
  try {
    const result = await oneGraderCall(session, variant);
    if (variant === 'final') {
      result.score = computeScore(result.rows);
    }
    return result;
  } catch (err) {
    firstError = err;
  }
  const result = await oneGraderCall(session, variant);
  if (variant === 'final') {
    result.score = computeScore(result.rows);
  }
  return result;
}

export function graderTokenEstimate(session) {
  // Rough cost note for the mid-interview button: chars of the assembled
  // grader input, both directions, divided by 4.
  const messages = buildGraderMessages(session, 'final');
  const chars = messages.reduce((sum, m) => sum + m.content.length, 0);
  return Math.ceil((chars * 2) / 4);
}
