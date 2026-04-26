"""Smoke test for the ~80 nx-parity wrappers shipped by OrangeHorse.

Each wrapper was committed as a thin Python delegate to networkx; this
suite verifies that they remain exported, on the module, and exercisable
with a tiny canonical input. It is intentionally a "does it crash" guard
rather than a deep correctness test (see the per-bead verify scripts for
the full numeric parity assertions).
"""

import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Symbol catalog: names must be in __all__ and on the module
# ---------------------------------------------------------------------------

ALL_NEW_SYMBOLS = [
    # TSP family (br-8vobd)
    "asadpour_atsp", "christofides", "greedy_tsp", "metric_closure",
    "simulated_annealing_tsp", "threshold_accepting_tsp",
    "traveling_salesman_problem",
    # approximation extension (br-d967f)
    "treewidth_min_degree", "treewidth_min_fill_in", "steiner_tree",
    "min_edge_dominating_set", "min_maximal_matching",
    "min_weighted_dominating_set", "one_exchange",
    "randomized_partitioning", "ramsey_R2", "densest_subgraph",
    # bipartite (br-5q77h)
    "eppstein_matching", "maximum_matching", "minimum_weight_full_matching",
    "to_vertex_cover", "cc_dot", "cc_max", "cc_min", "latapy_clustering",
    "robins_alexander_clustering", "degrees", "sets", "node_redundancy",
    # dag + structuralholes (br-rnxtc)
    "has_cycle", "colliders", "v_structures",
    "mutual_weight", "normalized_mutual_weight",
    # node_classification (br-ygr0e)
    "harmonic_function", "local_and_global_consistency",
    # utils (br-bj91d)
    "random_uniform_k_out_graph", "reverse_cuthill_mckee_ordering",
    "flow_matrix_row",
    # utils.rcm + utils.misc test helpers (br-wxjtp)
    "cuthill_mckee_ordering", "connected_cuthill_mckee_ordering",
    "pseudo_peripheral_node",
    "edges_equal", "graphs_equal", "nodes_equal", "make_list_of_ints",
    # utils.random_sequence (br-ntkdn)
    "powerlaw_sequence", "zipf_rv", "cumulative_distribution",
    "is_valid_tree_degree_sequence",
    # tree (br-wjv9o)
    "branching_weight", "minimal_branching",
    "boruvka_mst_edges", "kruskal_mst_edges", "prim_mst_edges",
    # classes.filters (br-uuo38)
    "hide_nodes", "hide_edges", "hide_diedges", "hide_multiedges",
    "hide_multidiedges", "show_nodes", "show_edges", "show_diedges",
    "show_multiedges", "show_multidiedges", "no_filter",
    # heaps + frozen (br-9yavb)
    "BinaryHeap", "MinHeap", "PairingHeap", "frozen",
    # coloring strategies + matching (br-75r94)
    "strategy_largest_first", "strategy_random_sequential",
    "strategy_smallest_last", "strategy_independent_set",
    "strategy_connected_sequential_bfs",
    "strategy_connected_sequential_dfs",
    "strategy_connected_sequential",
    "strategy_saturation_largest_first",
    "matching_dict_to_set",
]


@pytest.mark.parametrize("name", ALL_NEW_SYMBOLS)
def test_symbol_in_all(name):
    assert name in fnx.__all__, f"{name} not in fnx.__all__"


@pytest.mark.parametrize("name", ALL_NEW_SYMBOLS)
def test_symbol_on_module(name):
    assert hasattr(fnx, name), f"{name} not on fnx module"


# ---------------------------------------------------------------------------
# Crash-smoke: exercise each callable with a tiny canonical input
# ---------------------------------------------------------------------------


def _bipartite_graph():
    G = fnx.Graph()
    top = [0, 1, 2]
    bot = [3, 4]
    for u in top:
        for v in bot:
            G.add_edge(u, v)
    for n in top:
        G.nodes[n]["bipartite"] = 0
    for n in bot:
        G.nodes[n]["bipartite"] = 1
    return G, top


def _weighted_undirected_k4():
    G = fnx.complete_graph(4)
    for u, v in G.edges():
        G[u][v]["weight"] = abs(u - v) + 1
    return G


def _dag():
    G = fnx.DiGraph()
    G.add_edges_from([(0, 2), (1, 2), (2, 3)])
    return G


def test_tsp_family():
    G = _weighted_undirected_k4()
    assert fnx.greedy_tsp(G, weight="weight")
    assert fnx.christofides(G, weight="weight")
    assert fnx.traveling_salesman_problem(G, weight="weight")
    assert fnx.metric_closure(G).number_of_nodes() == 4


def test_approx_extension():
    G = _weighted_undirected_k4()
    assert fnx.treewidth_min_degree(G)[0] >= 1
    assert fnx.treewidth_min_fill_in(G)[0] >= 1
    assert fnx.steiner_tree(fnx.cycle_graph(6), [0, 2, 4]).number_of_edges() >= 1
    assert fnx.min_edge_dominating_set(fnx.path_graph(6))
    assert fnx.min_maximal_matching(fnx.path_graph(6))
    assert fnx.min_weighted_dominating_set(fnx.path_graph(6))
    val, _cut = fnx.randomized_partitioning(G, seed=42)
    assert val >= 0
    val, _cut = fnx.one_exchange(G, seed=42)
    assert val >= 0
    rs = fnx.ramsey_R2(fnx.cycle_graph(7))
    assert len(rs) == 2
    fnx.densest_subgraph(fnx.barabasi_albert_graph(20, 2, seed=42), iterations=1)


