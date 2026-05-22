"""br-r37-c1-zcbtx: regression tests for API-ergonomics signature audit.

Companion to ``scripts/api_ergonomics_audit.py``. Locks in:

1. The audit script runs to completion and produces both .md and .json.
2. Critical drop-in surfaces (``read_edgelist``, ``from_pandas_edgelist``,
   ``write_edgelist``, ``parse_edgelist``) have signatures matching
   ``networkx`` exactly. These are the highest-traffic IO/conversion
   points; signature drift here breaks adoption.
3. The remaining intentional ergonomic extension
   (``draw_bipartite`` adds ``top_nodes``) is stable; if it changes
   shape we want a re-classification, not silent drift.
"""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

import franken_networkx as fnx
import networkx as nx


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "api_ergonomics_audit.py"


# ---------------------------------------------------------------------------
# IO / conversion family parity (high-traffic drop-in surface)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "read_edgelist",
        "read_weighted_edgelist",
        "read_adjlist",
        "write_edgelist",
        "write_weighted_edgelist",
        "write_adjlist",
        "parse_edgelist",
        "parse_adjlist",
        "from_pandas_edgelist",
        "to_pandas_edgelist",
        "from_dict_of_dicts",
        "from_dict_of_lists",
        "from_edgelist",
        "to_dict_of_dicts",
        "to_dict_of_lists",
    ],
)
def test_io_family_signature_matches_networkx(name):
    fnx_obj = getattr(fnx, name, None)
    nx_obj = getattr(nx, name, None)
    assert fnx_obj is not None, f"{name} not exposed in fnx"
    assert nx_obj is not None, f"{name} not exposed in nx"

    fnx_sig = inspect.signature(fnx_obj)
    nx_sig = inspect.signature(nx_obj)

    # Compare parameter names + kinds (defaults can drift e.g. type-objects
    # but parameter shape must match for drop-in compatibility).
    fnx_params = [(p.name, p.kind.name) for p in fnx_sig.parameters.values()]
    nx_params = [(p.name, p.kind.name) for p in nx_sig.parameters.values()]
    assert fnx_params == nx_params, (
        f"{name} signature drift: fnx={fnx_params} nx={nx_params}"
    )


# ---------------------------------------------------------------------------
# Intentional extensions (must not regress)
# ---------------------------------------------------------------------------


def test_draw_bipartite_keeps_top_nodes_extension():
    sig = inspect.signature(fnx.draw_bipartite)
    params = list(sig.parameters.values())
    assert [p.name for p in params] == ["G", "top_nodes", "kwargs"], (
        f"br-r37-c1-bvf5w extension changed shape: {[p.name for p in params]}"
    )


def test_tutte_polynomial_signature_matches_networkx():
    sig = inspect.signature(fnx.tutte_polynomial)
    nx_sig = inspect.signature(nx.tutte_polynomial)

    assert str(sig) == str(nx_sig)


# ---------------------------------------------------------------------------
# Audit script smoke test
# ---------------------------------------------------------------------------


def test_audit_script_runs_to_completion(tmp_path):
    out_dir = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--quiet", "--output-dir", str(out_dir)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"

    md = out_dir / "api_ergonomics_audit.md"
    js = out_dir / "api_ergonomics_audit.json"
    assert md.exists()
    assert js.exists()

    payload = json.loads(js.read_text(encoding="utf-8"))
    # Sanity: at least 500 functions audited (most of nx's top-level surface
    # is mirrored on fnx).
    assert len(payload) >= 500, f"only {len(payload)} functions audited"

    # Spot check: shortest_path_length classified as identical (catches
    # any future drift).
    by_name = {p["name"]: p for p in payload}
    sp = by_name.get("shortest_path_length")
    assert sp is not None, "shortest_path_length not in audit"
    assert sp["classification"] == "identical", (
        f"shortest_path_length drifted: {sp['deltas']}"
    )
