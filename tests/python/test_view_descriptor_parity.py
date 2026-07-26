"""Regression lock for br-r37-c1-wbwkb — the cached non-data view descriptor.

``nodes`` / ``edges`` / ``degree`` are installed by ``_CachedViewDescriptor``, a
NON-data descriptor that memoises the built view under its public attribute name so
repeat access is a C-level instance-dict hit (networkx's own ``@cached_property``
mechanism). These tests pin every contract that mechanism could disturb; they are the
acceptance gate the lever shipped against.

Two of them lock traps that the change actually hit during development:

* ``test_deepcopy_does_not_alias_the_memoised_view`` / ``test_pickle_...`` — the copy
  and ``__reduce_ex__`` paths preserve user instance attributes and skip only
  ``_fnx_``-prefixed keys, so a view memoised under its PUBLIC name was copied to the
  new graph while still bound to the original.
* ``test_subgraph_keeps_its_own_node_view`` — ``_FilteredGraphView.__init__`` sets its
  own ``self.nodes`` and then assigns ``self.adj`` (which routes through
  ``_set_private_override``); an unscoped invalidation there deletes the subgraph's
  node view and exposes the bare ``_FilteredGraphView.nodes`` FUNCTION as a bound
  method.
"""

from __future__ import annotations

import copy
import inspect
import pickle

import networkx as nx
import pytest

import franken_networkx as fnx

CLASS_NAMES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
ACCESSORS = ["nodes", "edges", "degree"]
EDGES = [("n0", "n1"), ("n1", "n2"), ("n2", "n3"), ("n0", "n3"), ("n1", "n1")]


def _build(lib, cls_name):
    graph = getattr(lib, cls_name)()
    graph.add_nodes_from([(f"n{i}", {"w": i}) for i in range(4)])
    for left, right in EDGES:
        graph.add_edge(left, right, weight=len(left) + len(right))
    return graph


def _pair(cls_name):
    return _build(nx, cls_name), _build(fnx, cls_name)


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_accessor_content_matches_networkx(cls_name):
    gnx, gfx = _pair(cls_name)
    assert list(gfx.nodes) == list(gnx.nodes)
    assert list(gfx.nodes(data=True)) == list(gnx.nodes(data=True))
    assert list(gfx.edges) == list(gnx.edges)
    assert list(gfx.edges(data=True)) == list(gnx.edges(data=True))
    assert sorted(gfx.degree) == sorted(gnx.degree)


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
@pytest.mark.parametrize("accessor", ACCESSORS)
def test_accessor_identity_type_and_repr_match_networkx(cls_name, accessor):
    """nx's cached_property returns the SAME object on repeat access."""
    gnx, gfx = _pair(cls_name)
    view_a = getattr(gfx, accessor)
    view_b = getattr(gfx, accessor)
    assert view_a is view_b
    assert type(view_a).__name__ == type(getattr(gnx, accessor)).__name__
    assert repr(view_a) == repr(getattr(gnx, accessor))


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_memoised_view_is_live_not_a_snapshot(cls_name):
    gnx, gfx = _pair(cls_name)
    nodes_fx, edges_fx, degree_fx = gfx.nodes, gfx.edges, gfx.degree
    nodes_nx, edges_nx, degree_nx = gnx.nodes, gnx.edges, gnx.degree

    gfx.add_edge("zz", "n0", weight=99)
    gnx.add_edge("zz", "n0", weight=99)
    assert list(nodes_fx) == list(nodes_nx)
    assert list(edges_fx) == list(edges_nx)
    assert sorted(degree_fx) == sorted(degree_nx)

    gfx.remove_node("n2")
    gnx.remove_node("n2")
    assert list(nodes_fx) == list(nodes_nx)
    assert list(edges_fx) == list(edges_nx)
    assert sorted(degree_fx) == sorted(degree_nx)


