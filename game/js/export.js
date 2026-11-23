// TADSDI export.js: the stored session as a Markdown document.
// transcriptMarkdown is a pure function: the same session gives the same
// text. It reads the stored record only, so an export never calls a model.

const SPEAKER = { interviewer: 'Interviewer', candidate: 'Candidate', system: 'System' };
const FENCE = { latex: 'latex', mermaid: 'mermaid', prose: 'text' };

function pad(number) {
  return String(number).padStart(2, '0');
}

// The file name carries the problem and the start time, so two exports of
// one interview share a name and two interviews never do.
export function exportFileName(session) {
  const started = new Date((session.transcript[0] && session.transcript[0].ts) || session.updatedAt);
  const day = `${started.getFullYear()}${pad(started.getMonth() + 1)}${pad(started.getDate())}`;
  const time = `${pad(started.getHours())}${pad(started.getMinutes())}`;
  return `tadsdi-${session.problemId}-${day}-${time}.md`;
}

function transcriptLine(session, msg, artifact) {
  if (artifact) {
    return [
      `**Candidate** submitted a ${artifact.kind} artifact (step ${artifact.step}, ${artifact.id}):`,
      '',
      `\`\`\`${FENCE[artifact.kind] || 'text'}\n${artifact.source}\n\`\`\``,
      '',
    ];
  }
  return [`**${SPEAKER[msg.speaker] || msg.speaker}:** ${msg.text}`, ''];
}

function bulletList(title, lines) {
  return [title, '', ...lines.map((line) => `- ${line}`), ''];
}

function gradeSection(grade) {
  const out = [
    '## Grade', '',
    `- Score: ${grade.score} / 10`,
    `- Steps with transcript evidence: ${grade.process_coverage.join(', ')}`,
    '',
    '### Diagnostic rows', '',
    '| Row | Verdict | Fix |',
    '| --- | --- | --- |',
  ];
  for (const row of grade.rows) {
    out.push(`| ${row.name} | ${row.pass ? 'pass' : 'fail'} | ${row.fix || ''} |`);
  }
  out.push('');
  out.push(...bulletList('### Estimation realism',
    grade.realism.map((r) => `${r.claim}: ${r.verdict} (${r.note})`)));
  out.push(...bulletList('### Missed items', grade.missing));
  out.push(...bulletList('### Artifact comments',
    grade.artifact_comments.map((c) => `${c.artifact_id}: ${c.comment}`)));
  out.push("### Interviewer's closing", '', `> ${grade.closing}`, '');
  return out;
}

function progressReports(grades) {
  const out = ['## Progress reports', ''];
  grades.forEach((snap, i) => {
    const result = snap.result;
    out.push(`${i + 1}. ${new Date(snap.ts).toLocaleString()}: solid steps ` +
      `${result.solid_steps.join(', ')}; passing rows ${result.passing_rows.join(', ')}; ` +
      `gaps: ${result.obvious_gaps.join(', ')}. ${result.note}`);
  });
  out.push('');
  return out;
}

export function transcriptMarkdown(session) {
  const artifacts = new Map(session.artifacts.map((a) => [a.id, a]));
  const out = [
    `# System design interview: ${session.problem.title}`,
    '',
    `- Help mode: ${session.helpMode}`,
    `- Constraints: ${session.constraintMode}`,
  ];
  if (session.timer && session.timer.enabled) {
    out.push(`- Timer: ${Math.round(session.timer.presetMs / 60000)} minutes`);
  }
  out.push('', `> ${session.problem.vague_prompt}`, '', '## Transcript', '');
  for (const msg of session.transcript) {
    out.push(...transcriptLine(session, msg, artifacts.get(msg.artifactId)));
  }
  if (session.midInterviewGrades && session.midInterviewGrades.length) {
    out.push(...progressReports(session.midInterviewGrades));
  }
  if (session.grade) {
    out.push(...gradeSection(session.grade));
  }
  return out.join('\n');
}

export function downloadText(fileName, text) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Both export buttons (interview sidebar and feedback screen) write the
// same document from the stored session.
export function initExport(getSession) {
  for (const id of ['export-transcript', 'export-feedback']) {
    document.getElementById(id).addEventListener('click', () => {
      const session = getSession();
      if (session) {
        downloadText(exportFileName(session), transcriptMarkdown(session));
      }
    });
  }
}
