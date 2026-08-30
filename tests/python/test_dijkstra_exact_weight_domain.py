"""br-r37-c1-04z53.9172 — the Dijkstra weight classifier needs an EXACTNESS dimension.

The shared delegation predicate decided on three flags: ``has_negative``,
``requires_exact_fallback`` and ``has_nonnumeric``. The per-class scans computed
them with ``val.extract::<f64>()`` as the numeric test, and that test succeeds
*lossily* for a Python int of any width and for anything carrying ``__float__``.
So a weight f64 cannot represent was classified "numeric, finite, non-negative",
entered the native f64 kernel, and produced a **wrong number** — not a type
difference, a wrong answer.

Every assertion here is against live networkx, which is the authority. The suite
is deliberately split three ways:

* ``test_*_matches_networkx`` — the defect rows. These FAIL on the pre-fix build.
* ``test_already_correct_*`` — the eight rows verified correct BEFORE the fix.
  They are the non-regression half: a fix that simply delegated everything, or
  one that broke the negative/non-finite rules, would fail here.
* ``test_ordinary_weights_stay_on_the_native_path`` — the negative case for the
  fix itself. Over-delegating is invisible in output parity (nx and fnx agree
  either way), so nothing else in this file can catch a "delegate always" patch.
"""

import copy
from fractions import Fraction

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = [
    (nx.Graph, fnx.Graph),
    (nx.DiGraph, fnx.DiGraph),
    (nx.MultiGraph, fnx.MultiGraph),
    (nx.MultiDiGraph, fnx.MultiDiGraph),
]
CLASS_IDS = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _pair(nx_cls, fnx_cls, first_weight, second_weight=1):
    """a-b-c with ``first_weight`` then ``second_weight``, in both libraries."""
    gnx, gfx = nx_cls(), fnx_cls()
    for graph in (gnx, gfx):
        graph.add_edge("a", "b", weight=first_weight)
        graph.add_edge("b", "c", weight=second_weight)
    return gnx, gfx


def _lengths(gnx, gfx):
    return (
        nx.dijkstra_path_length(gnx, "a", "c", weight="weight"),
        fnx.dijkstra_path_length(gfx, "a", "c", weight="weight"),
    )


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_large_int_sum_stays_exact_matches_networkx(nx_cls, fnx_cls):
    """2**60 + 1 is not representable in f64; the sum must not round back down."""
    want, got = _lengths(*_pair(nx_cls, fnx_cls, 2**60))
    assert want == 2**60 + 1
    assert got == want, f"expected exact {want}, got {got}"


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_int_wider_than_f64_matches_networkx(nx_cls, fnx_cls):
    """2**70 loses both the value and the int type through an f64 kernel."""
    want, got = _lengths(*_pair(nx_cls, fnx_cls, 2**70))
    assert got == want
    assert isinstance(got, int), f"expected an int, got {type(got).__name__}"


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_fraction_weight_matches_networkx(nx_cls, fnx_cls):
    """networkx keeps Fraction arithmetic exact; f64 cannot represent 1/3."""
    want, got = _lengths(*_pair(nx_cls, fnx_cls, Fraction(1, 3)))
    assert want == Fraction(4, 3)
    assert got == want
    assert isinstance(got, Fraction), f"expected a Fraction, got {type(got).__name__}"


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_many_small_ints_summing_past_the_envelope_match_networkx(nx_cls, fnx_cls):
    """The case a per-edge magnitude check cannot catch.

    Forty weights of ``2**53 // 10`` are each far inside f64's exact range; only
    their SUM leaves it. Pre-fix this returned 36028797018963984 against nx's
    36028797018963960 — high by 24, while the 2**60 row was low by 1, so the
    error has no consistent direction and no tolerance can paper over it.
    """
    weight = 2**53 // 10
    gnx, gfx = nx_cls(), fnx_cls()
    nodes = [f"n{i}" for i in range(41)]
    for graph in (gnx, gfx):
        for left, right in zip(nodes, nodes[1:]):
            graph.add_edge(left, right, weight=weight)

    want = nx.dijkstra_path_length(gnx, nodes[0], nodes[-1], weight="weight")
    got = fnx.dijkstra_path_length(gfx, nodes[0], nodes[-1], weight="weight")
    assert want == weight * 40
    assert got == want, f"expected exact {want}, got {got} (delta {got - want})"


# --------------------------------------------------------------------------
# Non-regression: rows verified correct BEFORE the fix. The classifier's
# existing negative / non-finite / non-numeric rules are sound and must survive.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_already_correct_infinity_and_nan(nx_cls, fnx_cls):
    want, got = _lengths(*_pair(nx_cls, fnx_cls, float("inf")))
    assert got == want == float("inf")

    want, got = _lengths(*_pair(nx_cls, fnx_cls, float("nan")))
    assert (want != want) and (got != got), "NaN must stay NaN on both sides"


