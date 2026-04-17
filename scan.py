#!/usr/bin/env python3
"""
AutoBots Nexus — Front-end code scanner.
Runs HTMLHint, ESLint (embedded JS), Stylelint (embedded CSS), and Gitleaks
on the active HTML files. Designed to run unattended (no prompts).
"""

import html
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
TARGET_FILES = ["index.html", "pipeline.html"]

# ── colour helpers (disabled when piped) ──────────────────────────────────────
USE_COLOUR = sys.stdout.isatty()

def _c(code, text):
    return f"\033[{code}m{text}\033[0m" if USE_COLOUR else text

def _print(msg=""):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode())

def header(msg):  _print(f"\n{'-'*60}\n{_c('1;36', msg)}\n{'-'*60}")
def ok(msg):      _print(_c("32", f"  [OK] {msg}"))
def warn(msg):    _print(_c("33", f"  [!!] {msg}"))
def fail(msg):    _print(_c("31", f"  [FAIL] {msg}"))
def info(msg):    _print(f"  {msg}")


def run(cmd, **kwargs):
    """Run a command, return (returncode, stdout+stderr)."""
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        cwd=kwargs.get("cwd", REPO_ROOT),
        timeout=kwargs.get("timeout", 120),
        shell=True,
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode, output


# ── extraction helpers ────────────────────────────────────────────────────────

def extract_blocks(html_text, tag):
    """Extract content of all <tag>...</tag> blocks, preserving line offsets."""
    pattern = re.compile(
        rf"<{tag}[^>]*>(.*?)</{tag}>", re.DOTALL | re.IGNORECASE
    )
    blocks = []
    for m in pattern.finditer(html_text):
        # count newlines before the match to compute the starting line
        start_line = html_text[:m.start(1)].count("\n") + 1
        content = m.group(1)
        blocks.append((start_line, content))
    return blocks


def unescape_html_entities(text):
    """Decode HTML entities that appear in embedded JS/CSS (e.g. &amp; &lt;)."""
    return html.unescape(text)


# ── per-tool runners ──────────────────────────────────────────────────────────

def run_htmlhint(filepath):
    """Run HTMLHint on a single file."""
    rc, out = run(["htmlhint", str(filepath)])
    return rc, out


def run_eslint_on_embedded(filepath, html_text):
    """Extract <script> blocks, write to temp file, run ESLint."""
    blocks = extract_blocks(html_text, "script")
    if not blocks:
        return 0, "(no embedded JS found)"

    combined = []
    for start_line, content in blocks:
        # pad with blank lines so ESLint line numbers roughly match the source
        combined.append("\n" * (start_line - len(combined) - 1))
        combined.append(unescape_html_entities(content))
    js_text = "\n".join(combined)

    with tempfile.NamedTemporaryFile(
        suffix=".js", prefix=f"{filepath.stem}_",
        dir=REPO_ROOT, delete=False, mode="w", encoding="utf-8"
    ) as tmp:
        tmp.write(js_text)
        tmp_path = tmp.name

    try:
        rc, out = run(["eslint", "--no-config-lookup", "-c", str(REPO_ROOT / "eslint.config.mjs"), tmp_path])
        # replace temp filename with original for readability
        out = out.replace(tmp_path, str(filepath))
        out = out.replace(Path(tmp_path).name, filepath.name)
    finally:
        os.unlink(tmp_path)
    return rc, out


def run_stylelint_on_embedded(filepath, html_text):
    """Extract <style> blocks, write to temp file, run Stylelint."""
    blocks = extract_blocks(html_text, "style")
    if not blocks:
        return 0, "(no embedded CSS found)"

    combined = []
    for start_line, content in blocks:
        combined.append("\n" * (start_line - len(combined) - 1))
        combined.append(unescape_html_entities(content))
    css_text = "\n".join(combined)

    with tempfile.NamedTemporaryFile(
        suffix=".css", prefix=f"{filepath.stem}_",
        dir=REPO_ROOT, delete=False, mode="w", encoding="utf-8"
    ) as tmp:
        tmp.write(css_text)
        tmp_path = tmp.name

    try:
        rc, out = run(["stylelint", tmp_path])
        out = out.replace(tmp_path, str(filepath))
        out = out.replace(Path(tmp_path).name, filepath.name)
    finally:
        os.unlink(tmp_path)
    return rc, out


def run_gitleaks():
    """Run Gitleaks on the repo."""
    rc, out = run(["gitleaks", "detect", "--source", str(REPO_ROOT), "--no-git", "-v"])
    return rc, out


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    _print(_c("1;37", "\n[SCAN] AutoBots Nexus -- Code Scan"))
    _print(f"   Targets: {', '.join(TARGET_FILES)}")

    totals = {"htmlhint": 0, "eslint": 0, "stylelint": 0, "gitleaks": 0}
    all_details = {}

    for filename in TARGET_FILES:
        filepath = REPO_ROOT / filename
        if not filepath.exists():
            warn(f"{filename} not found — skipping")
            continue

        html_text = filepath.read_text(encoding="utf-8")

        # ── HTMLHint ──
        header(f"HTMLHint  ·  {filename}")
        rc, out = run_htmlhint(filepath)
        if rc == 0 and ("0 errors" in out.lower() or "found 0" in out.lower() or not out):
            ok("No issues")
        else:
            # count errors/warnings from output
            err_match = re.search(r"(\d+)\s+error", out, re.IGNORECASE)
            warn_match = re.search(r"(\d+)\s+warning", out, re.IGNORECASE)
            count = int(err_match.group(1)) if err_match else 0
            count += int(warn_match.group(1)) if warn_match else 0
            totals["htmlhint"] += count
            info(out)

        # ── ESLint ──
        header(f"ESLint   ·  {filename}  (embedded JS)")
        rc, out = run_eslint_on_embedded(filepath, html_text)
        if rc == 0:
            ok("No issues")
        else:
            err_match = re.search(r"(\d+)\s+error", out)
            warn_match = re.search(r"(\d+)\s+warning", out)
            count = int(err_match.group(1)) if err_match else 0
            count += int(warn_match.group(1)) if warn_match else 0
            totals["eslint"] += count
            info(out)

        # ── Stylelint ──
        header(f"Stylelint · {filename}  (embedded CSS)")
        rc, out = run_stylelint_on_embedded(filepath, html_text)
        if rc == 0:
            ok("No issues")
        else:
            # stylelint outputs one line per issue
            lines = [l for l in out.splitlines() if l.strip() and not l.startswith(" ")]
            issue_lines = [l for l in out.splitlines() if re.match(r"\s+\d+:\d+", l)]
            totals["stylelint"] += len(issue_lines) if issue_lines else (1 if rc else 0)
            info(out)

    # ── Gitleaks ──
    header("Gitleaks  ·  repo-wide secret scan")
    rc, out = run_gitleaks()
    if rc == 0:
        ok("No leaks detected")
    else:
        leak_count = out.count("RuleID") if out else 1
        totals["gitleaks"] = leak_count
        fail(f"{leak_count} potential leak(s)")
        info(out)

    # ── Summary ──
    header("SCAN SUMMARY")
    grand_total = sum(totals.values())
    for tool, count in totals.items():
        label = f"{tool:12s}"
        if count == 0:
            ok(f"{label} clean")
        else:
            warn(f"{label} {count} finding(s)")

    _print()
    if grand_total == 0:
        _print(_c("1;32", "  [PASS] All checks passed -- 0 findings."))
    else:
        _print(_c("1;33", f"  [WARN] {grand_total} total finding(s) across all tools."))
    _print()

    return 1 if grand_total > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
