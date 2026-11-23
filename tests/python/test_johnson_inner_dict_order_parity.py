"""Parity for ``johnson`` all-pairs shortest path inner-dict order.

Bead br-r37-c1-9l73c. The local
``dict(all_pairs_bellman_ford_path(G))`` short-circuit produced
inner-dict keys in Bellman-Ford-tree-discovery order, but nx's
johnson algorithm runs per-node Dijkstra after reweighting and
emits inner-dict keys in Dijkstra's discovery order (which differs
from BF's).

Drop-in code that iterated the inner dicts of johnson() in order
(e.g. for plotting paths or computing per-target metrics) silently
broke.

Repro: edges = [('a','b',1),('b','c',2),('c','d',1),('a','d',5),('b','d',3)]
  fnx['a'].keys() -> ['a','b','d','c']
  nx ['a'].keys() -> ['a','b','c','d']
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _make_weighted(lib, edges, directed=False):
    g = (lib.DiGraph if directed else lib.Graph)()
    for u, v, w in edges:
        g.add_edge(u, v, weight=w)
    return g


@needs_nx
def test_undirected_repro_inner_dict_keys_match_nx():
    edges = [("a", "b", 1), ("b", "c", 2), ("c", "d", 1), ("a", "d", 5), ("b", "d", 3)]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)
    f = fnx.johnson(g)
    n = nx.johnson(gx)
    assert list(f.keys()) == list(n.keys())
    for k in n:
        assert list(f[k].keys()) == list(n[k].keys()), (
            f"inner[{k}]: fnx={list(f[k].keys())} nx={list(n[k].keys())}"
        )


@needs_nx
def test_int_node_inner_dict_keys_match_nx():
    edges = [(0, 1, 1), (1, 2, 2), (2, 3, 3), (0, 3, 1)]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)
    f = fnx.johnson(g)
    n = nx.johnson(gx)
    assert list(f.keys()) == list(n.keys())
    for k in n:
        assert list(f[k].keys()) == list(n[k].keys())


@needs_nx
def test_directed_inner_dict_keys_match_nx():
    edges = [("a", "b", 1), ("b", "c", 2), ("a", "c", 4), ("c", "d", 1)]
    dg = _make_weighted(fnx, edges, directed=True)
    dgx = _make_weighted(nx, edges, directed=True)
    f = fnx.johnson(dg)
    n = nx.johnson(dgx)
    assert list(f.keys()) == list(n.keys())
    for k in n:
        assert list(f[k].keys()) == list(n[k].keys())


@needs_nx
def test_paths_themselves_match_nx():
    """Path values (the lists from u to v) must also match nx — not
    just the dict iteration order."""
    edges = [("a", "b", 1), ("b", "c", 2), ("c", "d", 1), ("a", "d", 5), ("b", "d", 3)]
    g = _make_weighted(fnx, edges)
    gx = _make_weighted(nx, edges)
    assert fnx.johnson(g) == nx.johnson(gx)


@needs_nx
def test_negative_weights_supported():
    """Johnson's main differentiator from Dijkstra is negative
    edges. Verify it works and matches nx."""
    dg = fnx.DiGraph()
    dgx = nx.DiGraph()
    for u, v, w in [("a", "b", 1), ("b", "c", -2), ("a", "c", 4), ("c", "d", 3)]:
        dg.add_edge(u, v, weight=w)
        dgx.add_edge(u, v, weight=w)
    f = fnx.johnson(dg)
    n = nx.johnson(dgx)
    assert f == n
    for k in n:
        assert list(f[k].keys()) == list(n[k].keys())


@needs_nx
def test_default_weight_attr_matches_nx():
    g = fnx.path_graph(4)
    gx = nx.path_graph(4)
    f = fnx.johnson(g)
    n = nx.johnson(gx)
    assert list(f.keys()) == list(n.keys())
    for k in n:
        assert list(f[k].keys()) == list(n[k].keys())


@needs_nx
def test_custom_weight_attr_matches_nx():
    edges = [("a", "b", 1), ("b", "c", 2), ("c", "d", 1)]
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v, w in edges:
        g.add_edge(u, v, custom=w)
        gx.add_edge(u, v, custom=w)
    f = fnx.johnson(g, weight="custom")
    n = nx.johnson(gx, weight="custom")
    assert f == n


@needs_nx
def test_callable_weight_matches_nx():
    edges = [("a", "b", 1), ("b", "c", 2), ("c", "d", 1)]
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v, w in edges:
        g.add_edge(u, v, weight=w)
        gx.add_edge(u, v, weight=w)
    weight_fn = lambda u, v, d: d.get("weight", 1) * 2
    f = fnx.johnson(g, weight=weight_fn)
    n = nx.johnson(gx, weight=weight_fn)
    assert f == n


@needs_nx
def test_empty_graph_matches_nx():
    g = fnx.Graph()
    gx = nx.Graph()
    assert fnx.johnson(g) == nx.johnson(gx) == {}


def _wide_potential_graph(lib, weight, storage, magnitude=2**53):
    graph = lib.DiGraph()
    graph.add_edges_from([
        ("anchor", "x", {weight: -magnitude}),
        ("s", "x", {weight: 0}),
        ("x", "a", {}),
        ("a", "t", {}),
        ("x", "b", {weight: 0}),
        ("b", "t", {}),
    ])
    if storage == "mirrored":
        list(graph.edges(data=True))
    elif storage == "mixed":
        graph.get_edge_data("a", "t")
    return graph


@needs_nx
@pytest.mark.parametrize("weight", ["weight", "cost"])
@pytest.mark.parametrize("storage", ["lazy", "mirrored", "mixed"])
def test_wide_negative_potential_and_implicit_units_preserve_optimal_path(weight, storage):
    """Reweighting must not erase the unit improvement through x -> b -> t.

    The explicit magnitudes alone fit 2**53. Ignoring three default unit
    weights admitted f64 reweighting and returned s -> x -> a -> t, cost 2,
    instead of the uniquely optimal path, cost 1.
    """
    graph = _wide_potential_graph(fnx, weight, storage)
    oracle = _wide_potential_graph(nx, weight, storage)
    expected = nx.johnson(oracle, weight=weight)
    assert expected["s"]["t"] == ["s", "x", "b", "t"]
    for _ in range(2):
        actual = fnx.johnson(graph, weight=weight)
        assert actual == expected
        assert list(actual) == list(expected)
        for source in expected:
            assert list(actual[source]) == list(expected[source])


@needs_nx
def test_backend_johnson_retains_exact_reweighting():
    graph = _wide_potential_graph(nx, "cost", "lazy")
    expected = nx.johnson(graph, weight="cost", backend="networkx")
    for _ in range(2):
        assert nx.johnson(graph, weight="cost", backend="franken_networkx") == expected


@needs_nx
def test_safe_negative_integer_potentials_keep_native_johnson(monkeypatch):
    graph = _wide_potential_graph(fnx, "cost", "lazy", magnitude=7)
    oracle = _wide_potential_graph(nx, "cost", "lazy", magnitude=7)
    original = fnx._raw_johnson_path_directed
    calls = []

    def recorded(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(fnx, "_raw_johnson_path_directed", recorded)
    assert fnx.johnson(graph, weight="cost") == nx.johnson(oracle, weight="cost")
    assert calls == [graph]


@needs_nx
@pytest.mark.parametrize("prewarmed", [False, True])
@pytest.mark.parametrize("positional", [False, True])
def test_backend_johnson_callable_retains_live_edge_identity(prewarmed, positional):
    def make_graph():
        graph = nx.DiGraph()
        graph.add_weighted_edges_from([("a", "b", 4), ("a", "t", 7), ("b", "t", 9)])
        return graph

    def callback_for(graph):
        def weight(source, target, attrs):
            assert attrs is graph[source][target]
            if (source, target) == ("a", "b"):
                graph["b"]["t"]["weight"] = 1
                attrs["visited"] = True
            return attrs["weight"]

        return weight

    graph = make_graph()
    oracle = make_graph()
    if prewarmed:
        assert nx.shortest_path_length(
            graph, "a", "t", weight="weight", backend="franken_networkx"
        ) == 7
    expected = nx.johnson(oracle, callback_for(oracle), backend="networkx")
    callback = callback_for(graph)
    if positional:
        actual = nx.johnson(graph, callback, backend="franken_networkx")
    else:
        actual = nx.johnson(graph, weight=callback, backend="franken_networkx")
    assert actual == expected
    assert actual["a"]["t"] == ["a", "b", "t"]
    assert list(actual) == list(expected)
    for source in expected:
        assert list(actual[source]) == list(expected[source])
    assert graph["a"]["b"]["visited"] is True
    assert graph["b"]["t"]["weight"] == 1
    # A prewarmed conversion must not survive a callback's dictionary writes.
    assert nx.shortest_path_length(
        graph, "a", "t", weight="weight", backend="franken_networkx"
    ) == 5


def _johnson_with_attribute_readers(module, graph_type, scenario, route, monkeypatch=None):
    """Expose weights through the public mapping rather than stored scalars."""
    graph = getattr(module, graph_type)()
    reads = []
    changed = False

    class EdgeAttributes(dict):
        def get(self, key, default=None):
            nonlocal changed
            if key != "weight":
                return dict.get(self, key, default)
            edge = dict.get(self, "edge")
            reads.append(edge)
            if scenario == "mutating" and edge == ("s", "a") and not changed:
                changed = True
                later = graph["a"]["b"]
                if graph.is_multigraph():
                    later = later[0]
                later["effective_weight"] = -5
            return dict.get(self, "effective_weight", default)

    if module is nx:
        graph.edge_attr_dict_factory = EdgeAttributes
    edges = [("s", "a", 4), ("s", "b", 1), ("a", "b", 3), ("b", "t", 2)]
    if scenario == "negative-cycle" and graph.is_directed():
        edges.append(("b", "a", 4))
    for source, target, stored_weight in edges:
        effective_weight = (
            -5 if (source, target) == ("a", "b")
            and scenario in ("negative", "negative-cycle")
            else stored_weight
        )
        graph.add_edge(
            source, target, weight=stored_weight,
            effective_weight=effective_weight, edge=(source, target),
        )
    if module is fnx:
        # Native graphs own their write-watched dictionaries. Patch their
        # existing read method rather than replacing native/private storage,
        # as consumers of those escaped dictionaries are allowed to do.
        rows = [attrs for _, _, attrs in graph.edges(data=True)]
        for cls in {type(attrs) for attrs in rows}:
            monkeypatch.setattr(cls, "get", EdgeAttributes.get)
    # Construction is outside the query's observable read boundary.
    reads.clear()
    try:
        if route == "backend":
            result = nx.johnson(graph, backend="franken_networkx")
        elif route == "reference":
            result = nx.johnson(graph, backend="networkx")
        else:
            result = fnx.johnson(graph)
    except Exception as error:
        outcome = ("raised", type(error).__name__, str(error))
    else:
        outcome = ("returned", [
            (source, list(paths.items())) for source, paths in result.items()
        ])
    return outcome, reads, changed


@needs_nx
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("scenario", ["positive", "negative", "negative-cycle", "mutating"])
@pytest.mark.parametrize("route", ["native-input", "networkx-input", "backend"])
def test_johnson_uses_effective_weights_and_live_attribute_readers(
    graph_type, scenario, route, monkeypatch
):
    """Stored positive weights cannot prove Dijkstra is valid for custom readers.

    The same reader may provide a negative edge, reveal a negative cycle, or
    change a later edge while Bellman-Ford establishes its reweighting. Match
    paths, dictionary order, exceptions and the complete read sequence.
    """
    expected = _johnson_with_attribute_readers(nx, graph_type, scenario, "reference")
    module = fnx if route == "native-input" else nx
    actual = _johnson_with_attribute_readers(module, graph_type, scenario, route, monkeypatch)
    assert actual == expected
    assert expected[1], "the query must consume the supplied attribute reader"
    if scenario in ("negative", "mutating") and "DiGraph" in graph_type:
        paths = dict(dict(expected[0][1])["s"])
        assert paths["t"] == ["s", "a", "b", "t"]
    if scenario == "negative-cycle":
        assert expected[0][0:2] == ("raised", "NetworkXUnbounded")


@needs_nx
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("location", ["instance", "class"])
def test_johnson_does_not_consume_replaced_edge_provider(graph_type, location, monkeypatch):
    graph = _make_weighted(fnx, [("s", "a", 2), ("a", "t", 1)], directed=graph_type == "DiGraph")
    oracle = _make_weighted(nx, [("s", "a", 2), ("a", "t", 1)], directed=graph_type == "DiGraph")
    expected = nx.johnson(oracle, backend="networkx")

    def edges_were_read(*args, **kwargs):
        raise AssertionError("Johnson consumes private adjacency, not an edge provider")

    if location == "class":
        monkeypatch.setattr(type(graph), "edges", property(edges_were_read))
    else:
        graph.edges = edges_were_read
    assert fnx.johnson(graph) == expected


@needs_nx
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("negative_cycle", [False, True])
@pytest.mark.parametrize("route", ["native-input", "networkx-input"])
def test_johnson_weight_selector_mutates_before_reweighting(graph_type, negative_cycle, route):
    # These direct entrypoints have the same selector-hash boundary. NetworkX's
    # backend dispatcher additionally hashes weight selectors while building
    # its conversion metadata, before the backend implementation is invoked.
    def run(module, reference=False):
        graph = getattr(module, graph_type)()
        graph.add_weighted_edges_from([
            ("s", "a", 4), ("s", "b", 1), ("a", "b", 3), ("b", "t", 2),
        ])
        if negative_cycle and graph.is_directed():
            graph.add_edge("b", "a", weight=4)
        hashes = []
        changed = False

        class WeightSelector(str):
            def __hash__(self):
                nonlocal changed
                hashes.append("weight")
                if not changed:
                    changed = True
                    graph["a"]["b"]["weight"] = -5
                return str.__hash__(self)

        weight = WeightSelector("weight")
        try:
            if reference:
                result = nx.johnson(graph, weight=weight, backend="networkx")
            else:
                result = fnx.johnson(graph, weight=weight)
        except Exception as error:
            outcome = ("raised", type(error).__name__, str(error))
        else:
            outcome = ("returned", [
                (source, list(paths.items())) for source, paths in result.items()
            ])
        return outcome, hashes, changed

    expected = run(nx, reference=True)
    actual = run(fnx if route == "native-input" else nx)
    assert actual == expected
    assert expected[2]
    if negative_cycle or graph_type == "Graph":
        assert expected[0][0:2] == ("raised", "NetworkXUnbounded")
