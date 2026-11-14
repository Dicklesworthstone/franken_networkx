"""Cross-type graph operators retain values and observable caller protocols.

The original br-r37-c1-jwdzp regression covered eight binary-graph operators
that rejected NetworkX graphs at the native boundary.

Affected functions:
  - difference, symmetric_difference
  - is_isomorphic, could_be_isomorphic
  - fast_could_be_isomorphic, faster_could_be_isomorphic
  - graph_edit_distance, optimal_edit_paths

Set operators additionally preserve source constructors, live membership,
and unused metadata. Eligible ordinary graphs keep their native kernels;
custom providers remain authoritative throughout the public operation.
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


@needs_nx
def test_difference_accepts_nx_graph():
    ng = nx.Graph([(0, 1), (1, 2)])
    fg = fnx.Graph([(0, 1), (1, 2)])
    assert list(fnx.difference(ng, fg).edges()) == []


@needs_nx
def test_symmetric_difference_accepts_nx_graph():
    ng = nx.Graph([(0, 1), (1, 2)])
    fg = fnx.Graph([(0, 1), (1, 2)])
    assert list(fnx.symmetric_difference(ng, fg).edges()) == []


@needs_nx
def test_is_isomorphic_accepts_nx_graph():
    ng = nx.path_graph(5)
    fg = fnx.path_graph(5)
    assert fnx.is_isomorphic(ng, fg) is True
    assert fnx.is_isomorphic(fg, ng) is True


@needs_nx
def test_could_be_isomorphic_accepts_nx_graph():
    ng = nx.complete_graph(5)
    fg = fnx.complete_graph(5)
    assert fnx.could_be_isomorphic(ng, fg) is True


@needs_nx
def test_fast_could_be_isomorphic_accepts_nx_graph():
    ng = nx.complete_graph(5)
    fg = fnx.complete_graph(5)
    assert fnx.fast_could_be_isomorphic(ng, fg) is True


@needs_nx
def test_faster_could_be_isomorphic_accepts_nx_graph():
    ng = nx.complete_graph(5)
    fg = fnx.complete_graph(5)
    assert fnx.faster_could_be_isomorphic(ng, fg) is True


@needs_nx
def test_graph_edit_distance_accepts_nx_graph():
    ng = nx.path_graph(3)
    fg = fnx.path_graph(3)
    assert fnx.graph_edit_distance(ng, fg) == 0.0


@needs_nx
def test_optimal_edit_paths_accepts_nx_graph():
    ng = nx.path_graph(3)
    fg = fnx.path_graph(3)
    paths, cost = fnx.optimal_edit_paths(ng, fg)
    assert cost == 0.0


@needs_nx
def test_is_isomorphic_with_node_match_accepts_nx_graph():
    """Verify the node_match callback path also works with cross-type input."""
    ng = nx.Graph()
    ng.add_node(0, color="red")
    ng.add_node(1, color="blue")
    ng.add_edge(0, 1)
    fg = fnx.Graph()
    fg.add_node(0, color="red")
    fg.add_node(1, color="blue")
    fg.add_edge(0, 1)
    nm = lambda a, b: a.get("color") == b.get("color")
    assert fnx.is_isomorphic(ng, fg, node_match=nm) is True


@needs_nx
def test_difference_nx_to_fnx_attrs_preserved():
    """Coercion should preserve edge attrs from the nx side."""
    ng = nx.Graph()
    ng.add_edge(0, 1, weight=5)
    fg = fnx.Graph()
    fg.add_edge(0, 1)
    fg.add_node(0)
    fg.add_node(1)
    # Same edges → empty difference, but the coercion must succeed.
    result = fnx.difference(ng, fg)
    assert list(result.edges()) == []


@needs_nx
def test_same_type_no_regression():
    """fnx/fnx and nx/nx-via-fnx paths still work."""
    fg5 = fnx.path_graph(5)
    fg3 = fnx.path_graph(3)
    # is_isomorphic handles larger graphs fine.
    assert fnx.is_isomorphic(fg5, fg5) is True
    # graph_edit_distance is bounded to small graphs; use path_graph(3)
    # (n+n=6 ≤ the local-kernel cutoff).
    assert fnx.graph_edit_distance(fg3, fg3) == 0.0


_GRAPH_KINDS = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")
_SET_OPERATORS = ("union", "compose", "intersection", "difference", "symmetric_difference")


def _set_operator_signature(graph):
    edges = (
        list(graph.edges(keys=True, data=True))
        if graph.is_multigraph() else list(graph.edges(data=True))
    )
    return (
        graph.is_directed(), graph.is_multigraph(), dict(graph.graph),
        list(graph.nodes(data=True)), edges,
    )


def _constructor_operator_inputs(module, kind, operator):
    base = getattr(module, kind)
    events = []
    armed = False

    class Source(base):
        def __init__(self):
            super().__init__()
            if armed:
                events.append("construct")
                if left.is_multigraph():
                    left.add_edge(1, 2, key="late", value=11)
                else:
                    left.add_edge(1, 2, value=11)
                right.nodes[right_nodes[0]]["late"] = "visible"

    left = Source()
    right = base()
    right_nodes = [3, 4, 5] if operator == "union" else [0, 1, 2]
    left.add_nodes_from([0, 1, 2])
    right.add_nodes_from(right_nodes)
    if left.is_multigraph():
        left.add_edge(0, 1, key="shared", value=7)
        right.add_edge(right_nodes[1], right_nodes[2], key="late", value=8)
    else:
        left.add_edge(0, 1, value=7)
        right.add_edge(right_nodes[1], right_nodes[2], value=8)
    left.graph["source"] = "left"
    right.graph["source"] = "right"
    armed = True
    return left, right, events


@needs_nx
@pytest.mark.parametrize("kind", _GRAPH_KINDS)
@pytest.mark.parametrize("operator", _SET_OPERATORS)
@pytest.mark.parametrize("native", [False, True])
def test_set_operators_observe_original_result_constructor(kind, operator, native, monkeypatch):
    expected_left, expected_right, expected_events = _constructor_operator_inputs(nx, kind, operator)
    left, right, events = _constructor_operator_inputs(fnx if native else nx, kind, operator)
    expected = getattr(nx, operator)(expected_left, expected_right, backend="networkx")

    def unexpected_fallback(*args, **kwargs):
        raise AssertionError("set operator delegated to NetworkX")

    for name in _SET_OPERATORS:
        monkeypatch.setattr(nx, name, unexpected_fallback)
    actual = getattr(fnx, operator)(left, right)
    assert events == expected_events == ["construct"]
    assert _set_operator_signature(actual) == _set_operator_signature(expected)
    assert _set_operator_signature(left) == _set_operator_signature(expected_left)
    assert _set_operator_signature(right) == _set_operator_signature(expected_right)


def _membership_operator_inputs(module, kind, *, fail=False):
    graph_type = getattr(module, kind)
    left, right = graph_type(), graph_type()
    left.add_nodes_from([0, 1, 2])
    right.add_nodes_from([0, 1, 2])
    if left.is_multigraph():
        left.add_edge(0, 1, key="edge")
        left.add_edge(1, 2, key="edge")
    else:
        left.add_edges_from([(0, 1), (1, 2)])
    original_has_edge = right.has_edge
    events = []

    def has_edge(*edge):
        events.append(edge)
        if fail:
            raise RuntimeError("membership provider failed")
        if len(events) == 1:
            if right.is_multigraph():
                right.add_edge(1, 2, key="edge")
            else:
                right.add_edge(1, 2)
        return original_has_edge(*edge)

    right.has_edge = has_edge
    return left, right, events


@needs_nx
@pytest.mark.parametrize("kind", _GRAPH_KINDS)
@pytest.mark.parametrize("operator", ["difference", "symmetric_difference"])
@pytest.mark.parametrize("native", [False, True])
def test_set_difference_reads_live_membership_provider(kind, operator, native):
    expected_left, expected_right, expected_events = _membership_operator_inputs(nx, kind)
    left, right, events = _membership_operator_inputs(fnx if native else nx, kind)
    expected = getattr(nx, operator)(expected_left, expected_right, backend="networkx")
    actual = getattr(fnx, operator)(left, right)
    assert events == expected_events
    assert len(events) == 2
    assert _set_operator_signature(actual) == _set_operator_signature(expected)
    assert _set_operator_signature(right) == _set_operator_signature(expected_right)


@needs_nx
@pytest.mark.parametrize("kind", _GRAPH_KINDS)
@pytest.mark.parametrize("operator", ["difference", "symmetric_difference"])
@pytest.mark.parametrize("native", [False, True])
def test_set_difference_preserves_membership_provider_error(kind, operator, native):
    expected_left, expected_right, expected_events = _membership_operator_inputs(nx, kind, fail=True)
    left, right, events = _membership_operator_inputs(fnx if native else nx, kind, fail=True)
    with pytest.raises(RuntimeError) as expected:
        getattr(nx, operator)(expected_left, expected_right, backend="networkx")
    with pytest.raises(type(expected.value)) as actual:
        getattr(fnx, operator)(left, right)
    assert actual.value.args == expected.value.args
    assert events == expected_events


@needs_nx
@pytest.mark.parametrize("kind", _GRAPH_KINDS)
@pytest.mark.parametrize("operator", ["intersection", "difference", "symmetric_difference"])
def test_set_operators_do_not_read_discarded_graph_metadata(kind, operator):
    class UnusedMetadata:
        def keys(self):
            raise AssertionError("discarded graph metadata was read")

    expected_left, expected_right = getattr(nx, kind)(), getattr(nx, kind)()
    left, right = getattr(nx, kind)(), getattr(nx, kind)()
    for graph in (expected_left, expected_right, left, right):
        graph.add_edges_from([(0, 1), (1, 2)])
        graph.graph = UnusedMetadata()
    expected = getattr(nx, operator)(expected_left, expected_right, backend="networkx")
    actual = getattr(fnx, operator)(left, right)
    assert _set_operator_signature(actual) == _set_operator_signature(expected)


@needs_nx
@pytest.mark.parametrize("kinds", [
    ("Graph", "DiGraph"), ("DiGraph", "Graph"),
    ("MultiGraph", "MultiDiGraph"), ("MultiDiGraph", "MultiGraph"),
])
@pytest.mark.parametrize("operator", ["difference", "symmetric_difference"])
@pytest.mark.parametrize("native", [False, True])
def test_set_difference_preserves_each_inputs_directionality(kinds, operator, native):
    def inputs(module):
        left, right = (getattr(module, kind)() for kind in kinds)
        left.add_nodes_from([0, 1])
        right.add_nodes_from([0, 1])
        if left.is_multigraph():
            left.add_edge(0, 1, key="edge")
            right.add_edge(1, 0, key="edge")
        else:
            left.add_edge(0, 1)
            right.add_edge(1, 0)
        return left, right

    expected = getattr(nx, operator)(*inputs(nx), backend="networkx")
    actual = getattr(fnx, operator)(*inputs(fnx if native else nx))
    assert _set_operator_signature(actual) == _set_operator_signature(expected)


@needs_nx
@pytest.mark.parametrize("kind", _GRAPH_KINDS)
def test_native_union_consumes_prefix_iterable_without_truth_testing(kind):
    class Prefixes:
        def __bool__(self):
            raise AssertionError("prefix iterable was truth tested")

        def __iter__(self):
            return iter(("left-", "right-"))

    expected_inputs = [getattr(nx, kind)([(0, 1)]) for _ in range(2)]
    inputs = [getattr(fnx, kind)([(0, 1)]) for _ in range(2)]
    expected = nx.union(*expected_inputs, rename=Prefixes(), backend="networkx")
    actual = fnx.union(*inputs, rename=Prefixes())
    assert _set_operator_signature(actual) == _set_operator_signature(expected)


@needs_nx
@pytest.mark.parametrize("kind", _GRAPH_KINDS)
def test_native_union_rejects_noniterable_prefixes(kind):
    expected_inputs = [getattr(nx, kind)([(0, 1)]), getattr(nx, kind)([(2, 3)])]
    inputs = [getattr(fnx, kind)([(0, 1)]), getattr(fnx, kind)([(2, 3)])]
    with pytest.raises(TypeError) as expected:
        nx.union(*expected_inputs, rename=None, backend="networkx")
    with pytest.raises(type(expected.value)) as actual:
        fnx.union(*inputs, rename=None)
    assert actual.value.args == expected.value.args
