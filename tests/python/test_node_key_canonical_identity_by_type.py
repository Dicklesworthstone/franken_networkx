"""A node key canonicalizes by TYPE, and reordering the type probes changed nothing.

br-r37-c1-keyextract-rwsvk. `node_key_to_string` reached its float and tuple branches
by falling THROUGH `extract::<i64>()` (and, for a tuple, `extract::<f64>()` as
well). Each of those failures constructs and discards a `PyErr`, which is the
cost `br-ctaxkey` removed for string keys and left in place for every other type.
Measured on the 5000-key node batch against the string path as the control:

    keys              before      after
    str               271.5       273.7    control, must not move
    int               326.3       324.4    control, must not move
    float integral    540.2       326.1    one failed extract removed
    float fractional  870.8       618.3
    tuple all-int     880.9       464.5    two failed extracts removed
    tuple with a str 1044.1       611.7

The fix is to answer str / int / float / tuple from cheap C-level `downcast`
type checks placed BEFORE the extract chain.

WHICH MAKES THIS FILE ABOUT IDENTITY, NOT SPEED. A canonical string IS the node's
identity: two keys that canonicalize alike are ONE node, and two that do not are
two. Reordering the probes is therefore a change that can silently merge or split
nodes, and the existing branches encode hard-won rules that a reorder could
quietly drop -- br-r37-c1-dr1h9 (a wide int must not reach the float branch, where
`extract::<f64>()` rounds 2**63+7 and 2**63+8 onto the same value), and
br-r37-c1-9q5kq (an integral float wider than i64 must canonicalize as the exact
integer, or it splits from the int that Python says it equals).

The extract chain is KEPT, in its original order, for everything that is not one
of those four concrete types, because such objects are reached by CONVERSION
rather than by type: a numpy integer is not a `PyInt` but supplies `__index__`,
and it has to keep canonicalizing to the same decimal it always did.
"""

from __future__ import annotations

import decimal
import fractions

import networkx as nx
import pytest

import franken_networkx as fnx

np = pytest.importorskip("numpy", reason="numpy scalars exercise the extract fallback")


# Every key below is added to one graph, in this order, by both libraries.
KEYS = [
    0,
    1,
    -1,
    True,
    False,
    2**62,
    2**63,
    2**63 + 7,
    2**63 + 8,
    -(2**63) - 5,
    10**30,
    0.0,
    -0.0,
    1.0,
    1.5,
    -2.5,
    float(2**63),
    float(2**64),
    1e20,
    1e-20,
    float("inf"),
    float("-inf"),
    "a",
    "",
    "1",
    "1.0",
    "(0, 1)",
    "str:1:a",
    (),
    (0,),
    (0, 1),
    (1, 2, 3),
    ("a", 1),
    (0, (1, 2)),
    (True, 1),
    (2**63, 1),
    b"bytes",
    complex(1, 2),
]
# `None` is deliberately absent: networkx forbids it as a node and so does fnx.
# It gets its own test below rather than a silent omission.


def _add_all(mod):
    graph = mod.Graph()
    for key in KEYS:
        graph.add_node(key)
    return graph


def test_the_whole_key_matrix_yields_networkxs_node_sequence():
    """Count AND order: a merge shows up in the count, a split in both."""
    fx, ref = _add_all(fnx), _add_all(nx)

    assert fx.number_of_nodes() == ref.number_of_nodes()
    assert [repr(n) for n in fx.nodes()] == [repr(n) for n in ref.nodes()]


@pytest.mark.parametrize("key", KEYS, ids=[repr(k) for k in KEYS])
def test_each_key_round_trips_as_itself(key):
    """The key that comes back out is the key that went in, type included."""
    fx, ref = fnx.Graph(), nx.Graph()
    fx.add_node(key)
    ref.add_node(key)

    got, want = list(fx.nodes()), list(ref.nodes())
    assert repr(got) == repr(want)
    assert [type(n) for n in got] == [type(n) for n in want]
    assert fx.has_node(key) == ref.has_node(key) is True


# Pairs whose identity is decided by the canonical, one way or the other.
COLLISION_PAIRS = [
    ("int and its float", 1, 1.0),
    ("True is 1", True, 1),
    ("False is 0", False, 0),
    ("zero and negative zero", 0, -0.0),
    ("float zero and int zero", 0.0, 0),
    ("2**63 as int and as float", 2**63, float(2**63)),
    ("2**64 as int and as float", 2**64, float(2**64)),
    ("wide ints one apart", 2**63 + 7, 2**63 + 8),
    ("wide negative int and float", -(2**63) - 5, float(-(2**63) - 5)),
    ("tuple and its repr string", (0, 1), "(0, 1)"),
    ("int and its str", 1, "1"),
    ("float and its str", 1.0, "1.0"),
    ("singleton tuple and its int", (0,), 0),
    ("wide int inside a tuple", (2**63, 1), (2**63 + 1, 1)),
    ("nested tuple and flat", (0, (1, 2)), (0, 1, 2)),
    ("empty tuple and empty string", (), ""),
]


