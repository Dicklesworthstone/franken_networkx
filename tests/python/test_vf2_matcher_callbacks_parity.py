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


_VF2PP_BACKEND_APIS = (
    "vf2pp_is_isomorphic", "vf2pp_isomorphism", "vf2pp_all_isomorphisms",
)
_ISOMORPHISM_BACKEND_APIS = ("is_isomorphic", *_VF2PP_BACKEND_APIS)


def _warm_isomorphism_backend_inputs(graphs):
    for graph in graphs:
        nx.relabel_nodes(graph, {}, backend="franken_networkx")
        assert graph.__networkx_cache__["backends"]["franken_networkx"]


def _isomorphism_backend_inputs(graph_type, route, view=False):
    input_kind = {
        "cold": "networkx", "warm": "networkx",
        "native": "native", "mixed": "mixed",
    }[route]
    parents, graphs = _callback_graphs(graph_type, input_kind, view)
    if route == "warm":
        _warm_isomorphism_backend_inputs(graphs)
    return parents, graphs


def _vf2pp_backend_result(name, result):
    return list(result) if name == "vf2pp_all_isomorphisms" else result


@needs_nx
@pytest.mark.parametrize("name", _ISOMORPHISM_BACKEND_APIS)
def test_isomorphism_backend_metadata_and_signature(name):
    from franken_networkx import backend as fnx_backend

    assert name in fnx_backend.get_backend_info()["functions"]
    graphs = (nx.path_graph(2), nx.path_graph(2))
    assert fnx_backend.BackendInterface.can_run(name, graphs, {})
    assert fnx_backend.BackendInterface.can_run(
        name, (), {"G1": graphs[0], "G2": graphs[1]}
    )
    assert not fnx_backend.BackendInterface.can_run(name, graphs[:1], {})


@needs_nx
@pytest.mark.parametrize("graph_type", _GRAPH_TYPES)
@pytest.mark.parametrize("route", ["cold", "warm", "native", "mixed"])
@pytest.mark.parametrize("view", [False, True])
def test_isomorphism_backend_callbacks_keep_original_dictionaries(graph_type, route, view):
    parents, graphs = _isomorphism_backend_inputs(graph_type, route, view)
    seen = set()

    def node_match(left, right):
        assert left is parents[0].nodes[left["node"]]
        assert right is parents[1].nodes[right["node"]]
        left["visited"] = right["visited"] = True
        seen.add("node")
        return left["node"] == right["node"]

    def edge_match(left, right):
        if graphs[0].is_multigraph():
            assert set(left) == set(right) == {0, "other"}
            left, right = left[0], right[0]
            original_left = parents[0][0][1][0]
            original_right = parents[1][0][1][0]
        else:
            original_left, original_right = parents[0][0][1], parents[1][0][1]
        assert left is original_left
        assert right is original_right
        left["visited"] = right["visited"] = True
        seen.add("edge")
        return left["color"] == right["color"]

    assert nx.is_isomorphic(
        *graphs, node_match=node_match, edge_match=edge_match,
        backend="franken_networkx",
    )
    assert seen == {"node", "edge"}
    for graph in parents:
        assert all(attrs["visited"] for _, attrs in graph.nodes(data=True))
        attrs = graph[0][1][0] if graph.is_multigraph() else graph[0][1]
        assert attrs["visited"]
    for graph in graphs:
        assert not getattr(graph, "__networkx_cache__", {}).get("backends")


@needs_nx
@pytest.mark.parametrize("error_base", [ValueError, fnx.NetworkXNotImplemented])
def test_isomorphism_backend_preserves_callback_failure_and_clears_both_caches(error_base):
    class CallbackFailure(error_base):
        pass

    failure = CallbackFailure("isomorphism callback failed")
    parents, graphs = _isomorphism_backend_inputs("Graph", "warm")
    calls = []

    def reject(left, right):
        assert left is parents[0].nodes[left["node"]]
        assert right is parents[1].nodes[right["node"]]
        left["visited"] = right["visited"] = True
        calls.append(True)
        for graph in graphs:
            graph.__networkx_cache__["backends"] = {"other_backend": {"stale": object()}}
        raise failure

    with pytest.raises(CallbackFailure) as caught:
        nx.is_isomorphic(*graphs, node_match=reject, backend="franken_networkx")
    assert caught.value is failure
    assert calls == [True], "a callback exception must not retry the search"
    assert any(attrs.get("visited") for _, attrs in parents[0].nodes(data=True))
    assert any(attrs.get("visited") for _, attrs in parents[1].nodes(data=True))
    assert all("backends" not in graph.__networkx_cache__ for graph in graphs)


