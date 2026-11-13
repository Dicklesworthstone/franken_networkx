"""Parity for ``transitive_reduction`` and ``transitive_closure_dag``.

Bead br-r37-c1-utmy6. Both functions used the Rust binding which
produced output graphs whose edge() and adj iteration order
drifted from nx.

Repro:
  edges = [('a','b'),('a','c'),('b','d'),('c','d'),('d','e')]
  fnx.transitive_reduction(dag).edges() ->
    [('a','c'),('a','b'),('b','d'),('c','d'),('d','e')]
  nx.transitive_reduction(dagx).edges()  ->
    [('a','b'),('a','c'),('b','d'),('c','d'),('d','e')]

Drop-in code that iterated ``R.edges()`` or ``adj[node]`` of either
output silently broke. Fix delegates both to nx so output graph
iteration order matches nx's contract.
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


def _make_dag(lib, edges):
    g = lib.DiGraph()
    for u, v in edges:
        g.add_edge(u, v)
    return g


# ----- transitive_reduction -----

@needs_nx
def test_repro_diamond_dag_edges_match_nx():
    edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("d", "e")]
    dag = _make_dag(fnx, edges)
    dagx = _make_dag(nx, edges)
    assert list(fnx.transitive_reduction(dag).edges()) == list(
        nx.transitive_reduction(dagx).edges()
    )


@needs_nx
def test_redundant_edge_removed_matches_nx():
    """A direct edge a->c is redundant when a->b->c exists."""
    edges = [("a", "b"), ("b", "c"), ("a", "c")]
    dag = _make_dag(fnx, edges)
    dagx = _make_dag(nx, edges)
    f = fnx.transitive_reduction(dag)
    n = nx.transitive_reduction(dagx)
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_transitive_reduction_path_unchanged():
    """A path is already its own TR."""
    edges = [("a", "b"), ("b", "c"), ("c", "d")]
    dag = _make_dag(fnx, edges)
    dagx = _make_dag(nx, edges)
    f = fnx.transitive_reduction(dag)
    n = nx.transitive_reduction(dagx)
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_transitive_reduction_returns_digraph():
    edges = [("a", "b"), ("b", "c")]
    dag = _make_dag(fnx, edges)
    f = fnx.transitive_reduction(dag)
    assert isinstance(f, fnx.DiGraph)


@needs_nx
def test_transitive_reduction_undirected_raises():
    g = fnx.Graph([(0, 1)])
    with pytest.raises(fnx.NetworkXNotImplemented, match="undirected"):
        fnx.transitive_reduction(g)


@needs_nx
def test_transitive_reduction_cycle_raises():
    """Non-DAG raises NetworkXError."""
    dg = fnx.DiGraph([(0, 1), (1, 0)])
    with pytest.raises(fnx.NetworkXError, match="Directed Acyclic Graph"):
        fnx.transitive_reduction(dg)


@needs_nx
def test_transitive_reduction_adj_matches_nx():
    edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("d", "e")]
    dag = _make_dag(fnx, edges)
    dagx = _make_dag(nx, edges)
    f = fnx.transitive_reduction(dag)
    n = nx.transitive_reduction(dagx)
    for nn in n.nodes():
        assert list(f.adj[nn]) == list(n.adj[nn])


# ----- transitive_closure_dag -----

@needs_nx
def test_tc_dag_repro_diamond_edges_match_nx():
    edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("d", "e")]
    dag = _make_dag(fnx, edges)
    dagx = _make_dag(nx, edges)
    f = fnx.transitive_closure_dag(dag)
    n = nx.transitive_closure_dag(dagx)
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_tc_dag_adj_matches_nx():
    edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("d", "e")]
    dag = _make_dag(fnx, edges)
    dagx = _make_dag(nx, edges)
    f = fnx.transitive_closure_dag(dag)
    n = nx.transitive_closure_dag(dagx)
    for nn in n.nodes():
        assert list(f.adj[nn]) == list(n.adj[nn])


@needs_nx
def test_tc_dag_path_matches_nx():
    edges = [(0, 1), (1, 2), (2, 3)]
    dag = _make_dag(fnx, edges)
    dagx = _make_dag(nx, edges)
    f = fnx.transitive_closure_dag(dag)
    n = nx.transitive_closure_dag(dagx)
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_tc_dag_with_topo_order_matches_nx():
    edges = [("a", "b"), ("a", "c"), ("b", "d")]
    dag = _make_dag(fnx, edges)
    dagx = _make_dag(nx, edges)
    topo = ["a", "b", "c", "d"]
    f = fnx.transitive_closure_dag(dag, topo_order=topo)
    n = nx.transitive_closure_dag(dagx, topo_order=topo)
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_tc_dag_undirected_raises():
    g = fnx.Graph([(0, 1)])
    with pytest.raises(fnx.NetworkXNotImplemented, match="undirected"):
        fnx.transitive_closure_dag(g)


@needs_nx
def test_tc_dag_returns_digraph():
    dag = _make_dag(fnx, [("a", "b"), ("b", "c")])
    f = fnx.transitive_closure_dag(dag)
    assert isinstance(f, fnx.DiGraph)


@needs_nx
def test_tc_dag_empty_graph():
    dag = fnx.DiGraph()
    dagx = nx.DiGraph()
    f = fnx.transitive_closure_dag(dag)
    n = nx.transitive_closure_dag(dagx)
    assert list(f.edges()) == list(n.edges()) == []


@needs_nx
def test_tc_dag_single_edge():
    dag = _make_dag(fnx, [("a", "b")])
    dagx = _make_dag(nx, [("a", "b")])
    f = fnx.transitive_closure_dag(dag)
    n = nx.transitive_closure_dag(dagx)
    assert list(f.edges()) == list(n.edges())


@needs_nx
@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
def test_tc_dag_reversible_order_reads_the_live_working_copy(graph_type):
    def run(lib):
        graph = getattr(lib, graph_type)([(0, 1), (1, 2)])
        graph.add_node(3)
        copies, events = [], []
        original_copy = graph.copy

        def copy():
            events.append("copy")
            result = original_copy()
            copies.append(result)
            return result

        class Order:
            def __iter__(self):
                raise AssertionError("the supplied order must only be reversed")

            def __reversed__(self):
                events.append("reverse")
                yield 3
                copies[0].add_edge(2, 3)
                yield 2
                yield 1
                yield 0

        graph.copy = copy
        result = lib.transitive_closure_dag(graph, topo_order=Order())
        assert result is copies[0]
        assert list(graph.edges()) == [(0, 1), (1, 2)]
        return list(result.edges()), events

    assert run(fnx) == run(nx) == (
        [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)],
        ["copy", "reverse"],
    )


@needs_nx
@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("provider", ["native", "networkx", "filtered", "reverse"])
def test_tc_dag_one_shot_order_fails_after_copy(graph_type, provider):
    def run(lib):
        source_lib = nx if provider == "networkx" else lib
        graph = getattr(source_lib, graph_type)([(0, 1), (1, 2)])
        if provider == "filtered":
            graph = lib.subgraph_view(graph, filter_node=lambda node: True)
        elif provider == "reverse":
            graph = graph.reverse(copy=False)
        events = []
        original_copy = graph.copy

        def copy():
            events.append("copy")
            return original_copy()

        graph.copy = copy
        with pytest.raises(TypeError) as error:
            lib.transitive_closure_dag(graph, topo_order=iter([0, 1, 2]))
        return error.value.args, events

    assert run(fnx) == run(nx) == (
        ("'list_iterator' object is not reversible",), ["copy"],
    )


@needs_nx
@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("provider", ["native", "networkx"])
def test_tc_dag_preserves_copy_class_attributes_and_hooks(graph_type, provider):
    def run(lib):
        base = getattr(nx if provider == "networkx" else lib, graph_type)
        events = []
        shared = []

        class Custom(base):
            def copy(self):
                events.append("copy")
                result = super().copy()
                result.add_edge(2, 3, inserted=shared)
                return result

        graph = Custom([(0, 1), (1, 2)])
        graph.graph["payload"] = shared
        graph.nodes[0]["payload"] = shared
        result = lib.transitive_closure_dag(graph)
        assert type(result) is Custom
        assert result.graph["payload"] is shared
        assert result.nodes[0]["payload"] is shared
        attrs = result[2][3][0] if result.is_multigraph() else result[2][3]
        assert attrs["inserted"] is shared
        assert list(graph.edges()) == [(0, 1), (1, 2)]
        return list(result.edges()), events

    assert run(fnx) == run(nx) == (
        [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)], ["copy"],
    )


@needs_nx
@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
def test_tc_dag_partial_closure_survives_invalid_supplied_node(graph_type):
    def run(lib):
        graph = getattr(lib, graph_type)([(0, 1), (1, 2), (2, 3)])
        copies = []
        original_copy = graph.copy

        def copy():
            copies.append(original_copy())
            return copies[0]

        graph.copy = copy
        with pytest.raises(nx.NetworkXError) as error:
            lib.transitive_closure_dag(graph, topo_order=[99, 0, 1, 2, 3])
        return type(error.value).__name__, error.value.args, list(copies[0].edges())

    assert run(fnx) == run(nx) == (
        "NetworkXError", ("The node 99 is not in the graph.",),
        [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)],
    )


@needs_nx
@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
def test_tc_dag_copy_mutators_run_at_each_node(graph_type):
    def run(lib):
        graph = getattr(lib, graph_type)([(0, 1), (1, 2)])
        graph.add_node(3)
        batches = []
        original_copy = graph.copy

        def copy():
            result = original_copy()
            original_add = result.add_edges_from

            def add_edges_from(edges):
                batch = list(edges)
                batches.append(batch)
                original_add(batch)
                if len(batches) == 1:
                    result.add_edge(2, 3)

            result.add_edges_from = add_edges_from
            return result

        graph.copy = copy
        result = lib.transitive_closure_dag(graph, topo_order=[0, 1, 2, 3])
        return list(result.edges()), batches

    actual, expected = run(fnx), run(nx)
    assert actual == expected
    assert len(actual[1]) == 4
    assert actual[0] == [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
def test_tc_dag_default_order_keeps_degree_provider_errors(graph_type):
    events = []
    graph = getattr(fnx, graph_type)([(0, 1)])

    def in_degree():
        events.append("degree")
        raise ValueError("live degree provider failed")

    def copy():
        raise AssertionError("copy must follow topological validation")

    graph.in_degree = in_degree
    graph.copy = copy
    with pytest.raises(ValueError, match="live degree provider failed"):
        fnx.transitive_closure_dag(graph)
    assert events == ["degree"]


@needs_nx
@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
def test_tc_dag_default_order_reads_graph_kind_before_degrees(graph_type):
    def run(lib):
        graph = getattr(nx, graph_type)([(0, 1)])
        graph.add_node(2)
        events = []
        original_kind = graph.is_multigraph
        original_degree = graph.in_degree
        original_copy = graph.copy

        def is_multigraph():
            events.append("kind")
            graph.add_edge(1, 2)
            return original_kind()

        def in_degree():
            events.append("degree")
            return original_degree()

        def copy():
            events.append("copy")
            graph.is_multigraph = original_kind
            graph.in_degree = original_degree
            return original_copy()

        graph.is_multigraph = is_multigraph
        graph.in_degree = in_degree
        graph.copy = copy
        result = lib.transitive_closure_dag(graph)
        return list(result.edges()), events

    assert run(fnx) == run(nx) == (
        [(0, 1), (0, 2), (1, 2)], ["kind", "degree", "degree", "copy"],
    )


@needs_nx
@pytest.mark.parametrize("supplied_order", [False, True])
def test_tc_dag_plain_graph_retains_batched_native_closure(monkeypatch, supplied_order):
    graph = fnx.DiGraph([(0, 1), (1, 2), (2, 3)])
    namespace = fnx.transitive_closure_dag.__globals__
    original = namespace["_transitive_closure_dag_inproc"]
    calls = []

    def native(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setitem(namespace, "_transitive_closure_dag_inproc", native)
    order = [0, 1, 2, 3] if supplied_order else None
    result = fnx.transitive_closure_dag(graph, topo_order=order)
    assert list(result.edges()) == list(nx.transitive_closure_dag(nx.DiGraph(graph.edges())).edges())
    assert calls == [1]


@needs_nx
@pytest.mark.parametrize("warm_cache", [False, True])
def test_tc_dag_backend_retains_original_copy_provider(warm_cache):
    from franken_networkx.backend import BackendInterface
    from franken_networkx.backend_info import get_backend_info

    assert "transitive_closure_dag" in get_backend_info()["functions"]
    graph = nx.DiGraph([(0, 1), (1, 2)])
    if warm_cache:
        nx.degree_centrality(graph, backend="franken_networkx")
        assert graph.__networkx_cache__["backends"]["franken_networkx"]
    events = []
    original_copy = graph.copy

    def copy():
        events.append("copy")
        result = original_copy()
        result.add_edge(2, 3)
        return result

    graph.copy = copy
    assert BackendInterface.can_run("transitive_closure_dag", (graph,), {}) is True
    result = nx.transitive_closure_dag(graph, backend="franken_networkx")
    assert type(result) is nx.DiGraph
    assert events == ["copy"]
    assert list(result.edges()) == [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("reflexive", [False, True, None])
def test_transitive_closure_adds_each_reachable_pair_once(cls, reflexive):
    """networkx's add_edges_from consumes the closure's generator lazily, so its
    `e[1] not in TC[v]` sees the edges already added in the same pass; the
    generator was materialized first here, and on a MultiGraph every repeated
    target became another parallel edge (a 24-ring gave 288 edges, nx 276)."""
    ring = [(i, (i + 1) % 24, float(i % 5) + 1.5) for i in range(24)]
    chords = [(i, (i + 7) % 24, 1.0) for i in range(0, 24, 3)]
    rows = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        graph = getattr(lib, cls)()
        graph.add_weighted_edges_from(ring + chords)
        closure = lib.transitive_closure(graph, reflexive=reflexive)
        keys = {"keys": True} if closure.is_multigraph() else {}
        rows[name] = sorted(map(repr, closure.edges(data=True, **keys)))
    assert rows["fnx"] == rows["nx"]
