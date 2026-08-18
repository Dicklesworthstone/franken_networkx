"""MultiDiGraph ``degree/in_degree/out_degree(nbunch, weight=...)``, bit-for-bit.

br-r37-c1-mdgwdegsubf. The directed sibling of br-r37-c1-mgwdegsubf.
``PyMultiDiGraph::weighted_degree_subset_impl`` serves all THREE nbunch spellings
and had an int fast path and no float one, so one float weight anywhere sent
every node to a per-node ``PyList`` + ``builtins.sum``. Measured 1.0203/1.0337
against networkx for the float total spelling while the INT spelling of the same
call ran 1.4360/1.4384 - the gap is the missing path, not the class.

The fix routes to ``weighted_total_degree_float_node{,_store}`` (Total) and
``weighted_directional_degree_float_node{,_store}`` (In/Out), the same per-node
accumulators the ALL-NODE paths already use.

WHY BIT PATTERNS AND NOT ``==``. Those accumulators are Neumaier-compensated
sums in Rust standing in for CPython's ``builtins.sum``, which is itself
compensated. Agreement is a LAST-ULP property: a plain left-to-right fold passes
every test written with small tidy weights and diverges precisely on the inputs
where compensation is the point. So results are compared as ``struct.pack``
bytes, over fixtures chosen to make an uncompensated sum visibly wrong.

DIRECTION IS THE PART MULTIGRAPH CANNOT TEST, and it is where this kernel can go
wrong in ways the undirected sibling cannot:

  * networkx's directed total degree is ``sum(succ) + sum(pred)`` - TWO
    independent compensated sums added with a plain ``+``. Folding all the
    weights into ONE compensated sum is a different number in the last ULP, so
    the total spelling is checked against fixtures where that difference is
    observable;
  * a SELF-LOOP appears in both succ and pred, so it lands twice in the total
    and once in each single direction;
  * an EDGELESS DIRECTION must yield networkx's int ``0`` - a sink asked for
    out_degree, a source asked for in_degree. The helpers return None there
    precisely so the int-0 survives, and the TYPE is part of parity.

These tests pass BEFORE the Rust change is compiled (they exercise the
PyList+sum fallback) and must keep passing after it.
"""

from __future__ import annotations

import struct

import networkx as nx
import pytest

import franken_networkx as fnx

SPELLINGS = ["degree", "in_degree", "out_degree"]

# 1e16 next to 1.0 is where an uncompensated fold drops the small term outright.
COMPENSATION_SENSITIVE = [1e16, 1.0, -1e16, 1.0, 0.1, 0.2, 0.3]
ORDINARY = [1.5, 2.25, 3.125, 0.5]


def _bits(value):
    if isinstance(value, float):
        return ("float", struct.pack("<d", value))
    return (type(value).__name__, value)


def _pairs(graph, spelling, nbunch, weight="w"):
    view = getattr(graph, spelling)
    return {str(n): _bits(d) for n, d in view(nbunch, weight=weight)}


def _assert_parity(got, want, nbunch, label, weight="w"):
    for spelling in SPELLINGS:
        assert _pairs(got, spelling, nbunch, weight) == _pairs(
            want, spelling, nbunch, weight
        ), f"{label}: {spelling}(nbunch, weight) diverged from networkx"


def _build(lib, *, bulk, succ=(), pred=(), selfloop=()):
    """``succ`` leave 'hub'; ``pred`` enter it; ``selfloop`` are hub->hub."""
    g = lib.MultiDiGraph()
    edges = [("hub", "s%d" % i, w) for i, w in enumerate(succ)]
    edges += [("p%d" % i, "hub", w) for i, w in enumerate(pred)]
    edges += [("hub", "hub", w) for w in selfloop]
    if bulk:
        g.add_weighted_edges_from(edges, weight="w")
    else:
        for u, v, w in edges:
            g.add_edge(u, v, w=w)
    g.add_node("isolated")
    return g


def _nodes(graph):
    return [str(n) for n in graph]


