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


SMALL_WEIGHTS = [2.0**-50, 2.0**-500, float.fromhex("0x0.0000000000001p-1022")]


def _close_weight_alternatives(nx_cls, fnx_cls, unit):
    """The first path is longer; two later paths tie exactly, one via zero."""
    graphs = nx_cls(), fnx_cls()
    for graph in graphs:
        graph.add_edge("s", "t", weight=5 * unit)
        graph.add_edge("s", "a", weight=unit)
        graph.add_edge("a", "t", weight=unit)
        graph.add_edge("s", "b", weight=2 * unit)
        graph.add_edge("b", "t", weight=0.0)
        graph.add_node("isolated")
        if graph.is_multigraph():
            graph.add_edge("s", "a", weight=4 * unit)
    return graphs


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
@pytest.mark.parametrize("unit", SMALL_WEIGHTS)
def test_sub_epsilon_dijkstra_paths_and_distances_match_networkx(nx_cls, fnx_cls, unit):
    gnx, gfx = _close_weight_alternatives(nx_cls, fnx_cls, unit)
    assert fnx._should_delegate_dijkstra_to_networkx(gfx, "weight") is False
    assert nx.dijkstra_path_length(gnx, "s", "t") == 2 * unit
    for name in ("dijkstra_path", "dijkstra_path_length", "bidirectional_dijkstra"):
        assert getattr(fnx, name)(gfx, "s", "t") == getattr(nx, name)(gnx, "s", "t")
    for name in ("shortest_path", "shortest_path_length"):
        assert getattr(fnx, name)(gfx, "s", "t", weight="weight") == getattr(nx, name)(
            gnx, "s", "t", weight="weight"
        )
    for cutoff in (None, 3 * unit):
        for name in (
            "single_source_dijkstra", "single_source_dijkstra_path",
            "single_source_dijkstra_path_length", "dijkstra_predecessor_and_distance",
        ):
            assert getattr(fnx, name)(gfx, "s", cutoff=cutoff) == getattr(nx, name)(
                gnx, "s", cutoff=cutoff
            )
        for name in (
            "multi_source_dijkstra", "multi_source_dijkstra_path",
            "multi_source_dijkstra_path_length",
        ):
            assert getattr(fnx, name)(gfx, ["s", "isolated"], cutoff=cutoff) == getattr(nx, name)(
                gnx, ["s", "isolated"], cutoff=cutoff
            )
    assert fnx.single_source_dijkstra(gfx, "s", target="t") == nx.single_source_dijkstra(
        gnx, "s", target="t"
    )
    for name in ("all_pairs_dijkstra", "all_pairs_dijkstra_path", "all_pairs_dijkstra_path_length"):
        assert list(getattr(fnx, name)(gfx)) == list(getattr(nx, name)(gnx))


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
@pytest.mark.parametrize("unit", SMALL_WEIGHTS)
def test_sub_epsilon_bellman_ford_and_exact_path_ties_match_networkx(nx_cls, fnx_cls, unit):
    gnx, gfx = _close_weight_alternatives(nx_cls, fnx_cls, unit)
    for name in ("bellman_ford_path", "bellman_ford_path_length"):
        assert getattr(fnx, name)(gfx, "s", "t") == getattr(nx, name)(gnx, "s", "t")
    for name in (
        "single_source_bellman_ford", "single_source_bellman_ford_path",
        "single_source_bellman_ford_path_length",
    ):
        assert getattr(fnx, name)(gfx, "s") == getattr(nx, name)(gnx, "s")
    for method in ("dijkstra", "bellman-ford"):
        got = list(fnx.all_shortest_paths(gfx, "s", "t", weight="weight", method=method))
        want = list(nx.all_shortest_paths(gnx, "s", "t", weight="weight", method=method))
        assert got == want
        assert ["s", "t"] not in got  # Close distances are not equal distances.
    for name in ("all_pairs_bellman_ford_path", "all_pairs_bellman_ford_path_length"):
        assert list(getattr(fnx, name)(gfx)) == list(getattr(nx, name)(gnx))


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_representable_improvement_near_one_is_not_a_tie(nx_cls, fnx_cls):
    gnx, gfx = nx_cls(), fnx_cls()
    for graph in (gnx, gfx):
        graph.add_edge("s", "t", weight=1.0 + 2.0**-50)
        graph.add_edge("s", "a", weight=0.5)
        graph.add_edge("a", "t", weight=0.5)
    assert fnx.dijkstra_path_length(gfx, "s", "t") == nx.dijkstra_path_length(gnx, "s", "t") == 1.0
    assert fnx.dijkstra_path(gfx, "s", "t") == nx.dijkstra_path(gnx, "s", "t") == ["s", "a", "t"]


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
@pytest.mark.parametrize("unit", SMALL_WEIGHTS)
def test_bellman_ford_detects_sub_epsilon_negative_cycles(nx_cls, fnx_cls, unit):
    gnx, gfx = nx_cls(), fnx_cls()
    for graph in (gnx, gfx):
        graph.add_edge("s", "a", weight=0.0)
        graph.add_edge("a", "t", weight=-unit)
        if graph.is_directed():
            graph.add_edge("t", "a", weight=0.0)
    with pytest.raises(nx.NetworkXUnbounded):
        nx.single_source_bellman_ford_path_length(gnx, "s")
    with pytest.raises(fnx.NetworkXUnbounded):
        fnx.single_source_bellman_ford_path_length(gfx, "s")


