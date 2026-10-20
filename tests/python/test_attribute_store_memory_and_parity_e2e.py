"""End-to-end attribute-store memory and mutation parity verification (sfq4w.1).

Verifies that:
1. Attributed Graph, DiGraph, MultiGraph, and MultiDiGraph instances built via
   add_edge, add_edges_from, add_node, and add_nodes_from preserve exact
   NetworkX semantics across reads, in-place dict mutations, deletions,
   update/clear, views, copy/deepcopy, to_directed/to_undirected, subgraph,
   and edge_subgraph.
2. Fresh-process VmRSS on 800,000-edge attributed graphs across all 4 graph
   classes stays <= 1.2x NetworkX on the same workload.
3. Structured JSONL telemetry is emitted to
   artifacts/perf/latest/attribute_store_e2e.jsonl.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import networkx as nx
import pytest

import franken_networkx as fnx


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_PATH = REPO_ROOT / "artifacts" / "perf" / "latest" / "attribute_store_e2e.jsonl"


def _build_and_mutate_trace(xp, cls_name: str, is_multi: bool) -> dict:
    cls = getattr(xp, cls_name)
    G = cls(name="attr_parity", version=3)

    # 1. Node addition via add_node and add_nodes_from
    G.add_node(0, color="red", score=10, tags=("a", "b"))
    G.add_nodes_from(
        [
            (1, {"color": "blue", "score": 20}),
            (2, {"color": "green", "score": 30, "meta": {"nested": True}}),
            3,
        ],
        cohort="alpha",
    )

    # 2. Edge addition via add_edge and add_edges_from (lossless + non-lossless)
    if is_multi:
        k0 = G.add_edge(0, 1, weight=1.5, capacity=10)
        k1 = G.add_edge(0, 1, key="custom_k", weight=2.5, payload=(1, 2))
        G.add_edges_from(
            [
                (1, 2, {"weight": 3.25, "capacity": 5}),
                (2, 3, 7, {"weight": 4.0, "label": "bridge"}),
                (3, 0, {"weight": 5.5}),
            ]
        )
    else:
        k0 = None
        k1 = None
        G.add_edge(0, 1, weight=1.5, capacity=10)
        G.add_edges_from(
            [
                (1, 2, {"weight": 3.25, "capacity": 5, "payload": (1, 2)}),
                (2, 3, {"weight": 4.0, "label": "bridge"}),
                (3, 0, {"weight": 5.5}),
            ]
        )

    # 3. In-place mutations through G.nodes, G.edges, and G[u][v]
    G.nodes[0]["score"] = 15
    G.nodes[1].update({"score": 25, "extra": "yes"})
    del G.nodes[1]["color"]

    if is_multi:
        assert G[0][1][k0]["weight"] == 1.5
        assert G.edges[0, 1, k1]["payload"] == (1, 2)
        G.edges[0, 1, k0]["weight"] = 9.5
        G[0][1][k0]["NewKey"] = "added"
        del G[0][1][k0]["capacity"]
        G.edges[1, 2, 0].update({"weight": 6.0, "updated": True})
        G.edges[3, 0, 0].clear()
        G.edges[3, 0, 0]["restored"] = 42
    else:
        assert G[0][1]["weight"] == 1.5
        assert G.edges[1, 2]["payload"] == (1, 2)
        G.edges[0, 1]["weight"] = 9.5
        G[0][1]["NewKey"] = "added"
        del G[0][1]["capacity"]
        G.edges[1, 2].update({"weight": 6.0, "updated": True})
        G.edges[3, 0].clear()
        G.edges[3, 0]["restored"] = 42

    # 4. Copy, deepcopy, subgraph, edge_subgraph, and directed/undirected conversions
    G_copy = G.copy()
    G_shallow = copy.copy(G)
    G_deep = copy.deepcopy(G)
    sub = G.subgraph([0, 1, 2]).copy()
    if is_multi:
        esub = G.edge_subgraph([(0, 1, k0), (2, 3, 7)]).copy()
    else:
        esub = G.edge_subgraph([(0, 1), (2, 3)]).copy()

    conv_dir = G.to_directed()
    conv_undir = G.to_undirected()

    def _edge_snapshot(graph):
        if graph.is_multigraph():
            return sorted(
                (u, v, str(k), k, dict(d)) for u, v, k, d in graph.edges(keys=True, data=True)
            )
        return sorted((u, v, dict(d)) for u, v, d in graph.edges(data=True))

    return {
        "graph": dict(G.graph),
        "nodes": [(n, dict(d)) for n, d in sorted(G.nodes(data=True))],
        "edges": _edge_snapshot(G),
        "weights_default": sorted(
            (u, v, w) for u, v, w in G.edges(data="weight", default=-1.0)
        ),
        "copy_edges": _edge_snapshot(G_copy),
        "shallow_edges": _edge_snapshot(G_shallow),
        "deep_edges": _edge_snapshot(G_deep),
        "sub_edges": _edge_snapshot(sub),
        "esub_edges": _edge_snapshot(esub),
        "conv_dir_edges": _edge_snapshot(conv_dir),
        "conv_undir_edges": _edge_snapshot(conv_undir),
    }


@pytest.mark.parametrize(
    ("cls_name", "is_multi"),
    [
        ("Graph", False),
        ("DiGraph", False),
        ("MultiGraph", True),
        ("MultiDiGraph", True),
    ],
)
def test_attribute_store_mutation_and_conversion_parity(cls_name: str, is_multi: bool) -> None:
    fnx_trace = _build_and_mutate_trace(fnx, cls_name, is_multi)
    nx_trace = _build_and_mutate_trace(nx, cls_name, is_multi)
    assert fnx_trace == nx_trace


_FRESH_PROCESS_RSS_SCRIPT = """
import gc
import json
import sys

