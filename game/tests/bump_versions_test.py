"""Test for tools/bump_versions.py. Run from game/:
    python3 tests/bump_versions_test.py
"""

import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

GAME_DIR = pathlib.Path(__file__).resolve().parent.parent
TOOL = GAME_DIR / "tools" / "bump_versions.py"
URL_RE = re.compile(r"([A-Za-z0-9_./\-{}$*]+\.(?:js|css|json))\?v=(\d+)")


def make_tree(root):
    """A small copy of the layout the tool walks, with mixed versions."""
    (root / "tools").mkdir()
    (root / "js" / "vendor").mkdir(parents=True)
    (root / "js" / "prompts").mkdir(parents=True)
    (root / "tests").mkdir()
    shutil.copy(TOOL, root / "tools" / "bump_versions.py")
    files = {
        "index.html": ('<link rel="stylesheet" href="js/vendor/katex.min.css?v=1">\n'
                       '<link rel="stylesheet" href="css/main.css?v=4">\n'
                       '<script src="js/vendor/mermaid.min.js?v=1"></script>\n'
                       '<script type="module" src="js/app.js?v=7"></script>\n'),
        "js/app.js": "import { initEngine } from './engine.js?v=5';\n"
                     "import { loadProblems } from './problems.js?v=3';\n",
        "js/engine.js": "import { STEPS } from './prompts/assemble.js?v=4';\n",
        "js/context.js": "import { STEPS } from './prompts/assemble.js?v=3';\n"
                         "import { assembleInterviewerPrompt } from './prompts/assemble.js?v=3';\n",
        "js/providers.js": "const url = new URL('prompts/mock-script.json?v=4', base);\n",
        # a URL built from a template hole must be versioned too
        "js/problems.js": "const url = new URL(`problems/${slug}.json?v=3`, import.meta.url).href;\n",
        "js/vendor/mermaid.min.js": "// vendored, must stay untouched\n",
        "js/prompts/assemble.js": "import { ESTIMATION_REFERENCE } from './estimation.js?v=3';\n",
        "tests/vendor_probe.py": "KATEX_CSS = '/js/vendor/katex.min.css?v=1'\n",
        "tests/m2_units.py": "await import('./js/grader.js?v=6');\n",
        # fixture URLs in the tool's own test must survive a bump
        "tests/bump_versions_test.py": "fixture = \"./engine.js?v=5\"\nfixture2 = './engine.js?v=3'\n",
    }
    for rel, text in files.items():
        (root / rel).write_text(text)


def refs(text):
    """Every (path, version) pair in the text."""
    return sorted(set(URL_RE.findall(text)))


def game_refs(text):
    """(path, version) pairs that are not vendor URLs."""
    return [r for r in refs(text) if "vendor/" not in r[0]]


def run(root, *args):
    return subprocess.run(
        [sys.executable, str(root / "tools" / "bump_versions.py"), *args],
        capture_output=True, text=True)


def main():
    failures = []

    def check(name, condition, detail=""):
        print(f"  {'ok  ' if condition else 'FAIL'} {name}{'' if condition else ': ' + detail}")
        if not condition:
            failures.append(name)

    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        make_tree(root)
        own_test_before = (root / "tests" / "bump_versions_test.py").read_text()

        # 1. report mode refuses a mixed tree
        report = run(root)
        check("report exits 1 on mixed versions", report.returncode == 1, report.stdout + report.stderr)
        check("report names the problem", "MIXED VERSIONS" in report.stderr, report.stderr)

        # 2. bump sets one version on game assets only
        bump = run(root, "--to", "10")
        check("bump exits 0", bump.returncode == 0, bump.stderr)
        for rel in ["index.html", "js/app.js", "js/engine.js", "js/context.js",
                    "js/providers.js", "js/prompts/assemble.js", "tests/m2_units.py"]:
            versions = {v for (_, v) in game_refs((root / rel).read_text())}
            check(f"{rel} carries only v10 on game assets", versions == {"10"}, f"{versions}")

        template_url = (root / "js" / "problems.js").read_text()
        check("a URL with a template hole is versioned", "problems/${slug}.json?v=10" in template_url,
              template_url)

        vendor_refs = [r for r in refs((root / "index.html").read_text()) +
                       refs((root / "tests" / "vendor_probe.py").read_text())
                       if "vendor/" in r[0]]
        check("vendor URLs stay at v1",
              len(vendor_refs) == 3 and all(v == "1" for (_, v) in vendor_refs), f"{vendor_refs}")

        # 3. the tool's own test file is never rewritten
        own_test_after = (root / "tests" / "bump_versions_test.py").read_text()
        check("the tool's own test is untouched", own_test_after == own_test_before, own_test_after)

        # 4. report mode passes a uniform tree
        report = run(root)
        check("report exits 0 on one version", report.returncode == 0, report.stdout + report.stderr)

        # 5. bumping to the same version again changes nothing
        again = run(root, "--to", "10")
        check("second bump changes no file", "0 file(s) changed" in again.stdout, again.stdout)

        # 6. a bad version is refused
        bad = run(root, "--to", "0")
        check("version 0 is refused", bad.returncode == 2, bad.stdout + bad.stderr)

    print(f"BUMP VERSIONS: {'PASS' if not failures else 'FAIL'} ({len(failures)} failed)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