def _outcome(fn, *args, **kwargs):
    """Return the value, or the exception type, so parity can be asserted either way."""
    try:
        return ("value", fn(*args, **kwargs))
    except Exception as exc:  # noqa: BLE001 - parity is about matching nx exactly
        return ("raised", type(exc).__name__)


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_already_correct_negative_and_negative_infinity_match_networkx(
    nx_cls, fnx_cls
):
    """Whatever networkx does with a negative weight, fnx must do.

    Deliberately NOT asserted as ``pytest.raises(ValueError)``: on this a-b-c
    shape networkx returns 0 for weight -1 and -inf for weight -inf rather than
    raising, so pinning an exception here would encode a divergence that does
    not exist and would fail against the real oracle.
    """
    for bad in (-1, float("-inf")):
        gnx, gfx = _pair(nx_cls, fnx_cls, bad)
        want = _outcome(nx.dijkstra_path_length, gnx, "a", "c", weight="weight")
        got = _outcome(fnx.dijkstra_path_length, gfx, "a", "c", weight="weight")
        assert got == want, f"weight={bad!r}: nx gave {want}, fnx gave {got}"


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_already_correct_bool_and_numeric_subclasses(nx_cls, fnx_cls):
    class MyInt(int):
        pass

    class MyFloat(float):
        pass

    for value, expected in ((True, 2), (MyInt(3), 4), (MyFloat(2.5), 3.5)):
        want, got = _lengths(*_pair(nx_cls, fnx_cls, value))
        assert want == expected
        assert got == want, f"{type(value).__name__} weight diverged"


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_already_correct_decimal_and_plain_numbers(nx_cls, fnx_cls):
    from decimal import Decimal

    want, got = _lengths(*_pair(nx_cls, fnx_cls, Decimal("0.1"), Decimal("1.0")))
    assert got == want

    want, got = _lengths(*_pair(nx_cls, fnx_cls, 3, 4))
    assert want == 7
    assert got == want


# --------------------------------------------------------------------------
# The negative case for the FIX. Output parity cannot see over-delegation,
# because networkx and the native kernel agree on ordinary weights either way.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_ordinary_weights_stay_on_the_native_path(nx_cls, fnx_cls):
    """A 'delegate whenever unsure' patch would pass every test above.

    Ordinary small int and float weights must still be classified as NOT
    requiring NetworkX, or the fix has traded a correctness bug for a blanket
    perf regression on the hot path.
    """
    should_delegate = fnx._should_delegate_dijkstra_to_networkx

    gnx, gfx = _pair(nx_cls, fnx_cls, 3, 4)
    assert should_delegate(gfx, "weight") is False

    gnx, gfx = _pair(nx_cls, fnx_cls, 2.5, 0.25)
    assert should_delegate(gfx, "weight") is False

    # ...and the rows this bead is about must be classified as REQUIRING it.
    for bad in (2**60, 2**70, Fraction(1, 3)):
        _, gfx = _pair(nx_cls, fnx_cls, bad)
        assert should_delegate(gfx, "weight") is True, f"{bad!r} must delegate"


# --------------------------------------------------------------------------
# Serialization exposure must invalidate the native weight store before a
# retained state dictionary can be edited.  The copy routes are deliberately
# included: they must inherit or rebuild from that invalidated state, never
# clone the pre-exposure store and answer from stale weights.
# --------------------------------------------------------------------------


def _edge_attrs(graph):
    if graph.is_multigraph():
        return graph["a"]["b"][0]
    return graph["a"]["b"]


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
@pytest.mark.parametrize("bad_weight", [-1, float("inf"), "not-a-number"])
@pytest.mark.parametrize("copy_graph", [lambda graph: graph.copy(), copy.copy])
def test_retained_state_weight_then_copy_matches_networkx(
    nx_cls, fnx_cls, bad_weight, copy_graph
):
    """A state-owned live dict must not leave a copy's native weights stale."""
    reference, graph = _pair(nx_cls, fnx_cls, 1, 1)
    state = graph.__getstate__()
    attrs = state["edges"][0][-1]
    assert attrs is _edge_attrs(graph)
    attrs["weight"] = bad_weight
    _edge_attrs(reference)["weight"] = bad_weight

    reference_copy = copy_graph(reference)
    graph_copy = copy_graph(graph)
    want = _outcome(nx.dijkstra_path_length, reference_copy, "a", "c", weight="weight")
    got = _outcome(fnx.dijkstra_path_length, graph_copy, "a", "c", weight="weight")
    assert got == want, f"weight={bad_weight!r}: nx gave {want}, fnx gave {got}"
