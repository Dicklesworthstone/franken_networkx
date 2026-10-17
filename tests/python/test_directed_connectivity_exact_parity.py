"""Directed connectivity exact-value parity (asymmetric s,t).

Directed local connectivity is asymmetric: the number of node/edge-disjoint
paths from s to t need not equal t to s. This is the domain where two P1
node_connectivity bugs were fixed earlier this cycle (adjacency / directed
undercount), so it warrants exact-value pinning in BOTH directions plus the
global measures.

No mocks: real fnx and real networkx on identically-built digraphs.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx
import franken_networkx.algorithms.connectivity as fc
import networkx.algorithms.connectivity as nc


def _digraph(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    edges = [
        (u, v) for u in range(n) for v in range(n)
        if u != v and r.random() < 0.35
    ]
    fg = fnx.DiGraph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.DiGraph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng, n, r


@pytest.mark.parametrize("seed", range(50))
def test_local_connectivity_both_directions(seed):
    fg, ng, n, r = _digraph(seed)
    for _ in range(3):
        s, t = r.sample(range(n), 2)
        # Forward and reverse local node connectivity match nx exactly.
        assert fc.local_node_connectivity(fg, s, t) == (
            nc.local_node_connectivity(ng, s, t)
        )
        assert fc.local_node_connectivity(fg, t, s) == (
            nc.local_node_connectivity(ng, t, s)
        )
        assert fc.local_edge_connectivity(fg, s, t) == (
            nc.local_edge_connectivity(ng, s, t)
        )


@pytest.mark.parametrize("seed", range(50))
def test_global_directed_connectivity(seed):
    fg, ng, n, r = _digraph(seed)
    assert fnx.node_connectivity(fg) == nx.node_connectivity(ng)
    assert fnx.edge_connectivity(fg) == nx.edge_connectivity(ng)


def test_directed_connectivity_is_genuinely_asymmetric():
    # A directed path 0->1->2 has connectivity 1 forward, 0 backward — confirming
    # the asymmetry is real (and fnx tracks it, matching nx).
    fg = fnx.DiGraph([(0, 1), (1, 2)])
    ng = nx.DiGraph([(0, 1), (1, 2)])
    assert fc.local_node_connectivity(fg, 0, 2) == nc.local_node_connectivity(ng, 0, 2)
    assert fc.local_node_connectivity(fg, 2, 0) == nc.local_node_connectivity(ng, 2, 0)
    assert fc.local_node_connectivity(fg, 0, 2) != fc.local_node_connectivity(fg, 2, 0)


@pytest.mark.parametrize("seed", range(50))
def test_local_edge_connectivity_reverse_direction(seed):
    """The node version checks both directions; the edge version checks one.

    Edge connectivity is asymmetric on a digraph just as node connectivity is —
    measured, the sampled pairs differ in that direction on 103 of 150 — so the
    reverse call is a distinct value and was never compared with networkx.
    """
    fg, ng, n, r = _digraph(seed)
    for _ in range(3):
        s, t = r.sample(range(n), 2)
        assert fc.local_edge_connectivity(fg, t, s) == (
            nc.local_edge_connectivity(ng, t, s)
        )


def test_the_family_is_genuinely_asymmetric():
    """Guards "both directions": if conn(s,t) always equalled conn(t,s), the
    forward and reverse assertions would be checking one number twice."""
    asymmetric = 0
    sampled = 0
    for seed in range(50):
        fg, _, n, r = _digraph(seed)
        for _ in range(3):
            s, t = r.sample(range(n), 2)
            sampled += 1
            if fc.local_node_connectivity(fg, s, t) != fc.local_node_connectivity(fg, t, s):
                asymmetric += 1
    # Measured 99 of 150.
    assert asymmetric >= 40, f"only {asymmetric} of {sampled} sampled pairs are asymmetric"


def test_source_equals_target_contracts_differ():
    """s == t is not handled uniformly by the two local measures.

    local_node_connectivity answers 1 — a node is connected to itself — while
    local_edge_connectivity refuses. Both match networkx, and the split is easy
    to assume away.
    """
    fg, ng, _, _ = _digraph(0)

    assert fc.local_node_connectivity(fg, 0, 0) == nc.local_node_connectivity(ng, 0, 0) == 1
    with pytest.raises(fnx.NetworkXError):
        fc.local_edge_connectivity(fg, 0, 0)
    with pytest.raises(nx.NetworkXError):
        nc.local_edge_connectivity(ng, 0, 0)


def test_global_measures_on_a_disconnected_digraph():
    """29 of the 50 draws are not strongly connected, but none is built to be
    disconnected outright; both global measures are 0 there."""
    fg = fnx.DiGraph([(0, 1), (2, 3)])
    ng = nx.DiGraph([(0, 1), (2, 3)])

    assert fnx.node_connectivity(fg) == nx.node_connectivity(ng) == 0
    assert fnx.edge_connectivity(fg) == nx.edge_connectivity(ng) == 0


# br-r37-c1-8xp4a: these scalar contracts do not expose traversal order.
# Reversing all arcs preserves their values; the ordered component generators
# must NOT take the same root shortcut.
_REVERSE_SCALARS = (
    "number_strongly_connected_components", "is_strongly_connected",
    "number_weakly_connected_components", "is_weakly_connected",
    "is_directed_acyclic_graph", "is_semiconnected",
)


def _reverse_scalar_graphs(graph_type, case="cycle"):
    fixtures = {
        "empty": (0, []),
        "singleton": (1, []),
        "chain": (4, [(0, 1), (1, 2), (2, 3)]),
        "cycle": (4, [(0, 1), (1, 2), (2, 0), (2, 3)]),
        "disconnected": (5, [(0, 1), (2, 3)]),
        "fork": (3, [(0, 1), (0, 2)]),
        "loops": (3, [(0, 0), (1, 1), (0, 1)]),
    }
    if case == "random":
        rng = random.Random(1953)
        count = 9
        edges = [(u, v) for u in range(count) for v in range(count)
                 if rng.random() < 0.24]
    else:
        count, edges = fixtures[case]
    fg, ng = getattr(fnx, graph_type)(), getattr(nx, graph_type)()
    for graph in (fg, ng):
        graph.add_nodes_from(range(count))
        graph.add_edges_from(edges)
        if graph.is_multigraph():
            graph.add_edges_from(edges[:2])
    return fg, ng


def _reverse_scalar_outcome(function, graph, **kwargs):
    try:
        value = function(graph, **kwargs)
    except (nx.NetworkXException, fnx.NetworkXException) as error:
        return ("error", type(error).__name__, str(error))
    return ("value", type(value).__name__, value)


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_SCALARS)
@pytest.mark.parametrize("case", ["empty", "singleton", "chain", "cycle",
                                  "disconnected", "fork", "loops", "random"])
def test_reverse_scalar_values_and_errors_match_live_networkx(graph_type, name, case):
    fg, ng = _reverse_scalar_graphs(graph_type, case)
    before = (list(fg), list(fg.edges(keys=True) if fg.is_multigraph() else fg.edges()))
    assert _reverse_scalar_outcome(getattr(fnx, name), fg.reverse(copy=False)) == (
        _reverse_scalar_outcome(getattr(nx, name), ng.reverse(copy=False))
    )
    assert before == (list(fg), list(fg.edges(keys=True) if fg.is_multigraph() else fg.edges()))


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_SCALARS)
def test_reverse_scalar_native_producer_receives_root_without_copy(graph_type, name, monkeypatch):
    fg, ng = _reverse_scalar_graphs(graph_type)
    produced, copied = [], []
    raw = getattr(fnx, "_raw_" + name)
    materialize = fnx._materialize_view

    def observed_raw(graph):
        produced.append(graph)
        return raw(graph)

    def observed_copy(view):
        copied.append(view)
        return materialize(view)

    monkeypatch.setattr(fnx, "_raw_" + name, observed_raw)
    monkeypatch.setattr(fnx, "_materialize_view", observed_copy)
    assert getattr(fnx, name)(fg.reverse(copy=False)) == getattr(nx, name)(ng.reverse(copy=False))
    assert len(produced) == 1 and produced[0] is fg
    assert copied == []


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_SCALARS)
def test_reverse_scalar_warm_view_observes_live_edge_mutation(graph_type, name):
    fg, ng = _reverse_scalar_graphs(graph_type, "chain")
    fv, nv = fg.reverse(copy=False), ng.reverse(copy=False)
    for edges in (None, [(3, 0)], [(0, 3)], [(2, 1)]):
        if edges is not None:
            fg.add_edges_from(edges)
            ng.add_edges_from(edges)
        assert _reverse_scalar_outcome(getattr(fnx, name), fv) == (
            _reverse_scalar_outcome(getattr(nx, name), nv)
        )
    fg.remove_node(2)
    ng.remove_node(2)
    assert _reverse_scalar_outcome(getattr(fnx, name), fv) == (
        _reverse_scalar_outcome(getattr(nx, name), nv)
    )
    fg.clear()
    ng.clear()
    assert _reverse_scalar_outcome(getattr(fnx, name), fv) == (
        _reverse_scalar_outcome(getattr(nx, name), nv)
    )


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_SCALARS)
@pytest.mark.parametrize("namespace", ["top", "algorithms", "family"])
def test_reverse_scalar_public_namespaces_reach_same_native_root(graph_type, name, namespace, monkeypatch):
    fg, ng = _reverse_scalar_graphs(graph_type)
    if namespace == "top":
        surface = fnx
    elif namespace == "algorithms":
        import franken_networkx.algorithms as surface
    elif name == "is_directed_acyclic_graph":
        import franken_networkx.dag as surface
    else:
        import franken_networkx.components as surface
    produced = []
    raw = getattr(fnx, "_raw_" + name)

    def observed_raw(graph):
        produced.append(graph)
        return raw(graph)

    monkeypatch.setattr(fnx, "_raw_" + name, observed_raw)
    assert getattr(surface, name)(fg.reverse(copy=False)) == getattr(nx, name)(ng.reverse(copy=False))
    assert len(produced) == 1 and produced[0] is fg


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_SCALARS)
def test_reverse_scalar_backend_errors_do_not_invoke_native(graph_type, name, monkeypatch):
    fg, _ = _reverse_scalar_graphs(graph_type)
    produced = []
    raw = getattr(fnx, "_raw_" + name)

    def observed_raw(graph):
        produced.append(graph)
        return raw(graph)

    monkeypatch.setattr(fnx, "_raw_" + name, observed_raw)
    with pytest.raises(ImportError):
        getattr(fnx, name)(fg.reverse(copy=False), backend="nonexistent")
    with pytest.raises(TypeError, match="unexpected keyword argument 'foo'"):
        getattr(fnx, name)(fg.reverse(copy=False), foo="bar")
    assert produced == []


@pytest.mark.parametrize("graph_type", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_SCALARS)
@pytest.mark.parametrize("kind", ["filtered", "nested", "conversion", "subclass", "private"])
def test_reverse_scalar_ineligible_views_keep_materialized_route(graph_type, name, kind, monkeypatch):
    fg, ng = _reverse_scalar_graphs(graph_type, "chain")
    if kind == "filtered":
        fv = fg.subgraph([0, 1, 2]).reverse(copy=False)
        nv = ng.subgraph([0, 1, 2]).reverse(copy=False)
    elif kind == "nested":
        fv = fnx._reverse_directed_view_for(fg.reverse(copy=False))
        nv = nx.classes.graphviews.reverse_view(ng.reverse(copy=False))
    elif kind == "conversion":
        fv = fg.to_undirected(as_view=True).to_directed(as_view=True).reverse(copy=False)
        nv = ng.to_undirected(as_view=True).to_directed(as_view=True).reverse(copy=False)
    elif kind == "subclass":
        class CustomGraph(getattr(fnx, graph_type)):
            pass
        fg = CustomGraph(fg)
        fv, nv = fg.reverse(copy=False), ng.reverse(copy=False)
    else:
        # Install mappings before view creation; mutate them after warming below.
        # Replacing them beneath an existing view remains a separate open gap.
        for graph in (fg, ng):
            graph._succ = {node: {} for node in graph}
            graph._adj = graph._succ
            graph._pred = {node: {} for node in graph}
        fv, nv = fg.reverse(copy=False), ng.reverse(copy=False)
    assert fnx._reverse_view_root(fv) is None
    copied = []
    materialize = fnx._materialize_view

    def observed_copy(view):
        copied.append(view)
        return materialize(view)

    monkeypatch.setattr(fnx, "_materialize_view", observed_copy)
    assert _reverse_scalar_outcome(getattr(fnx, name), fv) == (
        _reverse_scalar_outcome(getattr(nx, name), nv)
    )
    assert copied == [fv]
    if kind == "private":
        for graph in (fg, ng):
            for source, target in ((0, 1), (1, 2), (2, 0)):
                attrs = {"marker": source}
                data = {7: attrs} if graph.is_multigraph() else attrs
                graph._succ[source][target] = data
                graph._pred[target][source] = data
        # Python-only writes do not advance native epochs. The warmed view must
        # still read the assigned cycle plus isolate, not its native chain/cache.
        assert _reverse_scalar_outcome(getattr(fnx, name), fv) == (
            _reverse_scalar_outcome(getattr(nx, name), nv)
        )
        assert copied == [fv, fv]


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", _REVERSE_SCALARS)
def test_reverse_scalar_concrete_routes_and_undirected_guards_unchanged(graph_type, name, monkeypatch):
    fg, ng = _reverse_scalar_graphs(graph_type)
    copied = []
    materialize = fnx._materialize_view

    def observed_copy(view):
        copied.append(view)
        return materialize(view)

    monkeypatch.setattr(fnx, "_materialize_view", observed_copy)
    assert _reverse_scalar_outcome(getattr(fnx, name), fg) == (
        _reverse_scalar_outcome(getattr(nx, name), ng)
    )
    assert copied == []
