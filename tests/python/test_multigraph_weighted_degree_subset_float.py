"""MultiGraph ``degree(nbunch, weight=...)`` with FLOAT weights, bit-for-bit.

br-r37-c1-mgwdegsubf. ``PyMultiGraph::_native_weighted_degree_subset`` had an
INT fast path and no float one, so a float-weighted graph fell through to a
per-node ``PyList`` + ``builtins.sum``. Measured 0.8753/0.8620 against networkx
at N=400 while the int spelling of the same call ran 1.0456/1.0429 and
MultiDiGraph float ran 1.0203/1.0337 - the last cell of the weighted-attr family
still below networkx (ledger row 2026-08-18).

The fix routes the float case through ``weighted_degree_float_node`` /
``weighted_degree_float_node_store``, the SAME per-node accumulators the all-node
weighted-degree path already uses.

WHY THIS FILE EXISTS RATHER THAN TRUSTING THAT ARGUMENT. Those accumulators are
Neumaier-compensated sums in Rust standing in for CPython's ``builtins.sum``,
which is itself compensated. Agreement there is a LAST-ULP property: a plain
left-to-right fold would pass every test written with small tidy weights and
diverge on the values that actually matter. So the comparisons here are on the
BIT PATTERN of the result, not ``==``, and the fixtures deliberately include
magnitudes where compensation is load-bearing.

These tests pass BEFORE the Rust change is compiled (they exercise the
PyList+sum fallback) and must keep passing after it. That is the point: they pin
the behaviour the fast path has to reproduce, so a rebuild that changes any of
these answers is a regression rather than a surprise.

PINNED HERE, each of which routes differently inside the kernel:

  * pure float -> the new fast path;
  * any missing weight (networkx defaults to int 1), any int, any mixed row ->
    must still take the exact fallback, because the helpers return None there;
  * an edgeless node -> networkx yields int ``0``, so the TYPE is part of parity;
  * self-loops, which networkx's undirected ``MultiDegreeView`` counts TWICE,
    and which the kernel accumulates as a SECOND compensated sum added to the
    first with a plain ``+``;
  * bulk-built vs per-edge-built graphs, which select the store twin and the
    mirror twin respectively, and a MUTATED graph, which flips authority back to
    the mirror.
"""

from __future__ import annotations

import struct

import networkx as nx
import pytest

import franken_networkx as fnx


def _bits(value):
    """Compare floats by bit pattern; ``==`` hides the ULP this lever risks."""
    if isinstance(value, float):
        return ("float", struct.pack("<d", value))
    return (type(value).__name__, value)


def _degree_pairs(graph, nbunch, weight="w"):
    return {str(n): _bits(d) for n, d in graph.degree(nbunch, weight=weight)}


def _assert_parity(got_graph, want_graph, nbunch, weight="w", label=""):
    got = _degree_pairs(got_graph, nbunch, weight)
    want = _degree_pairs(want_graph, nbunch, weight)
    assert got == want, f"{label}: weighted degree diverged from networkx"


# The magnitudes matter: 1e16 next to 1.0 is where a naive fold loses the small
# term entirely and a compensated sum keeps it.
COMPENSATION_SENSITIVE = [1e16, 1.0, -1e16, 1.0, 0.1, 0.2, 0.3]
ORDINARY = [1.5, 2.25, 3.125, 0.5]


def _build(lib, weights, *, bulk, selfloop_weights=()):
    """Bulk build leaves the native store authoritative; per-edge populates the mirror."""
    g = lib.MultiGraph()
    edges = [("a", "b", w) for w in weights]
    edges += [("a", "a", w) for w in selfloop_weights]
    if bulk:
        g.add_weighted_edges_from(edges, weight="w")
    else:
        for u, v, w in edges:
            g.add_edge(u, v, w=w)
    g.add_node("isolated")
    return g


@pytest.mark.parametrize("bulk", [True, False], ids=["bulk_built", "per_edge_built"])
@pytest.mark.parametrize(
    "weights",
    [COMPENSATION_SENSITIVE, ORDINARY, [0.1] * 40, [1e308, 1e308, -1e308]],
    ids=["compensation_sensitive", "ordinary", "many_tenths", "overflow_row"],
)
def test_float_weights_match_networkx_bitwise(bulk, weights):
    got = _build(fnx, weights, bulk=bulk)
    want = _build(nx, weights, bulk=bulk)
    _assert_parity(got, want, ["a", "b", "isolated"], label=f"bulk={bulk}")


@pytest.mark.parametrize("bulk", [True, False], ids=["bulk_built", "per_edge_built"])
def test_self_loop_weight_is_counted_twice(bulk):
    """networkx's undirected MultiDegreeView double counts a self-loop."""
    got = _build(fnx, ORDINARY, bulk=bulk, selfloop_weights=(2.5, 0.75))
    want = _build(nx, ORDINARY, bulk=bulk, selfloop_weights=(2.5, 0.75))
    _assert_parity(got, want, ["a", "b"], label="selfloop")
    # And the double count is real, not an artifact of both being wrong.
    plain = _build(nx, ORDINARY, bulk=bulk)
    assert dict(got.degree(["a"], weight="w"))["a"] != dict(plain.degree(["a"], weight="w"))["a"]


