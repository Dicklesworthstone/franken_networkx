"""Parity tests for all_shortest_paths method parameter (bead 8kb)."""
import pytest
import franken_networkx as fnx
import networkx as nx


def _assert_same_result_or_exception(fnx_call, nx_call):
    try:
        nx_result = nx_call()
    except Exception as nx_exc:
        with pytest.raises(Exception) as fnx_exc_info:
            fnx_call()
        fnx_exc = fnx_exc_info.value
        assert type(fnx_exc).__name__ == type(nx_exc).__name__
        assert str(fnx_exc) == str(nx_exc)
        return

    fnx_result = fnx_call()
    assert fnx_result == nx_result


@pytest.fixture
def weighted_graph():
    G = fnx.Graph()
    G.add_edge(0, 1, weight=1)
    G.add_edge(1, 2, weight=1)
    G.add_edge(0, 2, weight=3)
    return G


@pytest.fixture
def nx_weighted_graph():
    G = nx.Graph()
    G.add_edge(0, 1, weight=1)
    G.add_edge(1, 2, weight=1)
    G.add_edge(0, 2, weight=3)
    return G


class TestAllShortestPathsMethod:
    def test_default_unweighted(self, weighted_graph, nx_weighted_graph):
        """Default (no weight) uses BFS — should find direct edge 0→2."""
        paths = list(fnx.all_shortest_paths(weighted_graph, 0, 2))
        npaths = list(nx.all_shortest_paths(nx_weighted_graph, 0, 2))
        assert paths == npaths

    def test_dijkstra_weighted(self, weighted_graph, nx_weighted_graph):
        """With weight='weight', Dijkstra finds 0→1→2 (cost 2) over 0→2 (cost 3)."""
        paths = list(fnx.all_shortest_paths(weighted_graph, 0, 2, weight="weight"))
        npaths = list(nx.all_shortest_paths(nx_weighted_graph, 0, 2, weight="weight"))
        assert paths == npaths
        assert paths == [[0, 1, 2]]

    def test_explicit_dijkstra(self, weighted_graph):
        """method='dijkstra' should behave same as default weighted."""
        paths = list(
            fnx.all_shortest_paths(
                weighted_graph, 0, 2, weight="weight", method="dijkstra"
            )
        )
        assert paths == [[0, 1, 2]]

    def test_bellman_ford_undirected_matches_nx(
        self, weighted_graph, nx_weighted_graph
    ):
        """method='bellman-ford' on an undirected graph is supported by
        upstream nx (bellman-ford handles negative weights; undirected is
        fine when there are no negative cycles). fnx matches — verify
        both sides agree rather than asserting a spurious raise.
        """
        fnx_paths = list(
            fnx.all_shortest_paths(
                weighted_graph, 0, 2, weight="weight", method="bellman-ford"
            )
        )
        nx_paths = list(
            nx.all_shortest_paths(
                nx_weighted_graph, 0, 2, weight="weight", method="bellman-ford"
            )
        )
        assert fnx_paths == nx_paths

    def test_unweighted_method_explicit(self, weighted_graph, nx_weighted_graph):
        """method='unweighted' ignores edge weights."""
        paths = list(fnx.all_shortest_paths(weighted_graph, 0, 2, method="unweighted"))
        npaths = list(nx.all_shortest_paths(nx_weighted_graph, 0, 2))
        assert paths == npaths

    def test_multiple_shortest_paths(self):
        """Graph with multiple shortest paths returns all of them."""
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3)])
        nG = nx.Graph(G.edges())
        paths = sorted(fnx.all_shortest_paths(G, 0, 3))
        npaths = sorted(nx.all_shortest_paths(nG, 0, 3))
        assert paths == npaths
        assert len(paths) == 2

    def test_no_path_raises(self):
        """Missing path raises NetworkXNoPath."""
        G = fnx.Graph()
        G.add_nodes_from([0, 1])
        with pytest.raises(fnx.NetworkXNoPath):
            list(fnx.all_shortest_paths(G, 0, 1))

    def test_negative_weight_dijkstra_matches_networkx(self):
        G_fnx = fnx.Graph()
        G_nx = nx.Graph()
        for graph in (G_fnx, G_nx):
            graph.add_edge("a", "b", weight=2.0)
            graph.add_edge("b", "c", weight=-5.0)
            graph.add_edge("a", "c", weight=1.0)

        for kwargs in ({"weight": "weight"}, {"weight": "weight", "method": "dijkstra"}):
            _assert_same_result_or_exception(
                lambda kwargs=kwargs: list(
                    fnx.all_shortest_paths(G_fnx, "a", "c", **kwargs)
                ),
                lambda kwargs=kwargs: list(
                    nx.all_shortest_paths(G_nx, "a", "c", **kwargs)
                ),
            )

    def test_negative_weight_directed_dijkstra_matches_networkx(self):
        D_fnx = fnx.DiGraph()
        D_nx = nx.DiGraph()
        for graph in (D_fnx, D_nx):
            graph.add_edge("a", "b", weight=2.0)
            graph.add_edge("b", "c", weight=-5.0)
            graph.add_edge("a", "c", weight=1.0)

        for kwargs in ({"weight": "weight"}, {"weight": "weight", "method": "dijkstra"}):
            _assert_same_result_or_exception(
                lambda kwargs=kwargs: list(
                    fnx.all_shortest_paths(D_fnx, "a", "c", **kwargs)
                ),
                lambda kwargs=kwargs: list(
                    nx.all_shortest_paths(D_nx, "a", "c", **kwargs)
                ),
            )


