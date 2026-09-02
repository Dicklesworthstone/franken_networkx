#!/usr/bin/env python3
"""Run `ubs` over the CHANGED REGIONS of oversized Python and Rust files.

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

`crates/fnx-algorithms/src/lib.rs` (br-r37-c1-61d7x) has the same problem from
the other side: at 91k lines / 3.17 MiB the rust module DOES finish, but it
reports two criticals that are both substring false positives in test code, so
`ubs <that file>` exits 1 no matter what you changed and the gate is unusable
for small edits.

THE APPROACH: emit a file the SAME LENGTH as the original in which every line
outside the changed definitions is blank.

  * ubs's reported line numbers are then the REAL line numbers, so a finding can
    be acted on directly. Extracting the changed region into a short file would
    make every reported location wrong by an offset that varies per file.
  * the slice stays parseable, because whole definitions are kept — a naive
    line-range cut lands mid-function and the scanner reports a syntax error
    that is an artefact of the cut. Python uses `ast`; Rust uses an
    indentation heuristic that is brace-checked (see `covering_rust_ranges`).
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


# Bounded, because a gate that can hang is not a gate — which is the whole
# subject of this script. `ubs` gets a generous ceiling (a legitimate scan of a
# large slice ran 220s here) and a timeout is reported as a FAILURE, never as a
# pass. ubs surfaced these two missing timeouts on itself.
GIT_TIMEOUT_SECONDS = 60
UBS_TIMEOUT_SECONDS = 900


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
        timeout=GIT_TIMEOUT_SECONDS,
    ).stdout


def changed_source_files(staged: bool) -> list[pathlib.Path]:
    args = ["diff", "--name-only", "--diff-filter=ACMR"]
    if staged:
        args.append("--cached")
    names = _git(*args).split()
    return [
        REPO / n
        for n in names
        if n.endswith((".py", ".rs")) and (REPO / n).is_file()
    ]


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


_RUST_FN = re.compile(
    r'^(\s*)(?:pub(?:\([^)]*\))?\s+)?'
    r'(?:const\s+|async\s+|unsafe\s+|extern\s+"[^"]*"\s+)*fn\s'
)


def covering_rust_ranges(source: str, touched: set[int]) -> list[tuple[int, int]]:
    """Line ranges of the enclosing `fn` for each touched line.

    br-r37-c1-61d7x. THE UNIT IS THE FUNCTION, NOT THE TOP-LEVEL ITEM, and that
    is measured rather than stylistic: in `crates/fnx-algorithms/src/lib.rs` a
    single top-level `mod tests {` spans ~37000 lines, so top-level granularity
    would pull in 1.3 MiB — past the size where ubs silently stops running its
    expensive checks — for a one-line change. The enclosing `fn` is 20-160 lines.

    There is no Rust parser here, so this is an indentation heuristic that holds
    for rustfmt'd code: a `fn` runs to the first line at or left of its own
    indentation that starts with `}`. Every range is BRACE-CHECKED below and
    dropped if it does not balance, so a heuristic miss loses coverage rather
    than emitting a slice that cannot parse.
    """
    lines = source.splitlines()
    ranges: list[tuple[int, int]] = []
    for target in sorted(touched):
        if any(start <= target <= end for start, end in ranges):
            continue
        for index in range(min(target, len(lines)) - 1, -1, -1):
            match = _RUST_FN.match(lines[index])
            if not match:
                continue
            indent = len(match.group(1))
            for j in range(index + 1, len(lines)):
                line = lines[j]
                if not line.strip():
                    continue
                if (len(line) - len(line.lstrip())) <= indent and line.strip().startswith("}"):
                    if j + 1 >= target:
                        start = index + 1
                        while start - 2 >= 0 and lines[start - 2].strip().startswith(
                            ("#[", "///", "//!")
                        ):
                            start -= 1
                        body = "\n".join(lines[start - 1 : j + 1])
                        if body.count("{") == body.count("}"):
                            ranges.append((start, j + 1))
                    break
            break
    return ranges


def covering_ranges(path: pathlib.Path, source: str, touched: set[int]):
    if path.suffix == ".rs":
        return covering_rust_ranges(source, touched)
    return covering_top_level_ranges(source, touched)


def build_slice(path: pathlib.Path, touched: set[int]) -> pathlib.Path | None:
    """Write the blank-padded slice; None when nothing needs slicing."""
    source = path.read_text()
    lines = source.splitlines(keepends=True)
    ranges = covering_ranges(path, source, touched)
    if not ranges:
        return None
    keep = set()
    for start, end in ranges:
        keep.update(range(start, end + 1))
    SLICE_DIR.mkdir(parents=True, exist_ok=True)
    # NAMED FROM THE REPO-RELATIVE PATH, not the basename: this repo has TWELVE
    # files called `lib.rs`, so two of them changed in one commit would collide
    # here and one slice would be silently overwritten — the gate would then
    # report a clean scan of the wrong file. The suffix is preserved because ubs
    # picks its scanner from it.
    relative = path.relative_to(REPO)
    out = SLICE_DIR / (
        "__".join(relative.with_suffix("").parts) + relative.suffix
    )
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
        targets = changed_source_files(args.staged)
    if not targets:
        print("no changed Python or Rust files; nothing to scan")
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
    try:
        proc = subprocess.run(
            ["ubs", *[str(p) for p in to_scan]],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=UBS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        print(
            f"FAILED: ubs did not finish within {UBS_TIMEOUT_SECONDS}s. The gate "
            f"proved nothing and does not pass.",
            file=sys.stderr,
        )
        return 1
    output = proc.stdout + proc.stderr
    print(output)

    # A SCAN THAT SCANNED NOTHING MUST NOT PASS. This is the whole point of
    # br-r37-c1-nyhxy: ubs exits 0 on a module timeout, having reported
    # `Files: 0` and a `Critical: 1` that IS the timeout.
    if "MODULE_TIMEOUT" in output:
        print(
            "FAILED: ubs hit MODULE_TIMEOUT, so it scanned nothing. The gate "
            "proved nothing and does not pass.",
            file=sys.stderr,
        )
        return 1

    # `Files:` ALONE IS NOT A LIVENESS SIGNAL, and assuming it was would have
    # made this script fail every Rust scan. br-r37-c1-61d7x: the rust module
    # reports `Files: 0 source files (rs)` while genuinely scanning — verified by
    # findings that cite the scanned path with correct line numbers. So the real
    # question is whether there is EVIDENCE the file was read, and a finding
    # citing it is that evidence.
    files = re.search(r"^Files:\s+(\d+)", output, re.M)
    cited = any(f"{path.name}:" in output for path in to_scan)
    if files and files.group(1) == "0" and not cited:
        print(
            "FAILED: ubs reported `Files: 0` and no finding cites any scanned "
            "file, so there is no evidence anything was read. A gate that cannot "
            "show it scanned does not pass. Re-run, or scan the file directly to "
            "see which failure mode this is.",
            file=sys.stderr,
        )
        return 1
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
