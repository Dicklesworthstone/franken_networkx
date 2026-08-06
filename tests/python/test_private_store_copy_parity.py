"""An assigned private store must survive copy/deepcopy/pickle, as it does in nx.

br-r37-c1-s8obc. ``g._node = {...}`` is not an ordinary attribute in fnx: it is
intercepted and stashed under ``_fnx_private_node_override`` with method shadows
installed beside it. All three copy paths skip ``key.startswith("_fnx_")``, so
the assignment was silently dropped and the clone reverted to the native store —
``'x' in g`` True, ``'x' in copy.copy(g)`` False. networkx keeps the mapping in
``__dict__``, where the default copy protocol carries it, so this was a real
divergence rather than an implementation detail.

Every assertion here is written against live networkx on the same input, so the
suite states the contract rather than fnx's current behaviour.
"""

from __future__ import annotations

import copy
import pickle

import networkx as nx
import pytest

import franken_networkx as fnx

_CLASS_PAIRS = [
    pytest.param(nx.Graph, fnx.Graph, id="Graph"),
    pytest.param(nx.DiGraph, fnx.DiGraph, id="DiGraph"),
    pytest.param(nx.MultiGraph, fnx.MultiGraph, id="MultiGraph"),
    pytest.param(nx.MultiDiGraph, fnx.MultiDiGraph, id="MultiDiGraph"),
]

_CLONERS = [
    pytest.param(copy.copy, id="copy"),
    pytest.param(copy.deepcopy, id="deepcopy"),
    # nosec B301  # ubs:ignore - round trip of an object this test just dumped
    pytest.param(lambda g: pickle.loads(pickle.dumps(g)), id="pickle"),
]


def _with_private_node(cls):
    graph = cls()
    graph.add_nodes_from(["a", 7, 2.5])
    graph._node = {"x": {}}
    return graph


@pytest.mark.parametrize("nx_cls, fnx_cls", _CLASS_PAIRS)
@pytest.mark.parametrize("clone", _CLONERS)
def test_assigned_node_store_survives_cloning(nx_cls, fnx_cls, clone):
    """The bead's exact repro, for every class and every copy path."""
    nx_graph = _with_private_node(nx_cls)
    fnx_graph = _with_private_node(fnx_cls)

    expected = ("x" in nx_graph, "a" in nx_graph)
    assert (("x" in fnx_graph), ("a" in fnx_graph)) == expected, "precondition"

    nx_clone = clone(nx_graph)
    fnx_clone = clone(fnx_graph)

    assert (("x" in nx_clone), ("a" in nx_clone)) == expected, "networkx changed"
    assert (("x" in fnx_clone), ("a" in fnx_clone)) == expected


@pytest.mark.parametrize("nx_cls, fnx_cls", _CLASS_PAIRS)
@pytest.mark.parametrize("clone", _CLONERS)
def test_clone_membership_spellings_agree_with_networkx(nx_cls, fnx_cls, clone):
    """`in`, has_node and the nodes view must all read the restored store."""
    nx_clone = clone(_with_private_node(nx_cls))
    fnx_clone = clone(_with_private_node(fnx_cls))

    assert fnx_clone.has_node("x") == nx_clone.has_node("x")
    assert ("x" in fnx_clone.nodes) == ("x" in nx_clone.nodes)
    assert fnx_clone.number_of_nodes() == nx_clone.number_of_nodes()
    assert list(fnx_clone) == list(nx_clone)


@pytest.mark.parametrize("nx_cls, fnx_cls", _CLASS_PAIRS)
def test_shallow_copy_shares_the_mapping_like_networkx(nx_cls, fnx_cls):
    """copy.copy shares the object; a write through the clone is visible in the source."""
    for cls in (nx_cls, fnx_cls):
        graph = cls()
        graph.add_nodes_from(["a"])
        mapping = {"x": {}}
        graph._node = mapping

        clone = copy.copy(graph)
        assert clone._node is mapping, f"{cls.__name__}: shallow copy did not share"

        clone._node["z"] = {}
        assert "z" in graph._node, f"{cls.__name__}: shared write not visible"


