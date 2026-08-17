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