def _overflowed_distance_pair(nx_cls, fnx_cls, weight="weight"):
    graphs = nx_cls(), fnx_cls()
    for graph in graphs:
        for u, v, value in (
            ("s", "a", 1e308),
            ("a", "b", 1e308),
            ("a", "c", 1e308),
            ("c", "t", 0.0),
            ("b", "c", 0.0),
            ("b", "b", 0.0),
            ("s", "s", 0.0),
        ):
            graph.add_edge(u, v, **{weight: value})
        # A missing attribute still contributes the default weight of one
        # after the preceding path sum has overflowed.
        graph.add_edge("b", "t")
        graph.add_node("isolated")
        if graph.is_multigraph():
            graph.add_edge("s", "a", **{weight: 1.5e308})
    return graphs


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_overflowed_dijkstra_target_queries_preserve_reachability(nx_cls, fnx_cls):
    # Each API gets a fresh graph, then repeats against its warmed native data.
    # All edge weights are finite: only accumulated distances become infinity.
    for name in (
        "dijkstra_path", "dijkstra_path_length", "bidirectional_dijkstra",
        "shortest_path", "shortest_path_length",
    ):
        gnx, gfx = _overflowed_distance_pair(nx_cls, fnx_cls)
        assert fnx._should_delegate_dijkstra_to_networkx(gfx, "weight") is False
        kwargs = {"weight": "weight"} if name.startswith("shortest_") else {}
        expected = getattr(nx, name)(gnx, "s", "t", **kwargs)
        for _ in range(2):
            assert getattr(fnx, name)(gfx, "s", "t", **kwargs) == expected
        with pytest.raises(nx.NetworkXNoPath):
            getattr(nx, name)(gnx, "s", "isolated", **kwargs)
        with pytest.raises(fnx.NetworkXNoPath):
            getattr(fnx, name)(gfx, "s", "isolated", **kwargs)


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_overflowed_dijkstra_sources_and_cutoffs_match_networkx(nx_cls, fnx_cls):
    gnx, gfx = _overflowed_distance_pair(nx_cls, fnx_cls)
    expected = {"s": 0, "a": 1e308, "b": float("inf"),
                "c": float("inf"), "t": float("inf")}
    assert nx.single_source_dijkstra_path_length(gnx, "s") == expected
    # Exercise the length-only route both before and after its native cache exists.
    for _ in range(2):
        assert fnx.single_source_dijkstra_path_length(gfx, "s") == expected
    for cutoff in (None, 1e308, float("inf")):
        for name in (
            "single_source_dijkstra", "single_source_dijkstra_path",
            "single_source_dijkstra_path_length", "dijkstra_predecessor_and_distance",
        ):
            assert getattr(fnx, name)(gfx, "s", cutoff=cutoff) == getattr(nx, name)(
                gnx, "s", cutoff=cutoff
            )
        for name in (
            "multi_source_dijkstra", "multi_source_dijkstra_path",
            "multi_source_dijkstra_path_length",
        ):
            assert getattr(fnx, name)(gfx, ["s", "isolated"], cutoff=cutoff) == getattr(
                nx, name
            )(gnx, ["s", "isolated"], cutoff=cutoff)
        for name, source in (
            ("single_source_dijkstra", "s"),
            ("multi_source_dijkstra", ["s"]),
        ):
            for target in ("t", "isolated"):
                assert _outcome(
                    getattr(fnx, name), gfx, source, target=target, cutoff=cutoff
                ) == _outcome(
                    getattr(nx, name), gnx, source, target=target, cutoff=cutoff
                )


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_overflowed_dijkstra_all_pairs_keeps_reachable_infinity(nx_cls, fnx_cls):
    gnx, gfx = _overflowed_distance_pair(nx_cls, fnx_cls)
    for cutoff in (None, 1e308, float("inf")):
        for name in (
            "all_pairs_dijkstra", "all_pairs_dijkstra_path",
            "all_pairs_dijkstra_path_length",
        ):
            assert list(getattr(fnx, name)(gfx, cutoff=cutoff)) == list(
                getattr(nx, name)(gnx, cutoff=cutoff)
            )
    if not gfx.is_multigraph():
        # The packed binding is also used independently of the public lazy
        # all-pairs generators, including by metric_closure's Graph fast path.
        expected = dict(nx.all_pairs_dijkstra(gnx))
        for _ in range(2):
            assert fnx._raw_all_pairs_dijkstra(gfx, weight="weight") == expected


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_finite_dijkstra_alternative_replaces_pending_infinity(nx_cls, fnx_cls):
    gnx, gfx = nx_cls(), fnx_cls()
    for graph in (gnx, gfx):
        graph.add_weighted_edges_from([
            ("s", "a", 1e308), ("a", "t", 1e308),
            ("s", "b", 1.5e308), ("b", "t", 0.0),
        ])
        if graph.is_multigraph():
            graph.add_edge("s", "b", weight=1.75e308)
    expected = (1.5e308, ["s", "b", "t"])
    assert nx.single_source_dijkstra(gnx, "s", target="t") == expected
    assert fnx._should_delegate_dijkstra_to_networkx(gfx, "weight") is False
    for _ in range(2):
        assert fnx.single_source_dijkstra(gfx, "s", target="t") == expected
        assert fnx.dijkstra_path(gfx, "s", "t") == expected[1]
        assert fnx.dijkstra_path_length(gfx, "s", "t") == expected[0]
        assert fnx.bidirectional_dijkstra(gfx, "s", "t") == nx.bidirectional_dijkstra(
            gnx, "s", "t"
        )
    assert fnx.multi_source_dijkstra(gfx, ["s"], target="t") == expected


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_overflowed_dijkstra_named_and_callable_weights_match_networkx(nx_cls, fnx_cls):
    gnx, gfx = _overflowed_distance_pair(nx_cls, fnx_cls, weight="cost")

    def cost(u, v, data):
        if gnx.is_multigraph():
            return min(attrs.get("cost", 1) for attrs in data.values())
        return data.get("cost", 1)

    for weight in ("cost", cost):
        for name in ("dijkstra_path", "dijkstra_path_length", "bidirectional_dijkstra"):
            assert getattr(fnx, name)(gfx, "s", "t", weight=weight) == getattr(nx, name)(
                gnx, "s", "t", weight=weight
            )
        for cutoff in (1e308, float("inf")):
            assert fnx.single_source_dijkstra(gfx, "s", cutoff=cutoff, weight=weight) == (
                nx.single_source_dijkstra(gnx, "s", cutoff=cutoff, weight=weight)
            )
            assert fnx.multi_source_dijkstra(
                gfx, ["s", "isolated"], cutoff=cutoff, weight=weight
            ) == nx.multi_source_dijkstra(
                gnx, ["s", "isolated"], cutoff=cutoff, weight=weight
            )
        assert list(fnx.all_pairs_dijkstra_path_length(gfx, weight=weight)) == list(
            nx.all_pairs_dijkstra_path_length(gnx, weight=weight)
        )


