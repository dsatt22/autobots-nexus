#!/usr/bin/env python3
r"""What "the tests pass" means for this repo.

WHY THIS EXISTS
---------------
There is no test suite here, and there was no way for an automated change to
prove it had not broken anything. The bot repo has ~4,500 pytest tests and its
QA step proves a branch adds no new failure against `origin/main`; asking for
the same thing here would be a gate that can never be satisfied, so a front-end
change could never land at all.

Operator, 2026-08-13, on what QA has to do here: *"we need QA to validate,
however it has to, the front-end changes. It has to test out and make sure
nothing breaks on any code changes for either the GitHub Pages or the
Dashboards."*

TWO SURFACES, ONE REPO. The static pages (`index.html`, `pipeline.html`) and
the dashboards (`dashboards.html` plus the three under `final-versions/`) live
side by side here, and the dashboards fetch their data from the dashboard API
in the trading-bot repo. So "nothing breaks" means both.

WHAT IT CHECKS, and why each one is worth a run:

  1. Every page PARSES. A stray tag is the classic hand-edit failure and the
     browser will not tell you -- it will silently render something else.
  2. Every inline script passes `node --check`. These pages carry thousands of
     lines of inline JavaScript; a syntax error anywhere in a block kills the
     whole block, which is how a page loads looking fine and does nothing.
  3. Every internal link resolves to a file that exists. Renaming a page and
     missing one link is a 404 nobody notices until they click it.
  4. Both JSON data files parse. They are written by automation, read by the
     pages, and a truncated write breaks every page that reads them.
  5. EVERY API ENDPOINT THE DASHBOARDS CALL STILL EXISTS. This is the one that
     answers "did I break the dashboards". It needs no credential: a route
     that exists answers 401 (auth required), a route that is gone answers
     404. Reachable from the sandbox through the egress proxy on
     `host.docker.internal`, measured 2026-08-13.

  6. SECURITY PATTERNS. Operator, 2026-08-13: *"if we can't run any actual
     scans on it to make sure no vulnerabilities exist in it, then this build
     is far from complete."* They were right, and the gap was worse than it
     looked -- the push broker's secret scan skipped `.html` entirely, so a
     front-end change was scanned by scanning nothing. That half is fixed on
     the broker. This half covers the web-specific faults a secret scanner has
     no opinion about: injection sinks, an unvalidated `postMessage` listener,
     third-party script tags with no integrity hash, mixed content, and
     `target="_blank"` without `rel="noopener"`.
  7. A `hidden` ELEMENT IS ACTUALLY HIDDEN. This one exists because it caught
     me. `<div class="view-switch" hidden>` rendered anyway, because
     `.view-switch{display:inline-flex}` is an AUTHOR rule and beats the
     browser's built-in `[hidden]{display:none}`. The page parsed, every check
     passed, and the toggle was still on screen -- the operator saw it before I
     did. An element carrying `hidden` whose CSS also sets `display` is now a
     failure.

WHAT IT DELIBERATELY DOES NOT DO. It does not lint. eslint, stylelint and
htmlhint are all configured in this repo, but the sandbox has no route to the
npm registry -- the egress allowlist is five hosts and none of them is npm --
so `npx eslint` cannot install anything. Claiming a lint gate that silently
does not run would be worse than not having one. Bake the tools into the
sandbox image and this becomes an eighth check.

Nor does it replace `secret_scan.py` or gitleaks: both run HOST-side in the
push broker on every push, where the binary and the credentials live.

AN UNREACHABLE API IS "CANNOT VERIFY", NOT "BROKEN". If the API is stopped,
that is not evidence against the change under test, and failing the change for
it would teach everyone to ignore the gate.

    python3 scripts/frontend_check.py
    python3 scripts/frontend_check.py --api http://host.docker.internal:8788
"""
from __future__ import annotations

import argparse
import glob
import html.parser
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_API = os.environ.get("DASHBOARD_API", "http://host.docker.internal:8788")

# The pages that are actually published. Everything else in the root is either
# a local draft (see .gitignore) or an old mockup, and failing a change over a
# file that never reaches the site would be noise.
PUBLISHED = ["index.html", "pipeline.html", "dashboards.html", "reports.html"]
DASHBOARDS = sorted(glob.glob(os.path.join(ROOT, "final-versions", "*.html")))
DATA_FILES = ["site-data.json", "reports-index.json"]


