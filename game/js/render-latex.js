// TADSDI render-latex.js: KaTeX wrapper.

export function renderLatex(container, tex, options = {}) {
  container.innerHTML = '';
  try {
    window.katex.render(tex, container, {
      // Throw, so a formula that does not parse gets the clear message below
      // instead of red text inside the formula.
      throwOnError: true,
      displayMode: options.displayMode !== false,
    });
  } catch (err) {
    const pre = document.createElement('pre');
    pre.className = 'render-error';
    pre.textContent = `KaTeX error: ${err.message}\n\n${tex}`;
    container.appendChild(pre);
  }
}