@needs_nx
@pytest.mark.parametrize("name", _VF2PP_BACKEND_APIS)
@pytest.mark.parametrize("graph_type", _GRAPH_TYPES)
@pytest.mark.parametrize("route", ["native", "mixed"])
def test_vf2pp_backend_accepts_native_and_mixed_inputs(name, graph_type, route):
    _, graphs = _isomorphism_backend_inputs(graph_type, route)
    actual = _vf2pp_backend_result(
        name, getattr(nx, name)(*graphs, node_label="node", backend="franken_networkx")
    )
    expected = {
        "vf2pp_is_isomorphic": True,
        "vf2pp_isomorphism": {0: 0, 1: 1},
        "vf2pp_all_isomorphisms": [{0: 0, 1: 1}],
    }
    assert actual == expected[name]


@needs_nx
@pytest.mark.parametrize("name", _VF2PP_BACKEND_APIS)
@pytest.mark.parametrize("graph_type", _GRAPH_TYPES)
@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("view", [False, True])
def test_vf2pp_backend_keeps_original_label_readers(name, graph_type, warm, view):
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
    originals = (left.nodes[0], right.nodes[1])
    graphs = (left.subgraph([0]), right.subgraph([1])) if view else (left, right)
    if warm:
        _warm_isomorphism_backend_inputs(graphs)
    reads.clear()
    result = getattr(nx, name)(*graphs, node_label="color", backend="franken_networkx")
    if name == "vf2pp_all_isomorphisms":
        assert reads == [], "constructing the iterator must not inspect labels"
    actual = _vf2pp_backend_result(name, result)
    expected = {
        "vf2pp_is_isomorphic": True,
        "vf2pp_isomorphism": {0: 1},
        "vf2pp_all_isomorphisms": [{0: 1}],
    }
    assert actual == expected[name]
    assert reads
    assert all(any(attrs is original for original in originals) for attrs in reads)
    assert all("backends" not in graph.__networkx_cache__ for graph in graphs)


@needs_nx
@pytest.mark.parametrize("name", ["vf2pp_is_isomorphic", "vf2pp_isomorphism"])
def test_vf2pp_backend_preserves_label_reader_failure(name):
    class LabelFailure(fnx.NetworkXNotImplemented):
        pass

    failure = LabelFailure("isomorphism label reader failed")
    _, graphs = _isomorphism_backend_inputs("Graph", "warm")
    calls = []

    class Labels(dict):
        def get(self, key, default=None):
            calls.append(key)
            for graph in graphs:
                graph.__networkx_cache__["backends"] = {"other_backend": {"stale": object()}}
            raise failure

    graphs[0]._node[0] = Labels(node=0)
    with pytest.raises(LabelFailure) as caught:
        getattr(nx, name)(*graphs, node_label="node", backend="franken_networkx")
    assert caught.value is failure
    assert calls == ["node"]
    assert all("backends" not in graph.__networkx_cache__ for graph in graphs)


@needs_nx
@pytest.mark.parametrize("graph_type", _GRAPH_TYPES)
@pytest.mark.parametrize("route", ["cold", "warm", "native", "mixed"])
def test_vf2pp_backend_defers_both_graphs_until_first_advancement(graph_type, route):
    parents, graphs = _isomorphism_backend_inputs(graph_type, route)
    result = nx.vf2pp_all_isomorphisms(
        *graphs, node_label="node", backend="franken_networkx"
    )
    for graph in parents:
        graph.add_node(2, node=2)
        graph.add_edge(1, 2)
    assert list(result) == [{0: 0, 1: 1, 2: 2}]


@needs_nx
@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("finish", ["exhaust", "close"])
def test_vf2pp_backend_iterator_releases_both_sources_when_finished(warm, finish):
    import gc
    import weakref

    left, right = nx.path_graph(2), nx.path_graph(2)
    if warm:
        _warm_isomorphism_backend_inputs((left, right))
    references = (weakref.ref(left), weakref.ref(right))
    result = nx.vf2pp_all_isomorphisms(left, right, backend="franken_networkx")
    del left, right
    gc.collect()
    assert all(reference() is not None for reference in references)
    first = next(result)
    assert set(first) == set(first.values()) == {0, 1}
    if finish == "close":
        result.close()
    else:
        assert len(list(result)) == 1
    gc.collect()
    assert all(reference() is None for reference in references)


@needs_nx
@pytest.mark.parametrize("name", _ISOMORPHISM_BACKEND_APIS)
def test_isomorphism_backend_keeps_an_explicit_native_conversion_independent(name):
    source = nx.path_graph(2)
    _warm_isomorphism_backend_inputs((source,))
    native = next(iter(source.__networkx_cache__["backends"]["franken_networkx"].values()))
    assert isinstance(native, fnx.Graph)
    native.add_edge(1, 2)
    actual = _vf2pp_backend_result(
        name, getattr(nx, name)(source, native, backend="franken_networkx")
    )
    expected = {
        "is_isomorphic": False,
        "vf2pp_is_isomorphic": False,
        "vf2pp_isomorphism": None,
        "vf2pp_all_isomorphisms": [],
    }
    assert actual == expected[name]
    assert set(source) == {0, 1}
    assert set(native) == {0, 1, 2}
