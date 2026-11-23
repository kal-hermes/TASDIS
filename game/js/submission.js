// TADSDI submission.js: one submission panel, three tabs (DESIGN.md 8):
// LaTeX with live KaTeX preview, Mermaid with live rendered preview, prose.
// Submit inserts the artifact into the chat tagged with the current step
// and prompts an interviewer response.

import { submitArtifact } from './engine.js?v=25';
import { renderLatex } from './render-latex.js?v=25';
import { renderMermaid } from './render-mermaid.js?v=25';

const TABS = ['latex', 'mermaid', 'prose'];

function el(id) { return document.getElementById(id); }

let activeTab = 'latex';
let previewTimer = null;

function renderPreview() {
  const source = el('artifact-source').value;
  const preview = el('artifact-preview');
  preview.innerHTML = '';
  if (!source.trim()) {
    preview.textContent = '(preview)';
    return;
  }
  if (activeTab === 'latex') {
    renderLatex(preview, source);
  } else if (activeTab === 'mermaid') {
    renderMermaid(preview, source);
  } else {
    preview.textContent = source;
  }
}

function schedulePreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(renderPreview, 300);
}

function switchTab(tab) {
  activeTab = tab;
  for (const t of TABS) {
    el(`tab-btn-${t}`).classList.toggle('active', t === tab);
  }
  renderPreview();
}

export function initSubmission() {
  for (const t of TABS) {
    el(`tab-btn-${t}`).addEventListener('click', () => switchTab(t));
  }
  el('artifact-source').addEventListener('input', schedulePreview);
  el('artifact-submit').addEventListener('click', async () => {
    const source = el('artifact-source').value;
    if (!source.trim()) return;
    el('artifact-submit').disabled = true;
    // Clear now, not after the reply: the source is stored, and a reply can
    // take long enough for the candidate to start the next artifact.
    el('artifact-source').value = '';
    renderPreview();
    try {
      await submitArtifact(activeTab, source);
    } finally {
      el('artifact-submit').disabled = false;
    }
  });
  switchTab('latex');
}
