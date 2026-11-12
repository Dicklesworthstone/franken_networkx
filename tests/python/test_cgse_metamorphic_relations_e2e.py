"""Metamorphic relation and negative-case tests for the 12 CGSE reference algorithms (wvztf.3)."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import networkx as nx
import pytest

import franken_networkx as fnx
from franken_networkx._fnx import cgse

REPO_ROOT = Path(__file__).resolve().parents[2]
JSONL_PATH = REPO_ROOT / "artifacts/conformance/latest/cgse_metamorphic_relations_e2e.jsonl"

EXPECTED_REGISTRY_POLICIES: dict[str, str] = {
    "dijkstra": "weight_then_insertion_order",
    "bellman_ford": "insertion_order",
    "bfs": "insertion_order",
    "dfs": "insertion_order",
    "max_weight_matching": "weight_then_lex",
    "min_weight_matching": "weight_then_lex",
    "connected_components": "lex_min",
    "strongly_connected_components": "insertion_order",
    "kruskal": "weight_then_lex",
    "prim": "weight_then_insertion_order",
    "eulerian_circuit": "insertion_order",
    "topological_sort": "insertion_order",
}


def compute_so_sha256() -> str:
    return hashlib.sha256(Path(fnx._fnx.__file__).read_bytes()).hexdigest()


def run_algorithm_case(lib: Any, algo_id: str, swap_ties: bool = False, offset: int = 0) -> Any:
    def _n(x: int) -> int:
        return x + offset

    if algo_id == "dijkstra":
        G = lib.Graph()
        order = [2, 1] if swap_ties else [1, 2]
        for m in order:
            G.add_edge(_n(0), _n(m), weight=1.0)
            G.add_edge(_n(m), _n(3), weight=1.0)
        return lib.shortest_path(G, _n(0), _n(3), weight="weight")

    if algo_id == "bellman_ford":
        G = lib.Graph()
        order = [2, 1] if swap_ties else [1, 2]
        for m in order:
            G.add_edge(_n(0), _n(m), weight=1.0)
            G.add_edge(_n(m), _n(3), weight=1.0)
        return lib.bellman_ford_path(G, _n(0), _n(3), weight="weight")

    if algo_id == "bfs":
        G = lib.Graph()
        order = [2, 1] if swap_ties else [1, 2]
        for m in order:
            G.add_edge(_n(0), _n(m))
            G.add_edge(_n(m), _n(3))
        return list(lib.bfs_edges(G, _n(0)))

    if algo_id == "dfs":
        G = lib.Graph()
        order = [2, 1] if swap_ties else [1, 2]
        for m in order:
            G.add_edge(_n(0), _n(m))
            G.add_edge(_n(m), _n(3))
        return list(lib.dfs_edges(G, _n(0)))

    if algo_id == "max_weight_matching":
        G = lib.Graph()
        edges = [(_n(0), _n(1), 5.0), (_n(1), _n(2), 5.0), (_n(2), _n(3), 5.0)]
        if swap_ties:
            edges = list(reversed(edges))
        G.add_weighted_edges_from(edges)
        return sorted(tuple(sorted(e)) for e in lib.max_weight_matching(G))

    if algo_id == "min_weight_matching":
        G = lib.Graph()
        edges = [(_n(0), _n(1), 2.0), (_n(2), _n(3), 2.0), (_n(1), _n(2), 9.0)]
        if swap_ties:
            edges = list(reversed(edges))
        G.add_weighted_edges_from(edges)
        return sorted(tuple(sorted(e)) for e in lib.min_weight_matching(G))

    if algo_id == "connected_components":
        G = lib.Graph()
        pairs = [(_n(0), _n(1)), (_n(2), _n(3))]
        if swap_ties:
            pairs = list(reversed(pairs))
        G.add_edges_from(pairs)
        return [sorted(c) for c in lib.connected_components(G)]

    if algo_id == "strongly_connected_components":
        G = lib.DiGraph()
        pairs = [(_n(0), _n(1)), (_n(1), _n(0)), (_n(2), _n(3)), (_n(3), _n(2))]
        if swap_ties:
            pairs = [(_n(2), _n(3)), (_n(3), _n(2)), (_n(0), _n(1)), (_n(1), _n(0))]
        G.add_edges_from(pairs)
        return [sorted(c) for c in lib.strongly_connected_components(G)]

    if algo_id == "kruskal":
        G = lib.Graph()
        order = [2, 1] if swap_ties else [1, 2]
        for m in order:
            G.add_edge(_n(0), _n(m), weight=1.0)
            G.add_edge(_n(m), _n(3), weight=1.0)
        return list(lib.minimum_spanning_tree(G, algorithm="kruskal").edges())

    if algo_id == "prim":
        G = lib.Graph()
        order = [2, 1] if swap_ties else [1, 2]
        for m in order:
            G.add_edge(_n(0), _n(m), weight=1.0)
            G.add_edge(_n(m), _n(3), weight=1.0)
        return list(lib.minimum_spanning_tree(G, algorithm="prim").edges())

    if algo_id == "eulerian_circuit":
        G = lib.Graph()
        edges = (
            [(_n(0), _n(3)), (_n(3), _n(4)), (_n(4), _n(0)), (_n(0), _n(1)), (_n(1), _n(2)), (_n(2), _n(0))]
            if swap_ties
            else [(_n(0), _n(1)), (_n(1), _n(2)), (_n(2), _n(0)), (_n(0), _n(3)), (_n(3), _n(4)), (_n(4), _n(0))]
        )
        G.add_edges_from(edges)
        return list(lib.eulerian_circuit(G, source=_n(0)))

    if algo_id == "topological_sort":
        G = lib.DiGraph()
        order = [2, 1] if swap_ties else [1, 2]
        for m in order:
            G.add_edge(_n(0), _n(m))
            G.add_edge(_n(m), _n(3))
        return list(lib.topological_sort(G))

    raise KeyError(f"Unknown algorithm: {algo_id}")


def remap_output(value: Any, delta: int) -> Any:
    if isinstance(value, int):
        return value + delta
    if isinstance(value, list):
        return [remap_output(v, delta) for v in value]
    if isinstance(value, tuple):
        return tuple(remap_output(v, delta) for v in value)
    return value


def verify_algorithm_metamorphic_relation(
    algo_id: str, expected_policy: str
) -> dict[str, Any]:
    out_fnx_a, w0 = cgse.collect_witnesses(
        lambda: run_algorithm_case(fnx, algo_id, swap_ties=False, offset=0)
    )
    out_nx_a = run_algorithm_case(nx, algo_id, swap_ties=False, offset=0)

    out_fnx_b, w1 = cgse.collect_witnesses(
        lambda: run_algorithm_case(fnx, algo_id, swap_ties=True, offset=0)
    )
    out_nx_b = run_algorithm_case(nx, algo_id, swap_ties=True, offset=0)

    # Order-preserving bijection phi(v) = v + 100
    out_fnx_relab, w_relab = cgse.collect_witnesses(
        lambda: run_algorithm_case(fnx, algo_id, swap_ties=False, offset=100)
    )
    out_nx_relab = run_algorithm_case(nx, algo_id, swap_ties=False, offset=100)

    assert len(w0) >= 1, f"{algo_id} emitted no CGSE witness"
    raw_policy = w0[0].policy
    observed_policy = str(getattr(raw_policy, "value", raw_policy)).split(".")[-1]
    if observed_policy != expected_policy:
        raise ValueError(
            f"Policy mismatch for {algo_id}: expected {expected_policy!r}, observed {observed_policy!r}"
        )

    # Parity with NetworkX on both tie orders and relabeled graph
    assert out_fnx_a == out_nx_a, f"{algo_id} order A diverged from nx"
    assert out_fnx_b == out_nx_b, f"{algo_id} order B diverged from nx"
    assert out_fnx_relab == out_nx_relab, f"{algo_id} relabeled diverged from nx"
    assert out_fnx_relab == remap_output(out_fnx_a, 100), (
        f"{algo_id} violated order-preserving bijection equivariance"
    )

    # Insertion-order tie-break sensitivity check
    if expected_policy in ("insertion_order", "weight_then_insertion_order"):
        assert out_fnx_a != out_fnx_b, (
            f"{algo_id} ({expected_policy}) did not respond to insertion-order swap on tie fixture"
        )

    return {
        "algorithm": algo_id,
        "policy": observed_policy,
        "out_a": out_fnx_a,
        "out_b": out_fnx_b,
        "witness_hash_a": w0[0].decision_path_hash,
        "witness_hash_b": w1[0].decision_path_hash,
        "witness_hash_relab": w_relab[0].decision_path_hash,
    }


def test_all_12_cgse_reference_algorithms_satisfy_metamorphic_relations_and_emit_jsonl():
    so_sha256 = compute_so_sha256()
    records = []
    for algo_id, expected_policy in EXPECTED_REGISTRY_POLICIES.items():
        t0 = time.perf_counter()
        res = verify_algorithm_metamorphic_relation(algo_id, expected_policy)
        duration_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        records.append(
            {
                "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
                "case_id": f"cgse_metamorphic::{algo_id}",
                "input_sha256": hashlib.sha256(algo_id.encode("utf-8")).hexdigest(),
                "fnx_version": getattr(fnx, "__version__", "0.1.0"),
                "nx_version": nx.__version__,
                "so_sha256": so_sha256,
                "graph_class": "Graph/DiGraph",
                "construction_path": "diamond_tie_and_bijection_100",
                "expected": expected_policy,
                "actual": res["policy"],
                "pass": True,
                "duration_ms": duration_ms,
            }
        )

    assert len(records) == 12
    JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSONL_PATH.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in records) + "\n",
        encoding="utf-8",
    )


def test_mislabeled_cgse_policy_fails_metamorphic_verification():
    """wvztf.3 negative test: mislabeling dfs as 'lex_min' in a scratch registry
    must fail metamorphic policy verification."""
    with pytest.raises(ValueError, match="Policy mismatch for dfs"):
        verify_algorithm_metamorphic_relation("dfs", "lex_min")

    jsonl_sha = hashlib.sha256(JSONL_PATH.read_bytes()).hexdigest()
    assert len(jsonl_sha) == 64