def test_bipartite_family():
    B, top = _bipartite_graph()
    assert fnx.eppstein_matching(B, top_nodes=top)
    assert fnx.maximum_matching(B, top_nodes=top)
    fnx.latapy_clustering(B, nodes=top)
    fnx.robins_alexander_clustering(B)
    fnx.node_redundancy(B, nodes=top)
    fnx.degrees(B, top)
    fnx.sets(B, top_nodes=top)
    assert fnx.cc_dot({1, 2}, {2, 3}) >= 0
    assert fnx.cc_max({1, 2}, {2, 3}) >= 0
    assert fnx.cc_min({1, 2}, {2, 3}) >= 0


def test_dag_and_structuralholes():
    DAG = _dag()
    assert fnx.has_cycle(DAG) is False
    cycle = fnx.DiGraph()
    cycle.add_edges_from([(0, 1), (1, 2), (2, 0)])
    assert fnx.has_cycle(cycle) is True
    list(fnx.colliders(DAG))
    list(fnx.v_structures(DAG))

    G = fnx.DiGraph()
    for u, v, w in [(0, 1, 2), (1, 0, 3)]:
        G.add_edge(u, v, weight=w)
    assert fnx.mutual_weight(G, 0, 1, weight="weight") == 5
    fnx.normalized_mutual_weight(G, 0, 1, weight="weight")


def test_node_classification():
    G = fnx.path_graph(5)
    G.nodes[0]["label"] = "A"
    G.nodes[4]["label"] = "B"
    labels = fnx.harmonic_function(G)
    assert labels[0] == "A" and labels[-1] == "B"
    labels = fnx.local_and_global_consistency(G)
    assert labels[0] == "A" and labels[-1] == "B"


def test_utils_and_helpers():
    G = fnx.path_graph(8)
    list(fnx.cuthill_mckee_ordering(G))
    list(fnx.connected_cuthill_mckee_ordering(G))
    list(fnx.reverse_cuthill_mckee_ordering(G))
    fnx.pseudo_peripheral_node(G)
    assert fnx.edges_equal([(0, 1)], [(0, 1)])
    assert fnx.nodes_equal([1, 2], [2, 1])
    assert fnx.graphs_equal(G, G)
    fnx.make_list_of_ints([1.0, 2.0])
    fnx.random_uniform_k_out_graph(8, 2, seed=42)
    list(fnx.flow_matrix_row(fnx.complete_graph(4)))


def test_random_sequence():
    fnx.powerlaw_sequence(20, exponent=2.5, seed=42)
    fnx.zipf_rv(2.0, xmin=1, seed=42)
    assert fnx.cumulative_distribution([0.5, 0.3, 0.2]) == [0.0, 0.5, 0.8, 1.0]
    fnx.is_valid_tree_degree_sequence([1, 1, 1, 3])


def test_tree_primitives():
    G = fnx.DiGraph()
    G.add_edge(0, 1, weight=5)
    G.add_edge(1, 2, weight=3)
    fnx.branching_weight(G)
    fnx.minimal_branching(G, attr="weight")
    K = _weighted_undirected_k4()
    list(fnx.boruvka_mst_edges(K))
    list(fnx.kruskal_mst_edges(K, minimum=True, keys=False))
    list(fnx.prim_mst_edges(K, minimum=True, keys=False))


def test_filter_factories():
    hide = fnx.hide_nodes([1])
    assert hide(0) is True and hide(1) is False
    show = fnx.show_nodes([1])
    assert show(1) is True and show(0) is False
    for name in (
        "hide_edges", "hide_diedges", "hide_multiedges", "hide_multidiedges",
        "show_edges", "show_diedges", "show_multiedges", "show_multidiedges",
    ):
        getattr(fnx, name)([])
    assert fnx.no_filter(1) is True


def test_heaps_and_frozen():
    h = fnx.BinaryHeap()
    h.insert("a", 1)
    h.insert("b", 0)
    assert h.min()[0] == "b"
    p = fnx.PairingHeap()
    p.insert("x", 10)
    assert p.min()[0] == "x"
    import networkx as nx
    with pytest.raises(nx.NetworkXError):
        fnx.frozen()


def test_coloring_strategies():
    import networkx as nx

    G = fnx.cycle_graph(6)
    G_nx = nx.cycle_graph(6)
    # Each strategy is a generator-returning callable; collect to list.
    # NOTE: strategy_saturation_largest_first hangs upstream when called with
    # empty colors={} (it expects greedy_color to drive it). Verified below
    # via greedy_color instead.
    list(fnx.strategy_largest_first(G, {}))
    list(fnx.strategy_random_sequential(G, {}, seed=42))
    list(fnx.strategy_smallest_last(G, {}))
    list(fnx.strategy_independent_set(G, {}))
    list(fnx.strategy_connected_sequential_bfs(G, {}))
    list(fnx.strategy_connected_sequential_dfs(G, {}))
    list(fnx.strategy_connected_sequential(G, {}, traversal="bfs"))
    # Callable strategy works with greedy_color (br-g915s fix); this also
    # exercises strategy_saturation_largest_first end-to-end.
    fnx.greedy_color(G, strategy=fnx.strategy_largest_first)
    fnx.greedy_color(G, strategy=fnx.strategy_saturation_largest_first)


def test_matching_dict_to_set():
    s = fnx.matching_dict_to_set({0: 1, 1: 0, 2: 3, 3: 2})
    assert s == {(0, 1), (2, 3)}