@pytest.mark.parametrize(
    "label,left,right", COLLISION_PAIRS, ids=[c[0] for c in COLLISION_PAIRS]
)
def test_two_keys_merge_exactly_when_networkx_merges_them(label, left, right):
    """ONE node or TWO - the question the canonical answers.

    br-r37-c1-dr1h9 and br-r37-c1-9q5kq are both in here: the wide-int pairs are
    the ones that silently merged when a wide int reached the float branch.
    """
    counts = []
    for mod in (fnx, nx):
        graph = mod.Graph()
        graph.add_node(left)
        graph.add_node(right)
        counts.append((graph.number_of_nodes(), [repr(n) for n in graph.nodes()]))

    assert counts[0] == counts[1], label


@pytest.mark.parametrize(
    "scalar",
    [np.int64(5), np.int32(7), np.int64(2**62), np.bool_(True), np.uint8(3)],
    ids=["int64", "int32", "int64-wide", "bool_", "uint8"],
)
def test_a_numpy_integer_still_canonicalizes_through_the_extract_fallback(scalar):
    """NOT a `PyInt`, so it reaches the kept extract chain by `__index__`.

    This is the case the reorder had to leave alone: answering only from concrete
    types would have sent these to `repr`, and `np.int64(5)` would have stopped
    being the node `5`.
    """
    counts = []
    for mod in (fnx, nx):
        graph = mod.Graph()
        graph.add_node(scalar)
        graph.add_node(int(scalar))
        counts.append(graph.number_of_nodes())

    assert counts[0] == counts[1] == 1


def test_a_tuple_subclass_is_not_diverted_from_its_inherited_conversion():
    """The concrete-tuple probe is EXACT, so subclasses keep the old route."""

    class Pair(tuple):
        pass

    fx, ref = fnx.Graph(), nx.Graph()
    for graph in (fx, ref):
        graph.add_node(Pair((0, 1)))
        graph.add_node((0, 1))

    assert fx.number_of_nodes() == ref.number_of_nodes()
    assert [repr(n) for n in fx.nodes()] == [repr(n) for n in ref.nodes()]


def test_an_int_subclass_with_a_custom_repr_canonicalizes_by_value():
    """`downcast::<PyInt>()` accepts the subclass; value, not repr, decides."""

    class Weird(int):
        def __repr__(self):
            return "surprise"

    fx, ref = fnx.Graph(), nx.Graph()
    for graph in (fx, ref):
        graph.add_node(Weird(5))
        graph.add_node(5)

    assert fx.number_of_nodes() == ref.number_of_nodes() == 1


def test_a_float_subclass_with_a_custom_repr_canonicalizes_by_value():
    """The numpy-free twin of the int-subclass test above.

    `float.__repr__` is called UNBOUND for exactly this reason: a subclass holds
    the same double, so Python calls it the same dict key however it spells
    itself. This is the mechanism behind the `numpy.float64` case without
    needing numpy to demonstrate it (br-r37-c1-numtower-29ggu).
    """

    class Loud(float):
        def __repr__(self):
            return "Loud(!!)"

    fx, ref = fnx.Graph(), nx.Graph()
    for graph in (fx, ref):
        graph.add_node(Loud(1.5))
        graph.add_node(1.5)

    assert fx.number_of_nodes() == ref.number_of_nodes() == 1
    assert [repr(n) for n in fx.nodes()] == [repr(n) for n in ref.nodes()]


def test_keys_survive_edges_and_lookups_not_only_the_node_set():
    """A canonical is also how an EDGE finds its endpoints."""
    keys = [(0, 1), (1, 2), 1.5, 2**63 + 7, "a"]
    fx, ref = fnx.Graph(), nx.Graph()
    for graph in (fx, ref):
        for i in range(len(keys) - 1):
            graph.add_edge(keys[i], keys[i + 1], weight=i)

    assert [repr(n) for n in fx.nodes()] == [repr(n) for n in ref.nodes()]
    for i in range(len(keys) - 1):
        assert fx.has_edge(keys[i], keys[i + 1]) is True
        assert fx[keys[i]][keys[i + 1]] == ref[keys[i]][keys[i + 1]]
    assert sorted(map(repr, fx.neighbors((1, 2)))) == sorted(map(repr, ref.neighbors((1, 2))))


def test_the_bulk_node_batch_agrees_with_the_per_node_loop_for_every_type():
    """The batch canonicalizes with the same function; a divergence here would
    mean bulk and per-node construction disagree about node identity."""
    keys = [(i, i) for i in range(10)] + [i + 0.5 for i in range(10)] + [f"z{i}" for i in range(10)]

    batched = fnx.Graph()
    batched.add_nodes_from(keys)
    looped = fnx.Graph()
    for key in keys:
        looped.add_node(key)
    ref = nx.Graph()
    ref.add_nodes_from(keys)

    assert [repr(n) for n in batched.nodes()] == [repr(n) for n in looped.nodes()]
    assert [repr(n) for n in batched.nodes()] == [repr(n) for n in ref.nodes()]


