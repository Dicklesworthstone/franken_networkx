"""Public Python API workloads for Criterion-backed gauntlet verification."""

from __future__ import annotations

import gc

import franken_networkx as fnx
import networkx as nx

gc.disable()

def _weighted_flow_edges(node_count: int) -> list[tuple[int, int, float]]:
    edges: list[tuple[int, int, float]] = []
    for i in range(node_count - 1):
        edges.append((i, i + 1, float((i % 11) + 1)))
        if i % 4 != 0:
            edges.append((i + 1, i, float(((i * 3) % 13) + 1)))
        if i + 7 < node_count:
            edges.append((i, i + 7, float(((i * 5) % 17) + 1)))
    return edges


def _build_weighted_digraph(module, node_count: int):
    graph = module.DiGraph()
    graph.add_nodes_from(range(node_count))
    graph.add_weighted_edges_from(_weighted_flow_edges(node_count))
    return graph


_FLOW_NODE_COUNT = 900
_FLOW_REPEAT = 100
_FNX_FLOW_GRAPH = _build_weighted_digraph(fnx, _FLOW_NODE_COUNT)
_NX_FLOW_GRAPH = _build_weighted_digraph(nx, _FLOW_NODE_COUNT)

_EXPECTED_FLOW = nx.flow_hierarchy(_NX_FLOW_GRAPH, weight="weight")
_FNX_FLOW = fnx.flow_hierarchy(_FNX_FLOW_GRAPH, weight="weight")
if abs(_FNX_FLOW - _EXPECTED_FLOW) > 1e-12:
    raise AssertionError(
        f"flow_hierarchy parity drift: fnx={_FNX_FLOW!r}, nx={_EXPECTED_FLOW!r}"
    )


def fnx_flow_hierarchy_weighted_cyclic_dag() -> float:
    total = 0.0
    for _ in range(_FLOW_REPEAT):
        total += fnx.flow_hierarchy(_FNX_FLOW_GRAPH, weight="weight")
    return total


def networkx_flow_hierarchy_weighted_cyclic_dag() -> float:
    total = 0.0
    for _ in range(_FLOW_REPEAT):
        total += nx.flow_hierarchy(_NX_FLOW_GRAPH, weight="weight")
    return total
