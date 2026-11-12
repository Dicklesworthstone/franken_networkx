"""A shortest-path distance keeps the TYPE networkx would have produced.

br-r37-c1-3dtn4. networkx never coerces a distance: its type follows the Python
sum along the chosen path, so int+int stays int, ``Fraction`` weights give a
``Fraction`` distance, and numpy scalars stay numpy scalars. fnx computes in f64
and could only ever restore ``int``, so every other numeric type came back as a
plain float - silently, with the rounding that implies for exact rational work.

WHY THE PARAMETRISATION IS CLASS x WEIGHT x SPELLING. The bead was filed from
one function and one class pair, and the defect was not shaped like that at all.
Measured before the fix, 29 of 140 cells diverged, and which ones depended on
which ROUTE reached the kernel:

    bool-mixed      bellman_ford and all_pairs_dijkstra only - single_source
                    dijkstra was already right
    Fraction etc.   bellman_ford on all four classes, plus dijkstra on the two
                    MULTIGRAPH classes - the simple classes' dijkstra was right
                    because its gate consults the native exactness scan

So any test that fixes one class, or one spelling, or one weight type would have
read as green over most of the defect. Three separate routes had to be closed:
the two multigraph collapses, Bellman-Ford's value-blind gate, and the directed
multigraph's own kernel.

THE TWO CONTROLS AT THE BOTTOM ARE NOT DECORATION. The repair is "delegate to
networkx when the type cannot survive", and the failure mode of that repair is
delegating for ordinary int/float graphs, which would trade a correctness bug for
a library-wide slowdown that no value assertion would catch.
"""

from __future__ import annotations

import decimal
import fractions

import networkx as nx
import pytest

import franken_networkx as fnx

np = pytest.importorskip("numpy", reason="numpy scalar weights are part of the contract")

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]

WEIGHTS = [
    ("int", 2),
    ("float", 2.5),
    ("bool-mixed", True),
    ("Fraction", fractions.Fraction(3, 2)),
    ("Decimal", decimal.Decimal("1.5")),
    ("np.int64", np.int64(2)),
    ("np.float64", np.float64(2.5)),
]

SPELLINGS = [
    "single_source_dijkstra_path_length",
    "single_source_bellman_ford_path_length",
    "dijkstra_path_length",
    "bellman_ford_path_length",
    "all_pairs_dijkstra_path_length",
]


def _build(mod, cls_name, weight):
    g = getattr(mod, cls_name)()
    g.add_edge("a", "b", w=weight)
    g.add_edge("b", "c", w=2)
    return g


def _distance_a_to_c(mod, graph, spelling):
    fn = getattr(mod, spelling)
    if spelling in ("dijkstra_path_length", "bellman_ford_path_length"):
        return fn(graph, "a", "c", weight="w")
    if spelling.startswith("all_pairs"):
        return dict(fn(graph, weight="w"))["a"]["c"]
    return fn(graph, "a", weight="w")["c"]


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("label,weight", WEIGHTS, ids=[w[0] for w in WEIGHTS])
@pytest.mark.parametrize("spelling", SPELLINGS)
def test_distance_type_matches_networkx(cls_name, label, weight, spelling):
    fx = _distance_a_to_c(fnx, _build(fnx, cls_name, weight), spelling)
    ref = _distance_a_to_c(nx, _build(nx, cls_name, weight), spelling)

    assert type(fx) is type(ref), (
        f"{cls_name} {label} {spelling}: networkx {type(ref).__name__}({ref!r}), "
        f"fnx {type(fx).__name__}({fx!r})"
    )
    assert fx == ref


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_fraction_distance_stays_exact(cls_name):
    """The reason the type matters, stated as arithmetic rather than as a type.

    A third summed three times is 1 exactly in Fraction arithmetic and is not in
    float arithmetic. If the distance comes back as a float, this fails by a
    rounding error - which is precisely the silent damage the bead describes.
    """
    third = fractions.Fraction(1, 3)
    fx, ref = (
        getattr(mod, cls_name)() for mod in (fnx, nx)
    )
    for graph in (fx, ref):
        graph.add_edge("a", "b", w=third)
        graph.add_edge("b", "c", w=third)
        graph.add_edge("c", "d", w=third)

    got = fnx.single_source_dijkstra_path_length(fx, "a", weight="w")["d"]
    want = nx.single_source_dijkstra_path_length(ref, "a", weight="w")["d"]

    assert got == want == fractions.Fraction(1, 1)
    assert type(got) is fractions.Fraction


@pytest.mark.parametrize("cls_name", CLASSES)
def test_bool_weights_sum_to_an_int_like_networkx(cls_name):
    """`True + 2` is `3`, an int - fnx used to exclude bool and return 3.0.

    The exclusion was explicit in `_sp_propagate_int_types`, and it is the half
    of this bead that needed no delegation: bool IS Integral for arithmetic, so
    following the arithmetic is the whole fix.
    """
    fx, ref = _build(fnx, cls_name, True), _build(nx, cls_name, True)

    got = fnx.single_source_bellman_ford_path_length(fx, "a", weight="w")["c"]
    want = nx.single_source_bellman_ford_path_length(ref, "a", weight="w")["c"]

    assert type(got) is type(want) is int
    assert got == want == 3


def test_an_ordinary_int_graph_does_not_start_delegating():
    """CONTROL: the repair must not send plain graphs to networkx.

    Delegating is how the exotic types are preserved, so the way this fix goes
    wrong is by over-triggering - and that would be a library-wide slowdown with
    every value assertion above still green.
    """
    graph = fnx.Graph()
    for i in range(400):
        graph.add_edge(f"n{i}", f"n{(i + 1) % 400}", w=(i % 7) + 1)

    assert fnx._sp_weights_need_networkx_for_type_parity(graph, "w") is False


def test_an_ordinary_float_graph_does_not_start_delegating():
    """CONTROL: the float sibling of the case above."""
    graph = fnx.Graph()
    for i in range(400):
        graph.add_edge(f"n{i}", f"n{(i + 1) % 400}", w=(i % 7) + 0.5)

    assert fnx._sp_weights_need_networkx_for_type_parity(graph, "w") is False


@pytest.mark.parametrize("label,weight", WEIGHTS, ids=[w[0] for w in WEIGHTS])
def test_the_gate_agrees_with_what_the_kernel_can_round_trip(label, weight):
    """The predicate itself, so a future fast path cannot quietly bypass it.

    int, float and bool are exactly the types the native kernel returns
    faithfully (bool arrives back as int, which is what nx's arithmetic gives).
    Everything else must route to networkx.
    """
    graph = fnx.Graph()
    graph.add_edge("a", "b", w=weight)

    survivable = type(weight) in (int, float, bool)
    assert (
        fnx._sp_weights_need_networkx_for_type_parity(graph, "w") is not survivable
    ), label