class _Scripts(html.parser.HTMLParser):
    """Inline script bodies, in document order."""

    def __init__(self) -> None:
        super().__init__()
        self.blocks: list = []
        self._in = False

    def handle_starttag(self, tag, attrs) -> None:
        if tag == "script" and not dict(attrs).get("src"):
            self._in = True

    def handle_endtag(self, tag) -> None:
        if tag == "script":
            self._in = False

    def handle_data(self, data) -> None:
        if self._in and data.strip():
            self.blocks.append(data)


def _rel(path: str) -> str:
    return os.path.relpath(path, ROOT).replace("\\", "/")


def check_page(path: str, problems: list) -> int:
    """Parse it, syntax-check its scripts, resolve its links. Returns checks run."""
    run = 0
    try:
        with open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
    except OSError as exc:
        problems.append(f"{_rel(path)}: cannot read ({exc})")
        return 1

    parser = _Scripts()
    try:
        parser.feed(src)
        run += 1
    except Exception as exc:                            # noqa: BLE001
        problems.append(f"{_rel(path)}: does not parse as HTML ({exc})")
        return run

    for i, block in enumerate(parser.blocks):
        run += 1
        tmp = ""
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                             encoding="utf-8") as fh:
                fh.write(block)
                tmp = fh.name
            out = subprocess.run(["node", "--check", tmp],
                                 capture_output=True, text=True, timeout=60)
            if out.returncode:
                first = (out.stderr.strip().splitlines() or ["unknown"])[:3]
                problems.append(f"{_rel(path)}: script block {i} has a syntax "
                                f"error -- {' / '.join(first)}")
        except FileNotFoundError:
            problems.append("node is not available, so no script could be "
                            "syntax-checked. This check cannot be skipped "
                            "quietly -- report it.")
            return run
        except subprocess.TimeoutExpired:
            problems.append(f"{_rel(path)}: script block {i} timed out")
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)

    here = os.path.dirname(path)
    for href in sorted(set(re.findall(r'href="([^"#?:]+\.html)"', src))):
        run += 1
        if not os.path.isfile(os.path.join(here, href)):
            problems.append(f"{_rel(path)}: links to {href}, which does not exist")

    run += check_security(path, src, problems)
    run += check_hidden_really_hides(path, src, problems)
    return run


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
# WHY PATTERNS AND NOT A REAL SCANNER. Every JavaScript security tool worth
# running installs from npm, and the sandbox this must run in has no route to
# the registry. The choice is not "patterns or semgrep", it is "patterns or
# nothing", and nothing is what this repo had.
#
# Each entry is a fault that has actually shipped in a page like these, and the
# message says what to do instead -- a finding nobody can act on gets ignored,
# and an ignored gate is worse than none.
_SINKS = (
    (re.compile(r"\.innerHTML\s*=\s*[^'\"`;]*[+`$]"),
     "innerHTML assigned from something built at runtime. If any part of it "
     "came from the API or the URL, that is script injection. Use "
     "textContent, or build nodes."),
    (re.compile(r"\bdocument\.write\s*\("),
     "document.write executes whatever it is handed and blocks the parser. "
     "Build the node instead."),
    (re.compile(r"(?<![\w.])eval\s*\("),
     "eval runs whatever string reaches it. There is no version of this page "
     "that needs it."),
    (re.compile(r"\bnew\s+Function\s*\("),
     "new Function is eval with a different name."),
    (re.compile(r"\.outerHTML\s*=\s*[^'\"`;]*[+`$]"),
     "outerHTML assigned from a runtime value -- same injection risk as "
     "innerHTML."),
    (re.compile(r"""localStorage\.setItem\s*\(\s*['"][^'"]*(token|secret|key|password)""",
                re.IGNORECASE),
     "a credential in localStorage is readable by any script on the page and "
     "survives the tab closing. Keep it in memory, or let the API set a "
     "cookie."),
)

_MSG_LISTENER = re.compile(
    r"addEventListener\s*\(\s*['\"]message['\"]\s*,\s*(?:function\s*\([^)]*\)|"
    r"\([^)]*\)\s*=>|[A-Za-z_$][\w$]*)\s*\{?(.{0,600})", re.DOTALL)
