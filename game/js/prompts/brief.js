// TADSDI brief.js: the interviewer brief (author-time prep pack) per
// DESIGN.md 7. The pack lives in the problem JSON. It is the model's stable
// mental model of the problem, written once by the authors instead of
// improvised per session. Its contents reach only the interviewer's
// context: the candidate hears an item only by asking, or by producing it.

const filledText = (v) => typeof v === 'string' && !!v.trim();

// The template floor of a pack: five dimensions (one per step), one anchor
// per hidden guidance item, and at least six probes. A problem without a
// pack is fine; a problem with a malformed pack fails loudly here, so the
// bank never feeds the interviewer half a mental model.
export function validateBrief(problem) {
  const brief = problem.interviewer_brief;
  if (!brief) return;
  const where = `problem ${problem.id}: interviewer_brief`;
  inspectGist(brief, where);
  inspectDimensions(brief, where);
  inspectAnchors(brief, problem, where);
  inspectProbes(brief, where);
}

function inspectGist(brief, where) {
  if (!filledText(brief.gist)) {
    throw new Error(`${where} gist needs text`);
  }
}

function inspectDimensions(brief, where) {
  const dims = brief.dimensions || {};
  const dimKeys = Object.keys(dims);
  const dimsOk = dimKeys.length === 5
    && ['1', '2', '3', '4', '5'].every((k) => dimKeys.includes(k))
    && dimKeys.every((k) => Array.isArray(dims[k]) && dims[k].length
      && dims[k].every((line) => filledText(line)));
  if (!dimsOk) {
    throw new Error(`${where} dimensions needs keys 1 to 5`);
  }
}

function inspectAnchors(brief, problem, where) {
  const anchors = brief.anchors || {};
  const itemCount = Array.isArray(problem.hidden_guidance)
    ? problem.hidden_guidance.length : 0;
  const anchorKeys = Object.keys(anchors);
  const anchorsOk = itemCount > 0 && anchorKeys.length === itemCount
    && anchorKeys.every((k, i) => k === String(i + 1)
      && filledText(anchors[k]));
  if (!anchorsOk) {
    throw new Error(`${where} anchors needs one entry per hidden item`);
  }
}

function inspectProbes(brief, where) {
  if (!Array.isArray(brief.probes) || brief.probes.length < 6) {
    throw new Error(`${where} needs at least 6 probes (template floor)`);
  }
  brief.probes.forEach((probe, i) => {
    const num = Number.isInteger(probe.step) && probe.step >= 1 && probe.step <= 5;
    if (!num) {
      throw new Error(`${where} probe ${i + 1} needs step 1 to 5`);
    }
    if (!filledText(probe.q)) {
      throw new Error(`${where} probe ${i + 1} needs text`);
    }
  });
}

function anchorLines(brief, revealed) {
  return Object.keys(brief.anchors || {})
    .map(Number)
    .filter((n) => !revealed.includes(n))
    .map((n) => `- item ${n}: ${brief.anchors[String(n)]}`);
}

function probeLines(brief, currentStep, helpMode, probeCap, probesAsked) {
  if (helpMode !== 'learning' || probeCap <= 0) return [];
  const stepProbes = brief.probes
    .map((p, i) => ({ ...p, n: i + 1 }))
    .filter((p) => p.step === currentStep);
  if (!stepProbes.length) return [];
  const left = probeCap - probesAsked;
  if (left <= 0) {
    return [`Prepared probes for this step: used up `
      + `(${probesAsked} of ${probeCap} asked). Ask your own questions.`];
  }
  return [`Prepared probes for this step (speakable questions; you `
    + `may ask at most ${left} more in this step; mark each asked `
    + `probe with its [[probe: N]] control line):`,
  ...stepProbes.map((p) => `- probe ${p.n}: ${p.q}`)];
}

// The system prompt block for one turn. The gist frames the session; the
// dimension list names what working the CURRENT step means for this
// problem; the anchors cover the items not surfaced yet, phrased as what
// hearing them sounds like so the model credits the candidate's own words
// instead of re-stating (which would leak the item); the probes are
// speakable questions for the current step, learning mode only, within the
// configured per-step budget.
export function briefBlock(options) {
  const { problem, currentStep, revealed = [], helpMode = 'learning',
    probeCap = 0, probesAsked = 0 } = options;
  const brief = problem.interviewer_brief;
  if (!brief) return '';
  const out = ['Interviewer brief (your own preparation. Listen for these; '
    + 'never state them unless the candidate asks or produces them):'];
  out.push(`Gist: ${brief.gist}`);
  const dims = (brief.dimensions[String(currentStep)] || [])
    .map((line) => `- ${line}`);
  if (dims.length) {
    out.push(`What a strong answer covers in step ${currentStep}:`, ...dims);
  }
  const anchors = anchorLines(brief, revealed);
  if (anchors.length) {
    out.push('What hearing a not-yet-surfaced item sounds like '
      + '(credit the candidate\'s own words):', ...anchors);
  }
  out.push(...probeLines(brief, currentStep, helpMode, probeCap, probesAsked));
  return out.join('\n');
}
