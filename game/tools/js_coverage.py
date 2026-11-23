"""Run Playwright test scripts with JavaScript coverage and write LCOV.

Why: the crapper needs an LCOV report to compute CRAP scores for the game's
JavaScript. The tests run in Python, so this runner starts Chromium's precise
JavaScript coverage on every page the tests open with `browser.new_page()`,
collects it before each navigation and at browser close, and converts it to
`coverage/lcov.info`.

Usage (from game/):
    uv run --with playwright python tools/js_coverage.py tests/m3_errors.py ...
    python3 tools/js_coverage.py --convert     rebuild from the last raw data

The exit code is the first nonzero exit code of a test script, so the runner
replaces the plain test run. Coverage adds a little run time.

Conversion notes:
- Chromium reports one range list per function: range 0 is the whole function
  with its call count, and the other ranges are blocks with their own counts.
- A block range becomes one BRDA record. Lines with code become DA records.
- The source text comes from the file on disk, which is what the test
  server serves. Several runs of one file merge by the higher count.
"""

import bisect
import json
import pathlib
import runpy
import sys
import traceback
from urllib.parse import unquote, urlparse

GAME_DIR = pathlib.Path(__file__).resolve().parent.parent
OUT = GAME_DIR / "coverage" / "lcov.info"
RAW = GAME_DIR / "coverage" / "raw.json"

collected = []
tracked = {}  # id(page) -> (page, DevTools session)
stats = {"started": 0, "reads": 0, "failed": 0}


def url_to_rel(url):
    """Path of a game module below js/, without the version query."""
    path = unquote(urlparse(url).path)
    if not path.startswith("/js/") or path.startswith("/js/vendor/"):
        return None
    return path[1:]


# ---- Chromium offsets to lines -----------------------------------------

def utf16_len(text):
    return len(text.encode("utf-16-le")) // 2


class Source:
    """Maps Chromium offsets (UTF-16 units) to lines and code positions."""

    def __init__(self, text):
        self.text = text
        self.starts = [0]
        for line in text.split("\n"):
            self.starts.append(self.starts[-1] + utf16_len(line) + 1)
        self.code_at = {}
        for number, start in enumerate(self.starts[:-1], start=1):
            # The final line has no closing newline, so its end stops at the text.
            self.code_at[number] = self._first_code(start, min(self.starts[number], len(text)))

    def _first_code(self, start, end):
        text = self.text
        offset = start
        while offset < end and text[offset] in " \t":
            offset += 1
        stripped = text[offset:end].lstrip()
        if not stripped or stripped.startswith(("//", "/*", "*")):
            return None
        return offset

    def line_of(self, offset):
        return bisect.bisect_right(self.starts, offset)

    def lines_between(self, start, end):
        return range(self.line_of(start), self.line_of(max(start, end - 1)) + 1)


def innermost_count(ranges, offset):
    """Count of the smallest range that holds the offset."""
    best = None
    for block in ranges:
        if block["startOffset"] <= offset < block["endOffset"]:
            if best is None or (block["endOffset"] - block["startOffset"] <
                                best["endOffset"] - best["startOffset"]):
                best = block
    return best["count"] if best else 0


def merge_script(entry):
    """Return ({line: hits}, {(line, block): hits}) for one coverage entry."""
    lines, branches = {}, {}
    source = Source(entry["source"])
    for function in entry["functions"]:
        ranges = function["ranges"]
        if not ranges:
            continue
        span = ranges[0]["endOffset"] - ranges[0]["startOffset"]
        start, end = ranges[0]["startOffset"], ranges[0]["endOffset"]
        for number in source.lines_between(start, end):
            code = source.code_at.get(number)
            if code is None:
                continue
            if start > code:
                # The function starts after the first code of the line, for
                # example a callback after `button.onclick = `. It owns the
                # line only when it starts on it.
                if source.line_of(start) != number:
                    continue
                code = start
            hits = innermost_count(ranges, code)
            if source.text[code] == "}":
                # A closing brace is a boundary. The line counts as run when
                # the code after the block ran too.
                after = source.code_at.get(number + 1)
                if after is not None and after < ranges[0]["endOffset"]:
                    hits = max(hits, innermost_count(ranges, after))
            # A nested callback has the smaller span, and its count is the
            # exact one for the lines inside it.
            known = lines.get(number)
            if known is None or span < known[0]:
                lines[number] = (span, hits)
        for index, block in enumerate(ranges[1:]):
            line = source.line_of(block["startOffset"])
            # Chromium lists the taken path of a branch as one block. LCOV
            # counts two outcomes, so the skipped path is the enclosing count
            # minus the block count.
            around = [r for r in ranges
                      if r is not block and r["startOffset"] <= block["startOffset"] < r["endOffset"]]
            enclosing = min(around, key=lambda r: r["endOffset"] - r["startOffset"])["count"] \
                if around else ranges[0]["count"]
            taken = block["count"]
            skipped = max(enclosing - taken, 1 if taken > 1 else 0)
            branches[(line, index, 0)] = max(branches.get((line, index, 0), 0), taken)
            branches[(line, index, 1)] = max(branches.get((line, index, 1), 0), skipped)
    return ({n: hits for n, (_span, hits) in lines.items()}, branches)