@pytest.mark.parametrize("bulk", [True, False], ids=["bulk_built", "per_edge_built"])
@pytest.mark.parametrize(
    "weights",
    [COMPENSATION_SENSITIVE, ORDINARY, [0.1] * 40, [1e308, 1e308, -1e308]],
    ids=["compensation_sensitive", "ordinary", "many_tenths", "overflow_row"],
)
def test_float_weights_match_networkx_bitwise(bulk, weights):
    got = _build(fnx, bulk=bulk, succ=weights, pred=list(reversed(weights)))
    want = _build(nx, bulk=bulk, succ=weights, pred=list(reversed(weights)))
    _assert_parity(got, want, _nodes(got), label=f"bulk={bulk}")


@pytest.mark.parametrize("bulk", [True, False], ids=["bulk_built", "per_edge_built"])
def test_total_is_two_sums_added_not_one_fold(bulk):
    """nx totals ``sum(succ) + sum(pred)``; one big fold is a different ULP.

    The two directions are given values that cancel WITHIN a direction, so
    summing each side separately and adding is observably different from
    concatenating everything into a single compensated sum.
    """
    succ = [1e16, 1.0, -1e16]
    pred = [1e16, 1.0, -1e16]
    got = _build(fnx, bulk=bulk, succ=succ, pred=pred)
    want = _build(nx, bulk=bulk, succ=succ, pred=pred)
    _assert_parity(got, want, ["hub"], label="two_sums")
    # Also pin it against Python's own arithmetic, so the test does not merely
    # assert that two implementations agree with each other.
    expected = sum(succ) + sum(pred)
    assert _bits(dict(got.degree(["hub"], weight="w"))["hub"]) == _bits(expected)


@pytest.mark.parametrize("bulk", [True, False], ids=["bulk_built", "per_edge_built"])
def test_self_loop_counts_twice_in_total_and_once_per_direction(bulk):
    got = _build(fnx, bulk=bulk, succ=ORDINARY, pred=ORDINARY, selfloop=(2.5, 0.75))
    want = _build(nx, bulk=bulk, succ=ORDINARY, pred=ORDINARY, selfloop=(2.5, 0.75))
    _assert_parity(got, want, _nodes(got), label="selfloop")

    loops = 2.5 + 0.75
    plain = _build(nx, bulk=bulk, succ=ORDINARY, pred=ORDINARY)
    total_delta = (
        dict(got.degree(["hub"], weight="w"))["hub"]
        - dict(plain.degree(["hub"], weight="w"))["hub"]
    )
    out_delta = (
        dict(got.out_degree(["hub"], weight="w"))["hub"]
        - dict(plain.out_degree(["hub"], weight="w"))["hub"]
    )
    assert total_delta == pytest.approx(2 * loops)
    assert out_delta == pytest.approx(loops)


@pytest.mark.parametrize("bulk", [True, False], ids=["bulk_built", "per_edge_built"])
def test_a_self_loop_only_node_matches(bulk):
    got = _build(fnx, bulk=bulk, selfloop=COMPENSATION_SENSITIVE)
    want = _build(nx, bulk=bulk, selfloop=COMPENSATION_SENSITIVE)
    _assert_parity(got, want, ["hub", "isolated"], label="selfloop_only")


@pytest.mark.parametrize("bulk", [True, False], ids=["bulk_built", "per_edge_built"])
def test_an_edgeless_direction_yields_int_zero(bulk):
    """A pure source has no in-edges; a pure sink has no out-edges."""
    got = _build(fnx, bulk=bulk, succ=ORDINARY)
    want = _build(nx, bulk=bulk, succ=ORDINARY)
    _assert_parity(got, want, _nodes(got), label="edgeless_direction")

    source_in = dict(got.in_degree(["hub"], weight="w"))["hub"]
    assert isinstance(source_in, int) and not isinstance(source_in, bool)
    assert source_in == 0

    sink = "s0"
    sink_out = dict(got.out_degree([sink], weight="w"))[sink]
    assert isinstance(sink_out, int) and not isinstance(sink_out, bool)
    assert sink_out == 0


