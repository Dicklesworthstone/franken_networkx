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