def to_lcov(entries):
    """Return the LCOV text for the collected Chromium coverage entries."""
    scripts = {}
    for entry in entries:
        rel = url_to_rel(entry.get("url", ""))
        if not rel:
            continue
        try:
            source = (GAME_DIR / rel).read_text()
        except OSError:
            continue
        scripts.setdefault(rel, []).append({**entry, "source": source})

    out = ["TN:"]
    for rel, group in sorted(scripts.items()):
        # One file runs in several page loads during a suite. A line or a
        # block counts as run when any load ran it.
        lines, branches = {}, {}
        for entry in group:
            entry_lines, entry_branches = merge_script(entry)
            for number, hits in entry_lines.items():
                lines[number] = max(lines.get(number, 0), hits)
            for key, hits in entry_branches.items():
                branches[key] = max(branches.get(key, 0), hits)
        out.append(f"SF:{rel}")
        for number, hits in sorted(lines.items()):
            out.append(f"DA:{number},{hits}")
        for (number, index, outcome), hits in sorted(branches.items()):
            out.append(f"BRDA:{number},{index},{outcome},{hits}")
        out.append("end_of_record")
    return "\n".join(out) + "\n"


# ---- Playwright hooks ---------------------------------------------------

def _start(page):
    """Begin precise JavaScript coverage for the page's current document."""
    try:
        client = page.context.new_cdp_session(page)
        client.send("Profiler.enable")
        client.send("Profiler.startPreciseCoverage", {"callCount": True, "detailed": True})
        tracked[id(page)] = (page, client)
        stats["started"] += 1
    except Exception as err:
        print(f"js_coverage: could not start coverage: {err}", file=sys.stderr)


def _harvest(page):
    """Read the coverage held for the page. Collection stays on: a restart
    would discard what the page load itself executed."""
    held = tracked.get(id(page))
    if held is None:
        return
    try:
        collected.extend(held[1].send("Profiler.takePreciseCoverage")["result"])
        stats["reads"] += 1
    except Exception as err:
        # A read that fails is lost data, so it is never silent.
        stats["failed"] += 1
        print(f"js_coverage: a coverage read failed: {err}", file=sys.stderr)


def _finish(page):
    """Read the coverage of a page that will not navigate again."""
    _harvest(page)
    held = tracked.pop(id(page), None)
    if held is not None:
        try:
            held[1].send("Profiler.stopPreciseCoverage")
        except Exception:
            pass


def install():
    from playwright.sync_api import Browser, BrowserContext, Page

    original_page, original_close = Browser.new_page, Browser.close
    original_context_page = BrowserContext.new_page
    original_goto, original_reload = Page.goto, Page.reload

    def new_page(self, **kwargs):
        # The same hook serves browser.new_page() and context.new_page().
        make = original_context_page if isinstance(self, BrowserContext) else original_page
        page = make(self, **kwargs)
        _start(page)
        return page

    def leave(page, navigate):
        # A navigation replaces the document, so read before it happens. The
        # same-origin navigations the tests use keep the collector running.
        _harvest(page)
        return navigate()

    def goto(self, *args, **kwargs):
        return leave(self, lambda: original_goto(self, *args, **kwargs))

    def reload(self, *args, **kwargs):
        return leave(self, lambda: original_reload(self, *args, **kwargs))

    def close(self, **kwargs):
        for page, _client in list(tracked.values()):
            _finish(page)
        return original_close(self, **kwargs)

    Browser.new_page = new_page
    Browser.close = close
    BrowserContext.new_page = new_page
    Page.goto = goto
    Page.reload = reload


def main(argv):
    if argv[:1] == ["--convert"]:
        # Rebuild the LCOV from the last raw collection, without a test run.
        return write_lcov(json.loads(RAW.read_text()), 0)
    if not argv:
        print(__doc__)
        return 2
    install()
    status = 0
    for script in argv:
        try:
            runpy.run_path(str(GAME_DIR / script), run_name="__main__")
        except SystemExit as exit_request:
            status = status or (exit_request.code or 0)
        except Exception:
            # A failed assertion must not stop the later scripts or the report.
            traceback.print_exc()
            status = status or 1
        sys.stdout.flush()
    for page, _client in list(tracked.values()):
        _finish(page)
    RAW.write_text(json.dumps(collected))
    return write_lcov(collected, status)


def write_lcov(entries, status):
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(to_lcov(entries))
    files = {url_to_rel(e.get("url", "")) for e in entries} - {None}
    print(f"js_coverage: wrote {OUT.relative_to(GAME_DIR)} for {len(files)} game files; "
          f"test exit status {status}; collectors started {stats['started']}, "
          f"reads {stats['reads']}, failed reads {stats['failed']}")
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
