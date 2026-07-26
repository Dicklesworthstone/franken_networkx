"""Ledger integrity gate — a rejection row without a null control fails the suite.

Adopted 2026-07-25 from frankensqlite's `sql_pipeline_candidate_preflight`, after the
fleet-wide resurrection audit produced the decay lesson: ledger integrity is not a
one-time cleanup. The one repo that audited once and then MECHANICALLY enforced the
check sits at 1.7% VOID; repos that audited once and banked the wins sit at 25-91%.

franken_networkx measured **75.5% VOID (120/159 rejection rows)** under the six-class
taxonomy, of which **113 are VOID-NONULL**: an A/B ran, the row was rejected on a
near-1.0 wall ratio, and neither an A/A null control nor a counted mechanism was
recorded — so the lever cannot be distinguished from the harness. Those rows are not
evidence, and re-deriving levers they appear to close is pure waste.

This test makes the next such row impossible rather than merely discouraged: a new
rejection row must carry an A/A null control OR a counted mechanism (instructions,
cycles, syscalls, allocations, faults unchanged). See `scripts/perf_ledger_preflight.py`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PREFLIGHT = REPO / "scripts" / "perf_ledger_preflight.py"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(PREFLIGHT), *args],
        cwd=REPO, capture_output=True, text=True, check=False,
    )


def test_preflight_script_exists():
    assert PREFLIGHT.exists(), "the ledger preflight is the enforcement mechanism"


def test_new_rejection_rows_are_falsifiable():
    """Every rejection row added on this branch must carry a null or a counted mechanism.

    Rationale: a rejection recording neither cannot distinguish the lever from the
    harness. It will be voided by the next audit, and in the meantime it wrongly closes
    a frontier for every future agent that greps the ledger.
    """
    for base in ("origin/main", "main", "HEAD~1"):
        probe = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", base],
            cwd=REPO, capture_output=True, text=True, check=False,
        )
        if probe.returncode == 0:
            break
    else:  # pragma: no cover - a repo with no refs at all
        pytest.skip("no git ref available to diff against")

    result = _run("--check", base)
    assert result.returncode != 2, (
        "BLOCKED: a rejection row added on this branch records neither an A/A null "
        "control nor a counted mechanism.\n\n" + result.stdout + result.stderr
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_audit_mode_reports_a_void_rate():
    """The audit must keep working — a rising void rate is how decay is detected."""
    result = _run("--audit")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "rejection rows audited" in result.stdout
    assert "VOID total" in result.stdout


def test_prior_art_mode_blocks_on_a_known_closed_lever():
    """`--prior-art` must surface an existing REJECT so levers are not re-derived.

    Uses the AVX2 dense-linalg row (br-r37-c1-2zn1u), which is a real, permanent
    rejection in this ledger.
    """
    result = _run("--prior-art", "avx2", "dense")
    assert result.returncode == 2, (
        "prior-art must BLOCK on a known closed lever:\n" + result.stdout + result.stderr
    )
    assert "REJECT" in result.stdout


def test_prior_art_mode_passes_on_an_unknown_lever():
    result = _run("--prior-art", "zzz_no_such_lever_zzz")
    assert result.returncode == 0, result.stdout + result.stderr
