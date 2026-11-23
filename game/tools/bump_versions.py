"""Set one cache-busting version on every asset URL that is not a vendor file.

Why one version: a browser identifies an ES module by its full URL. Two
imports of the same file with different `?v=` values load two copies of
that module. One version for all game files makes that state impossible.

Usage (from game/):
    python3 tools/bump_versions.py            report the versions in use
    python3 tools/bump_versions.py --to 11    set every game asset to v11

Report mode exits 1 when the game files carry more than one version, so a
test can use it as an assertion. Vendor files (js/vendor/) keep their own
version and are never changed.
"""

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
# The path class also allows a template hole such as `${slug}`, so a URL that
# a module builds from parts is versioned like any other.
URL_RE = re.compile(r"(?P<path>[A-Za-z0-9_./\-{}$*]+\.(?:js|css|json))\?v=(?P<ver>\d+)")


def target_files():
    yield ROOT / "index.html"
    yield from sorted((ROOT / "js").rglob("*.js"))
    # The tool's own test holds fixture URLs with deliberately mixed
    # versions, so a rewrite of that file would break the test.
    yield from sorted(
        p for p in (ROOT / "tests").glob("*.py") if p.name != "bump_versions_test.py")


def is_vendor(path):
    return "vendor/" in path


def rewrite(text, new_version=None):
    """Return (new_text, {(path, version): count}) for non-vendor URLs."""

    def sub(match):
        path, version = match.group("path"), match.group("ver")
        if is_vendor(path):
            return match.group(0)
        if new_version is not None:
            return f"{path}?v={new_version}"
        return match.group(0)

    seen = {}
    for match in URL_RE.finditer(text):
        key = (match.group("path"), match.group("ver"))
        if not is_vendor(match.group("path")):
            seen[key] = seen.get(key, 0) + 1
    return URL_RE.sub(sub, text), seen


def versions_in_use():
    """Return {version: [file names]} for every non-vendor asset URL."""
    by_version = {}
    for path in target_files():
        if not path.exists():
            continue
        for (_, version) in rewrite(path.read_text())[1]:
            names = by_version.setdefault(version, [])
            if path.name not in names:
                names.append(path.name)
    return by_version


def bump(new_version):
    changed = []
    for path in target_files():
        if not path.exists():
            continue
        text = path.read_text()
        new_text, _ = rewrite(text, new_version)
        if new_text != text:
            path.write_text(new_text)
            changed.append(path.name)
    return changed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--to", type=int, help="set every game asset to this version")
    args = parser.parse_args(argv)

    if args.to is not None:
        if args.to < 1:
            print("the version must be 1 or more", file=sys.stderr)
            return 2
        changed = bump(args.to)
        print(f"bumped to v{args.to}: {len(changed)} file(s) changed")
        if changed:
            print("  " + ", ".join(changed))
        return 0

    by_version = versions_in_use()
    for version in sorted(by_version, key=int):
        print(f"v{version}: {', '.join(sorted(by_version[version]))}")
    if len(by_version) > 1:
        print("MIXED VERSIONS: run with --to N to set one version", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