@pytest.mark.parametrize("nx_cls, fnx_cls", _CLASS_PAIRS)
def test_deep_copy_isolates_the_mapping_like_networkx(nx_cls, fnx_cls):
    """copy.deepcopy produces an independent mapping on both sides."""
    for cls in (nx_cls, fnx_cls):
        graph = cls()
        graph.add_nodes_from(["a"])
        mapping = {"x": {}}
        graph._node = mapping

        clone = copy.deepcopy(graph)
        assert clone._node is not mapping, f"{cls.__name__}: deepcopy shared"

        clone._node["y"] = {}
        assert "y" not in graph._node, f"{cls.__name__}: deepcopy leaked"


@pytest.mark.parametrize("clone_fn", [copy.copy, copy.deepcopy])
def test_clone_shadows_are_bound_to_the_clone_not_the_source(clone_fn):
    """The subtle half: re-apply through the public name, never by key-copy.

    The stashed `_fnx_private_*` keys travel with BOUND-METHOD shadows. Copying
    those keys across verbatim would hand the clone methods still bound to the
    ORIGINAL graph, so the clone's membership would answer for the wrong object.
    Re-assigning through `_node` re-runs the installer against the clone.

    Asserted on `__self__` identity rather than on membership behaviour: a
    behavioural probe here passes whether or not the store was restored (with no
    override, `clone._node[k] = {}` just writes to the clone's native store and
    answers the same way), so it cannot tell the two apart. This can.
    """
    graph = fnx.Graph()
    graph.add_nodes_from(["a"])
    graph._node = {"x": {}}
    assert graph.has_node.__self__ is graph, "precondition: source shadow installed"

    clone = clone_fn(graph)

    assert clone.has_node.__self__ is clone
    assert clone.has_node.__self__ is not graph
    clone_shadows = vars(clone).get("_fnx_private_node_method_shadows")
    assert clone_shadows is not None, "clone carries no shadow dict"
    assert clone_shadows is not vars(graph).get("_fnx_private_node_method_shadows")


def test_graph_without_private_store_is_unaffected():
    """The ordinary path must not change — no override, nothing re-applied."""
    graph = fnx.Graph()
    graph.add_edges_from([(0, 1), (1, 2)])

    round_trip = pickle.loads(pickle.dumps(graph))  # nosec B301  # ubs:ignore - self-dumped
    for clone in (copy.copy(graph), copy.deepcopy(graph), round_trip):
        assert sorted(clone.nodes()) == [0, 1, 2]
        assert sorted(map(sorted, clone.edges())) == [[0, 1], [1, 2]]
        assert "_fnx_private_node_override" not in vars(clone)


@pytest.mark.parametrize("clone", _CLONERS)
def test_assigned_adjacency_store_survives_cloning(clone):
    """`_adj` takes the same interception path as `_node`."""
    nx_graph = nx.Graph()
    nx_graph.add_edges_from([(0, 1)])
    nx_graph._adj = {"q": {}}

    fnx_graph = fnx.Graph()
    fnx_graph.add_edges_from([(0, 1)])
    fnx_graph._adj = {"q": {}}

    assert list(clone(fnx_graph)._adj) == list(clone(nx_graph)._adj)


@pytest.mark.parametrize("clone", _CLONERS)
def test_assigned_succ_and_pred_stores_survive_cloning(clone):
    """Directed graphs carry two more private stores."""
    nx_graph = nx.DiGraph()
    nx_graph.add_edges_from([(0, 1)])
    nx_graph._succ = {"s": {}}
    nx_graph._pred = {"p": {}}

    fnx_graph = fnx.DiGraph()
    fnx_graph.add_edges_from([(0, 1)])
    fnx_graph._succ = {"s": {}}
    fnx_graph._pred = {"p": {}}

    nx_clone = clone(nx_graph)
    fnx_clone = clone(fnx_graph)

    assert list(fnx_clone._succ) == list(nx_clone._succ)
    assert list(fnx_clone._pred) == list(nx_clone._pred)


def test_frozen_graph_with_private_store_keeps_both():
    """freeze() is re-applied on the clone too — the two must not fight."""
    graph = fnx.Graph()
    graph.add_nodes_from(["a"])
    graph._node = {"x": {}}
    fnx.freeze(graph)

    round_trip = pickle.loads(pickle.dumps(graph))  # nosec B301  # ubs:ignore - self-dumped
    for clone in (copy.copy(graph), copy.deepcopy(graph), round_trip):
        assert getattr(clone, "frozen", False)
        assert "x" in clone
        with pytest.raises(nx.NetworkXError):
            clone.add_node("nope")