def test_private_override_installed_after_a_plain_access_redispatches():
    """A graph given networkx private storage must stop serving the plain view."""
    graph = _build(fnx, "Graph")
    plain_type = type(graph.nodes).__name__
    _ = graph.edges
    _ = graph.degree

    graph._node = {"q1": {"tag": 1}, "q2": {"tag": 2}}

    assert sorted(graph.nodes) == ["q1", "q2"]
    assert graph.nodes["q1"] == {"tag": 1}
    assert type(graph.nodes).__name__ != plain_type or sorted(graph.nodes) == ["q1", "q2"]
    assert graph.has_node(n="q1")
    assert not graph.has_node(n="n0")
    assert graph.number_of_nodes() == graph.order() == 2
    assert {"has_node", "number_of_nodes", "order"} <= vars(graph).keys()


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_plain_node_primitives_are_raw_descriptors(cls_name):
    """br-r37-c1-qmi5w: ordinary graphs must not pay a Python shim frame."""
    graph = _build(fnx, cls_name)
    assert type(graph.has_node).__name__ == "builtin_function_or_method"
    assert type(graph.number_of_nodes).__name__ == "builtin_function_or_method"
    assert type(graph.order).__name__ == "builtin_function_or_method"
    assert graph.has_node(n="n0")
    assert graph.number_of_nodes() == graph.order() == 4
    assert not {"has_node", "number_of_nodes", "order"} & vars(graph).keys()


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_private_node_method_shadows_do_not_alias_copy_or_pickle(cls_name):
    graph = getattr(fnx, cls_name)()
    graph.add_node("native")
    graph._node = {"private": {"tag": 1}}

    assert graph.has_node("private")
    assert graph.number_of_nodes() == graph.order() == 1

    for other in (
        copy.copy(graph),
        copy.deepcopy(graph),
        pickle.loads(pickle.dumps(graph)),
    ):
        # Existing fnx contract: private NetworkX storage is an ephemeral view
        # override; graph copies serialize the canonical native storage.
        assert list(other) == ["native"]
        assert other.has_node("native")
        assert not other.has_node("private")
        assert other.number_of_nodes() == other.order() == 1
        assert not {"has_node", "number_of_nodes", "order"} & vars(other).keys()


def test_private_node_install_preserves_user_instance_methods():
    graph = fnx.Graph()

    def custom(n):
        return n == "sentinel"

    graph.has_node = custom
    graph._node = {"private": {}}

    assert graph.has_node is custom
    assert graph.has_node("sentinel")


def test_private_override_state_is_never_memoised():
    graph = _build(fnx, "Graph")
    graph._node = {"z9": {}}
    assert sorted(graph.nodes) == ["z9"]
    assert "nodes" not in vars(graph)


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_subgraph_keeps_its_own_node_view(cls_name):
    """The filtered view sets its own ``nodes`` attribute; it must survive."""
    gnx, gfx = _pair(cls_name)
    sub_fx = gfx.subgraph(["n0", "n1", "n2"])
    sub_nx = gnx.subgraph(["n0", "n1", "n2"])
    # NB: a NodeView is itself callable (``G.nodes(data=True)``), so the failure
    # mode to exclude is specifically a BOUND METHOD leaking through from
    # ``_FilteredGraphView.nodes``.
    assert not inspect.ismethod(sub_fx.nodes), "subgraph node view degraded to a bound method"
    assert list(sub_fx.nodes) == list(sub_nx.nodes)
    assert list(sub_fx.edges) == list(sub_nx.edges)
    assert sorted(sub_fx.degree) == sorted(sub_nx.degree)
    assert sub_fx.has_node("n0") == sub_nx.has_node("n0")
    assert sub_fx.number_of_nodes() == sub_fx.order() == sub_nx.number_of_nodes()


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_edge_subgraph_view(cls_name):
    gnx, gfx = _pair(cls_name)
    sub_fx = gfx.edge_subgraph(list(gfx.edges)[:2])
    sub_nx = gnx.edge_subgraph(list(gnx.edges)[:2])
    assert sorted(sub_fx.nodes) == sorted(sub_nx.nodes)


@pytest.mark.parametrize("cls_name", ["Graph", "MultiGraph"])
def test_copy_does_not_alias_the_memoised_view(cls_name):
    _, gfx = _pair(cls_name)
    _ = gfx.nodes, gfx.edges, gfx.degree
    other = gfx.copy()
    other.add_node("only_in_copy")
    assert "only_in_copy" in other.nodes
    assert "only_in_copy" not in gfx.nodes
    assert other.nodes is not gfx.nodes


@pytest.mark.parametrize("cls_name", ["Graph", "MultiGraph"])
def test_deepcopy_does_not_alias_the_memoised_view(cls_name):
    _, gfx = _pair(cls_name)
    _ = gfx.nodes, gfx.edges, gfx.degree
    other = copy.deepcopy(gfx)
    other.add_node("only_in_deepcopy")
    assert "only_in_deepcopy" in other.nodes
    assert "only_in_deepcopy" not in gfx.nodes


@pytest.mark.parametrize("cls_name", ["Graph", "MultiGraph"])
def test_pickle_round_trip_does_not_alias_the_memoised_view(cls_name):
    _, gfx = _pair(cls_name)
    _ = gfx.nodes, gfx.edges, gfx.degree
    other = pickle.loads(pickle.dumps(gfx))
    assert list(other.nodes) == list(gfx.nodes)
    assert list(other.edges) == list(gfx.edges)
    other.add_node("only_in_unpickled")
    assert "only_in_unpickled" in other.nodes
    assert "only_in_unpickled" not in gfx.nodes


