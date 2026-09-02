#!/usr/bin/env python3
"""Run `ubs` over the CHANGED REGIONS of oversized Python files.

br-r37-c1-nyhxy. AGENTS.md's standing gate is ``ubs <changed files>`` before every
commit, and for ``python/franken_networkx/__init__.py`` that gate cannot produce a
result: the file is ~71k lines / 3.0 MB and the python scanner module always hits
``UBS_MODULE_TIMEOUT``. Raising the limit does not help — 1500s (25 minutes)
wedges identically, measured, not assumed.

WHAT MAKES IT WORSE THAN A SLOW SCAN is how it FAILS. On a timeout ubs still
exits 0, reports ``Files: 0`` and reports ``Critical: 1`` — where that one
"critical" IS the timeout, not a finding. So the gate passes while proving
nothing, and an agent reading the tail of the output sees a clean-looking
summary. That is not hypothetical: it happened in this repo, to me, on the run
that produced this script.

THE APPROACH: emit a file the SAME LENGTH as the original in which every line
outside the changed top-level definitions is blank.

  * ubs's reported line numbers are then the REAL line numbers, so a finding can
    be acted on directly. Extracting the changed region into a short file would
    make every reported location wrong by an offset that varies per file.
  * the slice stays valid Python, because whole top-level statements are kept —
    a naive line-range cut lands mid-function and the scanner reports a syntax
    error that is an artefact of the cut.
  * blank lines are nearly free for the scanner, so the content it must actually
    analyse drops to the functions you touched.

Usage:

    scripts/ubs_changed_regions.py                # working tree vs HEAD
    scripts/ubs_changed_regions.py --staged       # the git index
    scripts/ubs_changed_regions.py FILE [FILE...] # explicit paths

Exit code is ubs's own, EXCEPT that a scan reporting ``Files: 0`` is turned into
a failure: a gate that scanned nothing must not pass.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
# Gitignored (`/target`), so nothing written here can reach the index. ubs
# prepares a shadow workspace and refuses paths outside the project, so this
# cannot live in /tmp.
SLICE_DIR = REPO / "target" / "ubs_changed_regions"

# Below this, scanning the whole file is fine and is what you want — a slice can
# only lose context. The shim is ~71k lines; the next largest Python file in the
# repo is far under this.
WHOLE_FILE_LINE_LIMIT = 5000


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout


def changed_python_files(staged: bool) -> list[pathlib.Path]:
    args = ["diff", "--name-only", "--diff-filter=ACMR"]
    if staged:
        args.append("--cached")
    names = _git(*args).split()
    return [REPO / n for n in names if n.endswith(".py") and (REPO / n).is_file()]


def changed_line_numbers(path: pathlib.Path, staged: bool) -> set[int]:
    """1-based line numbers touched in `path`, from the unified diff hunks."""
    args = ["diff", "-U0"]
    if staged:
        args.append("--cached")
    diff = _git(*args, "--", str(path.relative_to(REPO)))
    touched: set[int] = set()
    for header in re.finditer(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", diff, re.M):
        start = int(header.group(1))
        count = int(header.group(2) or 1)
        # A pure deletion has count 0; keep the line it collapsed onto so the
        # enclosing definition is still selected.
        touched.update(range(start, start + max(count, 1)))
    return touched


def covering_top_level_ranges(
    source: str, touched: set[int]
) -> list[tuple[int, int]]:
    """Line ranges of the TOP-LEVEL statements containing any touched line.

    Top level only, deliberately: keeping a whole `def`/`class` is what makes the
    slice parse, and a nested function cannot be lifted out of its parent.
    """
    tree = ast.parse(source)
    ranges = []
    for node in tree.body:
        start = min(
            [node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])]
        )
        end = getattr(node, "end_lineno", node.lineno)
        if any(start <= line <= end for line in touched):
            ranges.append((start, end))
    return ranges


def build_slice(path: pathlib.Path, touched: set[int]) -> pathlib.Path | None:
    """Write the blank-padded slice; None when nothing needs slicing."""
    source = path.read_text()
    lines = source.splitlines(keepends=True)
    ranges = covering_top_level_ranges(source, touched)
    if not ranges:
        return None
    keep = set()
    for start, end in ranges:
        keep.update(range(start, end + 1))
    SLICE_DIR.mkdir(parents=True, exist_ok=True)
    out = SLICE_DIR / path.name
    out.write_text(
        "".join(
            line if (index + 1) in keep else "\n" for index, line in enumerate(lines)
        )
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="use the git index")
    parser.add_argument("paths", nargs="*", help="explicit files (default: changed)")
    args = parser.parse_args()

    if args.paths:
        targets = [pathlib.Path(p).resolve() for p in args.paths]
    else:
        targets = changed_python_files(args.staged)
    if not targets:
        print("no changed Python files; nothing to scan")
        return 0

    to_scan: list[pathlib.Path] = []
    for path in targets:
        line_count = len(path.read_text().splitlines())
        if line_count <= WHOLE_FILE_LINE_LIMIT:
            to_scan.append(path)
            continue
        touched = changed_line_numbers(path, args.staged)
        if not touched:
            print(f"{path.name}: {line_count} lines, no diff hunks — skipped")
            continue
        sliced = build_slice(path, touched)
        if sliced is None:
            print(f"{path.name}: touched lines are outside any top-level statement")
            continue
        kept = sum(1 for line in sliced.read_text().splitlines() if line.strip())
        print(
            f"{path.name}: {line_count} lines is over the {WHOLE_FILE_LINE_LIMIT}-line "
            f"limit; scanning {kept} lines in the changed top-level definitions "
            f"(line numbers preserved)"
        )
        to_scan.append(sliced)

    print(f"\nubs {' '.join(str(p.relative_to(REPO)) for p in to_scan)}\n")
    proc = subprocess.run(
        ["ubs", *[str(p) for p in to_scan]], cwd=REPO, capture_output=True, text=True
    )
    output = proc.stdout + proc.stderr
    print(output)

    # A SCAN THAT SCANNED NOTHING MUST NOT PASS. This is the whole point of the
    # bead: ubs exits 0 on a module timeout, having reported `Files: 0`.
    files = re.search(r"^Files:\s+(\d+)", output, re.M)
    if "MODULE_TIMEOUT" in output or (files and files.group(1) == "0"):
        print(
            "FAILED: ubs reported no scanned files (module timeout). The gate "
            "proved nothing, so it does not pass.",
            file=sys.stderr,
        )
        return 1
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
