// TADSDI render-mermaid.js: Mermaid wrapper.

let mermaidReady = false;

function ensureInit() {
  if (!mermaidReady) {
    window.mermaid.initialize({ startOnLoad: false, securityLevel: 'loose' });
    mermaidReady = true;
  }
}

export async function renderMermaid(container, source) {
  ensureInit();
  container.innerHTML = '';
  const div = document.createElement('div');
  div.className = 'mermaid-diagram';
  container.appendChild(div);
  try {
    const { svg } = await window.mermaid.render(`mmd-${Date.now()}-${Math.floor(Math.random() * 1e6)}`, source, div);
    div.innerHTML = svg;
  } catch (err) {
    const pre = document.createElement('pre');
    pre.className = 'render-error';
    pre.textContent = `Mermaid error: ${err.message}\n\n${source}`;
    container.appendChild(pre);
  }
}
