"""Ledger integrity gate — undecidable REJECTs and unprovenanced KEEPs fail.

Adopted 2026-07-25 from frankensqlite's `sql_pipeline_candidate_preflight`, after the
fleet-wide resurrection audit produced the decay lesson: ledger integrity is not a
one-time cleanup. The one repo that audited once and then MECHANICALLY enforced the
check sits at 1.7% VOID; repos that audited once and banked the wins sit at 25-91%.

franken_networkx measured **81.8% VOID (130/159 rejection rows)** under the six-class
taxonomy, of which **121 are VOID-NONULL**: an A/B ran, the row was rejected on a
near-1.0 wall ratio, and neither an A/A null control nor a counted mechanism was
recorded — so the lever cannot be distinguished from the harness. Those rows are not
evidence, and re-deriving levers they appear to close is pure waste.

This test makes the next such row impossible rather than merely discouraged: a new
REJECT must carry an A/A null control OR a counted mechanism (instructions, cycles,
syscalls, allocations, faults unchanged), and a new KEEP must record the SHA-256 of
the ELF identified from inside the benchmark process. The committed pre-commit entry
applies the rule to the exact staged ledger text. See
`scripts/perf_ledger_preflight.py`.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PREFLIGHT = REPO / "scripts" / "perf_ledger_preflight.py"
PRECOMMIT_CONFIG = REPO / ".pre-commit-config.yaml"

_SPEC = importlib.util.spec_from_file_location("fnx_perf_ledger_preflight", PREFLIGHT)
assert _SPEC is not None and _SPEC.loader is not None
ledger_gate = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ledger_gate)


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(PREFLIGHT), *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def test_preflight_script_exists():
    assert PREFLIGHT.exists(), "the ledger preflight is the enforcement mechanism"


def test_precommit_config_runs_the_staged_ledger_gate():
    text = PRECOMMIT_CONFIG.read_text(encoding="utf-8")
    assert "perf-ledger-integrity" in text
    assert "scripts/perf_ledger_preflight.py --check-staged" in text
    assert "pass_filenames: false" in text
    assert "always_run: true" in text


def test_new_rejection_rows_are_falsifiable():
    """Every rejection row added on this branch must carry a null or a counted mechanism.

    Rationale: a rejection recording neither cannot distinguish the lever from the
    harness. It will be voided by the next audit, and in the meantime it wrongly closes
    a frontier for every future agent that greps the ledger.
    """
    for base in ("origin/main", "main", "HEAD~1"):
        probe = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", base],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
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
    assert "KEEP rows audited" in result.stdout
    assert "missing ELF sha" in result.stdout


def test_staged_mode_is_the_bare_and_explicit_precommit_default():
    explicit = _run("--check-staged")
    bare = _run()
    assert explicit.returncode == 0, explicit.stdout + explicit.stderr
    assert bare.returncode == 0, bare.stdout + bare.stderr
    assert "staged index" in explicit.stdout
    assert explicit.stdout == bare.stdout


def test_reject_requires_positive_null_evidence_or_exact_counted_mechanism():
    heading = "2026-07-26 REJECT candidate"
    no_null = (
        "A/B ratio was 1.0x. No A/A null control was recorded. "
        "Retry only after measuring a null control."
    )
    assert ledger_gate.falsifiable(heading, no_null) == (False, "VOID-NONULL")

    with_null = (
        "The same-invocation A/A null was measured at median 1.001x "
        "with bootstrap CI 0.995-1.008x; the A/B effect sat inside that floor."
    )
    assert ledger_gate.falsifiable(heading, with_null) == (True, "VALID-AB")

    with_mechanism = (
        "Counted instructions and allocation counts were unchanged in both arms, "
        "so the candidate removed no work."
    )
    assert ledger_gate.falsifiable(heading, with_mechanism) == (
        True,
        "VALID-MECHANISM",
    )

    profile_only = "The named frame's self-time was unchanged and the wall ratio was 1.0x."
    assert ledger_gate.falsifiable(heading, profile_only) == (
        False,
        "VOID-NONULL",
    )

    valid_profile = (
        "RESULT: VALID-PROFILE / NO SOURCE EDIT. Rejected before any source "
        "edit. The named frame `Graph::neighbors` carried 3.2% self-time. "
        "The computed Amdahl ceiling was 1.033x."
    )
    assert ledger_gate.classify(heading, valid_profile) == "VALID-PROFILE"
    # The taxonomy recognizes old profile-only rows, but the institutional
    # new-row contract remains stricter: A/A or counted mechanism is mandatory.
    assert ledger_gate.falsifiable(heading, valid_profile) == (
        False,
        "VALID-PROFILE",
    )

    profile_with_null = (
        valid_profile
        + "\n| unchanged / unchanged A/A null | 1.001x | [0.995,1.008] |"
    )
    assert ledger_gate.classify(heading, profile_with_null) == "VALID-PROFILE"
    assert ledger_gate.falsifiable(heading, profile_with_null) == (
        True,
        "VALID-PROFILE",
    )


def test_counted_mechanism_requires_the_metric_and_result_to_be_local():
    heading = "2026-07-26 REJECT candidate"
    incidental_words = (
        "The candidate sought to remove allocations. The unchanged design "
        "then ran at 1.0x, with no A/A null control recorded."
    )
    assert ledger_gate.falsifiable(heading, incidental_words) == (
        False,
        "VOID-NONULL",
    )
    assert ledger_gate.falsifiable(
        heading,
        "Counted allocation totals were unchanged between the two arms.",
    ) == (True, "VALID-MECHANISM")

    unrelated_null_value = (
        "Null node values were preserved. The A/B wall ratio was 1.001x "
        "with CI [0.995,1.008], but no control was recorded."
    )
    assert ledger_gate.falsifiable(heading, unrelated_null_value) == (
        False,
        "VOID-NONULL",
    )


def test_valid_profile_heading_is_a_rejection_for_precommit():
    assert ledger_gate.is_rejection(
        "2026-07-26 CloudyTurtle VALID-PROFILE: no source edit"
    )


def test_keep_requires_full_in_process_loaded_elf_sha():
    digest = "a" * 64
    adjacent_shell_hash = (
        f"Before the run, sha256sum reported binary sha256={digest}. "
        "The benchmark itself printed no identity."
    )
    assert not ledger_gate.has_loaded_elf_sha(adjacent_shell_hash)
    assert ledger_gate.has_loaded_elf_sha(
        f"bench_elf_sha256={digest} (13155240 bytes) /tmp/pkg/_fnx.abi3.so"
    )
    assert ledger_gate.has_loaded_elf_sha(
        f"Line one self-reported the loaded ELF SHA-256 `{digest}` from inside the process."
    )

    rows = [("NEGATIVE_EVIDENCE.md", "2026-07-26 KEEP candidate", adjacent_shell_hash)]
    assert ledger_gate.cmd_check_rows(rows, "in a synthetic index") == 2


def test_retry_predicate_is_extracted_for_prior_art_output():
    body = (
        "RESULT: REJECT.\n\n"
        "RETRY PREDICATE: reopen only after the doubled null floor is below 1.03x\n"
        "and a named frame owns at least 30% self-time.\n\n"
        "QUALITY GATES: complete."
    )
    assert ledger_gate.retry_predicate(body) == (
        "reopen only after the doubled null floor is below 1.03x "
        "and a named frame owns at least 30% self-time."
    )


def test_candidate_mode_accepts_lever_and_surface_and_prints_retry_predicate():
    result = _run(
        "--candidate",
        "--lever",
        "raw live descriptor",
        "--surface",
        "Graph.neighbors",
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "retry_predicate=" in result.stdout
    assert "Graph.neighbors" in result.stdout


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