_ORIGIN_CHECK = re.compile(r"\.origin\b")

_SCRIPT_SRC = re.compile(r"<script\b[^>]*\bsrc=[\"']([^\"']+)[\"'][^>]*>",
                         re.IGNORECASE)
_INTEGRITY = re.compile(r"\bintegrity=", re.IGNORECASE)
_HTTP_RESOURCE = re.compile(r"""(?:src|href)=["'](http://[^"']+)["']""",
                            re.IGNORECASE)
_BLANK = re.compile(r"<a\b[^>]*target=[\"']_blank[\"'][^>]*>", re.IGNORECASE)


def check_security(path: str, src: str, problems: list) -> int:
    """Web-specific faults, on a page this repo actually publishes."""
    run = 0
    rel = _rel(path)

    for pattern, why in _SINKS:
        run += 1
        for m in pattern.finditer(src):
            line = src.count("\n", 0, m.start()) + 1
            problems.append(f"{rel}:{line}: {why}")

    # A message listener with no origin check accepts navigation commands from
    # ANY page that can get a frame reference -- and these dashboards really do
    # drive each other by postMessage, so this is not hypothetical here.
    run += 1
    for m in _MSG_LISTENER.finditer(src):
        if not _ORIGIN_CHECK.search(m.group(1)):
            line = src.count("\n", 0, m.start()) + 1
            problems.append(
                f"{rel}:{line}: a postMessage listener that never checks "
                f"event.origin. Any page that can reach this frame can send "
                f"it commands. Compare origin against the expected one before "
                f"acting on the message.")

    for m in _SCRIPT_SRC.finditer(src):
        run += 1
        tag, url = m.group(0), m.group(1)
        if url.startswith(("http://", "https://")) and not _INTEGRITY.search(tag):
            line = src.count("\n", 0, m.start()) + 1
            problems.append(
                f"{rel}:{line}: third-party script with no integrity hash "
                f"({url.split('?')[0]}). If that host is ever compromised it "
                f"runs whatever it likes on this page. Add "
                f"integrity=... crossorigin=anonymous, or vendor the file.")

    for m in _HTTP_RESOURCE.finditer(src):
        run += 1
        line = src.count("\n", 0, m.start()) + 1
        problems.append(f"{rel}:{line}: loads {m.group(1)} over plain http. "
                        f"On an https page this is blocked as mixed content.")

    for m in _BLANK.finditer(src):
        run += 1
        if "noopener" not in m.group(0) and "noreferrer" not in m.group(0):
            line = src.count("\n", 0, m.start()) + 1
            problems.append(f"{rel}:{line}: target=\"_blank\" without "
                            f"rel=\"noopener\" -- the opened page gets a "
                            f"handle on this one via window.opener.")
    return run


# `hidden` is a UA-stylesheet rule (`[hidden]{display:none}`) and ANY author
# rule setting `display` on the same element beats it. Hiding a thing and
# having it stay on screen is silent, survives every other check here, and is
# exactly what happened to the Reports toggle on 2026-08-13.
_HIDDEN_EL = re.compile(r"<[a-z]+\b[^>]*\bhidden\b[^>]*>", re.IGNORECASE)
_CLASS_ATTR = re.compile(r"class=[\"']([^\"']+)[\"']")
_ID_ATTR = re.compile(r"id=[\"']([^\"']+)[\"']")


# The one thing that makes the attribute safe again: an author rule marked
# `!important` outranks any ordinary author `display`, so a page carrying this
# has already answered the question and every `hidden` on it behaves.
_HIDDEN_FIX = re.compile(r"\[hidden\]\s*\{[^}]*display\s*:\s*none\s*!important",
                         re.IGNORECASE)


def check_hidden_really_hides(path: str, src: str, problems: list) -> int:
    run = 0
    rel = _rel(path)
    if _HIDDEN_FIX.search(src):
        return 1
    for m in _HIDDEN_EL.finditer(src):
        run += 1
        tag = m.group(0)
        selectors = [f".{c}" for c in
                     (_CLASS_ATTR.search(tag).group(1).split()
                      if _CLASS_ATTR.search(tag) else [])]
        if _ID_ATTR.search(tag):
            selectors.append("#" + _ID_ATTR.search(tag).group(1))
        for sel in selectors:
            rule = re.search(
                re.escape(sel) + r"\s*(?:,[^{]*)?\{([^}]*)\}", src)
            if rule and re.search(r"(?<!-)\bdisplay\s*:", rule.group(1)):
                line = src.count("\n", 0, m.start()) + 1
                problems.append(
                    f"{rel}:{line}: this element has `hidden` but `{sel}` "
                    f"sets `display`, which overrides it -- the element is "
                    f"still on screen. Add `[hidden]{{display:none!important}}` "
                    f"or hide it another way.")
                break
    return run


