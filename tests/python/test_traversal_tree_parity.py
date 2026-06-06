"""br-r37-c1-wvbzw: bfs_tree/dfs_tree result parity across variants.

The tree bindings no longer clone the source's RuntimePolicy decision
ledger (unbounded — one entry per recorded op), which made tree assembly
scale with the SOURCE's construction history (5.3x on identical
structures). Results must be byte-identical to nx for every variant and
independent of how the source graph was built.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _canon(g):
    return (
        [repr(n) for n in g.nodes()],
        [tuple(map(repr, e)) for e in g.edges()],
        {repr(n): [repr(x) for x in g.adj[n]] for n in g},
        {repr(n): [repr(x) for x in g.pred[n]] for n in g},
    )


def _edges(seed=3, n=120, m=480):
    rnd = random.Random(seed)
    edges = [(i, (i + 1) % n) for i in range(n)]
    edges += [(rnd.randrange(n), rnd.randrange(n)) for _ in range(m - n)]
    return [(u, v) for u, v in edges if u != v]


@pytest.mark.parametrize("fn", ["bfs_tree", "dfs_tree"])
@pytest.mark.parametrize("directed", [True, False])
@pytest.mark.parametrize("depth_limit", [None, 2, 5])
def test_tree_matches_networkx(fn, directed, depth_limit):
    e = _edges()
    gf = (fnx.DiGraph if directed else fnx.Graph)(e)
    gn = (nx.DiGraph if directed else nx.Graph)(e)
    tf = getattr(fnx, fn)(gf, 0, depth_limit=depth_limit)
    tn = getattr(nx, fn)(gn, 0, depth_limit=depth_limit)
    assert _canon(tf) == _canon(tn)


def test_bfs_tree_reverse_matches():
    e = _edges()
    assert _canon(fnx.bfs_tree(fnx.DiGraph(e), 0, reverse=True)) == _canon(
        nx.bfs_tree(nx.DiGraph(e), 0, reverse=True)
    )


def test_dfs_tree_forest_no_source():
    e = _edges()
    assert _canon(fnx.dfs_tree(fnx.DiGraph(e))) == _canon(nx.dfs_tree(nx.DiGraph(e)))


def test_tree_independent_of_source_build_path():
    # identical structure via two build paths (different ledger histories)
    g_native = fnx.grid_2d_graph(12, 12)
    g_ctor = fnx.Graph(list(g_native.edges()))
    assert _canon(fnx.bfs_tree(g_native, (0, 0))) == _canon(
        fnx.bfs_tree(g_ctor, (0, 0))
    )
    assert _canon(fnx.dfs_tree(g_native, (0, 0))) == _canon(
        fnx.dfs_tree(g_ctor, (0, 0))
    )


def test_tree_result_is_mutable_and_independent():
    e = _edges()
    gf = fnx.DiGraph(e)
    t = fnx.bfs_tree(gf, 0)
    t.add_edge("x", "y", w=1)
    t.nodes[0]["a"] = 1
    assert ("x", "y") in t.edges() and "x" not in gf
    assert t.nodes[0]["a"] == 1 and "a" not in gf.nodes[0]


def test_dfs_discovery_objects_match_nx_mixed_keys():
    # br-r37-c1-wvbzw lever 2: nx traversal yields DISCOVERY objects —
    # the source as passed, every other node as its parent's
    # adjacency-ROW object (z6uka overrides for mixed hash-equal keys).
    for cls in ("DiGraph", "Graph"):
        gf, gn = getattr(fnx, cls)(), getattr(nx, cls)()
        for h in (gf, gn):
            h.add_node(28)
            h.add_edge(7, 28.0)
            h.add_edge(28.0, 5)
            h.add_edge(5, 7)
        assert [(repr(u), repr(v)) for u, v in fnx.dfs_edges(gf, 7)] == [
            (repr(u), repr(v)) for u, v in nx.dfs_edges(gn, 7)
        ], cls
        tf, tn = fnx.dfs_tree(gf, 7), nx.dfs_tree(gn, 7)
        assert [repr(n) for n in tf] == [repr(n) for n in tn], cls
        assert _canon(fnx.dfs_tree(fnx.DiGraph([(7, 28.0)]))) == _canon(
            nx.dfs_tree(nx.DiGraph([(7, 28.0)]))
        )


class TestDiscoveryObjectFamily:
    """br-r37-c1-6hpa9: nx traversal results carry DISCOVERY objects —
    the source as passed, every discovered node as its parent's
    adjacency-row object (pred rows for reverse walks)."""

    def _mixed(self, mod, directed=True):
        g = (mod.DiGraph if directed else mod.Graph)()
        g.add_node(28)
        g.add_edge(7, 28.0)
        g.add_edge(28.0, 5)
        g.add_edge(5, 7)
        g.add_edge(5, 9)
        return g

    def _rr(self, x):
        if isinstance(x, tuple):
            return tuple(self._rr(i) for i in x)
        if isinstance(x, frozenset) or isinstance(x, set):
            return sorted(self._rr(i) for i in x)
        if isinstance(x, list):
            return [self._rr(i) for i in x]
        if isinstance(x, dict):
            return {self._rr(k): self._rr(v) for k, v in x.items()}
        if hasattr(x, "nodes"):
            return [repr(n) for n in x]
        return repr(x)

    @pytest.mark.parametrize("directed", [True, False])
    @pytest.mark.parametrize(
        "fn",
        [
            lambda m, g: list(m.bfs_edges(g, 7)),
            lambda m, g: list(m.bfs_tree(g, 7)),
            lambda m, g: list(m.dfs_edges(g, 7)),
            lambda m, g: list(m.dfs_tree(g, 7)),
            lambda m, g: list(m.dfs_preorder_nodes(g, 7)),
            lambda m, g: list(m.dfs_postorder_nodes(g, 7)),
            lambda m, g: dict(m.bfs_predecessors(g, 7)),
            lambda m, g: dict(m.bfs_successors(g, 7)),
            lambda m, g: m.ancestors(g, 9),
            lambda m, g: m.descendants(g, 7),
        ],
    )
    def test_discovery_objects_match_nx(self, fn, directed):
        assert self._rr(fn(fnx, self._mixed(fnx, directed))) == self._rr(
            fn(nx, self._mixed(nx, directed))
        )

    def test_reverse_bfs_uses_pred_row_objects(self):
        gf, gn = self._mixed(fnx), self._mixed(nx)
        assert self._rr(list(fnx.bfs_edges(gf, 9, reverse=True))) == self._rr(
            list(nx.bfs_edges(gn, 9, reverse=True))
        )
        assert self._rr(fnx.bfs_tree(gf, 9, reverse=True)) == self._rr(
            nx.bfs_tree(gn, 9, reverse=True)
        )

    def test_uniform_keys_unchanged(self):
        e = _edges(seed=9, n=60, m=200)
        gf, gn = fnx.DiGraph(e), nx.DiGraph(e)
        assert self._rr(list(fnx.bfs_edges(gf, 0))) == self._rr(list(nx.bfs_edges(gn, 0)))
        assert self._rr(dict(fnx.bfs_successors(gf, 0))) == self._rr(
            dict(nx.bfs_successors(gn, 0))
        )


class TestDiscoveryObjectsKernelEmitted:
    """br-r37-c1-6hpa9 batch 2: kernels emit (node, len, parent) so
    sssp_length and bfs_layers carry nx discovery objects with no
    second walk."""

    def _mixed(self, mod, directed=True):
        g = (mod.DiGraph if directed else mod.Graph)()
        g.add_node(28)
        g.add_edge(7, 28.0)
        g.add_edge(28.0, 5)
        g.add_edge(5, 9)
        return g

    @pytest.mark.parametrize("directed", [True, False])
    def test_sssp_length_keys(self, directed):
        gf, gn = self._mixed(fnx, directed), self._mixed(nx, directed)
        df = {repr(k): v for k, v in fnx.single_source_shortest_path_length(gf, 7).items()}
        dn = {repr(k): v for k, v in nx.single_source_shortest_path_length(gn, 7).items()}
        assert df == dn
        # key ORDER too (BFS discovery order)
        assert [repr(k) for k in fnx.single_source_shortest_path_length(gf, 7)] == [
            repr(k) for k in nx.single_source_shortest_path_length(gn, 7)
        ]

    @pytest.mark.parametrize("directed", [True, False])
    def test_sssp_length_cutoff(self, directed):
        gf, gn = self._mixed(fnx, directed), self._mixed(nx, directed)
        df = {repr(k): v for k, v in fnx.single_source_shortest_path_length(gf, 7, cutoff=1).items()}
        dn = {repr(k): v for k, v in nx.single_source_shortest_path_length(gn, 7, cutoff=1).items()}
        assert df == dn

    @pytest.mark.parametrize("directed", [True, False])
    def test_bfs_layers_single_and_multi(self, directed):
        gf, gn = self._mixed(fnx, directed), self._mixed(nx, directed)
        assert [[repr(n) for n in layer] for layer in fnx.bfs_layers(gf, 7)] == [
            [repr(n) for n in layer] for layer in nx.bfs_layers(gn, 7)
        ]
        assert [[repr(n) for n in layer] for layer in fnx.bfs_layers(gf, [7, 9])] == [
            [repr(n) for n in layer] for layer in nx.bfs_layers(gn, [7, 9])
        ]

    def test_source_object_passes_through(self):
        # nx returns the SOURCE exactly as passed
        gf, gn = self._mixed(fnx), self._mixed(nx)
        kf = next(iter(fnx.single_source_shortest_path_length(gf, 7)))
        kn = next(iter(nx.single_source_shortest_path_length(gn, 7)))
        assert repr(kf) == repr(kn) == "7"


class TestShortestPathDiscoveryObjects:
    """br-r37-c1-6hpa9 batch 3: unweighted path dicts carry discovery
    objects (derived from each path's second-to-last element) and keep
    the kernel's BFS key order (previously scrambled by a HashMap)."""

    def _mixed(self, mod, directed=True):
        g = (mod.DiGraph if directed else mod.Graph)()
        g.add_node(28)
        g.add_edge(7, 28.0)
        g.add_edge(28.0, 5)
        g.add_edge(5, 9)
        return g

    def _rr(self, x):
        if isinstance(x, (list, tuple)):
            return [self._rr(i) for i in x]
        if isinstance(x, dict):
            return {repr(k): self._rr(v) for k, v in x.items()}
        return repr(x)

    @pytest.mark.parametrize("directed", [True, False])
    def test_single_source_paths(self, directed):
        gf, gn = self._mixed(fnx, directed), self._mixed(nx, directed)
        assert self._rr(fnx.single_source_shortest_path(gf, 7)) == self._rr(
            nx.single_source_shortest_path(gn, 7)
        )
        assert self._rr(fnx.shortest_path(gf, 7)) == self._rr(nx.shortest_path(gn, 7))

    @pytest.mark.parametrize("directed", [True, False])
    def test_all_pairs_paths(self, directed):
        gf, gn = self._mixed(fnx, directed), self._mixed(nx, directed)
        assert self._rr(dict(fnx.all_pairs_shortest_path(gf))) == self._rr(
            dict(nx.all_pairs_shortest_path(gn))
        )
        assert self._rr(dict(fnx.shortest_path(gf))) == self._rr(dict(nx.shortest_path(gn)))

    def test_key_order_deterministic(self):
        # previously HashMap-scrambled: repeated calls must agree with nx ORDER
        import random

        rnd = random.Random(11)
        e = [(rnd.randrange(40), rnd.randrange(40)) for _ in range(160)]
        gf, gn = fnx.Graph(e), nx.Graph(e)
        for _ in range(3):
            assert [repr(k) for k in fnx.single_source_shortest_path(gf, e[0][0])] == [
                repr(k) for k in nx.single_source_shortest_path(gn, e[0][0])
            ]


class TestBidirectionalShortestPathParity:
    """br-r37-c1-k4wsy: nx routes single-pair unweighted shortest_path
    through BIDIRECTIONAL BFS. The old fnx kernel was unidirectional
    (different equal-length path on tie-breaks) and the directed route
    delegated over a conversion whose succ-major walk REORDERS pred rows
    (br-r37-c1-w7nn3) — poisoning nx's reverse-frontier tie-break."""

    @pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
    def test_diamond_tie_break(self, cls):
        gn, gf = getattr(nx, cls)(), getattr(fnx, cls)()
        for g in (gn, gf):
            g.add_edge("s", "a")
            g.add_edge("s", "b")
            g.add_edge("b", "t")
            g.add_edge("a", "t")
        assert fnx.shortest_path(gf, "s", "t") == nx.shortest_path(gn, "s", "t")
        assert fnx.bidirectional_shortest_path(gf, "s", "t") == nx.bidirectional_shortest_path(
            gn, "s", "t"
        )

    @pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
    def test_mixed_key_discovery_objects(self, cls):
        gn, gf = getattr(nx, cls)(), getattr(fnx, cls)()
        for g in (gn, gf):
            g.add_node(28)
            g.add_edge(7, 28.0)
            g.add_edge(28.0, 5)
            g.add_edge(5, 9)
        for s, t in [(7, 5), (7, 9)]:
            assert [repr(x) for x in fnx.shortest_path(gf, s, t)] == [
                repr(x) for x in nx.shortest_path(gn, s, t)
            ], (cls, s, t)

    def test_random_tie_rich_corpus(self):
        import random

        rnd = random.Random(13)
        for trial in range(20):
            directed = trial % 2 == 0
            gn = (nx.DiGraph if directed else nx.Graph)()
            gf = (fnx.DiGraph if directed else fnx.Graph)()
            for _ in range(45):
                u, v = rnd.randrange(14), rnd.randrange(14)
                if u != v:
                    gn.add_edge(u, v)
                    gf.add_edge(u, v)
            for s, t in [(0, 13), (1, 12)]:
                try:
                    expected = nx.shortest_path(gn, s, t)
                except Exception as e:
                    expected = type(e).__name__
                try:
                    got = fnx.shortest_path(gf, s, t)
                except Exception as e:
                    got = type(e).__name__
                assert got == expected, (trial, s, t)

    def test_no_path_and_self_target_errors(self):
        gn, gf = nx.DiGraph([(1, 2)]), fnx.DiGraph([(1, 2)])
        assert fnx.bidirectional_shortest_path(gf, 1, 1) == nx.bidirectional_shortest_path(
            gn, 1, 1
        )
        with pytest.raises(nx.NetworkXNoPath):
            nx.bidirectional_shortest_path(gn, 2, 1)
        with pytest.raises(fnx.NetworkXNoPath):
            fnx.bidirectional_shortest_path(gf, 2, 1)


class TestSingleTargetPathsParity:
    """br-r37-c1-k4wsy close-out: shortest_path(G, target=t) = nx's ONE
    reverse level-BFS (key order target-first in discovery order,
    reverse-tree tie-breaks, pred-row discovery objects) — replacing the
    O(V) per-node bidirectional loop."""

    def _rr(self, x):
        if isinstance(x, (list, tuple)):
            return [self._rr(i) for i in x]
        if isinstance(x, dict):
            return {repr(k): self._rr(v) for k, v in x.items()}
        return repr(x)

    @pytest.mark.parametrize("directed", [True, False])
    def test_mixed_keys_ties_isolates(self, directed):
        gf = (fnx.DiGraph if directed else fnx.Graph)()
        gn = (nx.DiGraph if directed else nx.Graph)()
        for g in (gf, gn):
            g.add_node(28)
            g.add_edge(7, 28.0)
            g.add_edge(28.0, 5)
            g.add_edge(5, 9)
            g.add_node("iso")
            g.add_edge("s", "a")
            g.add_edge("s", "b")
            g.add_edge("b", 5)
            g.add_edge("a", 5)
        assert self._rr(fnx.shortest_path(gf, target=5)) == self._rr(
            nx.shortest_path(gn, target=5)
        )

    def test_random_corpus_strict_key_order(self):
        import random

        rnd = random.Random(23)
        for trial in range(20):
            directed = trial % 2 == 0
            gf = (fnx.DiGraph if directed else fnx.Graph)()
            gn = (nx.DiGraph if directed else nx.Graph)()
            for _ in range(rnd.randrange(3, 60)):
                u, v = rnd.randrange(13), rnd.randrange(13)
                if u != v:
                    gf.add_edge(u, v)
                    gn.add_edge(u, v)
            t = rnd.randrange(13)
            if t not in gn:
                continue
            assert self._rr(fnx.shortest_path(gf, target=t)) == self._rr(
                nx.shortest_path(gn, target=t)
            ), trial


class TestWeightedShortestPathParity:
    """Weighted sp batch: the weighted shortest_path dict family carries
    discovery objects + kernel dict order (dijkstra finalize / bellman
    SPFA discovery); target-only = nx's reverse-view single-source with
    flipped paths (ONE walk, pred-row objects); the old wrapper
    distance-re-sort (62jy2) actively broke bellman-ford order."""

    def _mixed(self, mod, directed=True):
        import random

        g = (mod.DiGraph if directed else mod.Graph)()
        g.add_node(28)
        g.add_edge(7, 28.0, weight=1)
        g.add_edge(28.0, 5, weight=1)
        g.add_edge(5, 9, weight=2)
        g.add_edge(7, 5, weight=2)
        rnd = random.Random(3)
        for _ in range(25):
            u, v = rnd.randrange(10), rnd.randrange(10)
            if u != v:
                g.add_edge(u, v, weight=1 + (u * v) % 3)
        g.add_edge(9, 7, weight=1)
        return g

    def _rr(self, x, d=0):
        if d > 5:
            return repr(x)
        if isinstance(x, (list, tuple)):
            return [self._rr(i, d + 1) for i in x]
        if isinstance(x, dict):
            return {repr(k): self._rr(v, d + 1) for k, v in x.items()}
        return repr(x)

    @pytest.mark.parametrize("directed", [True, False])
    @pytest.mark.parametrize("method", ["dijkstra", "bellman-ford"])
    def test_source_given_and_target_only(self, directed, method):
        gf, gn = self._mixed(fnx, directed), self._mixed(nx, directed)
        assert self._rr(fnx.shortest_path(gf, 7, weight="weight", method=method)) == self._rr(
            nx.shortest_path(gn, 7, weight="weight", method=method)
        )
        assert self._rr(
            fnx.shortest_path(gf, target=9, weight="weight", method=method)
        ) == self._rr(nx.shortest_path(gn, target=9, weight="weight", method=method))

    @pytest.mark.parametrize("directed", [True, False])
    def test_all_pairs_and_standalone(self, directed):
        gf, gn = self._mixed(fnx, directed), self._mixed(nx, directed)
        assert self._rr(dict(fnx.shortest_path(gf, weight="weight"))) == self._rr(
            dict(nx.shortest_path(gn, weight="weight"))
        )
        assert self._rr(fnx.single_source_dijkstra_path(gf, 7)) == self._rr(
            nx.single_source_dijkstra_path(gn, 7)
        )
        assert self._rr(dict(fnx.single_source_dijkstra_path_length(gf, 7))) == self._rr(
            dict(nx.single_source_dijkstra_path_length(gn, 7))
        )
        assert self._rr(dict(fnx.all_pairs_dijkstra_path(gf))) == self._rr(
            dict(nx.all_pairs_dijkstra_path(gn))
        )


class TestBellmanFordStandaloneParity:
    """Weighted sp batch 2: bellman-ford single-source trio carries
    discovery objects (SPFA relaxation parent's row object) and int
    distances for all-int weights."""

    def _mixed(self, mod, directed=True):
        import random

        g = (mod.DiGraph if directed else mod.Graph)()
        g.add_node(28)
        g.add_edge(7, 28.0, weight=1)
        g.add_edge(28.0, 5, weight=1)
        g.add_edge(5, 9, weight=2)
        g.add_edge(7, 5, weight=2)
        rnd = random.Random(3)
        for _ in range(25):
            u, v = rnd.randrange(10), rnd.randrange(10)
            if u != v:
                g.add_edge(u, v, weight=1 + (u * v) % 3)
        g.add_edge(9, 7, weight=1)
        return g

    def _rr(self, x, d=0):
        if d > 5:
            return repr(x)
        if isinstance(x, (list, tuple)):
            return [self._rr(i, d + 1) for i in x]
        if isinstance(x, dict):
            return {repr(k): self._rr(v, d + 1) for k, v in x.items()}
        return repr(x)

    @pytest.mark.parametrize("directed", [True, False])
    def test_single_source_trio(self, directed):
        gf, gn = self._mixed(fnx, directed), self._mixed(nx, directed)
        assert self._rr(fnx.single_source_bellman_ford(gf, 7)) == self._rr(
            nx.single_source_bellman_ford(gn, 7)
        )
        assert self._rr(fnx.single_source_bellman_ford_path(gf, 7)) == self._rr(
            nx.single_source_bellman_ford_path(gn, 7)
        )
        assert self._rr(dict(fnx.single_source_bellman_ford_path_length(gf, 7))) == self._rr(
            dict(nx.single_source_bellman_ford_path_length(gn, 7))
        )

    def test_int_distance_types(self):
        gf, gn = fnx.DiGraph([(1, 2, {"weight": 2})]), nx.DiGraph([(1, 2, {"weight": 2})])
        df = fnx.single_source_bellman_ford(gf, 1)[0]
        dn = nx.single_source_bellman_ford(gn, 1)[0]
        assert {k: (type(v), v) for k, v in df.items()} == {
            k: (type(v), v) for k, v in dn.items()
        }


class TestAllPairsWeightedDiscoveryObjects:
    """br-r37-c1-7hsew: the four all_pairs_* weighted bindings + the
    packed fast path + multi_source_dijkstra carry discovery objects;
    multi-source seeds display AS PASSED in the caller's set order."""

    def _mixed(self, mod, directed=True):
        import random

        g = (mod.DiGraph if directed else mod.Graph)()
        g.add_node(28)
        g.add_edge(7, 28.0, weight=1)
        g.add_edge(28.0, 5, weight=1)
        g.add_edge(5, 9, weight=2)
        g.add_edge(7, 5, weight=2)
        rnd = random.Random(3)
        for _ in range(25):
            u, v = rnd.randrange(10), rnd.randrange(10)
            if u != v:
                g.add_edge(u, v, weight=1 + (u * v) % 3)
        g.add_edge(9, 7, weight=1)
        return g

    def _rr(self, x, d=0):
        if d > 5:
            return repr(x)
        if isinstance(x, (list, tuple)):
            return [self._rr(i, d + 1) for i in x]
        if isinstance(x, dict):
            return {repr(k): self._rr(v, d + 1) for k, v in x.items()}
        return repr(x)

    @pytest.mark.parametrize("directed", [True, False])
    def test_all_pairs_family(self, directed):
        gf, gn = self._mixed(fnx, directed), self._mixed(nx, directed)
        assert self._rr(dict(fnx.all_pairs_bellman_ford_path(gf))) == self._rr(
            dict(nx.all_pairs_bellman_ford_path(gn))
        )
        assert self._rr(
            {k: dict(v) for k, v in fnx.all_pairs_bellman_ford_path_length(gf)}
        ) == self._rr({k: dict(v) for k, v in nx.all_pairs_bellman_ford_path_length(gn)})
        assert self._rr(
            {k: (dict(v[0]), v[1]) for k, v in fnx.all_pairs_dijkstra(gf)}
        ) == self._rr({k: (dict(v[0]), v[1]) for k, v in nx.all_pairs_dijkstra(gn)})
        assert self._rr(
            {k: dict(v) for k, v in fnx.all_pairs_dijkstra_path_length(gf)}
        ) == self._rr({k: dict(v) for k, v in nx.all_pairs_dijkstra_path_length(gn)})

    @pytest.mark.parametrize("directed", [True, False])
    @pytest.mark.parametrize("seeds", [{7, 9}, [9, 7], [7]], ids=["set", "list", "single"])
    def test_multi_source_seed_order_and_objects(self, directed, seeds):
        gf, gn = self._mixed(fnx, directed), self._mixed(nx, directed)
        assert self._rr(fnx.multi_source_dijkstra(gf, seeds)) == self._rr(
            nx.multi_source_dijkstra(gn, seeds)
        )
