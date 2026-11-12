"""br-r37-c1-pauth: the direction accessors must read ASSIGNED private storage.

networkx's `DiGraph.predecessors` is `iter(self._pred[n])` with the KeyError
reshaped into a NetworkXError. The assigned mapping is therefore the sole
authority on which nodes exist: a node reachable only through an assigned
`_pred` is answered, and a node the mapping lacks is refused.

Two independent defects broke that, found together:

1. `DiGraph.predecessors` consulted the NODE VIEW (`n not in self`) instead of
   the mapping, which got the question wrong in both directions at once -- it
   rejected a node present only in an assigned `_pred`, and it admitted a node
   present only in an assigned `_node`, letting a raw KeyError escape past every
   caller catching NetworkXError.

2. `has_private_override` was `node || adj`, so an assigned `_succ` or `_pred`
   never reached the Rust side at all. The directed multigraph accessors are
   native slots gated on exactly that question, so they read past the assignment
   and reported a present node absent. The `_adj` flag exists because "`_adj`
   can be assigned without `_node`, so the node flag cannot stand in for it";
   that argument was simply never carried down to `_succ`.

Every case here is asserted against live networkx rather than a written-down
expectation, so the file keeps testing the contract if nx changes it.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


def outcome(call):
    """Result or exception class+message, so both are compared the same way."""
    try:
        return ("ok", sorted(map(str, call())))
    except Exception as exc:  # noqa: BLE001 - the exception IS the observation
        return (type(exc).__name__, str(exc))


def build(mod, cls, assignments):
    g = getattr(mod, cls)()
    g.add_edge("a", "b")
    for name, value in assignments.items():
        setattr(g, name, value)
    return g


def both(cls, assignments, accessor, node):
    return tuple(
        outcome(lambda: getattr(build(mod, cls, assignments), accessor)(node))
        for mod in (nx, fnx)
    )


# --------------------------------------------------------------- the DiGraph half

def test_predecessors_answers_a_node_present_only_in_assigned_pred():
    """The mapping is the authority: `ZZ` exists because `_pred` says so."""
    expected, got = both(
        "DiGraph",
        {"_pred": {"a": {}, "b": {"a": {}}, "ZZ": {"a": {}}}},
        "predecessors",
        "ZZ",
    )
    assert expected == ("ok", ["a"]), "nx contract moved; update this file"
    assert got == expected


def test_predecessors_refuses_a_node_the_assigned_pred_lacks():
    """And refuses one it does not, with nx's wording -- 'digraph', not 'graph'."""
    expected, got = both(
        "DiGraph",
        {"_pred": {"a": {}, "b": {"a": {}}}},
        "predecessors",
        "nope",
    )
    assert expected[0] == "NetworkXError"
    assert got == expected


def test_predecessors_does_not_leak_a_raw_keyerror_under_a_node_override():
    """A node in `_node` but not `_pred` must raise NetworkXError, not KeyError.

    This is the severe direction of the same defect: `n not in self` ADMITTED
    the node, and the subscript's KeyError then escaped uncaught by every caller
    that catches NetworkXError.
    """
    expected, got = both(
        "DiGraph",
        {"_node": {"a": {}, "b": {}, "ZZ": {}}},
        "predecessors",
        "ZZ",
    )
    assert expected[0] == "NetworkXError"
    assert got[0] != "KeyError", "raw KeyError escaped the NetworkXError contract"
    assert got == expected


def test_predecessors_still_hashes_an_unhashable_node_first():
    """br-r37-c1-lvlu7: absence is reported only for a key that can be hashed."""
    for assignments in ({}, {"_pred": {"a": {}, "b": {"a": {}}}}):
        expected, got = both("DiGraph", assignments, "predecessors", ["unhashable"])
        assert expected[0] == "TypeError"
        assert got[0] == expected[0]


# ---------------------------------------------------- the native-slot detection half

@pytest.mark.parametrize(
    ("accessor", "attr", "mapping"),
    [
        ("successors", "_succ", {"a": {"b": {}}, "b": {}, "ZZ": {"b": {}}}),
        ("neighbors", "_succ", {"a": {"b": {}}, "b": {}, "ZZ": {"b": {}}}),
        ("predecessors", "_pred", {"a": {}, "b": {"a": {}}, "ZZ": {"a": {}}}),
    ],
)
def test_multidigraph_accessors_see_an_assigned_direction_mapping(accessor, attr, mapping):
    """`_succ` alone must register: it can be assigned without `_adj` or `_node`.

    Before the fix these passed only when a `_node` assignment happened to
    accompany the `_succ` one and set the flag for it -- which is why the gap
    survived a suite this large. The single-assignment form is the one that
    isolates the detection.
    """
    expected, got = both("MultiDiGraph", {attr: mapping}, accessor, "ZZ")
    assert expected[0] == "ok", "nx contract moved; update this file"
    assert got == expected


def test_digraph_and_multidigraph_agree_with_each_other():
    """The two classes reached this through different code; they must still match."""
    mapping = {"a": {}, "b": {"a": {}}, "ZZ": {"a": {}}}
    di = both("DiGraph", {"_pred": mapping}, "predecessors", "ZZ")
    mdi = both("MultiDiGraph", {"_pred": mapping}, "predecessors", "ZZ")
    assert di[1] == di[0]
    assert mdi[1] == mdi[0]
    assert di[1] == mdi[1]


