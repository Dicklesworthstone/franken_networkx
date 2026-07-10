"""Public Python API workloads for Criterion-backed gauntlet verification."""

from __future__ import annotations

import gc
import io
import random

import franken_networkx as fnx
from franken_networkx import summarization as fnx_summarization
import franken_networkx.tournament as fnx_tournament
import networkx as nx
from networkx.algorithms import summarization as nx_summarization
from networkx.algorithms import tournament as nx_tournament

gc.disable()

try:
    import scipy  # noqa: F401

    _SCIPY_AVAILABLE = True
    _NETWORKX_PAGERANK = nx.pagerank
    _NETWORKX_PAGERANK_KIND = "scipy"
except ImportError:
    from networkx.algorithms.link_analysis.pagerank_alg import _pagerank_python

    _SCIPY_AVAILABLE = False
    _NETWORKX_PAGERANK = _pagerank_python
    _NETWORKX_PAGERANK_KIND = "python-fallback"


def _build_graph6_source(module, node_count: int, edge_count: int):
    graph = module.Graph()
    graph.add_nodes_from(range(node_count))
    edges = []
    seen = set()
    step = 1
    u = 0
    while len(edges) < edge_count and step < node_count:
        v = (u * 29 + step * 11 + 5) % node_count
        left, right = (u, v) if u < v else (v, u)
        if left != right and (left, right) not in seen:
            seen.add((left, right))
            edges.append((left, right))
        u += 1
        if u == node_count:
            u = 0
            step += 1
    if len(edges) != edge_count:
        raise AssertionError("unable to build requested graph6 source graph")
    graph.add_edges_from(edges)
    return graph


def _consume_graph6_parse(graph) -> float:
    return float(
        graph.number_of_nodes()
        + graph.number_of_edges()
        + sum((u * 131 + v * 17) % 1_000_003 for u, v in graph.edges())
    )


_GRAPH6_NODE_COUNT = 700
_GRAPH6_EDGE_COUNT = 2862
_GRAPH6_REPEAT = 5
_NX_GRAPH6_SOURCE = _build_graph6_source(nx, _GRAPH6_NODE_COUNT, _GRAPH6_EDGE_COUNT)
_GRAPH6_PAYLOAD = nx.to_graph6_bytes(_NX_GRAPH6_SOURCE, header=False).strip()
_FNX_GRAPH6_PARSED = fnx.from_graph6_bytes(_GRAPH6_PAYLOAD)
_NX_GRAPH6_PARSED = nx.from_graph6_bytes(_GRAPH6_PAYLOAD)
if (
    _FNX_GRAPH6_PARSED.number_of_nodes() != _NX_GRAPH6_PARSED.number_of_nodes()
    or set(_FNX_GRAPH6_PARSED.edges()) != set(_NX_GRAPH6_PARSED.edges())
):
    raise AssertionError("from_graph6_bytes parity drift")


def fnx_from_graph6_bytes_sparse_700() -> float:
    total = 0.0
    for _ in range(_GRAPH6_REPEAT):
        total += _consume_graph6_parse(fnx.from_graph6_bytes(_GRAPH6_PAYLOAD))
    return total


def networkx_from_graph6_bytes_sparse_700() -> float:
    total = 0.0
    for _ in range(_GRAPH6_REPEAT):
        total += _consume_graph6_parse(nx.from_graph6_bytes(_GRAPH6_PAYLOAD))
    return total


def _build_gml_edge_attr_graph(module, node_count: int, edge_count: int):
    graph = module.Graph()
    graph.add_nodes_from(range(node_count))
    edges = []
    seen = set()
    step = 1
    u = 0
    while len(edges) < edge_count and step < node_count:
        v = (u * 37 + step * 17 + 3) % node_count
        left, right = (u, v) if u < v else (v, u)
        if left != right and (left, right) not in seen:
            seen.add((left, right))
            edges.append((left, right, {"weight": (left * 13 + right * 7) % 997}))
        u += 1
        if u == node_count:
            u = 0
            step += 1
    if len(edges) != edge_count:
        raise AssertionError("unable to build requested GML writer graph")
    graph.add_edges_from(edges)
    return graph


def _write_gml_signature(module, graph) -> float:
    buf = io.BytesIO()
    module.write_gml(graph, buf)
    payload = buf.getvalue()
    return float(len(payload) + sum(payload) % 1_000_003)


_GML_EDGE_ATTR_NODE_COUNT = 900
_GML_EDGE_ATTR_EDGE_COUNT = 3600
_GML_EDGE_ATTR_REPEAT = 20
_FNX_GML_EDGE_ATTR_GRAPH = _build_gml_edge_attr_graph(
    fnx, _GML_EDGE_ATTR_NODE_COUNT, _GML_EDGE_ATTR_EDGE_COUNT
)
_NX_GML_EDGE_ATTR_GRAPH = _build_gml_edge_attr_graph(
    nx, _GML_EDGE_ATTR_NODE_COUNT, _GML_EDGE_ATTR_EDGE_COUNT
)
_FNX_GML_EDGE_ATTR_BYTES = io.BytesIO()
_NX_GML_EDGE_ATTR_BYTES = io.BytesIO()
fnx.write_gml(_FNX_GML_EDGE_ATTR_GRAPH, _FNX_GML_EDGE_ATTR_BYTES)
nx.write_gml(_NX_GML_EDGE_ATTR_GRAPH, _NX_GML_EDGE_ATTR_BYTES)
if _FNX_GML_EDGE_ATTR_BYTES.getvalue() != _NX_GML_EDGE_ATTR_BYTES.getvalue():
    raise AssertionError("write_gml int edge-attr byte parity drift")


def fnx_write_gml_int_edge_attrs() -> float:
    total = 0.0
    for _ in range(_GML_EDGE_ATTR_REPEAT):
        total += _write_gml_signature(fnx, _FNX_GML_EDGE_ATTR_GRAPH)
    return total


def networkx_write_gml_int_edge_attrs() -> float:
    total = 0.0
    for _ in range(_GML_EDGE_ATTR_REPEAT):
        total += _write_gml_signature(nx, _NX_GML_EDGE_ATTR_GRAPH)
    return total


def _build_empty_copy_source(module, node_count: int):
    graph = module.Graph()
    graph.graph["name"] = "empty-copy-node-attrs"
    graph.add_nodes_from(
        (node, {"color": node % 7, "payload": (node, node + 1)})
        for node in range(node_count)
    )
    graph.add_edges_from((node, node + 1) for node in range(0, node_count - 1, 7))
    return graph


def _consume_empty_copy(graph) -> float:
    last_node = _EMPTY_COPY_NODE_COUNT - 1
    return float(
        graph.number_of_nodes()
        + graph.number_of_edges()
        + graph.nodes[0]["color"]
        + graph.nodes[last_node]["payload"][1]
        + len(graph.graph["name"])
    )


_EMPTY_COPY_NODE_COUNT = 10_000
_EMPTY_COPY_REPEAT = 20
_FNX_EMPTY_COPY_SOURCE = _build_empty_copy_source(fnx, _EMPTY_COPY_NODE_COUNT)
_NX_EMPTY_COPY_SOURCE = _build_empty_copy_source(nx, _EMPTY_COPY_NODE_COUNT)
_FNX_EMPTY_COPY_PARSED = fnx.create_empty_copy(_FNX_EMPTY_COPY_SOURCE, with_data=True)
_NX_EMPTY_COPY_PARSED = nx.create_empty_copy(_NX_EMPTY_COPY_SOURCE, with_data=True)
if (
    list(_FNX_EMPTY_COPY_PARSED.nodes()) != list(_NX_EMPTY_COPY_PARSED.nodes())
    or _FNX_EMPTY_COPY_PARSED.number_of_edges() != 0
    or _NX_EMPTY_COPY_PARSED.number_of_edges() != 0
    or _FNX_EMPTY_COPY_PARSED.graph != _NX_EMPTY_COPY_PARSED.graph
    or _FNX_EMPTY_COPY_PARSED.nodes[1234] != _NX_EMPTY_COPY_PARSED.nodes[1234]
    or _consume_empty_copy(_FNX_EMPTY_COPY_PARSED)
    != _consume_empty_copy(_NX_EMPTY_COPY_PARSED)
):
    raise AssertionError("create_empty_copy node-attr parity drift")