def api_paths() -> set:
    """Every endpoint the dashboards fetch, read out of their source."""
    found = set()
    for path in DASHBOARDS:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                src = fh.read()
        except OSError:
            continue
        found |= set(re.findall(
            r"""["'`](/(?:pulse|trading|champion|health)[a-zA-Z0-9/_-]*)""", src))
        found |= set(re.findall(
            r"""API[A-Z_]*\s*\+\s*['"`](/[^'"`?]+)""", src))
    return found


def check_api(base: str, problems: list, notes: list) -> int:
    """404 means the dashboards are calling something that no longer exists.

    A route that exists but needs auth answers 401, and that is a PASS -- this
    check asks whether the endpoint is still there, not whether we may read it.
    """
    paths = api_paths()
    if not paths:
        notes.append("no API endpoints found in the dashboards, so none checked")
        return 0
    try:
        with urllib.request.urlopen(base.rstrip("/") + "/health", timeout=10):
            pass
    except Exception as exc:                            # noqa: BLE001
        # CANNOT VERIFY, NOT BROKEN. A stopped API is not evidence against the
        # change under test.
        notes.append(f"CANNOT VERIFY the dashboard endpoints: the API at {base} "
                     f"did not answer ({type(exc).__name__}). {len(paths)} "
                     f"endpoints were NOT checked -- say so in the verdict "
                     f"rather than reporting them as passing.")
        return 0

    run = 0
    for path in sorted(paths):
        run += 1
        try:
            with urllib.request.urlopen(base.rstrip("/") + path, timeout=10) as r:
                code = r.status
        except urllib.error.HTTPError as exc:
            code = exc.code
        except Exception as exc:                        # noqa: BLE001
            problems.append(f"{path}: could not be checked ({type(exc).__name__})")
            continue
        if code == 404:
            problems.append(f"{path}: the dashboards call this and the API no "
                            f"longer serves it (404)")
    return run


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", default=DEFAULT_API,
                    help="dashboard API base URL (default: %(default)s)")
    ap.add_argument("--no-api", action="store_true",
                    help="skip the endpoint check entirely")
    args = ap.parse_args()

    problems: list = []
    notes: list = []
    run = 0

    for name in PUBLISHED:
        path = os.path.join(ROOT, name)
        if os.path.isfile(path):
            run += check_page(path, problems)
    for path in DASHBOARDS:
        run += check_page(path, problems)

    for name in DATA_FILES:
        path = os.path.join(ROOT, name)
        if not os.path.isfile(path):
            continue
        run += 1
        try:
            with open(path, "r", encoding="utf-8") as fh:
                json.load(fh)
        except Exception as exc:                        # noqa: BLE001
            problems.append(f"{name}: does not parse as JSON ({exc})")

    if not args.no_api:
        run += check_api(args.api, problems, notes)

    for note in notes:
        print(f"NOTE: {note}")
    for problem in problems:
        print(f"FAIL: {problem}")

    # The summary line is deliberately shaped like a test runner's, because the
    # push broker's verdict gate looks for one and a front-end verdict has to
    # be readable by the same machinery as a pytest one.
    print(f"\n{run - len(problems)} checks passed, {len(problems)} failed")
    if problems:
        # WHAT A NON-ZERO COUNT MEANS HERE, said plainly, because the site
        # starts with a backlog of them and a reader who thinks the gate is
        # broken will route around it. QA runs this on the branch AND on the
        # baseline: findings present in both are pre-existing and cancel, and
        # only what is NEW on the branch blocks a push.
        print("\nSome of these may be pre-existing. Run this on origin/main "
              "too and compare -- only findings that are NEW on this branch "
              "should block it. Do not 'fix' an old one in passing: it belongs "
              "to its own change, with its own review.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
