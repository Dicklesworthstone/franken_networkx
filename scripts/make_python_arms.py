#!/usr/bin/env python3
"""Snapshot two PYTHON arms from ONE tree state, and refuse contaminated pairs.

br-r37-c1-aeshim. This exists because I built one arm with ``git show HEAD:...``
and the other with ``cp -r`` of the working tree, a peer landed a commit between
the two acts, and my arms ended up differing by my five-line change PLUS their
entire commit. Nothing looked wrong: both arms imported, both parity-gated, both
gave plausible ordered numbers, and the resulting test failure was perfectly
DETERMINISTIC - which felt like proof of causation and was only proof that the
arms differed. Two ledger rows were retracted.

The fix is procedural, so this makes the correct procedure the cheap one:

  * both arms are copied from ONE tree read, in one act, so no commit can land
    between them;
  * the ELF is asserted IDENTICAL across arms (a Python-arm comparison that
    differs in the binary is measuring two things);
  * the shim diff is asserted to touch ONLY the file you name, and its line
    count is printed, because "16 lines" and "hundreds of lines" look the same
    in a benchmark result;
  * the binary is checked against the Rust sources it must match, the same
    staleness rule ``tests/python/conftest.py`` enforces, because routing around
    that guard is the second half of how this went wrong.

Usage:

    scripts/make_python_arms.py OUTDIR --patch path/to/patched__init__.py

``OUTDIR/armA`` is the tree as-is; ``OUTDIR/armB`` is the tree with the named
file substituted. Point ``PYTHONPATH`` at each in turn.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PKG = REPO / "python" / "franken_networkx"
CRATES = REPO / "crates"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:  # noqa: BLE001 - provenance is best-effort
        return "unknown"


def binary_is_stale() -> tuple[bool, float]:
    """Same rule as tests/python/conftest.py, applied where arms are built."""
    ext = PKG / "_fnx.abi3.so"
    if not ext.exists():
        return True, 0.0
    newest = 0.0
    for src in CRATES.glob("**/src/**/*.rs"):
        try:
            newest = max(newest, src.stat().st_mtime)
        except OSError:
            continue
    return (ext.stat().st_mtime + 1.0 < newest), newest - ext.stat().st_mtime


def build_arms(outdir: Path, patch: Path | None, relname: str) -> int:
    outdir.mkdir(parents=True, exist_ok=True)
    arm_a, arm_b = outdir / "armA", outdir / "armB"
    for arm in (arm_a, arm_b):
        if (arm / "franken_networkx").exists():
            print(f"REFUSING: {arm} already exists; use a fresh OUTDIR", file=sys.stderr)
            return 2

    head = _git_head()
    stale, delta = binary_is_stale()
    # ONE read of the tree, copied twice, before anything else can move.
    shutil.copytree(PKG, arm_a / "franken_networkx")
    shutil.copytree(PKG, arm_b / "franken_networkx")

    if patch is not None:
        target = arm_b / "franken_networkx" / relname
        if not target.exists():
            print(f"REFUSING: {relname} not in the package", file=sys.stderr)
            return 2
        shutil.copyfile(patch, target)

    elf_a = _sha(arm_a / "franken_networkx" / "_fnx.abi3.so")
    elf_b = _sha(arm_b / "franken_networkx" / "_fnx.abi3.so")
    if elf_a != elf_b:
        print("REFUSING: arms do not share an ELF", file=sys.stderr)
        return 2

    changed = [
        p.relative_to(arm_a / "franken_networkx")
        for p in sorted((arm_a / "franken_networkx").rglob("*"))
        if p.is_file()
        and (arm_b / "franken_networkx" / p.relative_to(arm_a / "franken_networkx")).is_file()
        and _sha(p)
        != _sha(arm_b / "franken_networkx" / p.relative_to(arm_a / "franken_networkx"))
    ]
    expected = [Path(relname)] if patch is not None else []
    if changed != expected:
        print(
            f"REFUSING: arms differ in {[str(c) for c in changed]}, expected "
            f"{[str(e) for e in expected]}",
            file=sys.stderr,
        )
        return 2

    diff_lines = 0
    if patch is not None:
        out = subprocess.run(
            [
                "diff",
                str(arm_a / "franken_networkx" / relname),
                str(arm_b / "franken_networkx" / relname),
            ],
            capture_output=True,
            text=True,
        ).stdout
        diff_lines = sum(1 for ln in out.splitlines() if ln[:1] in "<>")

    print(f"  git_head        {head}")
    print(f"  elf_sha256      {elf_a}")
    print(f"  shared ELF      yes")
    print(f"  differing files {[str(c) for c in changed] or 'none (A/A pair)'}")
    print(f"  diff lines      {diff_lines}")
    if stale:
        print(
            f"  WARNING: _fnx.abi3.so is {delta:.0f}s OLDER than the newest .rs "
            "source. Both arms carry the same stale binary, so a Python-only "
            "comparison is still internally valid - but anything you conclude "
            "about behaviour may be an artifact of the stale build. Rebuild "
            "before drawing correctness conclusions."
        )
    else:
        print("  binary          current against crates/**/*.rs")
    print(f"  armA {arm_a}")
    print(f"  armB {arm_b}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outdir", type=Path)
    ap.add_argument("--patch", type=Path, default=None)
    ap.add_argument("--file", default="__init__.py")
    args = ap.parse_args(argv[1:])
    return build_arms(args.outdir, args.patch, args.file)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
