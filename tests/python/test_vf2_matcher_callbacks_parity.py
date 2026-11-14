"""Parity for VF2 matcher node_match / edge_match constructors.

Bead br-r37-c1-matchersig. The ``_matcher_factory`` that builds
GraphMatcher / DiGraphMatcher / MultiGraphMatcher / MultiDiGraphMatcher
declared ``__init__(self, G1, G2)``, shadowing the node_match and
edge_match callback hooks nx exposes. Drop-in code calling
``GraphMatcher(G1, G2, node_match=fn)`` raised TypeError on fnx but
worked on nx.

Note: the inline classes earlier in __init__.py *did* have the right
signature, but the factory at the bottom overwrites them via module-
level reassignment. Fix: update the factory's ``__init__`` to accept
and forward both callbacks.
"""

from __future__ import annotations

import inspect

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


MATCHER_NAMES = [
    "GraphMatcher",
    "DiGraphMatcher",
    "MultiGraphMatcher",
    "MultiDiGraphMatcher",
]


@needs_nx
@pytest.mark.parametrize("name", MATCHER_NAMES)
def test_matcher_constructor_signature_matches_networkx(name):
    fnx_sig = inspect.signature(getattr(fnx, name))
    nx_sig = inspect.signature(getattr(nx.isomorphism, name))
    fnx_params = list(fnx_sig.parameters.keys())
    nx_params = list(nx_sig.parameters.keys())
    assert fnx_params == nx_params == ["G1", "G2", "node_match", "edge_match"]


@needs_nx
def test_graphmatcher_node_match_callback_invoked():
    """Pass a node_match callback that always returns False; the
    isomorphism check must reflect that constraint."""
    G1 = fnx.complete_graph(4)
    G2 = fnx.complete_graph(4)

    always_false = lambda d1, d2: False  # noqa: E731
    m = fnx.GraphMatcher(G1, G2, node_match=always_false)
    assert not m.is_isomorphic()

    always_true = lambda d1, d2: True  # noqa: E731
    m = fnx.GraphMatcher(G1, G2, node_match=always_true)
    assert m.is_isomorphic()


@needs_nx
def test_digraph_matcher_edge_match_callback_invoked():
    G1 = fnx.DiGraph()
    G1.add_edge(0, 1, color="red")
    G1.add_edge(1, 2, color="red")
    G2 = fnx.DiGraph()
    G2.add_edge(0, 1, color="red")
    G2.add_edge(1, 2, color="red")

    color_match = lambda d1, d2: d1.get("color") == d2.get("color")
    m = fnx.DiGraphMatcher(G1, G2, edge_match=color_match)
    assert m.is_isomorphic()

    G3 = fnx.DiGraph()
    G3.add_edge(0, 1, color="blue")
    G3.add_edge(1, 2, color="red")
    m = fnx.DiGraphMatcher(G1, G3, edge_match=color_match)
    # Mismatched colours → not isomorphic under the constraint
    assert not m.is_isomorphic()


@needs_nx
def test_multigraph_matcher_accepts_kwargs():
    """MultiGraphMatcher previously rejected the kwargs entirely
    (TypeError). Confirm both callbacks are accepted."""
    M = fnx.MultiGraph()
    M.add_edges_from([(0, 1), (1, 2)])
    m = fnx.MultiGraphMatcher(
        M, M,
        node_match=lambda d1, d2: True,
        edge_match=lambda d1, d2: True,
    )
    assert m.is_isomorphic()


@needs_nx
def test_multidigraph_matcher_accepts_kwargs():
    M = fnx.MultiDiGraph()
    M.add_edges_from([(0, 1), (1, 2)])
    m = fnx.MultiDiGraphMatcher(
        M, M,
        node_match=lambda d1, d2: True,
        edge_match=lambda d1, d2: True,
    )
    assert m.is_isomorphic()


@needs_nx
@pytest.mark.parametrize("name", MATCHER_NAMES)
def test_matcher_default_construction_still_works(name):
    """The 2-arg form must continue to work for existing callers."""
    cls = getattr(fnx, name)
    if name in ("DiGraphMatcher", "MultiDiGraphMatcher"):
        G = fnx.DiGraph() if "Multi" not in name else fnx.MultiDiGraph()
    else:
        G = fnx.Graph() if "Multi" not in name else fnx.MultiGraph()
    G.add_edges_from([(0, 1), (1, 2)])
    m = cls(G, G)
    assert m is not None


_GRAPH_TYPES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _callback_graphs(graph_type, input_kind, view):
    libraries = {
        "networkx": (nx, nx),
        "native": (fnx, fnx),
        "mixed": (nx, fnx),
    }[input_kind]
    parents = []
    for lib in libraries:
        graph = getattr(lib, graph_type)()
        graph.add_nodes_from([(0, {"node": 0}), (1, {"node": 1})])
        graph.add_edge(0, 1, color="same")
        if graph.is_multigraph():
            graph.add_edge(0, 1, key="other", color="parallel")
        parents.append(graph)
    graphs = [graph.subgraph([0, 1]) for graph in parents] if view else parents
    return parents, graphs