def test_overflowed_metric_closure_keeps_connected_graph():
    gnx, gfx = nx.Graph(), fnx.Graph()
    for graph in (gnx, gfx):
        graph.add_weighted_edges_from([
            ("s", "a", 1e308), ("a", "b", 1e308), ("b", "t", 1.0),
        ])
    with pytest.warns(DeprecationWarning, match="metric_closure"):
        expected = nx.approximation.metric_closure(gnx)
    with pytest.warns(DeprecationWarning, match="metric_closure"):
        actual = fnx.approximation.metric_closure(gfx)
    assert set(actual) == set(expected)
    assert actual.number_of_edges() == expected.number_of_edges()
    for u, v, attrs in expected.edges(data=True):
        assert dict(actual[u][v]) == attrs
    assert actual["s"]["t"]["distance"] == float("inf")
    assert actual["s"]["t"]["path"] == ["s", "a", "b", "t"]


# The all-shortest-path enumeration kernels are separate from target/source
# Dijkstra kernels; keep this regression separate from the reachability cases.
@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_overflowed_all_shortest_paths_preserves_order_and_terminates_cycles(nx_cls, fnx_cls):
    gnx, gfx = _overflowed_distance_pair(nx_cls, fnx_cls)
    for graph in (gnx, gfx):
        graph.remove_edge("s", "s")
        if graph.is_directed():
            graph.add_edge("c", "b", weight=0.0)
    expected = list(nx.all_shortest_paths(gnx, "s", "t", weight="weight", method="dijkstra"))
    assert expected
    assert all(len(path) == len(set(path)) for path in expected)
    for _ in range(2):
        assert list(fnx.all_shortest_paths(
            gfx, "s", "t", weight="weight", method="dijkstra"
        )) == expected
    with pytest.raises(nx.NetworkXNoPath):
        list(nx.all_shortest_paths(gnx, "s", "isolated", weight="weight", method="dijkstra"))
    with pytest.raises(fnx.NetworkXNoPath):
        list(fnx.all_shortest_paths(gfx, "s", "isolated", weight="weight", method="dijkstra"))
    gnx, gfx = nx_cls(), fnx_cls()
    for graph in (gnx, gfx):
        graph.add_weighted_edges_from([
            ("s", "a", 1e308), ("a", "t", 1e308),
            ("s", "b", 1.5e308), ("b", "t", 0.0),
        ])
    expected = list(nx.all_shortest_paths(gnx, "s", "t", weight="weight", method="dijkstra"))
    assert expected == [["s", "b", "t"]]
    assert list(fnx.all_shortest_paths(
        gfx, "s", "t", weight="weight", method="dijkstra"
    )) == expected


