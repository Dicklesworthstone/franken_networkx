"""A newly added, certified proof dir must name a bead the ledger records.

br-r37-c1-ml7s5. Measured on this repository: of 1065 proof directories under
``tests/artifacts/perf``, 21 carry BOTH a gate marker and a ship/keep verdict,
and 16 of those cite a bead that appears in no ledger. Certified work living only
in an artifact directory is work the next pane pays to measure again — four of
the sixteen are levers this pane later re-derived from its own memory rather than
from the ledger.

Filing that inventory does not stop it growing; the gate does. These tests pin
the gate's three judgement calls, because each of them can fail in a way that is
worse than not having the gate at all:

1. IT MUST NOT FIRE ON EXPLORATORY DIRS. An artifact directory exists precisely
   to hold sweeps and measured rejections. A gate that demanded a ledger row for
   every directory containing a number would push people to stop writing proof
   dirs, which is the opposite of the goal. Only a gate marker AND a verdict
   together constitute a claim.

2. IT MUST ONLY LOOK AT NEWLY ADDED FILES. The 16 pre-existing orphans must not
   block an unrelated commit. The point is to stop the inventory growing, not to
   hold the fleet hostage to its history — a gate that blocks everyone
   immediately gets disabled, and then it protects nothing.

3. A DIR WITH NO BEAD AT ALL MUST STILL BE CAUGHT. One of the sixteen
   (``ego-graph-return-direct``) cites no bead anywhere in its docs, so a check
   that only compared bead ids would have let exactly that case through.

The gate is exercised through its real entry point with only the staged-file
source substituted, so what is under test is the shipped decision logic rather
than a re-implementation of it in the test.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "perf_ledger_preflight.py"


@pytest.fixture()
def preflight():
    spec = importlib.util.spec_from_file_location("preflight_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CERTIFIED = "Result: 2.5x, all nulls clean, ADMISSIBLE. SHIPPED as abc123."
EXPLORATORY = "Swept six shapes, best was 1.02x. Not pursued."


def _run(preflight, monkeypatch, staged):
    monkeypatch.setattr(preflight, "staged_proof_dirs", lambda: staged)
    return preflight.cmd_check_proof_dirs()


def test_certified_dir_with_a_banked_bead_passes(preflight, monkeypatch):
    """The bead is in the ledger, so the work is discoverable. Allowed."""
    # br-r37-c1-ml7s5 is this bead: it is in the ledger by construction.
    staged = [("tests/artifacts/perf/20260816T-example", {"br-r37-c1-ml7s5"})]
    assert _run(preflight, monkeypatch, staged) == 0


def test_certified_dir_with_an_unbanked_bead_is_blocked(preflight, monkeypatch):
    """THE case the gate exists for — a certified result that would evaporate."""
    staged = [("tests/artifacts/perf/20260816T-orphan", {"br-r37-c1-zzzznotreal"})]
    assert _run(preflight, monkeypatch, staged) == 1


def test_certified_dir_with_no_bead_at_all_is_blocked(preflight, monkeypatch):
    """One of the real sixteen cites no bead anywhere; it must not slip through."""
    staged = [("tests/artifacts/perf/20260816T-nobead", set())]
    assert _run(preflight, monkeypatch, staged) == 1


def test_nothing_staged_passes(preflight, monkeypatch):
    assert _run(preflight, monkeypatch, []) == 0


def test_exploratory_docs_are_not_treated_as_a_claim(preflight):
    """Requirement 1: a sweep with a ratio but no verdict is not a claim.

    Asserted against the module's own classifiers rather than a copy of them, so
    a change to the wording it recognises is caught here.
    """
    assert not (
        preflight._PROOF_GATE.search(EXPLORATORY)
        and preflight._PROOF_VERDICT.search(EXPLORATORY)
    )
    assert preflight._PROOF_GATE.search(CERTIFIED)
    assert preflight._PROOF_VERDICT.search(CERTIFIED)


def test_a_verdict_without_a_gate_marker_is_not_a_claim(preflight):
    """Both halves are required: 'SHIPPED' alone is not a certified result."""
    verdict_only = "SHIPPED the rename; no measurement was taken."
    assert preflight._PROOF_VERDICT.search(verdict_only)
    assert not preflight._PROOF_GATE.search(verdict_only)


def test_bead_pattern_matches_this_repo_s_ids(preflight):
    found = preflight._PROOF_BEAD.findall(
        "see br-r37-c1-ml7s5 and br-r37-c1-04z53.44 for context"
    )
    assert {f.lower() for f in found} == {"br-r37-c1-ml7s5", "br-r37-c1-04z53.44"}


def test_gate_only_considers_added_files(preflight):
    """Requirement 2, asserted on the shipped implementation's own filter.

    ``staged_proof_dirs`` must ask git for ADDED paths only. If this ever widens
    to modified files, every touch of an existing orphan starts blocking.
    """
    source = SCRIPT.read_text()
    body = source.split("def staged_proof_dirs", 1)[1].split("\ndef ", 1)[0]
    assert "--diff-filter=A" in body, (
        "staged_proof_dirs must restrict itself to ADDED paths, or the 16 "
        "pre-existing orphans will block unrelated commits"
    )