def test_None_is_refused_as_a_node_exactly_as_networkx_refuses_it():
    """networkx forbids `None` outright, so there is no canonical to agree on."""
    fx, ref = fnx.Graph(), nx.Graph()

    with pytest.raises(ValueError) as fx_err:
        fx.add_node(None)
    with pytest.raises(ValueError) as ref_err:
        ref.add_node(None)

    assert str(fx_err.value) == str(ref_err.value)


# Keys Python calls EQUAL, which must therefore be ONE node
# (br-r37-c1-numtower-29ggu).
EQUAL_BY_VALUE = [
    ("float and numpy float64", 1.5, np.float64(1.5)),
    ("another float and numpy float64", 2.5, np.float64(2.5)),
    ("bool inside a tuple", (True, 1), (1, 1)),
    ("bool in a mixed tuple", ("a", True), ("a", 1)),
    ("bool in a NESTED tuple", (0, (1, True)), (0, (1, 1))),
    ("False inside a singleton", (False,), (0,)),
    ("bare bool and int", True, 1),
]


@pytest.mark.parametrize(
    "label,left,right", EQUAL_BY_VALUE, ids=[c[0] for c in EQUAL_BY_VALUE]
)
def test_a_subclass_or_a_bool_canonicalizes_by_value(label, left, right):
    """These are ONE dict key in Python, so networkx has ONE node.

    `numpy.float64` is a `float` subclass holding the identical double; its own
    `repr` spells it "np.float64(1.5)", which split it from the float. It now
    canonicalizes through `float.__repr__` called UNBOUND, exactly as an int
    subclass already did through `int.__repr__`.

    A bool inside a tuple was excluded from the all-int fast path because
    `repr(True)` is "True" -- correct about the FORMAT, wrong about IDENTITY,
    since `True == 1` unconditionally. Bools are now written as the int they
    equal, which keeps the canonical byte-identical to CPython's tuple repr.
    """
    counts = []
    for mod in (fnx, nx):
        graph = mod.Graph()
        graph.add_node(left)
        graph.add_node(right)
        counts.append((graph.number_of_nodes(), [repr(n) for n in graph.nodes()]))

    assert counts[0] == counts[1], label


# Keys Python keeps APART that an over-eager value canonical would merge. Merging
# these would be a worse bug than the split below, and is why the numeric tower
# is not fixed by converting to f64: `float(Decimal("0.1")) == 0.1` is True while
# `Decimal("0.1") == 0.1` is False.
DISTINCT_BY_VALUE = [
    ("float and Decimal that differ", 0.1, decimal.Decimal("0.1")),
    ("float and Fraction that differ", 0.1, fractions.Fraction(1, 10)),
    ("float and a near neighbour", 1.5, 1.5000000000000002),
]


@pytest.mark.parametrize(
    "label,left,right", DISTINCT_BY_VALUE, ids=[c[0] for c in DISTINCT_BY_VALUE]
)
def test_keys_python_keeps_apart_stay_two_nodes(label, left, right):
    counts = []
    for mod in (fnx, nx):
        graph = mod.Graph()
        graph.add_node(left)
        graph.add_node(right)
        counts.append(graph.number_of_nodes())

    assert counts[0] == counts[1] == 2, label


NUMERIC_TOWER_RESIDUE = [
    ("float and Decimal", 1.5, decimal.Decimal("1.5")),
    ("float and Fraction", 1.5, fractions.Fraction(3, 2)),
]


# br-r37-c1-numtower-29ggu: the strict xfail that used to wrap this is GONE, and
# removing it is the point. It read: "Decimal and Fraction are not float
# subclasses, so they canonicalize by repr and split from the float they equal.
# NOT fixed by converting to f64 - that would merge 0.1 with Decimal('0.1'),
# which Python keeps APART, and an over-merge is a worse bug than this split. A
# real fix needs exact rational comparison."
#
# That prediction was exactly right, and the fix is the exact comparison it asked
# for: `key == float(key)` is Python's own rational comparison, so
# Decimal('1.5') passes it and Decimal('0.1') does not. The strict marker did its
# job — these two XPASSed in the full suite the moment the change landed, while
# `test_keys_python_keeps_apart_stay_two_nodes` below, the over-merge guard the
# reason names, kept passing.
@pytest.mark.parametrize(
    "label,left,right", NUMERIC_TOWER_RESIDUE, ids=[c[0] for c in NUMERIC_TOWER_RESIDUE]
)
def test_keys_python_calls_equal_are_one_node(label, left, right):
    """Python says these are the same dict key; networkx therefore has one node."""
    counts = []
    for mod in (fnx, nx):
        graph = mod.Graph()
        graph.add_node(left)
        graph.add_node(right)
        counts.append(graph.number_of_nodes())

    assert counts[0] == counts[1], label
