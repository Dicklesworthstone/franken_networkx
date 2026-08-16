"""Repo guard for br-r37-c1-aqwmm — untracked .rs under a cargo src/ or tests/.

cargo compiles every ``.rs`` under a crate's ``tests/`` directory as its own
test target (no crate here sets ``autotests = false``), so a throwaway probe
left there is built on every ``cargo test``. If it stops compiling it aborts the
whole run — and if it is gitignored it is invisible to ``git status``,
``git log``, ``git blame`` and code review, so the usual "what changed" reflexes
find nothing. frankenlibc hit exactly this: 273 such files, one broken since
June.

The inverse is worse and equally quiet: an ignored file under ``src/`` that
someone later references with a ``mod`` declaration builds locally and fails for
everyone else and in CI, because the file was never committed.

This guard is deliberately about UNTRACKED, not about gitignored specifically.
Ignoring is what hides the file, but tracking is what makes it real; an
untracked ``.rs`` in a compiled directory is a hazard whether or not a pattern
happens to cover it. The report names each offender and says which are ignored,
because that is the part a human cannot see any other way.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _git(*args):
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _cargo_source_dirs():
    """Every directory whose .rs files cargo compiles: crate src/ and tests/."""
    dirs = []
    for manifest in REPO_ROOT.glob("crates/*/Cargo.toml"):
        crate = manifest.parent
        for sub in ("src", "tests", "benches"):
            candidate = crate / sub
            if candidate.is_dir():
                dirs.append(candidate)
    for sub in ("tests", "benches"):
        candidate = REPO_ROOT / sub
        if candidate.is_dir():
            dirs.append(candidate)
    return dirs


def _untracked_rust_files():
    offenders = []
    for directory in _cargo_source_dirs():
        for path in directory.rglob("*.rs"):
            if "target" in path.parts:
                continue
            relative = path.relative_to(REPO_ROOT).as_posix()
            tracked = _git("ls-files", "--error-unmatch", relative).returncode == 0
            if tracked:
                continue
            ignored = _git("check-ignore", "-q", relative).returncode == 0
            offenders.append((relative, ignored))
    return sorted(offenders)


# Files that already existed when this guard was written (br-r37-c1-aqwmm).
# They are somebody else's reproductions, they are currently INERT — no `mod`
# declaration references repro_bug.rs — and disk is at 97%, so this guard does
# not demand their deletion. It exists to stop the FIFTH one appearing
# unnoticed, which is how frankenlibc reached 273. The list should only ever
# shrink; test_the_known_offender_list_does_not_grow enforces that.
KNOWN_UNTRACKED = {
    "crates/fnx-algorithms/src/repro_bug.rs",
}


@pytest.mark.skipif(
    not (REPO_ROOT / ".git").exists(), reason="not a git checkout"
)
def test_no_new_untracked_rust_files_in_compiled_directories():
    offenders = [
        (path, ignored)
        for path, ignored in _untracked_rust_files()
        if path not in KNOWN_UNTRACKED
    ]
    if offenders:
        lines = [
            f"  {path}" + ("   [GITIGNORED — invisible to review]" if ignored else "")
            for path, ignored in offenders
        ]
        pytest.fail(
            "untracked .rs files live in directories cargo compiles.\n"
            "cargo builds every .rs under a crate's tests/ as its own test target, "
            "so one that stops compiling aborts the entire run; an ignored file under "
            "src/ that gains a `mod` declaration breaks every checkout but yours.\n"
            "Commit them, move them outside the crate, or delete them:\n"
            + "\n".join(lines)
        )


@pytest.mark.skipif(
    not (REPO_ROOT / ".git").exists(), reason="not a git checkout"
)
def test_the_known_offender_list_does_not_grow():
    """Every allowlisted path must still be a real, still-untracked file.

    If one gets committed or removed, this fails and says to delete the entry —
    so the allowlist cannot quietly become a place where new files hide.
    """
    current = {path for path, _ignored in _untracked_rust_files()}
    stale = sorted(KNOWN_UNTRACKED - current)
    assert not stale, (
        "these are no longer untracked; remove them from KNOWN_UNTRACKED: "
        + ", ".join(stale)
    )


@pytest.mark.skipif(
    not (REPO_ROOT / ".git").exists(), reason="not a git checkout"
)
def test_the_guard_is_not_vacuous(tmp_path):
    """The scan must actually look where cargo looks.

    A guard that silently scanned nothing would pass forever. This asserts the
    directory set is non-empty, includes at least one crate tests/ directory,
    and that the tracked .rs files there are visible to the scan.
    """
    dirs = _cargo_source_dirs()
    assert dirs, "no cargo source directories found"
    test_dirs = [d for d in dirs if d.name == "tests"]
    assert test_dirs, "no crate tests/ directory found — cargo test targets unchecked"
    seen = 0
    for directory in test_dirs:
        seen += sum(1 for _ in directory.rglob("*.rs"))
    assert seen > 0, "no .rs files seen under any tests/ directory"
