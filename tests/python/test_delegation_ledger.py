"""br-r37-c1-256q5: regression tests for delegation ledger.

Companion to ``scripts/delegation_ledger.py``. Locks in the runtime
probe outcomes for the families fixed by sjf4t (br-r37-c1-sjf4t) and
0x9pd (br-r37-c1-0x9pd) — if any of those wrappers regresses to nx
fallback on a previously-native shape, this test fails.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "delegation_ledger.py"


@pytest.fixture(scope="module")
def ledger_output(tmp_path_factory):
    out_dir = tmp_path_factory.mktemp("delegation_ledger")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--quiet", "--output-dir", str(out_dir)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    js = out_dir / "delegation_ledger.json"
    md = out_dir / "delegation_ledger.md"
    assert js.exists()
    assert md.exists()
    return json.loads(js.read_text(encoding="utf-8"))


def _runtime_by_key(ledger):
    return {
        (probe["name"], probe["shape"]): probe
        for probe in ledger["runtime"]
    }


@pytest.mark.parametrize(
    "name,shape",
    [
        ("single_source_dijkstra_path_length", "path-5-unweighted"),
        ("single_source_dijkstra_path_length", "path-5-weighted-kwargs"),
        ("single_source_dijkstra_path_length", "path-5-weighted-postmut"),
        ("single_source_bellman_ford_path_length", "path-5-unweighted"),
        ("single_source_bellman_ford_path_length", "path-5-weighted-kwargs"),
        ("single_source_bellman_ford_path_length", "path-5-weighted-postmut"),
        ("astar_path_length", "path-5-unweighted"),
        ("astar_path_length", "path-5-weighted-kwargs"),
        ("astar_path_length", "path-5-weighted-postmut"),
        ("shortest_path_length", "path-5-weighted-kwargs"),
        ("shortest_path_length", "path-5-weighted-postmut"),
    ],
)
def test_no_nx_fallback_on_sjf4t_protected_shapes(ledger_output, name, shape):
    """The sjf4t (br-r37-c1-sjf4t) and 0x9pd (br-r37-c1-0x9pd) fixes
    sync edge attrs to Rust before native algorithm calls. Verify
    that the Rust path is taken for all shapes the fixes cover —
    if any of these regresses to nx fallback, the perf gain is gone.
    """
    runtime = _runtime_by_key(ledger_output)
    probe = runtime.get((name, shape))
    assert probe is not None, f"no probe for {(name, shape)}"
    assert probe["error"] is None, f"probe error: {probe['error']}"
    assert probe["classification"] == "rust-native", (
        f"{name}/{shape} regressed to {probe['classification']}: "
        f"raw={probe['raw_called']}, parity={probe['parity_called_with_target']}"
    )


def test_static_classification_summary_shape(ledger_output):
    """Smoke: static section is well-formed and returns sensible counts."""
    static = ledger_output["static"]
    assert isinstance(static, list)
    assert len(static) >= 1000, f"only {len(static)} static entries"
    classifications = {entry["classification"] for entry in static}
    expected = {"rust-reexport", "rust-native", "mixed-route", "nx-fallback", "py-wrapper"}
    assert classifications & expected == expected, (
        f"missing classifications: {expected - classifications}"
    )
