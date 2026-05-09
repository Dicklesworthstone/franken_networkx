"""br-r37-c1-hchj7: regression tests for upstream-divergence ledger.

Companion to ``scripts/upstream_divergence_ledger.py``. The ledger
combines AST classification, runtime probes, raw-vs-public audit
output, Rust ``KNOWN GAP`` markers, and closed bead history into a
unified per-function divergence record. This test verifies:

1. The script runs and produces both .md / .json artifacts.
2. The known divergence cases (e.g., ``is_planar`` raw kernel known
   gap) are surfaced in the right category.
3. The post-sjf4t native-parity claims hold for shortest-path family.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "upstream_divergence_ledger.py"


@pytest.fixture(scope="module")
def ledger(tmp_path_factory):
    """Run the ledger; require companion audits to exist."""
    out_dir = tmp_path_factory.mktemp("upstream_divergence_ledger")
    # Companion artifacts live in the real docs/ — pass docs root as
    # the input dir for now by writing into out_dir but referencing
    # repo-root data paths (the script reads `docs/delegation_ledger.json`
    # etc. from REPO_ROOT). We just verify the run succeeds and
    # contents are sensible.
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--quiet", "--output-dir", str(out_dir)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    js = out_dir / "upstream_divergence_ledger.json"
    md = out_dir / "upstream_divergence_ledger.md"
    assert js.exists()
    assert md.exists()
    return json.loads(js.read_text(encoding="utf-8"))


def _entries_for(ledger, name):
    return [e for e in ledger["entries"] if e["name"] == name]


def test_ledger_runs_to_completion(ledger):
    assert isinstance(ledger.get("entries"), list)
    assert len(ledger["entries"]) > 100, (
        f"only {len(ledger['entries'])} entries — sources likely missing"
    )


def test_is_planar_surfaces_as_raw_known_gap(ledger):
    """The raw _raw_is_planar kernel is documented as a KNOWN GAP in
    crates/fnx-algorithms/src/lib.rs. The ledger must surface this
    so it's not lost across review rounds."""
    entries = _entries_for(ledger, "is_planar")
    assert entries, "is_planar should be in the divergence ledger"
    cats = {e["category"] for e in entries}
    assert "raw-known-gap" in cats, (
        f"is_planar lost raw-known-gap categorization: {cats}"
    )


def test_dijkstra_family_classified_as_native_parity(ledger):
    """After br-r37-c1-sjf4t the dijkstra family runs natively. The
    ledger should classify the raw bindings as native-parity (the
    Rust kernel itself); the wrappers themselves are wrapper-patched
    via raw-vs-public-audit (post-process for nx ordering/typing)."""
    raw_dijk = _entries_for(ledger, "_raw_single_source_dijkstra_path_length")
    assert raw_dijk, "_raw_single_source_dijkstra_path_length missing from ledger"
    cats = {e["category"] for e in raw_dijk}
    assert "native-parity" in cats, (
        f"raw dijkstra binding lost native-parity: {cats}"
    )


def test_intentionally_delegated_bucket_is_populated(ledger):
    """At least some non-trivial number of wrappers route to nx — if
    this bucket is empty something has broken in the AST scan."""
    delegated = [
        e for e in ledger["entries"] if e["category"] == "intentionally-delegated"
    ]
    assert len(delegated) >= 50, (
        f"only {len(delegated)} intentionally-delegated wrappers — AST scan may have regressed"
    )


def test_categories_are_well_formed(ledger):
    """Every entry has the five canonical category values; nothing else."""
    expected = {
        "native-parity",
        "wrapper-patched",
        "intentionally-delegated",
        "raw-known-gap",
        "owner-acknowledged-limitation",
    }
    seen = {e["category"] for e in ledger["entries"]}
    assert seen <= expected, f"unexpected categories: {seen - expected}"