def test_missing_weight_stays_on_the_exact_path():
    got, want = fnx.MultiDiGraph(), nx.MultiDiGraph()
    for g in (got, want):
        g.add_edge("hub", "a", w=1.5)
        g.add_edge("hub", "a")  # no weight -> nx default int 1
        g.add_edge("b", "hub", w=2.5)
    _assert_parity(got, want, ["hub", "a", "b"], label="missing_weight")


def test_mixed_int_and_float_matches_networkx():
    got, want = fnx.MultiDiGraph(), nx.MultiDiGraph()
    for g in (got, want):
        g.add_edge("hub", "a", w=1)
        g.add_edge("hub", "a", w=2.5)
        g.add_edge("b", "hub", w=3)
    _assert_parity(got, want, ["hub", "a", "b"], label="mixed")


def test_all_int_weights_keep_int_type():
    got, want = fnx.MultiDiGraph(), nx.MultiDiGraph()
    for g in (got, want):
        g.add_edge("hub", "a", w=2)
        g.add_edge("b", "hub", w=3)
        g.add_edge("hub", "hub", w=4)
    _assert_parity(got, want, ["hub", "a", "b"], label="all_int")
    assert isinstance(dict(got.degree(["hub"], weight="w"))["hub"], int)


def test_mutating_the_graph_flips_authority_and_stays_exact():
    got, want = fnx.MultiDiGraph(), nx.MultiDiGraph()
    for g in (got, want):
        g.add_weighted_edges_from(
            [("hub", "a", w) for w in COMPENSATION_SENSITIVE]
            + [("b", "hub", w) for w in ORDINARY],
            weight="w",
        )
    _assert_parity(got, want, ["hub", "a", "b"], label="clean")

    for g in (got, want):
        g.add_edge("hub", "a", w=0.5)
        g["hub"]["a"][0]["w"] = 7.25
    _assert_parity(got, want, ["hub", "a", "b"], label="after_mutation")

    for g in (got, want):
        g.remove_edge("hub", "a", key=1)
    _assert_parity(got, want, ["hub", "a", "b"], label="after_removal")


def test_nbunch_shapes_match_networkx():
    got, want = fnx.MultiDiGraph(), nx.MultiDiGraph()
    for g in (got, want):
        g.add_edge("hub", "a", w=1.5)
        g.add_edge("b", "hub", w=2.5)
    for nbunch in (["hub", "absent", "a"], ["hub", "hub"], [], ("hub", "a")):
        for spelling in SPELLINGS:
            got_pairs = [
                (str(n), _bits(d))
                for n, d in getattr(got, spelling)(list(nbunch), weight="w")
            ]
            want_pairs = [
                (str(n), _bits(d))
                for n, d in getattr(want, spelling)(list(nbunch), weight="w")
            ]
            assert got_pairs == want_pairs, f"{spelling} nbunch {nbunch!r} diverged"


def test_a_non_default_weight_key_is_honoured():
    got, want = fnx.MultiDiGraph(), nx.MultiDiGraph()
    for g in (got, want):
        g.add_edge("hub", "a", w=1.5, capacity=10.25)
        g.add_edge("b", "hub", w=2.5, capacity=0.125)
    for key in ("w", "capacity", "absent_key"):
        _assert_parity(got, want, ["hub", "a", "b"], label=f"key={key}", weight=key)


def test_agrees_with_the_all_node_spelling():
    """The subset and all-node paths must not disagree with each other.

    The all-node path already had these accumulators; the subset path is gaining
    them. Disagreement means one of the two is wrong, and this catches it with no
    reference to networkx at all.
    """
    g = _build(
        fnx,
        bulk=True,
        succ=COMPENSATION_SENSITIVE,
        pred=ORDINARY,
        selfloop=(1.5,),
    )
    for spelling in SPELLINGS:
        view = getattr(g, spelling)
        every = {str(n): _bits(d) for n, d in view(weight="w")}
        subset = {str(n): _bits(d) for n, d in view(_nodes(g), weight="w")}
        assert every == subset, f"{spelling}: subset disagrees with all-node"