def fnx_create_empty_copy_node_attrs_10k() -> float:
    total = 0.0
    for _ in range(_EMPTY_COPY_REPEAT):
        total += _consume_empty_copy(
            fnx.create_empty_copy(_FNX_EMPTY_COPY_SOURCE, with_data=True)
        )
    return total


def networkx_create_empty_copy_node_attrs_10k() -> float:
    total = 0.0
    for _ in range(_EMPTY_COPY_REPEAT):
        total += _consume_empty_copy(
            nx.create_empty_copy(_NX_EMPTY_COPY_SOURCE, with_data=True)
        )
    return total


def _build_tournament_graph(module, node_count: int):
    graph = module.DiGraph()
    graph.add_nodes_from(range(node_count))
    edges = []
    for left in range(node_count):
        for right in range(left + 1, node_count):
            bit = (
                left * 6_364_136_223_846_793_005
                + right * 1_442_695_040_888_963_407
            ) & 7
            if bit in (0, 1, 4, 6):
                edges.append((left, right))
            else:
                edges.append((right, left))
    graph.add_edges_from(edges)
    return graph


_TOURNAMENT_REACH_NODE_COUNT = 220
_TOURNAMENT_REACH_SOURCE = 146
_TOURNAMENT_REACH_TARGET = 73
_TOURNAMENT_REACH_REPEAT = 3
_FNX_TOURNAMENT_REACH_GRAPH = _build_tournament_graph(
    fnx, _TOURNAMENT_REACH_NODE_COUNT
)
_NX_TOURNAMENT_REACH_GRAPH = _build_tournament_graph(nx, _TOURNAMENT_REACH_NODE_COUNT)
_FNX_TOURNAMENT_REACHABLE = fnx_tournament.is_reachable(
    _FNX_TOURNAMENT_REACH_GRAPH,
    _TOURNAMENT_REACH_SOURCE,
    _TOURNAMENT_REACH_TARGET,
)
_NX_TOURNAMENT_REACHABLE = nx_tournament.is_reachable(
    _NX_TOURNAMENT_REACH_GRAPH,
    _TOURNAMENT_REACH_SOURCE,
    _TOURNAMENT_REACH_TARGET,
)
if _FNX_TOURNAMENT_REACHABLE != _NX_TOURNAMENT_REACHABLE:
    raise AssertionError("tournament.is_reachable parity drift")


def fnx_tournament_is_reachable_bitset_220() -> float:
    total = 0.0
    for _ in range(_TOURNAMENT_REACH_REPEAT):
        total += float(
            fnx_tournament.is_reachable(
                _FNX_TOURNAMENT_REACH_GRAPH,
                _TOURNAMENT_REACH_SOURCE,
                _TOURNAMENT_REACH_TARGET,
            )
        )
    return total


def networkx_tournament_is_reachable_bitset_220() -> float:
    total = 0.0
    for _ in range(_TOURNAMENT_REACH_REPEAT):
        total += float(
            nx_tournament.is_reachable(
                _NX_TOURNAMENT_REACH_GRAPH,
                _TOURNAMENT_REACH_SOURCE,
                _TOURNAMENT_REACH_TARGET,
            )
        )
    return total


def _build_dedensify_graph(module, low_count: int, hub_count: int):
    graph = module.DiGraph()
    graph.add_nodes_from(range(low_count + hub_count))
    for low_node in range(low_count):
        for hub_offset in range(hub_count):
            if (low_node * 13 + hub_offset * 7) % 5:
                graph.add_edge(low_node, low_count + hub_offset)
    return graph


def _dedensify_signature(
    result,
) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...], tuple[str, ...]]:
    graph, compressors = result
    return (
        tuple(sorted(map(str, graph.nodes()))),
        tuple(sorted((str(u), str(v)) for u, v in graph.edges())),
        tuple(sorted(map(str, compressors))),
    )


def _consume_dedensify(result) -> float:
    graph, compressors = result
    return float(
        graph.number_of_nodes()
        + graph.number_of_edges()
        + len(compressors)
        + sum(len(str(node)) for node in compressors)
    )


_DEDENSIFY_LOW_COUNT = 900
_DEDENSIFY_HUB_COUNT = 12
_DEDENSIFY_THRESHOLD = 5
_DEDENSIFY_REPEAT = 5
_FNX_DEDENSIFY_GRAPH = _build_dedensify_graph(
    fnx, _DEDENSIFY_LOW_COUNT, _DEDENSIFY_HUB_COUNT
)
_NX_DEDENSIFY_GRAPH = _build_dedensify_graph(
    nx, _DEDENSIFY_LOW_COUNT, _DEDENSIFY_HUB_COUNT
)
_FNX_DEDENSIFY_SIGNATURE = _dedensify_signature(
    fnx_summarization.dedensify(
        _FNX_DEDENSIFY_GRAPH,
        threshold=_DEDENSIFY_THRESHOLD,
        prefix="aux",
        copy=True,
    )
)
_NX_DEDENSIFY_SIGNATURE = _dedensify_signature(
    nx_summarization.dedensify(
        _NX_DEDENSIFY_GRAPH,
        threshold=_DEDENSIFY_THRESHOLD,
        prefix="aux",
        copy=True,
    )
)
# ubs:ignore - benchmark graph signatures are public parity data, not secrets.
if _FNX_DEDENSIFY_SIGNATURE != _NX_DEDENSIFY_SIGNATURE:
    raise AssertionError("summarization.dedensify copy=True parity drift")


def fnx_summarization_dedensify_copy_dense_hubs() -> float:
    total = 0.0
    for _ in range(_DEDENSIFY_REPEAT):
        total += _consume_dedensify(
            fnx_summarization.dedensify(
                _FNX_DEDENSIFY_GRAPH,
                threshold=_DEDENSIFY_THRESHOLD,
                prefix="aux",
                copy=True,
            )
        )
    return total


def networkx_summarization_dedensify_copy_dense_hubs() -> float:
    total = 0.0
    for _ in range(_DEDENSIFY_REPEAT):
        total += _consume_dedensify(
            nx_summarization.dedensify(
                _NX_DEDENSIFY_GRAPH,
                threshold=_DEDENSIFY_THRESHOLD,
                prefix="aux",
                copy=True,
            )
        )
    return total


def _build_edge_boundary_graph(module, node_count: int, probability: float):
    graph = module.Graph()
    graph.add_nodes_from(range(node_count))
    threshold = int(probability * 65_536)
    for u in range(node_count):
        for v in range(u + 1, node_count):
            if ((u * 1_103_515_245 + v * 12_345 + 99_991) & 0xFFFF) < threshold:
                graph.add_edge(u, v)
    return graph


def _edge_boundary_checksum(edges) -> float:
    total = 0
    for u, v in edges:
        total += (u * 31 + v * 17) % 1_000_003
    return float(total)