def test_user_instance_attributes_still_survive_copy_and_pickle():
    """The descriptor's skip-list must not swallow genuine user attributes."""
    graph = _build(fnx, "Graph")
    graph.custom_attr = 123
    _ = graph.nodes
    assert copy.deepcopy(graph).custom_attr == 123
    assert pickle.loads(pickle.dumps(graph)).custom_attr == 123


@pytest.mark.parametrize("accessor", ACCESSORS)
def test_accessor_assignment_matches_networkx(accessor):
    """nx's cached_property is assignable; fnx used to raise AttributeError."""
    gnx, gfx = _pair("Graph")
    setattr(gnx, accessor, "SENTINEL")
    setattr(gfx, accessor, "SENTINEL")
    assert getattr(gfx, accessor) == getattr(gnx, accessor) == "SENTINEL"


DIRECTED_ACCESSORS = ["in_degree", "out_degree", "in_edges", "out_edges"]


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("accessor", DIRECTED_ACCESSORS)
def test_directed_accessor_identity_matches_networkx(cls_name, accessor):
    """br-r37-c1-hwu8a: nx caches all four; fnx's edge views used to rebuild.

    ``G.out_edges is G.out_edges`` was False under the old per-access
    ``property`` getter while nx's ``cached_property`` makes it True.
    """
    gnx, gfx = _pair(cls_name)
    assert (getattr(gfx, accessor) is getattr(gfx, accessor)) is (
        getattr(gnx, accessor) is getattr(gnx, accessor)
    )
    assert type(getattr(gfx, accessor)).__name__ == type(getattr(gnx, accessor)).__name__


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("accessor", DIRECTED_ACCESSORS)
def test_directed_accessor_content_matches_networkx(cls_name, accessor):
    gnx, gfx = _pair(cls_name)
    assert sorted(map(str, getattr(gfx, accessor))) == sorted(map(str, getattr(gnx, accessor)))
    assert len(getattr(gfx, accessor)) == len(getattr(gnx, accessor))


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("accessor", DIRECTED_ACCESSORS)
def test_directed_accessor_view_is_live(cls_name, accessor):
    """A memoised edge/degree view must observe later mutation."""
    gnx, gfx = _pair(cls_name)
    view_fx, view_nx = getattr(gfx, accessor), getattr(gnx, accessor)
    gfx.add_edge("fresh_u", "fresh_v", weight=3)
    gnx.add_edge("fresh_u", "fresh_v", weight=3)
    assert sorted(map(str, view_fx)) == sorted(map(str, view_nx))
    gfx.remove_node("n1")
    gnx.remove_node("n1")
    assert sorted(map(str, view_fx)) == sorted(map(str, view_nx))


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_directed_accessor_copy_is_not_aliased(cls_name):
    _, gfx = _pair(cls_name)
    for accessor in DIRECTED_ACCESSORS:
        getattr(gfx, accessor)
    other = copy.deepcopy(gfx)
    other.add_edge("only_u", "only_v")
    assert ("only_u", "only_v") in {(u, v) for u, v, *_ in other.out_edges}
    assert ("only_u", "only_v") not in {(u, v) for u, v, *_ in gfx.out_edges}


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_randomized_mutation_differential(cls_name):
    """Accessor surface stays byte-identical to nx across mutation sequences."""
    import random

    rng = random.Random(hash(cls_name) & 0xFFFF)
    for trial in range(8):
        gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
        for _ in range(40):
            left, right = str(rng.randrange(12)), str(rng.randrange(12))
            weight = rng.randint(1, 9)
            gnx.add_edge(left, right, weight=weight)
            gfx.add_edge(left, right, weight=weight)
        for step in range(6):
            node = str(rng.randrange(12))
            if node in gnx:
                gnx.nodes[node]["mark"] = step
                gfx.nodes[node]["mark"] = step
        if trial % 3 == 0 and len(gnx) > 3:
            victim = list(gnx)[1]
            gnx.remove_node(victim)
            gfx.remove_node(victim)
        assert list(gfx.nodes(data=True)) == list(gnx.nodes(data=True))
        assert list(gfx.edges(data=True)) == list(gnx.edges(data=True))
        assert sorted(gfx.degree) == sorted(gnx.degree)
        assert {k: dict(v) for k, v in gfx.adjacency()} == {
            k: dict(v) for k, v in gnx.adjacency()
        }
