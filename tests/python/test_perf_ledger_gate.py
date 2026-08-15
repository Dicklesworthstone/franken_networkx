"""Ledger integrity gate — undecidable REJECTs and unprovenanced KEEPs fail.

Adopted 2026-07-25 from frankensqlite's `sql_pipeline_candidate_preflight`, after the
fleet-wide resurrection audit produced the decay lesson: ledger integrity is not a
one-time cleanup. The one repo that audited once and then MECHANICALLY enforced the
check sits at 1.7% VOID; repos that audited once and banked the wins sit at 25-91%.

The current franken_networkx audit measures **75.6% VOID (133/176 rejection rows)**
under the six-class taxonomy, of which **122 are VOID-NONULL**: an A/B ran, the row
was rejected on a near-1.0 wall ratio, and neither an A/A null control nor a counted
mechanism was recorded — so the lever cannot be distinguished from the harness. Those
rows are not evidence, and re-deriving levers they appear to close is pure waste.

This test makes the next such row impossible rather than merely discouraged: a new
REJECT must carry an A/A null control OR a counted mechanism (instructions, cycles,
syscalls, allocations, faults unchanged). A new KEEP must record the in-process ELF
SHA-256, a numeric A/A null, and median-CI-only decision metadata. It must also classify
the result as either a same-invocation win over the actual NetworkX incumbent, or a
non-campaign SELF-SPEEDUP maintenance result. The committed pre-commit entry applies
the rule to the exact staged ledger text. See `scripts/perf_ledger_preflight.py`.
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


def test_gate_selfcheck_covers_its_historical_escape_classes():
    result = _run("--selfcheck")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "gate selfcheck: PASS" in result.stdout
    assert "own_ledger_sentinels=6/6" in result.stdout


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


def test_comparison_class_is_an_explicit_field_never_inferred_from_prose():
    """Policy 2 (2026-07-27): a bare multiplier is not a competitive claim.

    A self-speedup — our own code before vs after — is maintenance. Only a ratio
    against the actual legacy incumbent, measured with the incumbent running
    side-by-side in the SAME invocation, is campaign output.

    The class is a declared field, never inferred from prose, and this test pins
    that: a self-speedup row routinely *mentions* NetworkX while explaining a public
    loss, so any prose rule that keys on "networkx" plus "same invocation" would
    promote maintenance to campaign output. Both prose forms below must therefore
    read as UNLABELED.
    """
    heading = "2026-07-27 KEEP: some lever — 4.0x"

    self_speedup_prose = (
        "Same-binary interleaved A/B: the frozen ORIG arm vs the candidate arm, "
        "21 paired rounds, ratio 4.0x. This is a self-speedup."
    )
    assert ledger_gate.claim_class(heading, self_speedup_prose) == "UNLABELED"

    incumbent_prose = (
        "Measured against genuine unpatched networkx 3.6.1 running side-by-side in "
        "the same invocation, with an A/A null control: 4.0x."
    )
    assert ledger_gate.claim_class(heading, incumbent_prose) == "UNLABELED"

    assert ledger_gate.claim_class(heading, "comparison_class = SELF-SPEEDUP") == "SELF-SPEEDUP"
    assert ledger_gate.claim_class(heading, "comparison_class = INCUMBENT") == "INCUMBENT"


def test_naming_the_incumbent_without_running_it_is_not_an_incumbent_win():
    """The exact conflation Policy 2 exists to stop.

    Regression guard for a real row: `br-r37-c1-wbwkb` headlined 17.98x, which is our
    own ORIG arm against our own candidate arm, while its prose legitimately discusses
    how networkx installs the same accessors. Against the incumbent that lever moved
    0.035-0.133x to 0.854-0.867x — it shrank a loss. Prose inference would have called
    it a campaign win.
    """
    heading = "2026-07-27 KEEP: accessor lever — 17.98x"
    names_but_does_not_run = (
        "networkx installs these accessors as cached_property. Our ORIG arm was the "
        "old property; the candidate is the cached descriptor. Ratio 17.98x."
    )
    assert ledger_gate.claim_class(heading, names_but_does_not_run) == "UNLABELED"


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

    same_sentence_false_positive = (
        "The candidate sought to remove allocations, but the unchanged source "
        "then ran at 1.001x. No A/A null control was recorded."
    )
    assert ledger_gate.falsifiable(heading, same_sentence_false_positive) == (
        False,
        "VOID-NONULL",
    )

    profile_filename_false_positive = (
        "perf record -e cycles:u wrote perf.flat.txt for the unchanged source. "
        "No A/A null control was recorded."
    )
    assert ledger_gate.falsifiable(heading, profile_filename_false_positive) == (
        False,
        "VOID-NONULL",
    )

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


def _keep_common() -> str:
    digest = "a" * 64
    return (
        f"bench_elf_sha256={digest} (13155240 bytes) /tmp/pkg/_fnx.abi3.so\n"
        "The same-invocation A/A null measured 1.001x with bootstrap "
        "CI [0.995,1.008].\n"
        "decision_gate=median_ci\n"
        "cv_role=report_only\n"
    )


def test_incumbent_keep_requires_actual_same_invocation_win():
    valid = (
        _keep_common()
        + "comparison_class=INCUMBENT\n"
        + "incumbent=networkx\n"
        + "incumbent_same_invocation=true\n"
        + "incumbent_ratio=1.234x\n"
        + "campaign_output=true\n"
    )
    assert ledger_gate.keep_contract("2026-07-27 KEEP candidate", valid) == (
        True,
        "KEEP-INCUMBENT",
        [],
    )

    missing_same_invocation = valid.replace("incumbent_same_invocation=true\n", "")
    assert not ledger_gate.keep_contract(
        "2026-07-27 KEEP candidate", missing_same_invocation
    )[0]

    incumbent_loss = valid.replace("incumbent_ratio=1.234x", "incumbent_ratio=0.912x")
    ok, label, problems = ledger_gate.keep_contract(
        "2026-07-27 KEEP candidate", incumbent_loss
    )
    assert not ok
    assert label == "KEEP-INCUMBENT"
    assert "incumbent_ratio must be greater than 1.0x" in problems


def test_self_speedup_is_maintenance_and_cannot_make_competitive_claims():
    maintenance = (
        _keep_common()
        + "comparison_class=SELF-SPEEDUP\n"
        + "campaign_output=false\n"
    )
    assert ledger_gate.keep_contract("2026-07-27 KEEP maintenance", maintenance) == (
        True,
        "KEEP-SELF-SPEEDUP",
        [],
    )

    assert not ledger_gate.keep_contract(
        "2026-07-27 WIN maintenance", maintenance
    )[0]
    assert not ledger_gate.keep_contract(
        "2026-07-27 KEEP maintenance",
        maintenance + "This beats NetworkX on the fixture.\n",
    )[0]
    assert not ledger_gate.keep_contract(
        "2026-07-27 KEEP maintenance",
        maintenance.replace("campaign_output=false\n", ""),
    )[0]


def test_keep_requires_explicit_comparison_class_and_median_ci_discipline():
    missing_class = _keep_common() + "campaign_output=false\n"
    ok, label, problems = ledger_gate.keep_contract(
        "2026-07-27 KEEP candidate", missing_class
    )
    assert not ok
    assert label == "KEEP-NO-COMPARISON-CLASS"
    assert "missing comparison_class=INCUMBENT|SELF-SPEEDUP" in problems

    missing_decision_gate = (
        _keep_common().replace("decision_gate=median_ci\n", "")
        + "comparison_class=SELF-SPEEDUP\n"
        + "campaign_output=false\n"
    )
    assert not ledger_gate.keep_contract(
        "2026-07-27 KEEP maintenance", missing_decision_gate
    )[0]


def test_every_active_verdict_ledger_has_a_fail_then_pass_keep_boundary():
    expected = {
        "docs/NEGATIVE_EVIDENCE.md",
        "docs/NEGATIVE_EVIDENCE_cc.md",
        "docs/progress/perf-negative-results.md",
    }
    assert {
        path.relative_to(REPO).as_posix() for path in ledger_gate.LEDGERS
    } == expected

    valid = (
        _keep_common()
        + "comparison_class=INCUMBENT\n"
        + "incumbent=networkx\n"
        + "incumbent_same_invocation=true\n"
        + "incumbent_ratio=1.234x\n"
        + "campaign_output=true\n"
    )
    for path in ledger_gate.LEDGERS:
        heading = "2026-07-27 KEEP boundary"
        assert (
            ledger_gate.cmd_check_rows(
                [(path.name, heading, "ratio 2.0x without provenance")],
                f"synthetic {path.name}",
            )
            == 2
        )
        assert (
            ledger_gate.cmd_check_rows(
                [(path.name, heading, valid)],
                f"synthetic {path.name}",
            )
            == 0
        )


def test_claim_modified_verdict_rows_reenter_the_gate():
    """br-r37-c1-qo7uf: a row re-enters the gate when its CLAIM moves.

    It used to re-enter on ANY body difference, which froze every row written
    before the current contract: touching one for markdown made it demand five
    provenance fields for a month-old measurement. What must still re-enter is
    anything a verdict rests on — a number, a contract field, a digest, or a
    classifier's reading of the body.
    """
    path = REPO / "docs" / "NEGATIVE_EVIDENCE.md"
    heading = "2026-07-27 KEEP modified boundary"
    row = f"# Ledger\n\n## {heading}\nmeasured 1.5000x on the grid fixture\n"

    def rows(after):
        return ledger_gate.changed_section_rows(path, row, after)

    assert rows(row) == []
    # A moved number is a claim change, wherever it sits in the body.
    moved = row.replace("1.5000x", "1.6000x")
    assert rows(moved) == [
        (path.name, heading, "measured 1.6000x on the grid fixture")
    ]
    # So is a newly declared contract field, and so is a new row.
    assert len(rows(row + "comparison_class=INCUMBENT\n")) == 1
    assert len(rows(row + f"\n## {heading} two\n\nno evidence\n")) == 1
    # Prose that carries no number, field, or verdict signal is an annotation.
    for annotation in (
        row.replace("measured", "MEASURED, and see the sibling row:"),
        row.replace("grid fixture", "`grid` fixture"),
        row + "See also the endpoint-lookaside row.\n",
    ):
        assert rows(annotation) == [], annotation


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
    """`--prior-art` must surface an existing row so levers are adjudicated.

    The AVX2 dense-linalg row is VOID-NONULL, not permanent evidence. The command
    still blocks blind proposal so the caller reads its retry predicate and says
    explicitly why a VOID row is being reopened.
    """
    result = _run("--prior-art", "avx2", "dense")
    assert result.returncode == 2, (
        "prior-art must BLOCK on a known closed lever:\n" + result.stdout + result.stderr
    )
    assert "REJECT" in result.stdout


def test_prior_art_mode_passes_on_an_unknown_lever():
    result = _run("--prior-art", "zzz_no_such_lever_zzz")
    assert result.returncode == 0, result.stdout + result.stderr
