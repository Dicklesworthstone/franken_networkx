"""`G.edges[...]` under ASSIGNED private storage must match networkx exactly.

br-r37-c1-4c6s7. Assigning `G._adj` swaps `G.edges` for
`_AssignedPrivateEdgeView`, a single class standing in for four networkx view
classes. Its `__getitem__` was `u, v = edge[:2]` with an optional third element
for multigraphs, which diverges from the incumbent in three ways at once:
networkx unpacks STRICTLY (`u, v = e`, or `u, v, k = e` for multigraphs, so a
multigraph subscript REQUIRES a 3-tuple), it unpacks BEFORE any lookup or
hashing (so an arity error beats an unhashable-endpoint error), and a slice
raises a typed `NetworkXError` naming the view class.

These assertions compare exception **args**, not just types. That distinction is
the whole point: several of these cases raise the right type with the wrong
payload, and a type-only sweep reports them green. The `1-tuple` case on a
multigraph is the sharpest example — both libraries raise `ValueError`, but
networkx says "expected 3, got 1" and the old code said "expected 2, got 1".

NEGATIVE CASE a naive implementation fails: `edges['a','b']` on a MultiGraph.
Anything that treats the key as optional returns data or raises KeyError; nx
raises ValueError from the strict 3-unpack.
"""

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(module, name, *, assign_private):
    graph = getattr(module, name)()
    graph.add_edge("a", "b", w=1)
    graph.add_edge("b", "c", w=2)
    if assign_private:
        # Hide every edge behind an assigned adjacency mapping. This is the
        # whole trigger: ordinary graphs never reach _AssignedPrivateEdgeView.
        graph._adj = {"a": {}, "b": {}, "c": {}}
    return graph


def _outcome(graph, operation):
    try:
        return ("ok", repr(operation(graph)))
    except Exception as exc:  # noqa: BLE001 - the exception IS the contract
        return (type(exc).__name__, repr(exc.args))


OPERATIONS = {
    "missing_pair": lambda g: g.edges["a", "zz"],
    "hidden_pair": lambda g: g.edges["a", "b"],
    "slice": lambda g: g.edges[0:2],
    "unhashable_endpoint": lambda g: g.edges[[1], "b"],
    "one_tuple": lambda g: g.edges[("a",)],
    "three_tuple": lambda g: g.edges["a", "b", 0],
    "missing_node": lambda g: g.edges["zz", "yy"],
}


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("operation_name", sorted(OPERATIONS))
def test_assigned_private_edge_getitem_matches_networkx(class_name, operation_name):
    operation = OPERATIONS[operation_name]
    expected = _outcome(_build(nx, class_name, assign_private=True), operation)
    actual = _outcome(_build(fnx, class_name, assign_private=True), operation)
    assert actual == expected, (
        f"{class_name}.edges[...] ({operation_name}) under assigned private "
        f"storage: networkx gave {expected}, fnx gave {actual}. Exception ARGS "
        f"are part of this contract, not just the type."
    )


@pytest.mark.parametrize("class_name", CLASSES)
def test_assigned_private_edge_getitem_reads_the_assigned_mapping(class_name):
    """An edge PRESENT in the assigned mapping must be returned from it.

    The counterpart to the hidden-edge cases above: the fix routes reads
    through `.adj`, so this pins that it reads the assigned storage rather than
    falling back to the native store — in the direction where the assigned
    mapping is the only place the edge exists.
    """
    graphs = {}
    for module in (nx, fnx):
        graph = getattr(module, class_name)()
        graph.add_node("a")
        graph.add_node("b")
        payload = {0: {"w": 7}} if graph.is_multigraph() else {"w": 7}
        graph._adj = {"a": {"b": payload}, "b": {"a": payload}}
        graphs[module.__name__] = graph

    subscript = ("a", "b", 0) if graphs["networkx"].is_multigraph() else ("a", "b")
    expected = _outcome(graphs["networkx"], lambda g: g.edges[subscript])
    actual = _outcome(graphs["franken_networkx"], lambda g: g.edges[subscript])
    assert actual == expected, (
        f"{class_name}: an edge present ONLY in the assigned mapping must be "
        f"read from it. networkx gave {expected}, fnx gave {actual}."
    )


@pytest.mark.parametrize("class_name", CLASSES)
def test_multigraph_subscript_requires_a_key(class_name):
    """Pinned separately because it is the case a naive fix gets wrong.

    networkx's OutMultiEdgeView does `u, v, k = e`. A 2-tuple is a ValueError
    from the unpack, NOT a lookup that happens to miss — so an implementation
    treating the key as optional passes every set-based assertion and still
    diverges here.
    """
    graph = _build(fnx, class_name, assign_private=True)
    reference = _build(nx, class_name, assign_private=True)
    if not graph.is_multigraph():
        pytest.skip("2-tuple is the correct arity for a simple graph")
    with pytest.raises(ValueError) as fnx_exc:
        graph.edges["a", "b"]
    with pytest.raises(ValueError) as nx_exc:
        reference.edges["a", "b"]
    assert fnx_exc.value.args == nx_exc.value.args


@pytest.mark.parametrize("class_name", CLASSES)
def test_ordinary_graphs_are_untouched(class_name):
    """Control: no graph without assigned private storage may change.

    This class is reached only through the assigned-storage path, so the
    ordinary view must keep answering exactly as networkx does. Without this
    row the test file cannot tell "fixed the private path" from "changed
    `G.edges` everywhere".
    """
    for operation_name, operation in OPERATIONS.items():
        expected = _outcome(_build(nx, class_name, assign_private=False), operation)
        actual = _outcome(_build(fnx, class_name, assign_private=False), operation)
        assert actual == expected, (
            f"{class_name}.edges[...] ({operation_name}) on an ORDINARY graph "
            f"changed: networkx {expected}, fnx {actual}."
        )