@needs_nx
@pytest.mark.parametrize("graph_type", _GRAPH_TYPES)
@pytest.mark.parametrize("input_kind", ["networkx", "native", "mixed"])
@pytest.mark.parametrize("view", [False, True])
@pytest.mark.parametrize("layer", ["node", "edge"])
def test_is_isomorphic_callbacks_receive_original_dictionaries(
    graph_type, input_kind, view, layer
):
    parents, graphs = _callback_graphs(graph_type, input_kind, view)
    calls = []

    def node_match(left, right):
        if layer == "node":
            assert left is parents[0].nodes[left["node"]]
            assert right is parents[1].nodes[right["node"]]
            left["visited"] = right["visited"] = True
            calls.append(True)
        return left["node"] == right["node"]

    def edge_match(left, right):
        if graphs[0].is_multigraph():
            assert set(left) == set(right) == {0, "other"}
            left, right = left[0], right[0]
            original_left, original_right = parents[0][0][1][0], parents[1][0][1][0]
        else:
            original_left, original_right = parents[0][0][1], parents[1][0][1]
        assert left is original_left
        assert right is original_right
        left["visited"] = right["visited"] = True
        calls.append(True)
        return left["color"] == right["color"]

    options = {"node_match": node_match}
    if layer == "edge":
        options["edge_match"] = edge_match
    assert fnx.is_isomorphic(*graphs, **options)
    assert calls
    for graph in parents:
        if layer == "node":
            assert all(attrs["visited"] for _, attrs in graph.nodes(data=True))
        else:
            attrs = graph[0][1][0] if graph.is_multigraph() else graph[0][1]
            assert attrs["visited"]


@needs_nx
@pytest.mark.parametrize("graph_type", _GRAPH_TYPES)
@pytest.mark.parametrize("input_kind", ["networkx", "native", "mixed"])
@pytest.mark.parametrize("view", [False, True])
def test_vf2_matcher_keeps_input_graphs_live(graph_type, input_kind, view):
    parents, graphs = _callback_graphs(graph_type, input_kind, view)
    left_attrs = parents[0][0][1][0] if parents[0].is_multigraph() else parents[0][0][1]
    right_attrs = parents[1][0][1][0] if parents[1].is_multigraph() else parents[1][0][1]
    right_attrs["color"] = "changed"
    edge_calls = []

    def node_match(left, right):
        assert left is parents[0].nodes[left["node"]]
        assert right is parents[1].nodes[right["node"]]
        return left["node"] == right["node"]

    def edge_match(left, right):
        if graphs[0].is_multigraph():
            left, right = left[0], right[0]
        assert left is left_attrs
        assert right is right_attrs
        edge_calls.append(True)
        left["visited"] = right["visited"] = True
        return left["color"] == right["color"]

    matcher = getattr(fnx, graph_type + "Matcher")(
        *graphs, node_match=node_match, edge_match=edge_match
    )
    assert matcher.G1 is graphs[0]
    assert matcher.G2 is graphs[1]
    assert not matcher.is_isomorphic()
    # Matchers retain their inputs, so a later attribute write must be visible
    # when a caller reuses the matcher, including through an existing view.
    left_attrs["color"] = "changed"
    assert matcher.is_isomorphic()
    assert edge_calls and left_attrs["visited"] and right_attrs["visited"]


@needs_nx
@pytest.mark.parametrize("graph_type", _GRAPH_TYPES)
@pytest.mark.parametrize("view", [False, True])
@pytest.mark.parametrize(
    "operation", ["vf2pp_is_isomorphic", "vf2pp_isomorphism", "vf2pp_all_isomorphisms"]
)
def test_labeled_vf2pp_uses_original_attribute_readers(graph_type, view, operation):
    def outcome(lib):
        reads = []

        class Labels(dict):
            def __getitem__(self, key):
                if key == "color":
                    reads.append(self)
                    return "live"
                return super().__getitem__(key)

            def get(self, key, default=None):
                try:
                    return self[key]
                except KeyError:
                    return default

        left, right = getattr(nx, graph_type)(), getattr(nx, graph_type)()
        left.add_node(0)
        right.add_node(1)
        left._node[0] = Labels(color="left")
        right._node[1] = Labels(color="right")
        original_attrs = (left.nodes[0], right.nodes[1])
        if view:
            left, right = left.subgraph([0]), right.subgraph([1])
        result = getattr(lib, operation)(left, right, node_label="color")
        if operation == "vf2pp_all_isomorphisms":
            result = list(result)
        assert reads and all(any(attrs is source for source in original_attrs) for attrs in reads)
        return result

    assert outcome(fnx) == outcome(nx)
