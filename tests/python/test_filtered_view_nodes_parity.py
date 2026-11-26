"""Parity coverage for filtered-view .nodes NodeView contract.

Bead franken_networkx-zlce: restricted_view and subgraph_view expose
.nodes as a NodeView object (not a bound method), so .data(), .items(),
dict(), and similar helpers all work matching upstream.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize(
    "builder_name",
    ["restricted_view", "subgraph_view"],
)
def test_filtered_view_nodes_is_not_a_method(builder_name):
    fg = fnx.Graph()
    fg.add_node("a", color="red")
    fg.add_node("b")
    fg.add_edge("a", "b")
    if builder_name == "restricted_view":
        fv = fnx.restricted_view(fg, [], [])
    else:
        fv = fnx.subgraph_view(fg)
    assert type(fv.nodes).__name__ != "method"


@pytest.mark.parametrize(
    "builder_name",
    ["restricted_view", "subgraph_view"],
)
def test_filtered_view_nodes_mapping_helpers_match_networkx(builder_name):
    fg = fnx.Graph()
    fg.add_node("a", color="red")
    fg.add_node("b")
    fg.add_edge("a", "b")
    ng = nx.Graph()
    ng.add_node("a", color="red")
    ng.add_node("b")
    ng.add_edge("a", "b")

    if builder_name == "restricted_view":
        fv = fnx.restricted_view(fg, [], [])
        nv = nx.restricted_view(ng, [], [])
    else:
        fv = fnx.subgraph_view(fg)
        nv = nx.subgraph_view(ng)

    assert dict(fv.nodes) == dict(nv.nodes)
    assert list(fv.nodes.data()) == list(nv.nodes.data())
    assert list(fv.nodes(data=True)) == list(nv.nodes(data=True))


# br-filtedgeop: _FilteredEdgeView must expose Set-algebra operators
# (nx.EdgeView inherits from collections.abc.Set) so nx.minimum_cycle_basis
# and other algorithms that do `G.edges - tree_edges` work on filtered views.
def test_filtered_edge_view_supports_set_subtraction():
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)])
    fv = fnx.subgraph_view(fg)
    diff = fv.edges - [(0, 1)]
    assert diff == {(0, 4), (1, 2), (2, 3), (3, 4)}


def test_filtered_edge_view_supports_reflected_set_ops():
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 3)])
    fv = fnx.subgraph_view(fg)
    assert {(0, 1), (999, 999)} - fv.edges == {(999, 999)}
    assert {(99, 100)} | fv.edges == {(0, 1), (1, 2), (2, 3), (99, 100)}
    assert {(0, 1), (77, 88)} & fv.edges == {(0, 1)}
    assert {(0, 1), (9, 9)} ^ fv.edges == {(1, 2), (2, 3), (9, 9)}


def test_filtered_edge_view_eq_matches_set():
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1), (1, 2)])
    fv = fnx.subgraph_view(fg)
    assert fv.edges == {(0, 1), (1, 2)}


def test_filtered_edge_view_data_none_yields_three_tuples_with_default():
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 3)])
    fv = fnx.subgraph_view(fg)
    result = list(fv.edges(data=None, default="sentinel"))
    assert len(result) == 3
    assert all(len(t) == 3 for t in result)
    assert all(t[2] == "sentinel" for t in result)


def test_filtered_edge_view_supports_nx_minimum_cycle_basis():
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (0, 2)])
    ng = nx.Graph()
    ng.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (0, 2)])

    fv = fnx.subgraph_view(fg)
    nv = nx.subgraph_view(ng)

    def canon(cycles):
        return sorted(tuple(sorted(c)) for c in cycles)

    assert canon(nx.minimum_cycle_basis(fv)) == canon(nx.minimum_cycle_basis(nv))


# The filtered edge view's set protocol is collections.abc.Set's, as on
# networkx's EdgeView: each result is built in Set's insertion order (this
# view's for `view - x` and `view | x`, the other operand's for `x - view` and
# `x & view`) and probes membership through the view itself, so a reversed
# undirected pair is an edge. Integer labels hash to themselves, so the bucket
# collisions that expose insertion order are the same under every
# PYTHONHASHSEED and Python version.
_SET_OPERATORS = {
    "view - x": lambda view, x: view - x,
    "x - view": lambda view, x: x - view,
    "view & x": lambda view, x: view & x,
    "x & view": lambda view, x: x & view,
    "view | x": lambda view, x: view | x,
    "x | view": lambda view, x: x | view,
    "view ^ x": lambda view, x: view ^ x,
    "x ^ view": lambda view, x: x ^ view,
    "view <= x": lambda view, x: view <= x,
    "view < x": lambda view, x: view < x,
    "view >= x": lambda view, x: view >= x,
    "view > x": lambda view, x: view > x,
    "x <= view": lambda view, x: x <= view,
    "x >= view": lambda view, x: x >= view,
    "view == x": lambda view, x: view == x,
    "view != x": lambda view, x: view != x,
    "view.isdisjoint(x)": lambda view, x: view.isdisjoint(x),
}


def _set_operator_outcome(operator, view, operand):
    try:
        result = operator(view, operand)
    except Exception as exc:  # noqa: BLE001 - the exception type is the contract
        return ("raises", type(exc).__name__)
    if isinstance(result, bool):
        return ("bool", result)
    return (type(result).__name__, list(result))


def _random_graph_pair(class_name, seed):
    import random

    rng = random.Random(seed)
    order = rng.randint(6, 30)
    edges = [(rng.randrange(order), rng.randrange(order)) for _ in range(3 * order)]
    edges = [(u, v) for u, v in edges if u != v]
    graphs = []
    for module in (fnx, nx):
        graph = getattr(module, class_name)()
        graph.add_nodes_from(range(order))
        graph.add_edges_from(edges)
        graphs.append(graph)
    keep = sorted(rng.sample(range(order), order - 2))
    picked = rng.sample(edges, len(edges) // 2)
    operands = {
        "pairs": [(u, v) for u, v in picked],
        "reversed": [(v, u) for u, v in picked],
        "keyed": [(u, v, 0) for u, v in picked],
        "foreign": [(order + i, order + 2 * i) for i in range(5)],
    }
    return graphs, keep, operands


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("operator", list(_SET_OPERATORS))
def test_filtered_edge_view_set_protocol_matches_networkx_order(class_name, operator):
    function = _SET_OPERATORS[operator]
    for seed in range(40):
        (fg, ng), keep, operands = _random_graph_pair(class_name, seed)
        fview, nview = fg.subgraph(keep).edges, ng.subgraph(keep).edges
        for name, values in operands.items():
            for container in (set, list, frozenset):
                expected = _set_operator_outcome(function, nview, container(values))
                actual = _set_operator_outcome(function, fview, container(values))
                assert actual == expected, (seed, name, container.__name__)
        # Another view is a Set operand: its own membership rule applies. Only
        # the filtered view's own methods are under test here; with the parent
        # view on the left, Python asks the parent's operator first, and
        # Set.__xor__ computes `other - self` with the parent's __sub__.
        if operator.startswith("view") and operator != "view ^ x":
            expected = _set_operator_outcome(function, nview, ng.edges)
            actual = _set_operator_outcome(function, fview, fg.edges)
            assert actual == expected, (seed, "parent edges")


def test_filtered_edge_view_is_a_set_like_networkx():
    from collections.abc import Set

    graph = fnx.Graph([(0, 1), (1, 2)])
    assert isinstance(graph.subgraph([0, 1, 2]).edges, Set)
    assert isinstance(nx.Graph([(0, 1)]).subgraph([0, 1]).edges, Set)


def test_filtered_edge_view_difference_drops_reversed_undirected_pairs():
    fview = fnx.Graph([("a", "b"), ("b", "c")]).subgraph("abc").edges
    nview = nx.Graph([("a", "b"), ("b", "c")]).subgraph("abc").edges
    for view in (fview, nview):
        assert {("b", "a"), ("c", "d")} - view == {("c", "d")}
        assert {("b", "a"), ("c", "d")} & view == {("b", "a")}
        assert view >= {("b", "a")}
        assert not view.isdisjoint([("c", "b")])
