"""A NaN edge weight must propagate as networkx propagates it, on all four classes.

br-r37-c1-kn5cu. An undirected MultiGraph carrying one NaN weight returned a
FINITE distance where networkx returns nan:

    single_source_dijkstra_path_length(g, 'a', weight='w')
      networkx  [('a', 0), ('b', nan), ('c', nan)]
      fnx       [('a', 0), ('b', 1.0), ('c', 2.0)]

WHY THIS IS WORSE THAN IT LOOKS, and why the assertions below are about VALUES
rather than about which path ran: fnx did not merely lose the NaN, it substituted
the DEFAULT WEIGHT 1. A caller with one corrupt weight in a real dataset got a
plausible shortest path instead of the nan that would have made the corruption
obvious.

THE MECHANISM WAS A SEAM BETWEEN TWO HALVES THAT EACH ASSUMED THE OTHER ASKED.
`check_dijkstra_edge_weights_fast`'s multigraph arms flagged `+inf` only, with a
comment saying "NaN keeps its existing routing"; the Python predicate's multigraph
branch excluded NaN with `and not _math.isnan(_value)`. But the native scan
answers first and the Python branch is then unreachable, so nothing asked at all,
and the graph reached a kernel that defaults a NaN to 1. The simple classes were
always right because their arms use `!f.is_finite()`.

So the parametrisation is over CLASS first: the bug was invisible on Graph and
DiGraph, which is exactly why it survived. Anything that tests one class here
tests the half that never broke.
"""

from __future__ import annotations

import math

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
NAN = float("nan")


def _pair(cls_name, weight):
    graphs = []
    for mod in (fnx, nx):
        g = getattr(mod, cls_name)()
        g.add_edge("a", "b", w=weight)
        g.add_edge("b", "c", w=1)
        graphs.append(g)
    return graphs[0], graphs[1]


def _canon(value):
    """NaN != NaN, so compare a printable form rather than the floats."""
    if isinstance(value, dict):
        return sorted((str(k), _canon(v)) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return [_canon(v) for v in value]
    if isinstance(value, float) and math.isnan(value):
        return "nan"
    return value


@pytest.mark.parametrize("cls_name", CLASSES)
def test_single_source_lengths_propagate_nan(cls_name):
    fx, ref = _pair(cls_name, NAN)

    assert _canon(fnx.single_source_dijkstra_path_length(fx, "a", weight="w")) == _canon(
        nx.single_source_dijkstra_path_length(ref, "a", weight="w")
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_all_pairs_lengths_propagate_nan(cls_name):
    """The entry point that stayed broken after the first fix attempt.

    `all_pairs` does not go through the multigraph collapse on the no-cutoff
    path - it asks the weight predicate directly - so a fix applied only to the
    collapse left this one diverging. It is here to keep the next fix honest
    about covering every route to the kernel.
    """
    fx, ref = _pair(cls_name, NAN)

    assert _canon(dict(fnx.all_pairs_dijkstra_path_length(fx, weight="w"))) == _canon(
        dict(nx.all_pairs_dijkstra_path_length(ref, weight="w"))
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_the_cutoff_route_propagates_nan(cls_name):
    """The cutoff path collapses the multigraph itself, a third route to the kernel."""
    fx, ref = _pair(cls_name, NAN)

    assert _canon(dict(fnx.all_pairs_dijkstra_path_length(fx, cutoff=10, weight="w"))) == (
        _canon(dict(nx.all_pairs_dijkstra_path_length(ref, cutoff=10, weight="w")))
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_nan_is_never_silently_replaced_by_the_default_weight(cls_name):
    """The specific failure shape, stated so a regression cannot read as a rounding.

    Weight 1 is the default a missing attribute takes, so the old answer was
    exactly "as if the attribute were absent". Distances of 1 and 2 here mean the
    NaN was dropped, whatever else is true.
    """
    fx, _ = _pair(cls_name, NAN)
    lengths = fnx.single_source_dijkstra_path_length(fx, "a", weight="w")

    assert math.isnan(lengths["b"]), f"{cls_name}: b={lengths['b']!r}, NaN was dropped"
    assert math.isnan(lengths["c"]), f"{cls_name}: c={lengths['c']!r}, NaN was dropped"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_the_weight_predicate_sees_nan(cls_name):
    """The seam itself: both halves must now answer the same question.

    The native scan's second slot and the Python predicate are the two places a
    NaN can be missed, and the multigraph arms of both missed it. Asserted
    directly, because a future fast path added to one half would otherwise
    reintroduce the divergence with every value test above still passing.
    """
    fx, _ = _pair(cls_name, NAN)

    assert fnx._should_delegate_dijkstra_to_networkx(fx, "w") is True

    native = getattr(fnx, "_native_check_dijkstra_weights_fast", None)
    if native is not None:
        result = native(fx, "w", False)
        if result is not None:
            assert any(result), f"{cls_name}: native scan flagged nothing for NaN"


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize(
    "label,weight",
    [
        ("positive infinity", float("inf")),
        ("negative", -2),
        ("ordinary float", 2.5),
        ("ordinary int", 3),
    ],
    ids=["+inf", "negative", "float", "int"],
)
def test_the_neighbouring_weights_are_unchanged(cls_name, label, weight):
    """Controls: the fix must move NaN and nothing else.

    +inf and negative already delegated and must keep doing so; ordinary weights
    must keep their native path and their answers.
    """
    fx, ref = _pair(cls_name, weight)

    fx_out, ref_out = None, None
    try:
        fx_out = _canon(fnx.single_source_dijkstra_path_length(fx, "a", weight="w"))
    except Exception as exc:  # noqa: BLE001 - the exception IS the contract here
        fx_out = ("raised", type(exc).__name__)
    try:
        ref_out = _canon(nx.single_source_dijkstra_path_length(ref, "a", weight="w"))
    except Exception as exc:  # noqa: BLE001
        ref_out = ("raised", type(exc).__name__)

    assert fx_out == ref_out, f"{cls_name} {label}"