def test_ordinary_graphs_are_untouched_by_the_flag():
    """No assignment, no private storage: the native paths must still be used."""
    for cls, accessor in (
        ("DiGraph", "predecessors"),
        ("DiGraph", "successors"),
        ("MultiDiGraph", "predecessors"),
        ("MultiDiGraph", "successors"),
    ):
        expected, got = both(cls, {}, accessor, "b")
        assert got == expected
        missing, got_missing = both(cls, {}, accessor, "nope")
        assert missing[0] == "NetworkXError"
        assert got_missing == missing


# ------------------------------------- the native predecessors path (2026-08-24)
#
# br-r37-c1-predrow-8vytj: `DiGraph.predecessors` was the last Python-bodied read
# on the directed classes. It kept its own keydict cache in the instance dict and
# called `_native_predecessor_row_dict` on a miss, which cost 389.9 ns against
# the same class's native `successors` at 184.7 ns. It is now
# `_native_predecessors_iter`, probing a node-INDEX twin of `pred_row_py`.
#
# THE PRIVATE-STORAGE BRANCH MOVED INTO RUST WITH IT, and that is what the tests
# above guard. Binding the bare native WITHOUT it was measured returning the
# STORE's predecessors for a node networkx says is absent -- caught before
# landing, and pinned here so it cannot come back.
#
# The rest is the index twin: it is stamped with `nodes_seq`, and a twin entry
# outliving a cleared row map serves a dict that in-place maintenance can no
# longer reach -- br-r37-c1-txkrn recorded five wrong-answer manifestations of
# exactly that on the successor side.

import pytest as _pytest


def _directed_pair(cls_name):
    return getattr(nx, cls_name)(), getattr(fnx, cls_name)()


@_pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_predecessors_is_the_native_iterator(cls_name):
    """Pins the WIRING. The answer stays right if this regresses to Python, so
    only an identity check notices the fast path going away."""
    assert (
        getattr(fnx, cls_name).predecessors.__name__ == "_native_predecessors_iter"
    ), "predecessors is no longer bound to the native iterator"


@_pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_predecessors_tracks_mutation_through_the_index_twin(cls_name):
    """Build the row, warm the twin, then mutate every way that moves indices."""
    ref, fx = _directed_pair(cls_name)
    for i in range(6):
        ref.add_edge(f"s{i}", "target")
        fx.add_edge(f"s{i}", "target")

    def agree(label):
        for node in ("target", "s0", "s3", "fresh"):
            got = sorted(map(str, fx.predecessors(node))) if fx.has_node(node) else None
            want = sorted(map(str, ref.predecessors(node))) if ref.has_node(node) else None
            assert got == want, (label, node)

    for _ in range(50):  # warm the row and its index twin
        list(fx.predecessors("target"))
    agree("warm")

    for graph in (ref, fx):
        graph.add_edge("fresh", "target")
    agree("after add")

    for graph in (ref, fx):
        graph.remove_edge("s2", "target")
    agree("after edge removal")

    for graph in (ref, fx):
        graph.remove_node("s0")          # renumbers every later node position
    agree("after node removal")

    for graph in (ref, fx):
        graph.add_node("s0")
        graph.add_edge("s0", "target")   # re-added at a NEW index
    agree("after re-add")

    for graph in (ref, fx):
        graph.clear_edges()
    agree("after clear_edges")


@_pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_predecessors_order_and_key_types_match(cls_name):
    """networkx yields insertion order, and the keys come back as themselves."""
    ref, fx = _directed_pair(cls_name)
    sources = ["b", "a", 7, (1, 2), 3.5, "z" * 2000]
    for graph in (ref, fx):
        for s in sources:
            graph.add_edge(s, "sink")

    assert list(map(repr, fx.predecessors("sink"))) == list(map(repr, ref.predecessors("sink")))
    assert [type(p) for p in fx.predecessors("sink")] == [type(p) for p in ref.predecessors("sink")]


@_pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_predecessors_of_an_absent_node_raises_networkxs_error(cls_name):
    ref, fx = _directed_pair(cls_name)
    for graph in (ref, fx):
        graph.add_edge("a", "b")

    with _pytest.raises(nx.NetworkXError) as fx_err:
        list(fx.predecessors("absent"))
    with _pytest.raises(nx.NetworkXError) as ref_err:
        list(ref.predecessors("absent"))
    assert str(fx_err.value) == str(ref_err.value)


@_pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_predecessors_of_an_unhashable_node_raises_typeerror(cls_name):
    """br-r37-c1-lvlu7: nx's `self._pred[n]` hashes first."""
    ref, fx = _directed_pair(cls_name)
    for graph in (ref, fx):
        graph.add_edge("a", "b")

    with _pytest.raises(TypeError):
        list(fx.predecessors(["unhashable"]))
    with _pytest.raises(TypeError):
        list(ref.predecessors(["unhashable"]))


@_pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_a_mutation_during_predecessor_iteration_matches_networkx(cls_name):
    """The row is live, so an in-flight iterator must behave as networkx's does."""

    def drive(graph):
        for i in range(5):
            graph.add_edge(f"s{i}", "target")
        try:
            seen = 0
            for _ in graph.predecessors("target"):
                seen += 1
                if seen == 1:
                    graph.add_edge("late", "target")
            return ("completed", seen)
        except RuntimeError:
            return ("RuntimeError",)

    assert drive(getattr(fnx, cls_name)()) == drive(getattr(nx, cls_name)())