def _assert_dijkstra_observables(actual, expected):
    """Dict equality alone misses finalize order and int/float type changes."""
    assert type(actual) is type(expected)
    if isinstance(expected, dict):
        assert list(actual) == list(expected)
        for node in expected:
            _assert_dijkstra_observables(actual[node], expected[node])
    elif isinstance(expected, (list, tuple)):
        assert len(actual) == len(expected)
        for got, want in zip(actual, expected):
            _assert_dijkstra_observables(got, want)
    else:
        assert actual == expected


def _reject_python_dijkstra_fallback(monkeypatch):
    def unexpected_fallback(*args, **kwargs):
        pytest.fail("finite float weights unexpectedly left the native Dijkstra route")

    for name in (
        "_multi_source_dijkstra_inproc", "_dijkstra_path_length_inproc",
        "_dijkstra_multisource_inproc",
        "_call_networkx_for_parity", "_call_networkx_for_dijkstra_parity",
    ):
        monkeypatch.setattr(fnx, name, unexpected_fallback)


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_overflowed_generic_target_queries_keep_reverse_discovery(
    nx_cls, fnx_cls, monkeypatch
):
    gnx, gfx = _overflowed_distance_pair(nx_cls, fnx_cls)
    assert fnx._should_delegate_dijkstra_to_networkx(gfx, "weight") is False
    _reject_python_dijkstra_fallback(monkeypatch)
    for name in ("shortest_path", "shortest_path_length"):
        expected = getattr(nx, name)(
            gnx, target="t", weight="weight", backend="networkx"
        )
        assert "s" in expected and "isolated" not in expected
        for _ in range(2):
            actual = getattr(fnx, name)(gfx, target="t", weight="weight")
            _assert_dijkstra_observables(actual, expected)
        # Directed graphs reverse their traversal for a target-only query;
        # an isolated target must still produce only its own zero/self path.
        _assert_dijkstra_observables(
            getattr(fnx, name)(gfx, target="isolated", weight="weight"),
            getattr(nx, name)(
                gnx, target="isolated", weight="weight", backend="networkx"
            ),
        )


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_overflowed_dijkstra_self_queries_reset_reached_nodes_as_sources(
    nx_cls, fnx_cls, monkeypatch
):
    gnx, gfx = _overflowed_distance_pair(nx_cls, fnx_cls)
    _reject_python_dijkstra_fallback(monkeypatch)
    # Populate reusable state first: b is reached at infinity in this query,
    # then becomes a source with distance zero and no predecessor below.
    assert fnx.single_source_dijkstra_path_length(gfx, "s")["b"] == float("inf")
    for source in ("s", "b", "isolated"):
        for name in (
            "dijkstra_path", "dijkstra_path_length", "bidirectional_dijkstra",
            "shortest_path", "shortest_path_length",
        ):
            _assert_dijkstra_observables(
                getattr(fnx, name)(gfx, source, source, weight="weight"),
                getattr(nx, name)(
                    gnx, source, source, weight="weight", backend="networkx"
                ),
            )
        for cutoff in (None, -1, 1e308, float("inf")):
            _assert_dijkstra_observables(
                fnx.single_source_dijkstra(
                    gfx, source, target=source, cutoff=cutoff
                ),
                nx.single_source_dijkstra(
                    gnx, source, target=source, cutoff=cutoff, backend="networkx"
                ),
            )


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_overflowed_dijkstra_competing_sources_keep_first_tie_and_roots(
    nx_cls, fnx_cls, monkeypatch
):
    gnx, gfx = nx_cls(), fnx_cls()
    for graph in (gnx, gfx):
        # Insertion order deliberately differs from the first source order.
        graph.add_nodes_from(["left", "right", "a", "b", "join", "tail", "isolated"])
        graph.add_weighted_edges_from([
            ("left", "right", 0.0), ("right", "left", 0.0),
            ("left", "a", 1e308), ("right", "b", 1e308),
            ("a", "join", 1e308), ("b", "join", 1e308),
            ("join", "tail", 0.0), ("tail", "join", 0.0),
            ("join", "join", 0.0),
        ])
    assert fnx._should_delegate_dijkstra_to_networkx(gfx, "weight") is False
    # MultiDiGraph's public multisource float route intentionally uses the
    # in-process implementation; the other three classes have native routes.
    if not (gfx.is_directed() and gfx.is_multigraph()):
        _reject_python_dijkstra_fallback(monkeypatch)
    for sources in (["right", "left"], ["left", "right"]):
        expected = nx.multi_source_dijkstra(gnx, sources, backend="networkx")
        branch = "b" if sources[0] == "right" else "a"
        assert expected[1]["join"] == [sources[0], branch, "join"]
        for cutoff in (None, -1, 1e308, float("inf")):
            for name in (
                "multi_source_dijkstra", "multi_source_dijkstra_path",
                "multi_source_dijkstra_path_length",
            ):
                _assert_dijkstra_observables(
                    getattr(fnx, name)(gfx, sources, cutoff=cutoff),
                    getattr(nx, name)(
                        gnx, sources, cutoff=cutoff, backend="networkx"
                    ),
                )
            for target in ("join", sources[0], sources[1]):
                _assert_dijkstra_observables(
                    _outcome(
                        fnx.multi_source_dijkstra, gfx, sources,
                        target=target, cutoff=cutoff,
                    ),
                    _outcome(
                        nx.multi_source_dijkstra, gnx, sources,
                        target=target, cutoff=cutoff, backend="networkx",
                    ),
                )


@pytest.mark.parametrize(("nx_cls", "fnx_cls"), CLASSES, ids=CLASS_IDS)
def test_overflowed_dijkstra_networkx_backend_dispatch_preserves_results(
    nx_cls, fnx_cls, monkeypatch
):
    gnx, _ = _overflowed_distance_pair(nx_cls, fnx_cls)
    _reject_python_dijkstra_fallback(monkeypatch)
    for name, args, kwargs in (
        ("dijkstra_path", ("s", "t"), {}),
        ("dijkstra_path_length", ("s", "t"), {}),
        ("single_source_dijkstra", ("s",), {"cutoff": float("inf")}),
        ("single_source_dijkstra_path_length", ("s",), {"cutoff": 1e308}),
        ("shortest_path", (), {"target": "t", "weight": "weight"}),
        ("shortest_path_length", (), {"target": "t", "weight": "weight"}),
    ):
        function = getattr(nx, name)
        expected = function(gnx, *args, backend="networkx", **kwargs)
        # An explicit backend exercises graph conversion and the registered
        # dispatch table, without relying on automatic conversion thresholds.
        for _ in range(2):
            actual = function(gnx, *args, backend="franken_networkx", **kwargs)
            _assert_dijkstra_observables(actual, expected)
