# M0 implementation plan - scaffold, settings, provider layer

Objective per PLAN.md: a loading page with a working settings dialog and a
provider layer proven by a mock provider round trip.

## Task order (test-first where practical)

1. **T1 Scaffold.** Create `game/` layout per DESIGN.md section 4:
   `index.html`, `css/main.css`, `js/*.js` module stubs, `js/vendor/`,
   `js/problems/`, `js/prompts/`, `tests/`. `index.html` loads all assets
   with `?v=1` version params. Boot: `<body data-screen="menu">` with five
   placeholder `<section data-screen=...>` screens (menu, briefing,
   interview, grading, feedback) and a screen router in `js/app.js`
   (`window.__tadsdi` debug handle for tests). Nav buttons move between
   screens so placeholders are reachable.

2. **T2 Vendor.** Download `mermaid.min.js` (v11.x, UMD) and `katex.min.js`
   + `katex.min.css` + fonts (0.16.x) into `js/vendor/` with LICENSE files.
   Verify: local http serve, both globals present, KaTeX renders a formula,
   Mermaid renders a diagram in headless Chromium. No console errors.

3. **T3 Smoke test first (TDD).** Write `tests/m0_smoke.py` (Playwright,
   container-local `http.server`, console+pageerror capture) covering the
   M0 acceptance: (a) page loads with zero console errors, (b) settings
   dialog saves three provider rows to localStorage and reloads them after
   a page reload, (c) test-connection button reports success against the
   mock provider, (d) a mock reply renders in a placeholder chat view.
   Run it against the scaffold stubs, and make sure that each assertion
   fails for the expected reason: a missing feature, not a missing file.

4. **T4 Settings dialog.** `js/settings.js`: three rows (roles `text`,
   `vision`, `image`), each with provider id select (`openai`,
   `anthropic`, `openai-compatible`, `mock`), base URL, model, API key,
   and a Test connection button. Persist whole settings object to
   localStorage key `tadsdi.settings.v1` on Save. Load into the form on
   open. Default role mapping: `text` -> mock so tests run offline.

5. **T5 Provider layer.** `js/providers.js`: `complete(role, messages,
   options)` -> Promise<string>. Adapters:
   - `mock`: reads scripted replies from `js/vendor/mock-script.json`...
     (final home `js/prompts/mock-script.json`), keyed by an `options.key`
     match, or in order, with a small delay so streaming/pause behavior is
     observable later.
   - `openai`: fetch POST `{base}/chat/completions`, Authorization header,
     `dangerouslyAllowBrowser` semantics (plain fetch has no SDK flag; the
     adapter just sends browser-origin headers).
   - `anthropic`: fetch POST `{base}/v1/messages` with
     `anthropic-dangerous-direct-browser-access: true` header.
   - `openai-compatible`: same shape as openai but arbitrary base URL.
   - CORS and network failures reject with a message that names the
     provider and points at the base URL field in settings.

6. **T6 Green.** Run the smoke test until every assertion passes. Bump
   `?v=` on every edited file. Assert localStorage writes, not just UI.

## Verification

- `tests/m0_smoke.py` green: all four assertions pass with zero console
  errors.
- Manual probe: `curl` the served URLs returns 200 for every vendored asset.
- Commit log entry per task.

## Risks

- KaTeX fonts are many files; vendor the whole `dist/fonts` tree.
- Mermaid v11 ESM/UMD choice: use the UMD `mermaid.min.js` for a no-build page.
- Playwright under uv needs the same scratch user-data-dir pattern per
  run. M0 uses fresh contexts and seeds localStorage within one page load
  instead of cross-run profiles.
