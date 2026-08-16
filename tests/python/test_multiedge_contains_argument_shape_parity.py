"""`edge in M.edges` must accept every shape networkx accepts.

br-r37-c1-ki2ni. networkx's `MultiEdgeView.__contains__` takes `len(e)` and then
UNPACKS — `u, v, k = e`. fnx subscripted instead (`e[0], e[1], e[2]`), which is
not the same contract: a 3-element **set** is Sized but not subscriptable, so
`{'a','b',0} in M.edges` raised `TypeError: 'set' object is not subscriptable`
where networkx unpacks it and answers False.

Subscripting also cannot be justified on speed — measured, the unpack is worth
about 3ns of a 500ns call, so this is a correctness fix that happens not to cost
anything. The wrapper's real cost is elsewhere and is tracked separately.

Every case is asserted against live networkx rather than a recorded expectation,
including the exception type and message, so the test stays honest if the
incumbent's contract moves.
"""

import pytest

import networkx as nx

import franken_networkx as fnx

CLASSES = ["MultiGraph", "MultiDiGraph"]


def _pair(class_name):
    fnx_graph = getattr(fnx, class_name)()
    nx_graph = getattr(nx, class_name)()
    for graph in (fnx_graph, nx_graph):
        graph.add_edge("a", "b")          # key 0
        graph.add_edge("a", "b")          # key 1, a genuine parallel edge
        graph.add_edge("c", "d", key="x")  # a non-integer key
        graph.add_node("solo")
    return fnx_graph, nx_graph


def _outcome(graph, edge):
    try:
        return ("ok", edge in graph.edges)
    except Exception as exc:  # noqa: BLE001 - the exception is the contract
        return (type(exc).__name__, str(exc))


ARGUMENTS = {
    "tuple3_key0": ("a", "b", 0),
    "tuple3_key1": ("a", "b", 1),
    "tuple3_missing_key": ("a", "b", 99),
    "tuple3_str_key": ("c", "d", "x"),
    "tuple2_present": ("a", "b"),
    "tuple2_str_keyed": ("c", "d"),
    "tuple2_absent": ("zz", "yy"),
    "list3": ["a", "b", 0],
    "list2": ["a", "b"],
    "set3": {"a", "b", 0},
    "set2": {"a", "b"},
    "frozenset3": frozenset({"a", "b", 0}),
    "len1": ("a",),
    "len4": ("a", "b", 0, 1),
    "empty": (),
    "string_of_two": "ab",
    "int": 5,
    "none": None,
}


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("argument_name", sorted(ARGUMENTS))
def test_multiedge_contains_matches_networkx(class_name, argument_name):
    edge = ARGUMENTS[argument_name]
    fnx_graph, nx_graph = _pair(class_name)
    assert _outcome(fnx_graph, edge) == _outcome(nx_graph, edge), (
        f"{class_name}: {edge!r} in M.edges diverged. networkx UNPACKS the edge "
        f"(`u, v, k = e`); anything that subscripts instead rejects sized "
        f"non-subscriptable arguments such as a set."
    )


@pytest.mark.parametrize("class_name", CLASSES)
def test_three_element_set_is_accepted_not_a_type_error(class_name):
    """The regression case, pinned on its own so the reason stays visible.

    A set has no order, so unpacking it yields an arbitrary (u, v, k). That is
    fine and is exactly what networkx does — the point is that both libraries
    answer, rather than one raising.
    """
    fnx_graph, nx_graph = _pair(class_name)
    fnx_result = _outcome(fnx_graph, {"a", "b", 0})
    assert fnx_result[0] == "ok", (
        f"a 3-element set raised {fnx_result[0]}; networkx unpacks it"
    )
    assert fnx_result == _outcome(nx_graph, {"a", "b", 0})


@pytest.mark.parametrize("class_name", CLASSES)
def test_two_element_spec_means_key_zero_not_any_key(class_name):
    """Guards the contract the unpack must not disturb (br-r37-c1-6fs77).

    networkx's body is `k = 0` then `k in self._adjdict[u][v]`, so a 2-tuple is
    False for an edge whose only key is 'x'. An implementation that answered
    "does the PAIR exist" would pass most cases here and fail this one.
    """
    fnx_graph, nx_graph = _pair(class_name)
    assert _outcome(fnx_graph, ("c", "d")) == _outcome(nx_graph, ("c", "d"))
    assert _outcome(fnx_graph, ("a", "b")) == _outcome(nx_graph, ("a", "b"))


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("override", [None, "_adj"])
def test_contains_matches_networkx_under_assigned_private_storage(
    class_name, override
):
    """The private-storage walk must keep agreeing with networkx.

    The `_adj` case is included because assigning it installs a `has_edge`
    shadow, so this pins that the override is honoured whichever path the
    implementation takes.
    """
    fnx_graph, nx_graph = _pair(class_name)
    if override == "_adj":
        assigned = {"a": {"b": {0: {}}}, "b": {"a": {0: {}}}, "c": {}, "d": {}, "solo": {}}
        for graph in (fnx_graph, nx_graph):
            graph._adj = {k: dict(v) for k, v in assigned.items()}
    for edge in (("a", "b", 0), ("a", "b", 1), ("c", "d", "x"), ("a", "b"), ("zz", "yy", 0)):
        assert _outcome(fnx_graph, edge) == _outcome(nx_graph, edge), (
            f"{class_name} with override={override}: {edge!r} diverged"
        )


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("attribute", ["_adj", "_node", "_succ", "_pred"])
def test_assigning_private_storage_swaps_the_view_class(class_name, attribute):
    """The invariant that made the private-storage walk removable.

    `MultiEdgeView.__contains__` no longer probes `_has_networkx_private_storage`
    or walks the adjacency, because assigning ANY private attribute replaces
    `G.edges` with `_AssignedPrivateEdgeView`. A `MultiEdgeView` therefore only
    ever exists on a graph with no private storage, and the probe could never be
    True there.

    If that ever stops holding, the removed walk becomes reachable again and its
    absence becomes a correctness bug — so this asserts the swap directly rather
    than trusting the reasoning.
    """
    graph = getattr(fnx, class_name)()
    graph.add_edge("a", "b")
    assert type(graph.edges).__name__ in ("MultiEdgeView", "OutMultiEdgeView")

    if attribute in ("_succ", "_pred") and class_name == "MultiGraph":
        pytest.skip("undirected multigraphs have no succ/pred storage")
    setattr(graph, attribute, {"a": {}, "b": {}})
    assert type(graph.edges).__name__ == "_AssignedPrivateEdgeView", (
        f"assigning {attribute} on {class_name} left G.edges as "
        f"{type(graph.edges).__name__}; the unreachable-walk assumption in "
        f"MultiEdgeView.__contains__ no longer holds"
    )
