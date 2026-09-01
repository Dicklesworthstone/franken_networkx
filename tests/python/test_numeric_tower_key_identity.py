"""br-r37-c1-numtower-29ggu — keys Python calls EQUAL are ONE key, and only those.

fnx canonicalises a key to a string and stores it. Two keys Python calls equal
must produce the SAME canonical, and two keys it calls unequal must produce
DIFFERENT ones. Both directions were broken, on different axes, and they fail in
opposite ways:

  a SPLIT key shows up as a duplicate — `add_node(1.5); add_node(Decimal('1.5'))`
  left `number_of_nodes()` saying 2 while `nodes()` yielded ONE display key;

  a COLLIDED key silently loses data — `add_edge(key=0.1)` then
  `add_edge(key=Decimal('0.1'))` produced ONE parallel edge where networkx has
  two, so the second edge and its attributes are simply gone.

WHAT WAS WRONG, four things across two canonicalisers:

  NODE keys, split:     Decimal / Fraction / numpy.float32 at a non-integral
                        value reached `repr` while the equal float reached
                        "1.5".
  NODE keys, collided:  `Decimal('3.0000000000000000000001')` has the double 3.0
                        and took the INTEGRAL branch to "3", merging with the
                        int 3 that Python does not call equal to it.
  EDGE keys, collided:  everything with a `__float__` was canonicalised by its
                        double, so `0.1` and `Decimal('0.1')` became one key.
  EDGE keys, split:     `(True, 1)` and `(1, 1)` canonicalised by `repr` to
                        "(True, 1)" and "(1, 1)".

THE RULE IS PYTHON'S OWN EQUALITY, not a type test, and that is what this file
checks. The cases are generated from `a == b` at runtime rather than from a table
of expected node counts, so a case cannot silently become vacuous if a library's
numeric tower changes: an EQUAL pair must give one key on both libraries, an
UNEQUAL pair two, and fnx must agree with networkx cell by cell either way.
"""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction

import networkx as nx
import pytest

import franken_networkx as fnx

np = pytest.importorskip("numpy")

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
MULTI = ["MultiGraph", "MultiDiGraph"]

# Each entry is a pair whose Python equality the test READS rather than asserts.
PAIRS = {
    "float / Decimal equal": (1.5, Decimal("1.5")),
    "float / Fraction equal": (1.5, Fraction(3, 2)),
    "float / np.float32 equal": (1.5, np.float32(1.5)),
    "float / np.float64 equal": (1.5, np.float64(1.5)),
    "float / Decimal UNEQUAL": (0.1, Decimal("0.1")),
    "float / Fraction UNEQUAL": (1 / 3, Fraction(1, 3)),
    "float / np.float32 UNEQUAL": (0.1, np.float32(0.1)),
    "int / Decimal": (3, Decimal(3)),
    "int / Fraction": (3, Fraction(3, 1)),
    "int / np.int64": (3, np.int64(3)),
    "int / near-int Decimal": (3, Decimal("3.0000000000000000000001")),
    "float / int": (1.0, 1),
    "bool / int": (True, 1),
    "bool in a tuple": ((True, 1), (1, 1)),
    "bool in a nested tuple": (((True,), 1), ((1,), 1)),
    "big int / float": (2**64, 2.0**64),
    "str / str": ("a", "a"),
    "tuple / tuple": ((1, 2), (1, 2)),
}


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("label", sorted(PAIRS))
def test_node_key_identity_matches_networkx(cls_name, label):
    """THE SWEEP on node keys, both directions."""
    a, b = PAIRS[label]
    out = []
    for lib in (nx, fnx):
        g = getattr(lib, cls_name)()
        g.add_node(a)
        g.add_node(b)
        out.append((g.number_of_nodes(), sorted(map(repr, g.nodes()))))
    assert out[1] == out[0], f"{cls_name} {label}"


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("label", sorted(PAIRS))
def test_the_node_count_agrees_with_what_nodes_yields(cls_name, label):
    """The TORN state, checked without an oracle.

    A split key used to leave `number_of_nodes()` at 2 while `nodes()` yielded
    one display key — the second node existed in the count and nowhere else.
    That is wrong on fnx's own terms whatever networkx does.
    """
    a, b = PAIRS[label]
    g = getattr(fnx, cls_name)()
    g.add_node(a)
    g.add_node(b)
    assert g.number_of_nodes() == len(list(g.nodes())), f"{cls_name} {label}"


@pytest.mark.parametrize("cls_name", MULTI)
@pytest.mark.parametrize("label", sorted(PAIRS))
def test_edge_key_identity_matches_networkx(cls_name, label):
    """THE SWEEP on multigraph EDGE keys, which is a separate canonicaliser."""
    a, b = PAIRS[label]
    out = []
    for lib in (nx, fnx):
        g = getattr(lib, cls_name)()
        g.add_edge("u", "v", key=a)
        g.add_edge("u", "v", key=b)
        out.append((g.number_of_edges(), sorted(map(repr, g.edges(keys=True)))))
    assert out[1] == out[0], f"{cls_name} {label}"


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("label", sorted(PAIRS))
def test_equal_keys_are_one_key_and_unequal_keys_are_two(cls_name, label):
    """The rule stated directly, with PYTHON deciding which case applies.

    Written this way so the file cannot go vacuous: if a future Python or numpy
    changes one of these equalities, the expectation moves with it instead of
    quietly testing the wrong branch.
    """
    a, b = PAIRS[label]
    equal = bool(a == b)
    if equal != (hash(a) == hash(b)):
        # NOT an fnx defect, and this test found it rather than assuming it:
        # `np.float32(0.1) == 0.1` is True — numpy compares after narrowing the
        # double to float32 — while `hash(np.float32(0.1)) != hash(0.1)`. A pair
        # that is equal with different hashes breaks the contract CPython's dict
        # is built on, so "equal means one key" has no meaning for it and a
        # dict genuinely holds both. The nx-vs-fnx sweeps above still cover the
        # pair, because both libraries meet the same numpy behaviour.
        pytest.skip(f"{label}: numpy breaks hash/eq for this pair")
    g = getattr(fnx, cls_name)()
    g.add_node(a)
    g.add_node(b)
    assert g.number_of_nodes() == (1 if equal else 2), (cls_name, label, equal)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_an_equal_key_reaches_the_same_node(cls_name):
    """Identity is not only a count: the second spelling must FIND the first.

    A canonical that merges the count but not the lookup would pass the sweep
    above and still be broken for every caller.
    """
    g = getattr(fnx, cls_name)()
    g.add_node(1.5, tag="first")
    assert Decimal("1.5") in g
    assert g.nodes[Decimal("1.5")]["tag"] == "first"
    assert g.nodes[Fraction(3, 2)]["tag"] == "first"
    assert g.nodes[np.float32(1.5)]["tag"] == "first"
    g.nodes[Decimal("1.5")]["tag"] = "second"
    assert g.nodes[1.5]["tag"] == "second"
    # And an UNEQUAL neighbour must not be reachable through it.
    assert Decimal("0.1") not in g