@pytest.mark.parametrize("bulk", [True, False], ids=["bulk_built", "per_edge_built"])
def test_a_self_loop_only_node_matches(bulk):
    got = _build(fnx, [], bulk=bulk, selfloop_weights=COMPENSATION_SENSITIVE)
    want = _build(nx, [], bulk=bulk, selfloop_weights=COMPENSATION_SENSITIVE)
    _assert_parity(got, want, ["a", "isolated"], label="selfloop_only")


def test_missing_weight_stays_on_the_exact_path():
    """A missing weight is networkx's int 1; the float helpers must decline."""
    got, want = fnx.MultiGraph(), nx.MultiGraph()
    for g in (got, want):
        g.add_edge("a", "b", w=1.5)
        g.add_edge("a", "b")  # no weight at all
        g.add_edge("a", "c", w=2.5)
    _assert_parity(got, want, ["a", "b", "c"], label="missing_weight")


def test_mixed_int_and_float_matches_networkx():
    got, want = fnx.MultiGraph(), nx.MultiGraph()
    for g in (got, want):
        g.add_edge("a", "b", w=1)
        g.add_edge("a", "b", w=2.5)
        g.add_edge("a", "c", w=3)
    _assert_parity(got, want, ["a", "b", "c"], label="mixed")


def test_all_int_weights_keep_int_type():
    """The int path must be untouched, including the RESULT TYPE."""
    got, want = fnx.MultiGraph(), nx.MultiGraph()
    for g in (got, want):
        g.add_edge("a", "b", w=2)
        g.add_edge("a", "b", w=3)
        g.add_edge("a", "a", w=4)
    _assert_parity(got, want, ["a", "b"], label="all_int")
    assert isinstance(dict(got.degree(["a"], weight="w"))["a"], int)


def test_an_edgeless_node_yields_int_zero():
    got, want = fnx.MultiGraph(), nx.MultiGraph()
    for g in (got, want):
        g.add_edge("a", "b", w=1.5)
        g.add_node("lonely")
    _assert_parity(got, want, ["lonely"], label="edgeless")
    value = dict(got.degree(["lonely"], weight="w"))["lonely"]
    assert isinstance(value, int) and not isinstance(value, bool)
    assert value == 0


def test_mutating_the_graph_flips_authority_and_stays_exact():
    """A write makes the mirror authoritative; the answer must not move."""
    got, want = fnx.MultiGraph(), nx.MultiGraph()
    for g in (got, want):
        g.add_weighted_edges_from([("a", "b", w) for w in COMPENSATION_SENSITIVE], weight="w")
    _assert_parity(got, want, ["a", "b"], label="clean")

    for g in (got, want):
        g.add_edge("a", "b", w=0.5)          # new parallel edge
        g["a"]["b"][0]["w"] = 7.25           # in-place attr edit on an existing edge
    _assert_parity(got, want, ["a", "b"], label="after_mutation")

    for g in (got, want):
        g.remove_edge("a", "b", key=1)
    _assert_parity(got, want, ["a", "b"], label="after_removal")


def test_nbunch_shapes_match_networkx():
    """Absent, duplicated and non-string nodes all keep networkx's semantics."""
    got, want = fnx.MultiGraph(), nx.MultiGraph()
    for g in (got, want):
        g.add_edge("a", "b", w=1.5)
        g.add_edge("b", "c", w=2.5)
    for nbunch in (
        ["a", "absent", "b"],
        ["a", "a", "b"],          # duplicates are NOT deduped by nx
        [],
        ("a", "b"),
        {"a", "b"},
    ):
        got_pairs = [(str(n), _bits(d)) for n, d in got.degree(list(nbunch), weight="w")]
        want_pairs = [(str(n), _bits(d)) for n, d in want.degree(list(nbunch), weight="w")]
        assert got_pairs == want_pairs, f"nbunch {nbunch!r} diverged"


def test_unhashable_nbunch_element_raises_like_networkx():
    got, want = fnx.MultiGraph(), nx.MultiGraph()
    for g in (got, want):
        g.add_edge("a", "b", w=1.5)

    def run(graph):
        try:
            return ("ok", list(graph.degree(["a", ["unhashable"]], weight="w")))
        except Exception as exc:  # noqa: BLE001 - comparing the raise itself
            return (type(exc).__name__, str(exc))

    got_kind, _ = run(got)
    want_kind, _ = run(want)
    assert got_kind == want_kind


def test_a_non_default_weight_key_is_honoured():
    """The fast path is keyed on the requested attribute, not on 'weight'."""
    got, want = fnx.MultiGraph(), nx.MultiGraph()
    for g in (got, want):
        g.add_edge("a", "b", w=1.5, capacity=10.25)
        g.add_edge("a", "b", w=2.5, capacity=0.125)
    for key in ("w", "capacity", "absent_key"):
        assert _degree_pairs(got, ["a", "b"], key) == _degree_pairs(want, ["a", "b"], key), key


def test_agrees_with_the_all_node_spelling():
    """degree(nbunch) and degree() must not disagree with each other.

    The all-node path already had a float accumulator; the subset path is
    gaining the same one. If the two ever disagree, one of them is wrong, and
    this catches it without reference to networkx at all.
    """
    g = _build(fnx, COMPENSATION_SENSITIVE, bulk=True, selfloop_weights=(1.5,))
    every = {str(n): _bits(d) for n, d in g.degree(weight="w")}
    subset = _degree_pairs(g, [str(n) for n in g])
    assert every == subset