def test_weighted_diamond_preserves_path_emission_order_matching_networkx():
    """Bead franken_networkx-q6qc: on a weighted diamond with equal-cost
    routes from a to e, the path list must appear in the same order as
    upstream NetworkX — not just contain the same paths.
    """
    edges = [
        ("a", "b", 1),
        ("a", "c", 1),
        ("b", "d", 1),
        ("c", "d", 1),
        ("d", "e", 1),
        ("b", "e", 2),
    ]
    fg = fnx.Graph()
    ng = nx.Graph()
    for u, v, w in edges:
        fg.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)

    fnx_paths = list(fnx.all_shortest_paths(fg, "a", "e", weight="weight"))
    nx_paths = list(nx.all_shortest_paths(ng, "a", "e", weight="weight"))
    assert fnx_paths == nx_paths, (
        f"all_shortest_paths order diverged: fnx={fnx_paths} nx={nx_paths}"
    )

    # method="dijkstra" path on the same fixture.
    fnx_paths_dj = list(
        fnx.all_shortest_paths(fg, "a", "e", weight="weight", method="dijkstra")
    )
    nx_paths_dj = list(
        nx.all_shortest_paths(ng, "a", "e", weight="weight", method="dijkstra")
    )
    assert fnx_paths_dj == nx_paths_dj


def test_directed_weighted_dijkstra_uses_rust_path_without_networkx_fallback(monkeypatch):
    edges = [
        ("a", "b", 1),
        ("a", "c", 1),
        ("b", "e", 2),
        ("b", "d", 1),
        ("c", "d", 1),
        ("d", "e", 1),
        ("a", "e", 3),
    ]
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for u, v, w in edges:
        fg.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)

    expected = list(nx.all_shortest_paths(ng, "a", "e", weight="weight"))
    monkeypatch.setattr(
        nx,
        "all_shortest_paths",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("NetworkX all_shortest_paths fallback used")
        ),
    )

    assert list(fnx.all_shortest_paths(fg, "a", "e", weight="weight")) == expected


