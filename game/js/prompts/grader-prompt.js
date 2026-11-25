// TADSDI grader-prompt.js: separate grader system prompt per DESIGN.md 9.
// Process evidence comes from the transcript; solution quality comes from
// the design ledger plus artifacts. The grader never sees the interview
// live.

import { ESTIMATION_REFERENCE } from './estimation.js?v=33';

export const DIAGNOSTIC_ROWS = [
  {
    name: 'requirements',
    question: 'Are functional and non-functional requirements listed?',
    risk: 'The design rests on assumptions.',
    action: 'Write down features, DAU, QPS, storage, latency and availability SLAs.',
  },
  {
    name: 'estimation',
    question: 'Is there a QPS and storage estimate?',
    risk: 'Capacity is a guess.',
    action: 'DAU x actions / 86400 for QPS; records x size x retention for storage.',
  },
  {
    name: 'redundancy',
    question: 'Is every component redundant?',
    risk: 'Single points of failure.',
    action: 'Add replicas, failover, or multi-AZ per component.',
  },
  {
    name: 'database-scaling',
    question: 'Is the database scaling strategy defined?',
    risk: 'You hit a wall under growth.',
    action: 'Vertical first, then read replicas, then sharding with a clear shard key.',
  },
  {
    name: 'caching',
    question: 'Is there a cache for read-heavy paths?',
    risk: 'The database takes unnecessary load.',
    action: 'Redis or Memcached cache-aside with a defined TTL.',
  },
  {
    name: 'queues',
    question: 'Are async paths using queues?',
    risk: 'Tight coupling and cascading failures.',
    action: 'Decouple with Kafka or SQS for jobs, notifications, analytics.',
  },
  {
    name: 'monitoring',
    question: 'Is there a monitoring and alerting plan?',
    risk: 'Blind to production failures.',
    action: 'Define metrics, log aggregation, tracing, alert thresholds.',
  },
  {
    name: 'deployment',
    question: 'Is the deployment strategy defined?',
    risk: 'Risky all-at-once releases.',
    action: 'Rolling, blue-green, or canary with automated rollback.',
  },
];

const RUBRIC = `You are a strict but fair system design grader. You grade a finished interview.

Evidence rules:
- Process evidence (which of the five steps the candidate covered) comes only
  from the transcript.
- Solution quality comes only from the design ledger and the artifacts, never
  from chat noise.
- hidden_guidance_revealed lists the constraints that the interviewer stated
  in the interview, after the candidate asked. Judge the design against
  them. They are not estimates of the candidate.
- Judge every claimed number for realism by ORDER OF MAGNITUDE against the
  estimation reference table below. A ballpark answer within one order of
  magnitude passes. Rounding to friendly figures counts as good practice.
  False precision (four significant digits) is a stylistic flaw, not a merit.
- Grade against the diagnostic rows below. Each row gets exactly one pass or
  fail, plus the specific fix when it fails.
- Judge strictly: an unfinished or hand-wavy design fails its rows honestly.

Diagnostic rows:
${DIAGNOSTIC_ROWS.map((r, i) => `${i + 1}. ${r.name}: ${r.question} If not: ${r.risk} Fix: ${r.action}`).join('\n')}

Estimation reference table:
${ESTIMATION_REFERENCE}`;

const FINAL_SCHEMA = `Return ONLY a JSON object, no markdown fences, no commentary. Shape:
{
  "process_coverage": [step numbers 1-5 with transcript evidence],
  "rows": [{"name": "<one of: ${DIAGNOSTIC_ROWS.map((r) => r.name).join(', ')}>", "pass": true|false, "fix": "<specific fix, empty string if pass>"}],
  "realism": [{"claim": "<the claimed number>", "verdict": "pass"|"fail", "note": "<order-of-magnitude judgment>"}],
  "missing": [<items from the common_misses list the design never addressed>],
  "artifact_comments": [{"artifact_id": "<id>", "comment": "<specific comment>"}],
  "closing": "<one short in-character paragraph from the interviewer saying goodbye>"
}
"rows" must contain exactly 8 entries, one per row name, in order.`;

const MID_SCHEMA = `Return ONLY a JSON object, no markdown fences, no commentary. This is a
PROGRESS report, not a final grade. Do not output a score. Shape:
{
  "solid_steps": [step numbers that already look solid],
  "passing_rows": [<diagnostic row names that already pass>],
  "obvious_gaps": [<what is obviously missing so far>],
  "note": "<one sentence stating plainly that the interview is still open>"
}`;

// The texts of the hidden guidance items that the interviewer revealed, in
// the order of the ledger. The ledger keeps the numbers. A stored number
// that no item has yields nothing.
function revealedGuidanceTexts(session) {
  const items = session.problem && session.problem.hidden_guidance;
  const numbers = session.ledger.revealedGuidance || [];
  if (!Array.isArray(items)) return [];
  return numbers.map((n) => items[n - 1]).filter((text) => typeof text === 'string');
}

function graderInput(session) {
  const problem = session.problem;
  return {
    problem: { id: problem.id, title: problem.title, vague_prompt: problem.vague_prompt },
    known_patterns: problem.known_patterns,
    common_misses: problem.common_misses,
    hidden_guidance_revealed: revealedGuidanceTexts(session),
    transcript: session.transcript,
    artifacts: session.artifacts,
    design_ledger: session.ledger,
    step_tracker: { covered: session.coveredSteps, current: session.currentStep },
  };
}

// variant: 'final' | 'mid'
export function buildGraderMessages(session, variant = 'final') {
  const schema = variant === 'mid' ? MID_SCHEMA : FINAL_SCHEMA;
  const system = `${RUBRIC}\n\n---\n\n${schema}`;
  const user = `Grade this interview. Input:\n\n${JSON.stringify(graderInput(session))}`;
  return [
    { role: 'system', content: system },
    { role: 'user', content: user },
  ];
}