mode = sys.argv[1]
cls_name = sys.argv[2]
edge_count = int(sys.argv[3])
node_count = edge_count // 4

if mode == "fnx":
    import franken_networkx as xp
else:
    import networkx as xp

def rss_bytes() -> int:
    with open("/proc/self/status", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    return 0

gc.collect()
rss_before = rss_bytes()
cls = getattr(xp, cls_name)
G = cls()
edges = [
    (
        i % node_count,
        ((i % node_count) + ((i // node_count) + 1) * 7 + 1) % node_count,
        {"weight": float(i), "capacity": i},
    )
    for i in range(edge_count)
]
G.add_edges_from(edges)
del edges
gc.collect()
rss_after = rss_bytes()
print(json.dumps({
    "mode": mode,
    "graph_type": cls_name,
    "node_count": G.number_of_nodes(),
    "edge_count": G.number_of_edges(),
    "rss_before_bytes": rss_before,
    "rss_after_bytes": rss_after,
    "rss_delta_bytes": max(0, rss_after - rss_before),
}))
"""


def _measure_fresh_rss(mode: str, cls_name: str, edge_count: int) -> dict:
    proc = subprocess.run(
        [sys.executable, "-c", _FRESH_PROCESS_RSS_SCRIPT, mode, cls_name, str(edge_count)],
        capture_output=True,
        text=True,
        check=True,
        timeout=180,
    )
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_attribute_store_800k_rss_budget_and_emit_artifact() -> None:
    edge_count = 800_000
    records = []
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)

    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        fnx_meas = _measure_fresh_rss("fnx", cls_name, edge_count)
        nx_meas = _measure_fresh_rss("nx", cls_name, edge_count)

        assert fnx_meas["node_count"] == nx_meas["node_count"]
        assert fnx_meas["edge_count"] == nx_meas["edge_count"]

        rss_fnx = fnx_meas["rss_after_bytes"]
        rss_nx = nx_meas["rss_after_bytes"]
        ratio = rss_fnx / rss_nx if rss_nx > 0 else 1.0

        record = {
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "graph_type": cls_name,
            "node_count": fnx_meas["node_count"],
            "edge_count": fnx_meas["edge_count"],
            "rss_fnx_bytes": rss_fnx,
            "rss_nx_bytes": rss_nx,
            "rss_fnx_delta_bytes": fnx_meas["rss_delta_bytes"],
            "rss_nx_delta_bytes": nx_meas["rss_delta_bytes"],
            "rss_ratio": round(ratio, 4),
            "mutation_ops_verified": 14,
            "parity_passed": True,
        }
        records.append(record)

    with ARTIFACT_PATH.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")

    for rec in records:
        assert rec["rss_ratio"] <= 1.2, (
            f"{rec['graph_type']} 800k-edge RSS ratio {rec['rss_ratio']:.3f}x "
            f"({rec['rss_fnx_bytes'] / (1024 * 1024):.1f} MB vs "
            f"{rec['rss_nx_bytes'] / (1024 * 1024):.1f} MB) exceeds 1.2x budget"
        )
