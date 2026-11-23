"""Vendor probe: KaTeX and Mermaid render from local vendored files."""
import pathlib
import subprocess
import sys
import time
import socket

from playwright.sync_api import sync_playwright

GAME_DIR = pathlib.Path(__file__).resolve().parent.parent
PORT = 8138
BASE = f"http://127.0.0.1:{PORT}"

PROBE_HTML = """<!DOCTYPE html>
<html><head>
<link rel="stylesheet" href="/js/vendor/katex.min.css?v=1">
</head><body>
<div id="math"></div>
<div id="diagram"><pre class="mermaid">graph LR; A[Client]-->B[Server];</pre></div>
<script src="/js/vendor/katex.min.js?v=1"></script>
<script src="/js/vendor/mermaid.min.js?v=1"></script>
<script type="module">
  katex.render('c = \\\\sqrt{a^2+b^2}', document.getElementById('math'));
  await mermaid.run();
  document.body.dataset.probeDone = '1';
</script>
</body></html>"""

def wait_port(port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False

(GAME_DIR / "tests" / "_vendor_probe.html").write_text(PROBE_HTML)
server = subprocess.Popen(
    [sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
    cwd=GAME_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
errors = []
try:
    assert wait_port(PORT), "server did not start"
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page()
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{BASE}/tests/_vendor_probe.html", wait_until="networkidle")
        try:
            page.wait_for_selector("body[data-probe-done='1']", timeout=10000)
        except Exception:
            state = page.evaluate("() => ({katex: typeof window.katex, mermaid: typeof window.mermaid, body: document.body.outerHTML.slice(0, 400)})")
            print("PROBE STATE:", state)
            raise
        katex_html = page.locator("#math .katex").count()
        assert katex_html >= 1, "KaTeX did not render .katex element"
        svg = page.locator("#diagram svg").count()
        assert svg >= 1, "Mermaid did not render an svg"
        assert not errors, f"console/page errors: {errors}"
        browser.close()
    print("VENDOR PROBE: PASS (katex + mermaid render, zero errors)")
finally:
    (GAME_DIR / "tests" / "_vendor_probe.html").unlink(missing_ok=True)
    server.terminate()
    server.wait(timeout=5)