_EDGE_BOUNDARY_NODE_COUNT = 900
_EDGE_BOUNDARY_PROBABILITY = 0.01
_EDGE_BOUNDARY_REPEAT = 80
_EDGE_BOUNDARY_SOURCE = list(range(_EDGE_BOUNDARY_NODE_COUNT // 5))
_EDGE_BOUNDARY_TARGET = list(
    range(
        _EDGE_BOUNDARY_NODE_COUNT // 2,
        _EDGE_BOUNDARY_NODE_COUNT // 2 + _EDGE_BOUNDARY_NODE_COUNT // 5,
    )
)
_FNX_EDGE_BOUNDARY_GRAPH = _build_edge_boundary_graph(
    fnx, _EDGE_BOUNDARY_NODE_COUNT, _EDGE_BOUNDARY_PROBABILITY
)
_NX_EDGE_BOUNDARY_GRAPH = _build_edge_boundary_graph(
    nx, _EDGE_BOUNDARY_NODE_COUNT, _EDGE_BOUNDARY_PROBABILITY
)
if list(
    fnx.edge_boundary(
        _FNX_EDGE_BOUNDARY_GRAPH,
        _EDGE_BOUNDARY_SOURCE,
        _EDGE_BOUNDARY_TARGET,
    )
) != list(
    nx.edge_boundary(
        _NX_EDGE_BOUNDARY_GRAPH,
        _EDGE_BOUNDARY_SOURCE,
        _EDGE_BOUNDARY_TARGET,
    )
):
    raise AssertionError("edge_boundary target-set parity drift")


def fnx_edge_boundary_target_sparse() -> float:
    total = 0.0
    for _ in range(_EDGE_BOUNDARY_REPEAT):
        total += _edge_boundary_checksum(
            fnx.edge_boundary(
                _FNX_EDGE_BOUNDARY_GRAPH,
                _EDGE_BOUNDARY_SOURCE,
                _EDGE_BOUNDARY_TARGET,
            )
        )
    return total


def networkx_edge_boundary_target_sparse() -> float:
    total = 0.0
    for _ in range(_EDGE_BOUNDARY_REPEAT):
        total += _edge_boundary_checksum(
            nx.edge_boundary(
                _NX_EDGE_BOUNDARY_GRAPH,
                _EDGE_BOUNDARY_SOURCE,
                _EDGE_BOUNDARY_TARGET,
            )
        )
    return total


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


_FAST_GNP_GRAPH_N = 1500
_FAST_GNP_GRAPH_P = 0.008
_FAST_GNP_DIGRAPH_N = 900
_FAST_GNP_DIGRAPH_P = 0.012
_FAST_GNP_SEED = 1234
_FAST_GNP_REPEAT = 20


def _fast_gnp_create_using(module, *, directed: bool):
    graph_type = module.DiGraph if directed else module.Graph
    if directed:
        return module.fast_gnp_random_graph(
            _FAST_GNP_DIGRAPH_N,
            _FAST_GNP_DIGRAPH_P,
            seed=_FAST_GNP_SEED,
            directed=True,
            create_using=graph_type(),
        )
    return module.fast_gnp_random_graph(
        _FAST_GNP_GRAPH_N,
        _FAST_GNP_GRAPH_P,
        seed=_FAST_GNP_SEED,
        create_using=graph_type(),
    )


def _edge_order_signature(graph) -> tuple[tuple, tuple]:
    return tuple(graph.nodes()), tuple(graph.edges())


_EXPECTED_FAST_GNP_GRAPH = _edge_order_signature(
    _fast_gnp_create_using(nx, directed=False)
)
_FNX_FAST_GNP_GRAPH = _edge_order_signature(_fast_gnp_create_using(fnx, directed=False))
# ubs:ignore - benchmark graph signatures are public parity data, not secrets.
if _FNX_FAST_GNP_GRAPH != _EXPECTED_FAST_GNP_GRAPH:
    raise AssertionError("fast_gnp_random_graph Graph create_using parity drift")

_EXPECTED_FAST_GNP_DIGRAPH = _edge_order_signature(
    _fast_gnp_create_using(nx, directed=True)
)
_FNX_FAST_GNP_DIGRAPH = _edge_order_signature(
    _fast_gnp_create_using(fnx, directed=True)
)
# ubs:ignore - benchmark graph signatures are public parity data, not secrets.
if _FNX_FAST_GNP_DIGRAPH != _EXPECTED_FAST_GNP_DIGRAPH:
    raise AssertionError("fast_gnp_random_graph DiGraph create_using parity drift")


def fnx_fast_gnp_create_using_graph() -> float:
    total = 0.0
    for _ in range(_FAST_GNP_REPEAT):
        total += _fast_gnp_create_using(fnx, directed=False).number_of_edges()
    return total


def networkx_fast_gnp_create_using_graph() -> float:
    total = 0.0
    for _ in range(_FAST_GNP_REPEAT):
        total += _fast_gnp_create_using(nx, directed=False).number_of_edges()
    return total


def fnx_fast_gnp_create_using_digraph() -> float:
    total = 0.0
    for _ in range(_FAST_GNP_REPEAT):
        total += _fast_gnp_create_using(fnx, directed=True).number_of_edges()
    return total


def networkx_fast_gnp_create_using_digraph() -> float:
    total = 0.0
    for _ in range(_FAST_GNP_REPEAT):
        total += _fast_gnp_create_using(nx, directed=True).number_of_edges()
    return total


def _build_ubizp_multigraph(module, node_count: int):
    graph = module.MultiGraph()
    graph.add_nodes_from(range(node_count))
    for node in range(node_count - 1):
        graph.add_edge(node, node + 1)
        graph.add_edge(node, node + 1, key=f"p{node}")
        if node + 7 < node_count:
            graph.add_edge(node, node + 7)
        if node + 37 < node_count:
            graph.add_edge(node, node + 37)
    return graph


_UBIZP_NODE_COUNT = 1600
_UBIZP_SOURCE = 0
_UBIZP_REPEAT = 80
_FNX_UBIZP_GRAPH = _build_ubizp_multigraph(fnx, _UBIZP_NODE_COUNT)
_NX_UBIZP_GRAPH = _build_ubizp_multigraph(nx, _UBIZP_NODE_COUNT)

_EXPECTED_UBIZP_SSSP = nx.single_source_shortest_path(_NX_UBIZP_GRAPH, _UBIZP_SOURCE)
_FNX_UBIZP_SSSP = fnx.single_source_shortest_path(_FNX_UBIZP_GRAPH, _UBIZP_SOURCE)
if _FNX_UBIZP_SSSP != _EXPECTED_UBIZP_SSSP:
    raise AssertionError("ubizp single_source_shortest_path parity drift")


def fnx_ubizp_multigraph_single_source_shortest_path() -> float:
    total = 0.0
    for _ in range(_UBIZP_REPEAT):
        total += len(fnx.single_source_shortest_path(_FNX_UBIZP_GRAPH, _UBIZP_SOURCE))
    return total


def networkx_ubizp_multigraph_single_source_shortest_path() -> float:
    total = 0.0
    for _ in range(_UBIZP_REPEAT):
        total += len(nx.single_source_shortest_path(_NX_UBIZP_GRAPH, _UBIZP_SOURCE))
    return total


def _build_single_target_mdg(module, node_count: int, fanout: int, parallels: int):
    graph = module.MultiDiGraph()
    graph.add_nodes_from(range(node_count))
    for node in range(1, node_count):
        for step in range(1, fanout + 1):
            target = node - step
            if target < 0:
                break
            for key in range(parallels):
                graph.add_edge(node, target, key=key)
    return graph


_ST_MDG_NODE_COUNT = 1400
_ST_MDG_FANOUT = 5
_ST_MDG_PARALLELS = 3
_ST_MDG_TARGET = 0
_ST_MDG_REPEAT = 30
_FNX_ST_MDG_GRAPH = _build_single_target_mdg(
    fnx, _ST_MDG_NODE_COUNT, _ST_MDG_FANOUT, _ST_MDG_PARALLELS
)
_NX_ST_MDG_GRAPH = _build_single_target_mdg(
    nx, _ST_MDG_NODE_COUNT, _ST_MDG_FANOUT, _ST_MDG_PARALLELS
)

_EXPECTED_ST_MDG = dict(
    nx.single_target_shortest_path_length(_NX_ST_MDG_GRAPH, _ST_MDG_TARGET)
)
_FNX_ST_MDG = fnx.single_target_shortest_path_length(
    _FNX_ST_MDG_GRAPH, _ST_MDG_TARGET
)
if list(_FNX_ST_MDG.items()) != list(_EXPECTED_ST_MDG.items()):
    raise AssertionError("single_target_shortest_path_length MultiDiGraph parity drift")


def _distance_checksum(lengths: dict[int, int]) -> float:
    total = 0
    for node, distance in lengths.items():
        total += node * 31 + distance
    return float(total + len(lengths))


def fnx_multidigraph_single_target_shortest_path_length() -> float:
    total = 0.0
    for _ in range(_ST_MDG_REPEAT):
        total += _distance_checksum(
            fnx.single_target_shortest_path_length(_FNX_ST_MDG_GRAPH, _ST_MDG_TARGET)
        )
    return total


def networkx_multidigraph_single_target_shortest_path_length() -> float:
    total = 0.0
    for _ in range(_ST_MDG_REPEAT):
        total += _distance_checksum(
            dict(nx.single_target_shortest_path_length(_NX_ST_MDG_GRAPH, _ST_MDG_TARGET))
        )
    return total


def _build_weighted_target_digraph(module, node_count: int, fanout: int):
    graph = module.DiGraph()
    graph.add_nodes_from(range(node_count))
    for node in range(1, node_count):
        for step in range(1, fanout + 1):
            target = node - step
            if target < 0:
                break
            weight = float(((node * 17 + step * 7) % 23) + 1)
            graph.add_edge(node, target, weight=weight)
    return graph


_WT_TARGET_NODE_COUNT = 360
_WT_TARGET_FANOUT = 4
_WT_TARGET = 0
_FNX_WT_TARGET_GRAPH = _build_weighted_target_digraph(
    fnx, _WT_TARGET_NODE_COUNT, _WT_TARGET_FANOUT
)
_NX_WT_TARGET_GRAPH = _build_weighted_target_digraph(
    nx, _WT_TARGET_NODE_COUNT, _WT_TARGET_FANOUT
)

_EXPECTED_WT_TARGET = dict(
    nx.shortest_path_length(_NX_WT_TARGET_GRAPH, target=_WT_TARGET, weight="weight")
)
_FNX_WT_TARGET = dict(
    fnx.shortest_path_length(_FNX_WT_TARGET_GRAPH, target=_WT_TARGET, weight="weight")
)
if list(_FNX_WT_TARGET.items()) != list(_EXPECTED_WT_TARGET.items()):
    raise AssertionError("weighted target shortest_path_length DiGraph parity drift")


def fnx_digraph_weighted_target_shortest_path_length() -> float:
    return _distance_checksum(
        dict(
            fnx.shortest_path_length(
                _FNX_WT_TARGET_GRAPH, target=_WT_TARGET, weight="weight"
            )
        )
    )


def networkx_digraph_weighted_target_shortest_path_length() -> float:
    return _distance_checksum(
        dict(
            nx.shortest_path_length(
                _NX_WT_TARGET_GRAPH, target=_WT_TARGET, weight="weight"
            )
        )
    )


def _build_string_sssp_graph(module, node_count: int):
    graph = module.Graph()
    nodes = [f"node_{idx:04d}" for idx in range(node_count)]
    graph.add_nodes_from(nodes)
    for idx in range(node_count - 1):
        graph.add_edge(nodes[idx], nodes[idx + 1])
    for step in (17, 31):
        for idx in range(node_count - step):
            if idx % 3 == 0:
                graph.add_edge(nodes[idx], nodes[idx + step])
    return graph


def _string_path_checksum(paths: dict[str, list[str]]) -> float:
    total = 0
    for node, path in paths.items():
        total += len(node) * 31 + len(path)
    return float(total + len(paths))


_STRING_SSSP_NODE_COUNT = 1400
_STRING_SSSP_REPEAT = 40
_STRING_SSSP_SOURCE = "node_0000"
_FNX_STRING_SSSP_GRAPH = _build_string_sssp_graph(fnx, _STRING_SSSP_NODE_COUNT)
_NX_STRING_SSSP_GRAPH = _build_string_sssp_graph(nx, _STRING_SSSP_NODE_COUNT)
_EXPECTED_STRING_SSSP = nx.single_source_shortest_path(
    _NX_STRING_SSSP_GRAPH, _STRING_SSSP_SOURCE
)
_FNX_STRING_SSSP = fnx.single_source_shortest_path(
    _FNX_STRING_SSSP_GRAPH, _STRING_SSSP_SOURCE
)
if _FNX_STRING_SSSP != _EXPECTED_STRING_SSSP:
    raise AssertionError("string Graph single_source_shortest_path parity drift")


def fnx_string_graph_single_source_shortest_path() -> float:
    total = 0.0
    for _ in range(_STRING_SSSP_REPEAT):
        total += _string_path_checksum(
            fnx.single_source_shortest_path(_FNX_STRING_SSSP_GRAPH, _STRING_SSSP_SOURCE)
        )
    return total


def networkx_string_graph_single_source_shortest_path() -> float:
    total = 0.0
    for _ in range(_STRING_SSSP_REPEAT):
        total += _string_path_checksum(
            nx.single_source_shortest_path(_NX_STRING_SSSP_GRAPH, _STRING_SSSP_SOURCE)
        )
    return total


_SS_MDG_SOURCE = _ST_MDG_NODE_COUNT - 1
_SS_MDG_REPEAT = 20

_EXPECTED_SS_MDG = nx.single_source_shortest_path(_NX_ST_MDG_GRAPH, _SS_MDG_SOURCE)
_FNX_SS_MDG = fnx.single_source_shortest_path(_FNX_ST_MDG_GRAPH, _SS_MDG_SOURCE)
if _FNX_SS_MDG != _EXPECTED_SS_MDG:
    raise AssertionError("single_source_shortest_path MultiDiGraph parity drift")

_EXPECTED_BFS_MDG = list(nx.bfs_edges(_NX_ST_MDG_GRAPH, _SS_MDG_SOURCE))
_FNX_BFS_MDG = list(fnx.bfs_edges(_FNX_ST_MDG_GRAPH, _SS_MDG_SOURCE))
if _FNX_BFS_MDG != _EXPECTED_BFS_MDG:
    raise AssertionError("bfs_edges MultiDiGraph parity drift")


def _path_checksum(paths: dict[int, list[int]]) -> float:
    total = 0
    for node, path in paths.items():
        total += node * 31 + len(path)
    return float(total + len(paths))


def fnx_multidigraph_single_source_shortest_path() -> float:
    total = 0.0
    for _ in range(_SS_MDG_REPEAT):
        total += _path_checksum(
            fnx.single_source_shortest_path(_FNX_ST_MDG_GRAPH, _SS_MDG_SOURCE)
        )
    return total


def networkx_multidigraph_single_source_shortest_path() -> float:
    total = 0.0
    for _ in range(_SS_MDG_REPEAT):
        total += _path_checksum(
            nx.single_source_shortest_path(_NX_ST_MDG_GRAPH, _SS_MDG_SOURCE)
        )
    return total


def fnx_multidigraph_bfs_edges() -> float:
    total = 0.0
    for _ in range(_SS_MDG_REPEAT):
        total += len(list(fnx.bfs_edges(_FNX_ST_MDG_GRAPH, _SS_MDG_SOURCE)))
    return total


def networkx_multidigraph_bfs_edges() -> float:
    total = 0.0
    for _ in range(_SS_MDG_REPEAT):
        total += len(list(nx.bfs_edges(_NX_ST_MDG_GRAPH, _SS_MDG_SOURCE)))
    return total


def _build_scc_mdg(module, component_count: int, component_size: int, parallels: int):
    graph = module.MultiDiGraph()
    node_count = component_count * component_size
    graph.add_nodes_from(range(node_count))
    for component in range(component_count):
        start = component * component_size
        for offset in range(component_size):
            u = start + offset
            v = start + ((offset + 1) % component_size)
            w = start + ((offset + 5) % component_size)
            for key in range(parallels):
                graph.add_edge(u, v, key=("cycle", key))
            graph.add_edge(u, w, key="chord")
        if component + 1 < component_count:
            graph.add_edge(start, start + component_size, key="forward")
    return graph


def _sorted_component_groups(components) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(sorted(int(node) for node in component)) for component in components)


def _component_checksum(components) -> float:
    total = 0
    for component_index, component in enumerate(components):
        for node in component:
            total += (component_index + 1) * 31 + int(node)
    return float(total)


_SCC_MDG_COMPONENTS = 90
_SCC_MDG_COMPONENT_SIZE = 20
_SCC_MDG_PARALLELS = 3
_SCC_MDG_REPEAT = 20
_FNX_SCC_MDG_GRAPH = _build_scc_mdg(
    fnx, _SCC_MDG_COMPONENTS, _SCC_MDG_COMPONENT_SIZE, _SCC_MDG_PARALLELS
)
_NX_SCC_MDG_GRAPH = _build_scc_mdg(
    nx, _SCC_MDG_COMPONENTS, _SCC_MDG_COMPONENT_SIZE, _SCC_MDG_PARALLELS
)
_EXPECTED_SCC_MDG = _sorted_component_groups(
    nx.strongly_connected_components(_NX_SCC_MDG_GRAPH)
)
_FNX_SCC_MDG = _sorted_component_groups(
    fnx.strongly_connected_components(_FNX_SCC_MDG_GRAPH)
)
if _FNX_SCC_MDG != _EXPECTED_SCC_MDG:
    raise AssertionError("strongly_connected_components MultiDiGraph parity drift")


def fnx_multidigraph_strongly_connected_components() -> float:
    total = 0.0
    for _ in range(_SCC_MDG_REPEAT):
        total += _component_checksum(
            fnx.strongly_connected_components(_FNX_SCC_MDG_GRAPH)
        )
    return total


def networkx_multidigraph_strongly_connected_components() -> float:
    total = 0.0
    for _ in range(_SCC_MDG_REPEAT):
        total += _component_checksum(
            nx.strongly_connected_components(_NX_SCC_MDG_GRAPH)
        )
    return total


def _build_directed_pagerank_graph(module, node_count: int):
    graph = module.DiGraph()
    graph.add_nodes_from(range(node_count))
    for node in range(node_count):
        graph.add_edge(node, (node + 1) % node_count)
        graph.add_edge(node, (node + 7) % node_count)
        if node % 5 != 0:
            graph.add_edge(node, (node * 17 + 11) % node_count)
        if node % 11 == 0:
            graph.add_edge(node, (node + 113) % node_count)
    return graph


def _pagerank_checksum(scores: dict[int, float]) -> float:
    total = 0.0
    for node, score in scores.items():
        total += (int(node) + 1) * float(score)
    return total


def _pagerank_max_abs_diff(left: dict[int, float], right: dict[int, float]) -> float:
    if left.keys() != right.keys():
        return float("inf")
    return max((abs(left[node] - right[node]) for node in left), default=0.0)


_PAGERANK_NODE_COUNT = 1800
_PAGERANK_REPEAT = 8
_PAGERANK_TOL = 1.0e-8
_FNX_PAGERANK_GRAPH = _build_directed_pagerank_graph(fnx, _PAGERANK_NODE_COUNT)
_NX_PAGERANK_GRAPH = _build_directed_pagerank_graph(nx, _PAGERANK_NODE_COUNT)
if _SCIPY_AVAILABLE:
    _EXPECTED_PAGERANK = _NETWORKX_PAGERANK(_NX_PAGERANK_GRAPH, tol=_PAGERANK_TOL)
    _FNX_PAGERANK = fnx.pagerank(_FNX_PAGERANK_GRAPH, tol=_PAGERANK_TOL)
    if _pagerank_max_abs_diff(_FNX_PAGERANK, _EXPECTED_PAGERANK) > 1.0e-9:
        raise AssertionError(
            f"pagerank DiGraph parity drift via NetworkX {_NETWORKX_PAGERANK_KIND}"
        )


def fnx_directed_pagerank_large() -> float:
    if not _SCIPY_AVAILABLE:
        raise RuntimeError("fnx pagerank benchmark requires scipy")
    total = 0.0
    for _ in range(_PAGERANK_REPEAT):
        total += _pagerank_checksum(
            fnx.pagerank(_FNX_PAGERANK_GRAPH, tol=_PAGERANK_TOL)
        )
    return total


def networkx_directed_pagerank_large() -> float:
    total = 0.0
    for _ in range(_PAGERANK_REPEAT):
        total += _pagerank_checksum(
            _NETWORKX_PAGERANK(_NX_PAGERANK_GRAPH, tol=_PAGERANK_TOL)
        )
    return total


def _build_weighted_target_mdg(module, node_count: int):
    graph = module.MultiDiGraph()
    graph.add_nodes_from(range(node_count))
    steps = (1, 7, 37, 113)
    for u in range(node_count):
        for step_index, step in enumerate(steps):
            v = (u + step) % node_count
            for key in range(2):
                weight = ((u * 17 + step_index * 5 + key * 3) % 31) + 1
                graph.add_edge(u, v, key=key, weight=weight)
    return graph


_DPL_MDG_NODE_COUNT = 5000
_DPL_MDG_SOURCE = 0
_DPL_MDG_TARGET = 113
_DPL_MDG_REPEAT = 64
_FNX_DPL_MDG_GRAPH = _build_weighted_target_mdg(fnx, _DPL_MDG_NODE_COUNT)
_NX_DPL_MDG_GRAPH = _build_weighted_target_mdg(nx, _DPL_MDG_NODE_COUNT)
_EXPECTED_DPL_MDG = nx.dijkstra_path_length(
    _NX_DPL_MDG_GRAPH, _DPL_MDG_SOURCE, _DPL_MDG_TARGET, weight="weight"
)
_FNX_DPL_MDG = fnx.dijkstra_path_length(
    _FNX_DPL_MDG_GRAPH, _DPL_MDG_SOURCE, _DPL_MDG_TARGET, weight="weight"
)
if _FNX_DPL_MDG != _EXPECTED_DPL_MDG:
    raise AssertionError("dijkstra_path_length MultiDiGraph parity drift")

_EXPECTED_DP_MDG = nx.dijkstra_path(
    _NX_DPL_MDG_GRAPH, _DPL_MDG_SOURCE, _DPL_MDG_TARGET, weight="weight"
)
_FNX_DP_MDG = fnx.dijkstra_path(
    _FNX_DPL_MDG_GRAPH, _DPL_MDG_SOURCE, _DPL_MDG_TARGET, weight="weight"
)
if _FNX_DP_MDG != _EXPECTED_DP_MDG:
    raise AssertionError("dijkstra_path MultiDiGraph parity drift")

_EXPECTED_SSDPL_MDG = nx.single_source_dijkstra_path_length(
    _NX_DPL_MDG_GRAPH, _DPL_MDG_SOURCE, weight="weight"
)
_FNX_SSDPL_MDG = fnx.single_source_dijkstra_path_length(
    _FNX_DPL_MDG_GRAPH, _DPL_MDG_SOURCE, weight="weight"
)
if list(_FNX_SSDPL_MDG.items()) != list(_EXPECTED_SSDPL_MDG.items()):
    raise AssertionError("single_source_dijkstra_path_length MultiDiGraph parity drift")


def fnx_multidigraph_dijkstra_path_length_target_early_exit() -> float:
    total = 0.0
    for _ in range(_DPL_MDG_REPEAT):
        total += fnx.dijkstra_path_length(
            _FNX_DPL_MDG_GRAPH, _DPL_MDG_SOURCE, _DPL_MDG_TARGET, weight="weight"
        )
    return total


def networkx_multidigraph_dijkstra_path_length_target_early_exit() -> float:
    total = 0.0
    for _ in range(_DPL_MDG_REPEAT):
        total += nx.dijkstra_path_length(
            _NX_DPL_MDG_GRAPH, _DPL_MDG_SOURCE, _DPL_MDG_TARGET, weight="weight"
        )
    return total


def _path_sequence_checksum(path: list[int]) -> float:
    total = 0
    for idx, node in enumerate(path):
        total += (idx + 1) * 31 + int(node)
    return float(total + len(path))


def fnx_multidigraph_dijkstra_path_target_early_exit() -> float:
    total = 0.0
    for _ in range(_DPL_MDG_REPEAT):
        total += _path_sequence_checksum(
            fnx.dijkstra_path(
                _FNX_DPL_MDG_GRAPH, _DPL_MDG_SOURCE, _DPL_MDG_TARGET, weight="weight"
            )
        )
    return total


def networkx_multidigraph_dijkstra_path_target_early_exit() -> float:
    total = 0.0
    for _ in range(_DPL_MDG_REPEAT):
        total += _path_sequence_checksum(
            nx.dijkstra_path(
                _NX_DPL_MDG_GRAPH, _DPL_MDG_SOURCE, _DPL_MDG_TARGET, weight="weight"
            )
        )
    return total


_SSDPL_MDG_REPEAT = 4


def _weighted_distance_checksum(lengths: dict[int, int | float]) -> float:
    total = 0.0
    for idx, (node, distance) in enumerate(lengths.items()):
        total += (idx + 1) * 0.25 + int(node) * 0.5 + float(distance)
    return total + len(lengths)


def fnx_multidigraph_single_source_dijkstra_path_length() -> float:
    total = 0.0
    for _ in range(_SSDPL_MDG_REPEAT):
        total += _weighted_distance_checksum(
            fnx.single_source_dijkstra_path_length(
                _FNX_DPL_MDG_GRAPH, _DPL_MDG_SOURCE, weight="weight"
            )
        )
    return total


def networkx_multidigraph_single_source_dijkstra_path_length() -> float:
    total = 0.0
    for _ in range(_SSDPL_MDG_REPEAT):
        total += _weighted_distance_checksum(
            nx.single_source_dijkstra_path_length(
                _NX_DPL_MDG_GRAPH, _DPL_MDG_SOURCE, weight="weight"
            )
        )
    return total


def _build_link_prediction_overlap_graph(
    module, clusters: int, size: int, probability: float, seed: int
):
    rng = random.Random(seed)
    graph = module.Graph()
    node_count = clusters * size
    for node in range(node_count):
        graph.add_node(node, community=node // size)
    for cluster in range(clusters):
        start = cluster * size
        for node in range(start, start + size - 1):
            graph.add_edge(node, node + 1)
        for u in range(start, start + size):
            for v in range(u + 2, start + size):
                if rng.random() < probability:
                    graph.add_edge(u, v)
    for cluster in range(clusters - 1):
        for _ in range(4):
            u = cluster * size + rng.randrange(size)
            v = (cluster + 1) * size + rng.randrange(size)
            graph.add_edge(u, v)
    return graph


def _link_prediction_overlap_ebunch(
    graph, clusters: int, size: int, target_count: int, repeats: int
):
    scored = []
    for cluster in range(clusters):
        start = cluster * size
        for u in range(start, start + size):
            u_neighbors = set(graph.neighbors(u))
            for v in range(u + 1, start + size):
                if not graph.has_edge(u, v):
                    common = len(u_neighbors & set(graph.neighbors(v)))
                    if common:
                        scored.append((common, u, v))
    scored.sort(reverse=True)
    ebunch = []
    for _, u, v in scored[:target_count]:
        for _ in range(repeats):
            ebunch.append((u, v))
    return ebunch


_RAW_LINK_CLUSTERS = 10
_RAW_LINK_CLUSTER_SIZE = 80
_RAW_LINK_PROBABILITY = 0.05
_RAW_LINK_TARGET_PAIRS = 1600
_RAW_LINK_PAIR_REPEATS = 4
_RAW_LINK_API_REPEATS = 80
_RAW_LINK_SEED = 9148
_FNX_RAW_LINK_GRAPH = _build_link_prediction_overlap_graph(
    fnx,
    _RAW_LINK_CLUSTERS,
    _RAW_LINK_CLUSTER_SIZE,
    _RAW_LINK_PROBABILITY,
    _RAW_LINK_SEED,
)
_NX_RAW_LINK_GRAPH = _build_link_prediction_overlap_graph(
    nx,
    _RAW_LINK_CLUSTERS,
    _RAW_LINK_CLUSTER_SIZE,
    _RAW_LINK_PROBABILITY,
    _RAW_LINK_SEED,
)
_RAW_LINK_EBUNCH = _link_prediction_overlap_ebunch(
    _NX_RAW_LINK_GRAPH,
    _RAW_LINK_CLUSTERS,
    _RAW_LINK_CLUSTER_SIZE,
    _RAW_LINK_TARGET_PAIRS,
    _RAW_LINK_PAIR_REPEATS,
)

_EXPECTED_RAW_AA = _consume_link_scores(
    nx.adamic_adar_index(_NX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH)
)
_FNX_RAW_AA = _consume_link_scores(
    fnx._fnx.adamic_adar_index(_FNX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH)
)
if abs(_FNX_RAW_AA - _EXPECTED_RAW_AA) > 1e-9:
    raise AssertionError(
        f"raw adamic_adar_index parity drift: fnx={_FNX_RAW_AA!r}, nx={_EXPECTED_RAW_AA!r}"
    )

_EXPECTED_RAW_RA = _consume_link_scores(
    nx.resource_allocation_index(_NX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH)
)
_FNX_RAW_RA = _consume_link_scores(
    fnx._fnx.resource_allocation_index(_FNX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH)
)
if abs(_FNX_RAW_RA - _EXPECTED_RAW_RA) > 1e-9:
    raise AssertionError(
        f"raw resource_allocation_index parity drift: fnx={_FNX_RAW_RA!r}, nx={_EXPECTED_RAW_RA!r}"
    )

_EXPECTED_RAW_PA = _consume_link_scores(
    nx.preferential_attachment(_NX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH)
)
_FNX_RAW_PA = _consume_link_scores(
    fnx._fnx.preferential_attachment(_FNX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH)
)
if abs(_FNX_RAW_PA - _EXPECTED_RAW_PA) > 1e-9:
    raise AssertionError(
        f"raw preferential_attachment parity drift: fnx={_FNX_RAW_PA!r}, nx={_EXPECTED_RAW_PA!r}"
    )

_EXPECTED_RAW_CN_SH = _consume_link_scores(
    nx.cn_soundarajan_hopcroft(_NX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH)
)
_FNX_RAW_CN_SH = _consume_link_scores(
    fnx._fnx.cn_soundarajan_hopcroft_rust(_FNX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH)
)
if abs(_FNX_RAW_CN_SH - _EXPECTED_RAW_CN_SH) > 1e-9:
    raise AssertionError(
        "raw cn_soundarajan_hopcroft parity drift: "
        f"fnx={_FNX_RAW_CN_SH!r}, nx={_EXPECTED_RAW_CN_SH!r}"
    )

_EXPECTED_RAW_RA_SH = _consume_link_scores(
    nx.ra_index_soundarajan_hopcroft(_NX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH)
)
_FNX_RAW_RA_SH = _consume_link_scores(
    fnx._fnx.ra_index_soundarajan_hopcroft_rust(_FNX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH)
)
if abs(_FNX_RAW_RA_SH - _EXPECTED_RAW_RA_SH) > 1e-9:
    raise AssertionError(
        "raw ra_index_soundarajan_hopcroft parity drift: "
        f"fnx={_FNX_RAW_RA_SH!r}, nx={_EXPECTED_RAW_RA_SH!r}"
    )


def fnx_raw_adamic_adar_repeated_overlap() -> float:
    total = 0.0
    for _ in range(_RAW_LINK_API_REPEATS):
        total += _consume_link_scores(
            fnx._fnx.adamic_adar_index(_FNX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH)
        )
    return total


def networkx_adamic_adar_repeated_overlap() -> float:
    total = 0.0
    for _ in range(_RAW_LINK_API_REPEATS):
        total += _consume_link_scores(
            nx.adamic_adar_index(_NX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH)
        )
    return total


def fnx_raw_resource_allocation_repeated_overlap() -> float:
    total = 0.0
    for _ in range(_RAW_LINK_API_REPEATS):
        total += _consume_link_scores(
            fnx._fnx.resource_allocation_index(_FNX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH)
        )
    return total


def networkx_resource_allocation_repeated_overlap() -> float:
    total = 0.0
    for _ in range(_RAW_LINK_API_REPEATS):
        total += _consume_link_scores(
            nx.resource_allocation_index(_NX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH)
        )
    return total


def fnx_raw_cn_soundarajan_hopcroft_repeated_overlap() -> float:
    total = 0.0
    for _ in range(_RAW_LINK_API_REPEATS):
        total += _consume_link_scores(
            fnx._fnx.cn_soundarajan_hopcroft_rust(_FNX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH)
        )
    return total


def networkx_cn_soundarajan_hopcroft_repeated_overlap() -> float:
    total = 0.0
    for _ in range(_RAW_LINK_API_REPEATS):
        total += _consume_link_scores(
            nx.cn_soundarajan_hopcroft(_NX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH)
        )
    return total


def fnx_raw_ra_index_soundarajan_hopcroft_repeated_overlap() -> float:
    total = 0.0
    for _ in range(_RAW_LINK_API_REPEATS):
        total += _consume_link_scores(
            fnx._fnx.ra_index_soundarajan_hopcroft_rust(
                _FNX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH
            )
        )
    return total


def networkx_ra_index_soundarajan_hopcroft_repeated_overlap() -> float:
    total = 0.0
    for _ in range(_RAW_LINK_API_REPEATS):
        total += _consume_link_scores(
            nx.ra_index_soundarajan_hopcroft(_NX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH)
        )
    return total


def _build_is_path_graph(module, node_count: int):
    graph = module.Graph()
    graph.add_edges_from((i, i + 1) for i in range(node_count - 1))
    return graph


_IS_PATH_NODE_COUNT = 128
_IS_PATH_REPEAT = 8000
_IS_PATH_LEN50 = list(range(50))
_FNX_IS_PATH_GRAPH = _build_is_path_graph(fnx, _IS_PATH_NODE_COUNT)
_NX_IS_PATH_GRAPH = _build_is_path_graph(nx, _IS_PATH_NODE_COUNT)

_EXPECTED_IS_PATH_LEN50 = nx.is_path(_NX_IS_PATH_GRAPH, _IS_PATH_LEN50)
_FNX_IS_PATH_LEN50 = fnx.is_path(_FNX_IS_PATH_GRAPH, _IS_PATH_LEN50)
if _FNX_IS_PATH_LEN50 is not _EXPECTED_IS_PATH_LEN50:
    raise AssertionError(
        f"is_path len-50 parity drift: fnx={_FNX_IS_PATH_LEN50!r}, "
        f"nx={_EXPECTED_IS_PATH_LEN50!r}"
    )


def fnx_is_path_len50() -> float:
    total = 0.0
    for _ in range(_IS_PATH_REPEAT):
        total += float(fnx.is_path(_FNX_IS_PATH_GRAPH, _IS_PATH_LEN50))
    return total


def networkx_is_path_len50() -> float:
    total = 0.0
    for _ in range(_IS_PATH_REPEAT):
        total += float(nx.is_path(_NX_IS_PATH_GRAPH, _IS_PATH_LEN50))
    return total


def _weighted_attr_edges(node_count: int, edge_count: int, *, directed: bool):
    edges = []
    seen = set()
    step = 1
    u = 0
    while len(edges) < edge_count and step < node_count:
        left = u
        right = (u + step) % node_count
        emit_u, emit_v = left, right
        if not directed and emit_u > emit_v:
            emit_u, emit_v = emit_v, emit_u
        key = (emit_u, emit_v) if directed else (min(emit_u, emit_v), max(emit_u, emit_v))
        if key not in seen:
            idx = len(edges)
            seen.add(key)
            edges.append((emit_u, emit_v, {"weight": idx % 1009, "tag": f"e{idx % 17}"}))
        u += 1
        if u == node_count:
            u = 0
            step += 1
    if len(edges) != edge_count:
        raise AssertionError("unable to build requested unique weighted edge set")
    return edges


def _build_weighted_attr_graph(module, *, directed: bool):
    graph = module.DiGraph() if directed else module.Graph()
    graph.add_edges_from(_GET_EDGE_ATTR_DIGRAPH_EDGES if directed else _GET_EDGE_ATTR_GRAPH_EDGES)
    return graph


_GET_EDGE_ATTR_NODE_COUNT = 1024
_GET_EDGE_ATTR_EDGE_COUNT = 4096
_GET_EDGE_ATTR_REPEAT = 30
_GET_EDGE_ATTR_GRAPH_EDGES = _weighted_attr_edges(
    _GET_EDGE_ATTR_NODE_COUNT, _GET_EDGE_ATTR_EDGE_COUNT, directed=False
)
_GET_EDGE_ATTR_DIGRAPH_EDGES = _weighted_attr_edges(
    _GET_EDGE_ATTR_NODE_COUNT, _GET_EDGE_ATTR_EDGE_COUNT, directed=True
)
_FNX_GET_EDGE_ATTR_GRAPH = _build_weighted_attr_graph(fnx, directed=False)
_NX_GET_EDGE_ATTR_GRAPH = _build_weighted_attr_graph(nx, directed=False)
_FNX_GET_EDGE_ATTR_DIGRAPH = _build_weighted_attr_graph(fnx, directed=True)
_NX_GET_EDGE_ATTR_DIGRAPH = _build_weighted_attr_graph(nx, directed=True)

if fnx.get_edge_attributes(
    _FNX_GET_EDGE_ATTR_GRAPH, "weight"
) != nx.get_edge_attributes(_NX_GET_EDGE_ATTR_GRAPH, "weight"):
    raise AssertionError("Graph get_edge_attributes parity drift")
if fnx.get_edge_attributes(
    _FNX_GET_EDGE_ATTR_DIGRAPH, "weight"
) != nx.get_edge_attributes(_NX_GET_EDGE_ATTR_DIGRAPH, "weight"):
    raise AssertionError("DiGraph get_edge_attributes parity drift")


def _sum_weight_attrs(attrs) -> float:
    return float(sum(attrs.values()))


def fnx_graph_get_edge_attributes_weight_4k() -> float:
    total = 0.0
    for _ in range(_GET_EDGE_ATTR_REPEAT):
        total += _sum_weight_attrs(
            fnx.get_edge_attributes(_FNX_GET_EDGE_ATTR_GRAPH, "weight")
        )
    return total


def networkx_graph_get_edge_attributes_weight_4k() -> float:
    total = 0.0
    for _ in range(_GET_EDGE_ATTR_REPEAT):
        total += _sum_weight_attrs(
            nx.get_edge_attributes(_NX_GET_EDGE_ATTR_GRAPH, "weight")
        )
    return total


def fnx_digraph_get_edge_attributes_weight_4k() -> float:
    total = 0.0
    for _ in range(_GET_EDGE_ATTR_REPEAT):
        total += _sum_weight_attrs(
            fnx.get_edge_attributes(_FNX_GET_EDGE_ATTR_DIGRAPH, "weight")
        )
    return total


def networkx_digraph_get_edge_attributes_weight_4k() -> float:
    total = 0.0
    for _ in range(_GET_EDGE_ATTR_REPEAT):
        total += _sum_weight_attrs(
            nx.get_edge_attributes(_NX_GET_EDGE_ATTR_DIGRAPH, "weight")
        )
    return total


def _duplicate_attr_edges(node_count: int, unique_count: int, *, directed: bool):
    edges = []
    for idx in range(unique_count):
        u = idx % node_count
        v = (idx * 17 + 23) % node_count
        if u == v:
            v = (v + 1) % node_count
        weight = float((idx % 29) + 1)
        edges.append((u, v, {"weight": weight, "left": idx % 97}))
        if idx % 4 == 0:
            du, dv = (u, v) if directed else (v, u)
            edges.append((du, dv, {"weight": weight + 0.5, "right": idx % 89}))
        if idx % 16 == 0:
            edges.append((u, v, {"tail": idx % 193}))
    return edges


def _build_duplicate_attr_graph(module, *, directed: bool):
    graph = module.DiGraph() if directed else module.Graph()
    graph.add_edges_from(_DUP_DG_ATTR_EDGES if directed else _DUP_G_ATTR_EDGES)
    return graph


def _directed_attr_record(graph) -> tuple:
    return tuple(
        (u, v, tuple(data.items()))
        for u, v, data in graph.edges(data=True)
    )


def _undirected_attr_record(graph) -> tuple:
    return tuple(
        sorted(
            (min(u, v), max(u, v), tuple(data.items()))
            for u, v, data in graph.edges(data=True)
        )
    )


def _consume_duplicate_attr_graph(graph, *, directed: bool) -> float:
    total = graph.number_of_nodes() * 131 + graph.number_of_edges() * 17
    for u, v, data in graph.edges(data=True):
        total += int(u) * 31 + int(v) * 37 + len(data)
        total += int(data.get("left", 0))
        total += int(data.get("right", 0))
        total += int(data.get("tail", 0))
        total += int(float(data.get("weight", 0.0)) * 2.0)
        if not directed and u > v:
            total += 1
    return float(total)


_DUP_ATTR_NODE_COUNT = 4096
_DUP_ATTR_UNIQUE_COUNT = 8192
_DUP_ATTR_REPEAT = 12
_DUP_G_ATTR_EDGES = _duplicate_attr_edges(
    _DUP_ATTR_NODE_COUNT, _DUP_ATTR_UNIQUE_COUNT, directed=False
)
_DUP_DG_ATTR_EDGES = _duplicate_attr_edges(
    _DUP_ATTR_NODE_COUNT, _DUP_ATTR_UNIQUE_COUNT, directed=True
)

_FNX_DUP_G_ATTR_GRAPH = _build_duplicate_attr_graph(fnx, directed=False)
_NX_DUP_G_ATTR_GRAPH = _build_duplicate_attr_graph(nx, directed=False)
if _undirected_attr_record(_FNX_DUP_G_ATTR_GRAPH) != _undirected_attr_record(_NX_DUP_G_ATTR_GRAPH):
    raise AssertionError("Graph duplicate attributed add_edges_from parity drift")

_FNX_DUP_DG_ATTR_GRAPH = _build_duplicate_attr_graph(fnx, directed=True)
_NX_DUP_DG_ATTR_GRAPH = _build_duplicate_attr_graph(nx, directed=True)
if _directed_attr_record(_FNX_DUP_DG_ATTR_GRAPH) != _directed_attr_record(_NX_DUP_DG_ATTR_GRAPH):
    raise AssertionError("DiGraph duplicate attributed add_edges_from parity drift")


def fnx_graph_duplicate_attr_add_edges_from() -> float:
    total = 0.0
    for _ in range(_DUP_ATTR_REPEAT):
        total += _consume_duplicate_attr_graph(
            _build_duplicate_attr_graph(fnx, directed=False), directed=False
        )
    return total


def networkx_graph_duplicate_attr_add_edges_from() -> float:
    total = 0.0
    for _ in range(_DUP_ATTR_REPEAT):
        total += _consume_duplicate_attr_graph(
            _build_duplicate_attr_graph(nx, directed=False), directed=False
        )
    return total


def fnx_digraph_duplicate_attr_add_edges_from() -> float:
    total = 0.0
    for _ in range(_DUP_ATTR_REPEAT):
        total += _consume_duplicate_attr_graph(
            _build_duplicate_attr_graph(fnx, directed=True), directed=True
        )
    return total


def networkx_digraph_duplicate_attr_add_edges_from() -> float:
    total = 0.0
    for _ in range(_DUP_ATTR_REPEAT):
        total += _consume_duplicate_attr_graph(
            _build_duplicate_attr_graph(nx, directed=True), directed=True
        )
    return total


def _attr_digraph_edges(node_count: int, edge_count: int):
    idx = 0
    for step in range(1, node_count):
        for u in range(node_count):
            v = (u + step) % node_count
            for left, right in ((u, v), (v, u)):
                idx += 1
                yield (left, right, idx)
                if idx >= edge_count:
                    return


def _build_attr_digraph(module, node_count: int, edge_count: int):
    graph = module.DiGraph()
    for node in range(node_count):
        graph.add_node(
            node,
            color=f"c{node % 17}",
            size=node,
            group=node % 31,
        )
    for u, v, idx in _attr_digraph_edges(node_count, edge_count):
        graph.add_edge(
            u,
            v,
            weight=float((idx % 23) + 1),
            label=f"e{idx % 257}",
            bucket=idx % 13,
        )
    graph.graph["name"] = "to-undirected-attr-heavy"
    graph.graph["nodes"] = node_count
    graph.graph["edges"] = edge_count
    return graph


def _to_undirected_record(graph) -> tuple:
    undirected = graph.to_undirected()
    nodes = tuple(sorted((node, tuple(sorted(data.items()))) for node, data in undirected.nodes(data=True)))
    edges = tuple(
        sorted(
            (
                min(u, v),
                max(u, v),
                tuple(sorted(data.items())),
            )
            for u, v, data in undirected.edges(data=True)
        )
    )
    return nodes, edges, tuple(sorted(undirected.graph.items()))


def _records_match(left: tuple, right: tuple) -> bool:
    return left == right


def _consume_to_undirected(graph) -> float:
    undirected = graph.to_undirected()
    return float(
        undirected.number_of_nodes()
        + undirected.number_of_edges()
        + len(undirected.graph)
    )


_TO_UNDIRECTED_NODE_COUNT = 3000
_TO_UNDIRECTED_EDGE_COUNT = 12000
_TO_UNDIRECTED_REPEAT = 100
_FNX_TO_UNDIRECTED_GRAPH = _build_attr_digraph(
    fnx, _TO_UNDIRECTED_NODE_COUNT, _TO_UNDIRECTED_EDGE_COUNT
)
_NX_TO_UNDIRECTED_GRAPH = _build_attr_digraph(
    nx, _TO_UNDIRECTED_NODE_COUNT, _TO_UNDIRECTED_EDGE_COUNT
)

_ORACLE_TO_UNDIRECTED = _to_undirected_record(_NX_TO_UNDIRECTED_GRAPH)
_FNX_TO_UNDIRECTED = _to_undirected_record(_FNX_TO_UNDIRECTED_GRAPH)
if not _records_match(_FNX_TO_UNDIRECTED, _ORACLE_TO_UNDIRECTED):
    raise AssertionError("DiGraph.to_undirected attr-heavy parity drift")


def fnx_digraph_to_undirected_attr_heavy() -> float:
    total = 0.0
    for _ in range(_TO_UNDIRECTED_REPEAT):
        total += _consume_to_undirected(_FNX_TO_UNDIRECTED_GRAPH)
    return total


def networkx_digraph_to_undirected_attr_heavy() -> float:
    total = 0.0
    for _ in range(_TO_UNDIRECTED_REPEAT):
        total += _consume_to_undirected(_NX_TO_UNDIRECTED_GRAPH)
    return total


def _build_sparse_weighted_multidigraph(module, node_count: int):
    graph = module.MultiDiGraph()
    graph.add_nodes_from(range(node_count))
    steps = (1, 7, 37, 113)
    for u in range(node_count):
        for step_index, step in enumerate(steps):
            v = (u + step) % node_count
            for key in range(2):
                weight = ((u * 17 + step_index * 5 + key * 3) % 31) + 1
                graph.add_edge(u, v, key=key, weight=weight)
    return graph


def _consume_sparse_matrix(matrix) -> float:
    csr = matrix.tocsr()
    return float(
        csr.nnz
        + int(csr.data.sum())
        + int(csr.indices.sum() % 1_000_003)
        + int(csr.indptr[-1])
    )


_MDG_MATRIX_NODE_COUNT = 2000
_MDG_MATRIX_REPEAT = 24
_FNX_MDG_MATRIX_GRAPH = _build_sparse_weighted_multidigraph(
    fnx, _MDG_MATRIX_NODE_COUNT
)
_NX_MDG_MATRIX_GRAPH = _build_sparse_weighted_multidigraph(
    nx, _MDG_MATRIX_NODE_COUNT
)

# br-gauntletfix (cc): scipy is not installed on every rch worker, and these matrix
# builds run at MODULE TOP-LEVEL — an unguarded ModuleNotFoundError here killed the whole
# helper import and the entire gauntlet bench. Guard the scipy-only setup so the helper
# imports without scipy; the two scipy workloads then no-op (return 0.0) on a scipy-less
# host while every other algorithm-level workload still runs.
try:
    _FNX_MDG_MATRIX = fnx.to_scipy_sparse_array(_FNX_MDG_MATRIX_GRAPH)
    _NX_MDG_MATRIX = nx.to_scipy_sparse_array(_NX_MDG_MATRIX_GRAPH)
    if (
        _FNX_MDG_MATRIX.shape != _NX_MDG_MATRIX.shape
        or (_FNX_MDG_MATRIX != _NX_MDG_MATRIX).nnz != 0
    ):
        raise AssertionError("MultiDiGraph to_scipy_sparse_array CSR parity drift")
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False


def fnx_multidigraph_to_scipy_sparse_array_csr_int_weights() -> float:
    if not _SCIPY_AVAILABLE:
        return 0.0
    total = 0.0
    for _ in range(_MDG_MATRIX_REPEAT):
        total += _consume_sparse_matrix(
            fnx.to_scipy_sparse_array(_FNX_MDG_MATRIX_GRAPH)
        )
    return total


def networkx_multidigraph_to_scipy_sparse_array_csr_int_weights() -> float:
    if not _SCIPY_AVAILABLE:
        return 0.0
    total = 0.0
    for _ in range(_MDG_MATRIX_REPEAT):
        total += _consume_sparse_matrix(
            nx.to_scipy_sparse_array(_NX_MDG_MATRIX_GRAPH)
        )
    return total


def fnx_raw_preferential_attachment_repeated_overlap() -> float:
    total = 0.0
    for _ in range(_RAW_LINK_API_REPEATS):
        total += _consume_link_scores(
            fnx._fnx.preferential_attachment(_FNX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH)
        )
    return total


def networkx_preferential_attachment_repeated_overlap() -> float:
    total = 0.0
    for _ in range(_RAW_LINK_API_REPEATS):
        total += _consume_link_scores(
            nx.preferential_attachment(_NX_RAW_LINK_GRAPH, _RAW_LINK_EBUNCH)
        )
    return total