# br-r37-c1-b5rqk: networkx weighs a multigraph hop by its LIGHTEST parallel
# edge (min over the keydict). The native kernel ran on a projection that kept
# the first edge, so a lighter edge added later was invisible: a tie through it
# was lost, or a path that is not shortest came back beside the shortest one.
_RING = [(i, (i + 1) % 24, {"weight": float(i % 5) + 1.5}) for i in range(24)]
_CHORDS = [(i, (i + 7) % 24, {"weight": float(i % 3) + 2.25}) for i in range(0, 24, 2)]
_PARALLEL_BUNCHES = {
    "lighter_later": [
        (0, 1, {"weight": 3.0}), (0, 1, {"weight": 1.0}), (1, 3, {"weight": 1.0}),
        (0, 2, {"weight": 1.0}), (2, 3, {"weight": 1.0}),
    ],
    "heavier_later": [
        (0, 1, {"weight": 1.0}), (0, 1, {"weight": 3.0}), (1, 3, {"weight": 1.0}),
        (0, 2, {"weight": 1.0}), (2, 3, {"weight": 1.0}),
    ],
    "unweighted_later": [
        (0, 1, {"weight": 5}), (0, 1, {}), (1, 3, {"weight": 1}),
        (0, 2, {"weight": 1}), (2, 3, {"weight": 1}),
    ],
    "ring": _RING + _CHORDS + [
        (0, 1, {"weight": 4.0}), (2, 3, {"weight": 0.25}), (1, 0, {"weight": 0.5}),
    ],
}


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("method", ["dijkstra", "bellman-ford"])
@pytest.mark.parametrize("bunch", sorted(_PARALLEL_BUNCHES))
def test_multigraph_hop_weighs_its_lightest_parallel_edge_like_networkx(cls, method, bunch):
    edges = _PARALLEL_BUNCHES[bunch]
    target = 12 if bunch == "ring" else 3
    G = getattr(fnx, cls)()
    G.add_edges_from(edges)
    H = getattr(nx, cls)()
    H.add_edges_from(edges)

    expected = list(nx.all_shortest_paths(H, 0, target, weight="weight", method=method))
    got = list(fnx.all_shortest_paths(G, 0, target, weight="weight", method=method))

    assert got == expected


# br-r37-c1-q6rrt: a MultiDiGraph's Dijkstra arm walks the cached min-parallel-
# weight rows instead of a per-call projection. Ties (many equal paths), zero
# weights (networkx appends predecessors to a node already final), int weights,
# str nodes and shuffled insertion order all decide the path ORDER; and the rows
# are a cache, so a graph mutated between calls must be answered afresh.
def _random_multidigraph_edges(seed):
    import random

    rng = random.Random(seed)
    n = rng.randint(4, 12)
    label = (lambda i: f"n{i}") if seed % 2 else (lambda i: i)
    order = list(range(n))
    rng.shuffle(order)
    edges = []
    for _ in range(rng.randint(n, 4 * n)):
        u, v = rng.randrange(n), rng.randrange(n)
        if u != v:
            edges.append((label(u), label(v), {"weight": rng.choice([0, 1, 1, 2, 2.0, 0.5, 3])}))
    return [label(i) for i in order], edges, label


@pytest.mark.parametrize("seed", range(60))
def test_multidigraph_dijkstra_paths_and_order_match_networkx(seed):
    nodes, edges, label = _random_multidigraph_edges(seed)
    G, H = fnx.MultiDiGraph(), nx.MultiDiGraph()
    for g in (G, H):
        g.add_nodes_from(nodes)
        g.add_edges_from(edges)
    for source, target in [(nodes[0], nodes[-1]), (nodes[1], nodes[2]), (label(0), label(1))]:
        try:
            expected = list(nx.all_shortest_paths(H, source, target, weight="weight"))
        except nx.NetworkXNoPath:
            with pytest.raises(nx.NetworkXNoPath):
                list(fnx.all_shortest_paths(G, source, target, weight="weight"))
            continue
        assert list(fnx.all_shortest_paths(G, source, target, weight="weight")) == expected


@pytest.mark.parametrize("mutation", ["lighter_parallel_edge", "edge_dict_weight", "remove_edge"])
def test_multidigraph_paths_follow_a_mutation_between_calls(mutation):
    edges = [(0, 1, 1.0), (1, 3, 1.0), (0, 2, 1.0), (2, 3, 2.0), (0, 3, 5.0)]
    G, H = fnx.MultiDiGraph(), nx.MultiDiGraph()
    for g in (G, H):
        g.add_weighted_edges_from(edges)
    assert list(fnx.all_shortest_paths(G, 0, 3, weight="weight")) == [[0, 1, 3]]
    for g in (G, H):
        if mutation == "lighter_parallel_edge":
            g.add_edge(2, 3, weight=1.0)
        elif mutation == "edge_dict_weight":
            g[2][3][0]["weight"] = 1.0
        else:
            g.remove_edge(1, 3)
    assert list(fnx.all_shortest_paths(G, 0, 3, weight="weight")) == list(
        nx.all_shortest_paths(H, 0, 3, weight="weight")
    )
