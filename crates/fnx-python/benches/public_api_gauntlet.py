"""Public Python API workloads for Criterion-backed gauntlet verification."""

from __future__ import annotations

import gc
import random

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


def _build_wic_graph(module, node_count: int, communities: int, seed: int):
    rng = random.Random(seed)
    graph = module.Graph()
    graph.add_nodes_from(range(node_count))
    for node in range(node_count):
        graph.nodes[node]["community"] = node % communities
    for u in range(node_count):
        u_community = u % communities
        for v in range(u + 1, node_count):
            edge_probability = 0.075 if u_community == (v % communities) else 0.006
            if rng.random() < edge_probability:
                graph.add_edge(u, v)
    return graph


def _wic_ebunch(graph, node_count: int, target_count: int, seed: int):
    rng = random.Random(seed)
    pairs = [
        (u, v)
        for u in range(node_count)
        for v in range(u + 1, node_count)
        if not graph.has_edge(u, v)
    ]
    rng.shuffle(pairs)
    return pairs[:target_count]


def _consume_link_scores(scores) -> float:
    total = 0.0
    count = 0
    for _, _, score in scores:
        total += float(score)
        count += 1
    return total + count


_WIC_NODE_COUNT = 480
_WIC_COMMUNITIES = 8
_WIC_EBUNCH_COUNT = 6000
_WIC_REPEAT = 100
_WIC_GRAPH_SEED = 9141
_WIC_EBUNCH_SEED = 9142
_FNX_WIC_GRAPH = _build_wic_graph(fnx, _WIC_NODE_COUNT, _WIC_COMMUNITIES, _WIC_GRAPH_SEED)
_NX_WIC_GRAPH = _build_wic_graph(nx, _WIC_NODE_COUNT, _WIC_COMMUNITIES, _WIC_GRAPH_SEED)
_WIC_EBUNCH = _wic_ebunch(_NX_WIC_GRAPH, _WIC_NODE_COUNT, _WIC_EBUNCH_COUNT, _WIC_EBUNCH_SEED)

_EXPECTED_WIC = _consume_link_scores(
    nx.within_inter_cluster(_NX_WIC_GRAPH, _WIC_EBUNCH)
)
_FNX_WIC = _consume_link_scores(fnx.within_inter_cluster(_FNX_WIC_GRAPH, _WIC_EBUNCH))
if abs(_FNX_WIC - _EXPECTED_WIC) > 1e-9:
    raise AssertionError(
        f"within_inter_cluster parity drift: fnx={_FNX_WIC!r}, nx={_EXPECTED_WIC!r}"
    )


def fnx_within_inter_cluster_explicit_community() -> float:
    total = 0.0
    for _ in range(_WIC_REPEAT):
        total += _consume_link_scores(fnx.within_inter_cluster(_FNX_WIC_GRAPH, _WIC_EBUNCH))
    return total


def networkx_within_inter_cluster_explicit_community() -> float:
    total = 0.0
    for _ in range(_WIC_REPEAT):
        total += _consume_link_scores(nx.within_inter_cluster(_NX_WIC_GRAPH, _WIC_EBUNCH))
    return total


def _sparse_undirected_edges(node_count: int, probability: float, seed: int):
    rng = random.Random(seed)
    for u in range(node_count):
        for v in range(u + 1, node_count):
            if rng.random() < probability:
                yield (u, v)


def _build_sparse_undirected_graph(module, node_count: int, probability: float, seed: int):
    graph = module.Graph()
    graph.add_nodes_from(range(node_count))
    graph.add_edges_from(_sparse_undirected_edges(node_count, probability, seed))
    return graph


def _consume_non_edges(pairs) -> float:
    total = 0
    count = 0
    for u, v in pairs:
        count += 1
        total = (
            total
            + count * 1_315_423_911
            + int(u) * 2_654_435_761
            + int(v) * 97_531
        ) & ((1 << 63) - 1)
    return float(total + count)


_NON_EDGES_NODE_COUNT = 900
_NON_EDGES_PROBABILITY = 0.008
_NON_EDGES_SEED = 9143
_NON_EDGES_REPEAT = 4
_FNX_NON_EDGES_GRAPH = _build_sparse_undirected_graph(
    fnx, _NON_EDGES_NODE_COUNT, _NON_EDGES_PROBABILITY, _NON_EDGES_SEED
)
_NX_NON_EDGES_GRAPH = _build_sparse_undirected_graph(
    nx, _NON_EDGES_NODE_COUNT, _NON_EDGES_PROBABILITY, _NON_EDGES_SEED
)

_EXPECTED_NON_EDGES = _consume_non_edges(nx.non_edges(_NX_NON_EDGES_GRAPH))
_FNX_NON_EDGES = _consume_non_edges(fnx.non_edges(_FNX_NON_EDGES_GRAPH))
if _FNX_NON_EDGES != _EXPECTED_NON_EDGES:
    raise AssertionError(
        f"non_edges parity drift: fnx={_FNX_NON_EDGES!r}, nx={_EXPECTED_NON_EDGES!r}"
    )


def fnx_non_edges_sparse_undirected() -> float:
    total = 0.0
    for _ in range(_NON_EDGES_REPEAT):
        total += _consume_non_edges(fnx.non_edges(_FNX_NON_EDGES_GRAPH))
    return total


def networkx_non_edges_sparse_undirected() -> float:
    total = 0.0
    for _ in range(_NON_EDGES_REPEAT):
        total += _consume_non_edges(nx.non_edges(_NX_NON_EDGES_GRAPH))
    return total
