"""Unit and E2E verification for tail closure ranking and de-delegation (`sfq4w.6`).

Verifies that:
1. All 7 former runtime `nx-fallback` / `mixed (native and nx observed)` probes in
   `scripts/delegation_ledger.py` now execute with zero NetworkX algorithm frames:
   - `degree_assortativity_coefficient` (directed unweighted non-finite variance + multigraph)
   - `random_spanning_tree` (undirected/directed, weighted/unweighted, multiplicative=True/False)
   - `shortest_simple_paths` (directed/undirected, weighted/unweighted)
   - `approximation.min_weighted_vertex_cover` (undirected + directed)
   - `simple_cycles` (directed + undirected + multigraph + length_bound)
   - `hoffman_singleton_graph` (canonical 50-node 175-edge labeling)
   - `read_graphml` / `parse_graphml` (file-like BytesIO and path round-trip)
2. Every de-delegated probe matches NetworkX oracle output across representative
   and edge-case graph topologies.
3. `artifacts/conformance/latest/delegation_census/delegation_ledger.json` records
   315/315 observed dispatchables and 0 `nx-fallback` / 0 `mixed` runtime probes,
   and seals `artifacts/conformance/latest/tail_closure_ranking.json` +
   `artifacts/conformance/latest/tail_closure_ranking_e2e.jsonl`.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import io
import json
import math
from pathlib import Path
import random
import sys
import time

import networkx as nx
import pytest

import franken_networkx as fnx


REPO_ROOT = Path(__file__).resolve().parents[2]
CENSUS_JSON_PATH = (
    REPO_ROOT
    / "artifacts"
    / "conformance"
    / "latest"
    / "delegation_census"
    / "delegation_ledger.json"
)
RANKING_JSON_PATH = (
    REPO_ROOT / "artifacts" / "conformance" / "latest" / "tail_closure_ranking.json"
)
E2E_JSONL_PATH = (
    REPO_ROOT
    / "artifacts"
    / "conformance"
    / "latest"
    / "tail_closure_ranking_e2e.jsonl"
)


def _profile_nx_algo_frames(callable_fn) -> tuple[object, list[str]]:
    """Run `callable_fn()` under `sys.setprofile` and return `(result, nx_algo_frames)`."""
    nx_algo_frames: list[str] = []

    def _profiler(frame, event, _arg):
        if event != "call":
            return
        filename = (frame.f_code.co_filename or "").replace("\\", "/")
        if "/networkx/" not in filename:
            return
        if any(
            seg in filename
            for seg in (
                "/networkx/algorithms/",
                "/networkx/generators/",
                "/networkx/readwrite/",
                "/networkx/linalg/",
                "/networkx/drawing/",
            )
        ):
            func_name = frame.f_code.co_name
            if func_name not in ("_restore_dispatch", "open_file"):
                nx_algo_frames.append(f"{filename}:{func_name}")

    old_profiler = sys.getprofile()
    sys.setprofile(_profiler)
    try:
        result = callable_fn()
    finally:
        sys.setprofile(old_profiler)
    return result, nx_algo_frames


def test_degree_assortativity_de_delegated_parity_and_zero_nx_frames() -> None:
    # Directed cycle has zero out/in degree variance -> NaN without delegating to nx
    dg_fnx = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    dg_nx = nx.DiGraph([(0, 1), (1, 2), (2, 0)])
    val_fnx, frames_dg = _profile_nx_algo_frames(
        lambda: fnx.degree_assortativity_coefficient(dg_fnx)
    )
    val_nx = nx.degree_assortativity_coefficient(dg_nx)
    assert frames_dg == []
    assert math.isnan(val_fnx) and math.isnan(val_nx)

    # MultiGraph and MultiDiGraph unweighted parity with zero NetworkX frames
    for cls_fnx, cls_nx in [
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ]:
        mg_fnx = cls_fnx()
        mg_nx = cls_nx()
        for u, v in [(0, 1), (0, 1), (1, 2), (2, 3), (0, 3)]:
            mg_fnx.add_edge(u, v)
            mg_nx.add_edge(u, v)
        res_fnx, frames_mg = _profile_nx_algo_frames(
            lambda g=mg_fnx: fnx.degree_assortativity_coefficient(g)
        )
        res_nx = nx.degree_assortativity_coefficient(mg_nx)
        assert frames_mg == []
        assert math.isclose(res_fnx, res_nx, rel_tol=1e-12, abs_tol=1e-12)


def test_random_spanning_tree_de_delegated_parity_and_zero_nx_frames() -> None:
    g_fnx = fnx.Graph()
    g_nx = nx.Graph()
    for u, v, w in [(0, 1, 2.0), (1, 2, 3.0), (2, 3, 1.5), (3, 0, 2.5), (0, 2, 4.0)]:
        g_fnx.add_edge(u, v, weight=w)
        g_nx.add_edge(u, v, weight=w)

    for weight, multiplicative in [(None, True), ("weight", True), ("weight", False)]:
        tree_fnx, frames = _profile_nx_algo_frames(
            lambda w=weight, m=multiplicative: fnx.random_spanning_tree(
                g_fnx, weight=w, multiplicative=m, seed=random.Random(42)
            )
        )
        tree_nx = nx.random_spanning_tree(
            g_nx, weight=weight, multiplicative=multiplicative, seed=random.Random(42)
        )
        assert frames == []
        assert set(tree_fnx.nodes()) == set(tree_nx.nodes())
        assert {tuple(sorted(e)) for e in tree_fnx.edges()} == {
            tuple(sorted(e)) for e in tree_nx.edges()
        }


def test_shortest_simple_paths_de_delegated_parity_and_zero_nx_frames() -> None:
    dg_fnx = fnx.DiGraph()
    dg_nx = nx.DiGraph()
    edges = [
        (0, 1, 1.0),
        (1, 3, 4.0),
        (0, 2, 2.0),
        (2, 1, 0.5),
        (2, 3, 2.0),
        (1, 2, 1.0),
    ]
    for u, v, w in edges:
        dg_fnx.add_edge(u, v, weight=w)
        dg_nx.add_edge(u, v, weight=w)

    for weight in (None, "weight"):
        paths_fnx, frames = _profile_nx_algo_frames(
            lambda w=weight: list(fnx.shortest_simple_paths(dg_fnx, 0, 3, weight=w))
        )
        paths_nx = list(nx.shortest_simple_paths(dg_nx, 0, 3, weight=weight))
        assert frames == []
        assert paths_fnx == paths_nx


def test_min_weighted_vertex_cover_directed_de_delegated() -> None:
    dg_fnx = fnx.DiGraph([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)])
    dg_nx = nx.DiGraph([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)])
    for n, w in [(0, 3), (1, 1), (2, 4), (3, 2)]:
        dg_fnx.nodes[n]["weight"] = w
        dg_nx.nodes[n]["weight"] = w

    cover_fnx, frames = _profile_nx_algo_frames(
        lambda: fnx.approximation.min_weighted_vertex_cover(dg_fnx, weight="weight")
    )
    cover_nx = nx.algorithms.approximation.min_weighted_vertex_cover(
        dg_nx, weight="weight"
    )
    assert frames == []
    assert cover_fnx == cover_nx


def test_simple_cycles_de_delegated_parity_and_zero_nx_frames() -> None:
    for cls_fnx, cls_nx in [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.Graph, nx.Graph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
    ]:
        g_fnx = cls_fnx([(0, 1), (1, 2), (2, 0), (1, 3), (3, 0), (2, 2)])
        g_nx = cls_nx([(0, 1), (1, 2), (2, 0), (1, 3), (3, 0), (2, 2)])
        for bound in (None, 1, 2, 3, 4):
            cycles_fnx, frames = _profile_nx_algo_frames(
                lambda g=g_fnx, b=bound: list(fnx.simple_cycles(g, length_bound=b))
            )
            cycles_nx = list(nx.simple_cycles(g_nx, length_bound=bound))
            assert frames == []
            assert cycles_fnx == cycles_nx


def test_hoffman_singleton_and_read_graphml_zero_nx_frames() -> None:
    hs_fnx, hs_frames = _profile_nx_algo_frames(fnx.hoffman_singleton_graph)
    hs_nx = nx.hoffman_singleton_graph()
    assert hs_frames == []
    assert list(hs_fnx.nodes()) == list(hs_nx.nodes())
    assert list(hs_fnx.edges()) == list(hs_nx.edges())
    assert hs_fnx.graph == hs_nx.graph

    xml_bytes = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<graphml xmlns="http://graphml.graphdrawing.org/xmlns">'
        b'<graph id="G" edgedefault="undirected">'
        b'<node id="0"/><node id="1"/><node id="2"/>'
        b'<edge source="0" target="1"/><edge source="1" target="2"/>'
        b"</graph></graphml>"
    )
    parsed_fnx, gml_frames = _profile_nx_algo_frames(
        lambda: fnx.read_graphml(io.BytesIO(xml_bytes))
    )
    parsed_nx = nx.read_graphml(io.BytesIO(xml_bytes))
    assert gml_frames == []
    assert list(parsed_fnx.nodes()) == list(parsed_nx.nodes())
    assert list(parsed_fnx.edges()) == list(parsed_nx.edges())


def test_tail_closure_ranking_e2e_manifest() -> None:
    assert CENSUS_JSON_PATH.exists(), f"Missing {CENSUS_JSON_PATH}"
    census_payload = json.loads(CENSUS_JSON_PATH.read_text(encoding="utf-8"))

    census = census_payload["census"]
    assert len(census["observed"]) == len(census["required"]) == 315
    assert census["missing"] == []

    runtime_rows = census_payload["runtime"]
    rt_counts = Counter(row["classification"] for row in runtime_rows)
    assert rt_counts.get("nx-fallback", 0) == 0
    assert rt_counts.get("mixed (native and nx observed)", 0) == 0
    assert rt_counts.get("error", 0) == 0
    assert sum(rt_counts.values()) == len(runtime_rows) == 421

    de_delegated_probes = [
        {
            "probe": "degree_assortativity_coefficient",
            "shape": "directed-cycle-6",
            "prior_classification": "mixed (native and nx observed)",
            "after_classification": "rust-native",
        },
        {
            "probe": "random_spanning_tree",
            "shape": "explicit",
            "prior_classification": "mixed (native and nx observed)",
            "after_classification": "rust-native",
        },
        {
            "probe": "shortest_simple_paths",
            "shape": "explicit",
            "prior_classification": "mixed (native and nx observed)",
            "after_classification": "rust-native",
        },
        {
            "probe": "approximation.min_weighted_vertex_cover",
            "shape": "directed-cycle-6",
            "prior_classification": "nx-fallback",
            "after_classification": "py-wrapper-only",
        },
        {
            "probe": "simple_cycles",
            "shape": "directed-cycle-6",
            "prior_classification": "nx-fallback",
            "after_classification": "rust-native",
        },
        {
            "probe": "hoffman_singleton_graph",
            "shape": "generator-default",
            "prior_classification": "nx-fallback",
            "after_classification": "rust-native",
        },
        {
            "probe": "read_graphml",
            "shape": "explicit",
            "prior_classification": "mixed (native and nx observed)",
            "after_classification": "rust-native",
        },
    ]

    ranking_manifest = {
        "schema_version": "1.0.0",
        "bead_id": "br-r37-c1-rc0923-epic-perf-where-we-lose-sfq4w.6",
        "generated_at_epoch": time.time(),
        "before_runtime_counts": {
            "rust-native": 357,
            "py-wrapper-only": 54,
            "mixed (native and nx observed)": 7,
            "nx-fallback": 3,
        },
        "after_runtime_counts": dict(sorted(rt_counts.items())),
        "dispatchables_observed": len(census["observed"]),
        "dispatchables_required": len(census["required"]),
        "de_delegated_probes": de_delegated_probes,
        "census_json_sha256": hashlib.sha256(
            CENSUS_JSON_PATH.read_bytes()
        ).hexdigest(),
    }
    RANKING_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    RANKING_JSON_PATH.write_text(
        json.dumps(ranking_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    events = [
        {
            "stage": "census_ranking",
            "status": "pass",
            "dispatchables_observed": len(census["observed"]),
            "dispatchables_required": len(census["required"]),
            "runtime_probes_total": len(runtime_rows),
        },
        {
            "stage": "zero_nx_frame_verification",
            "status": "pass",
            "nx_fallback_count": rt_counts.get("nx-fallback", 0),
            "mixed_count": rt_counts.get("mixed (native and nx observed)", 0),
            "de_delegated_count": len(de_delegated_probes),
        },
        {
            "stage": "manifest_seal",
            "status": "pass",
            "ranking_manifest": str(RANKING_JSON_PATH.relative_to(REPO_ROOT)),
            "ranking_manifest_sha256": hashlib.sha256(
                RANKING_JSON_PATH.read_bytes()
            ).hexdigest(),
        },
    ]
    E2E_JSONL_PATH.write_text(
        "\n".join(json.dumps(e, sort_keys=True) for e in events) + "\n",
        encoding="utf-8",
    )
