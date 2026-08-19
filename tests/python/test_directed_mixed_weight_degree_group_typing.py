"""Directed weighted degree types each ROW separately, and so must fnx.

br-r37-c1-weightupdate-9rts1. networkx's directed total degree is

    sum(dd.get(weight, 1) for dd in succ[n].values())
  + sum(dd.get(weight, 1) for dd in pred[n].values())

— two independent `builtins.sum` calls, added at the end. That makes the result
type depend on the rows *separately*: a node whose successor row is all int and
whose predecessor row holds a float gets `int + float`, and the promotion happens
in that final add rather than inside either sum.

An accumulator that folded both rows into one running value would still get the
common cases right, and would be wrong precisely when one row is float and the
other is not — including for `in_degree` and `out_degree`, which use one row
only. These assertions hold on the exact path; they exist so they keep holding
now that a mixed int/float accumulator serves these graphs.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["DiGraph", "MultiDiGraph"]


def _typed(view):
    return {str(node): (value, type(value).__name__) for node, value in view}


def _split_rows(lib, class_name):
    """`split` has an all-int OUT row and a float IN row."""
    graph = getattr(lib, class_name)()
    graph.add_edge("split", "a", weight=3)        # out row: int
    graph.add_edge("split", "b", weight=4)        # out row: int
    graph.add_edge("c", "split", weight=1.5)      # in  row: float
    graph.add_edge("allint", "d", weight=2)
    graph.add_edge("e", "allint", weight=6)
    graph.add_node("isolated")
    graph.add_edge("loop", "loop", weight=5)      # counted in BOTH rows
    graph.add_edge("floop", "floop", weight=2.5)
    return graph


@pytest.mark.parametrize("class_name", CLASSES)
def test_total_degree_matches_networkx_per_node(class_name):
    got = _typed(_split_rows(fnx, class_name).degree(weight="weight"))
    want = _typed(_split_rows(nx, class_name).degree(weight="weight"))
    assert got == want


@pytest.mark.parametrize("class_name", CLASSES)
def test_an_all_int_row_pair_stays_int(class_name):
    got = _typed(_split_rows(fnx, class_name).degree(weight="weight"))
    want = _typed(_split_rows(nx, class_name).degree(weight="weight"))
    assert got["allint"] == want["allint"]
    assert got["allint"][1] == "int", "all-int node promoted to %s" % got["allint"][1]


@pytest.mark.parametrize("class_name", CLASSES)
def test_out_degree_is_typed_from_its_own_row_only(class_name):
    """`split`'s OUT row is all int, even though its IN row is float."""
    got = _typed(_split_rows(fnx, class_name).out_degree(weight="weight"))
    want = _typed(_split_rows(nx, class_name).out_degree(weight="weight"))
    assert got == want
    assert got["split"][1] == "int", "out row typed from the wrong row"


@pytest.mark.parametrize("class_name", CLASSES)
def test_in_degree_is_typed_from_its_own_row_only(class_name):
    got = _typed(_split_rows(fnx, class_name).in_degree(weight="weight"))
    want = _typed(_split_rows(nx, class_name).in_degree(weight="weight"))
    assert got == want
    assert got["split"][1] == "float", "in row typed from the wrong row"


@pytest.mark.parametrize("class_name", CLASSES)
def test_self_loops_are_counted_in_both_rows(class_name):
    got = _typed(_split_rows(fnx, class_name).degree(weight="weight"))
    want = _typed(_split_rows(nx, class_name).degree(weight="weight"))
    assert got["loop"] == want["loop"]
    assert got["floop"] == want["floop"]


@pytest.mark.parametrize("class_name", CLASSES)
def test_an_isolated_node_is_int_zero(class_name):
    got = _typed(_split_rows(fnx, class_name).degree(weight="weight"))
    want = _typed(_split_rows(nx, class_name).degree(weight="weight"))
    assert got["isolated"] == want["isolated"] == (0, "int")


@pytest.mark.parametrize("class_name", CLASSES)
def test_missing_weights_bools_and_bignums_match_networkx(class_name):
    got, want = getattr(fnx, class_name)(), getattr(nx, class_name)()
    for graph in (got, want):
        graph.add_edge("a", "b", weight=2.5)
        graph.add_edge("a", "c")                       # missing -> int 1
        graph.add_edge("d", "a", weight=True)          # bool: not PyLong_CheckExact
        graph.add_edge("big", "a", weight=2**53 + 1)   # crosses into a float total
    for view in ("degree", "in_degree", "out_degree"):
        assert _typed(getattr(got, view)(weight="weight")) == _typed(
            getattr(want, view)(weight="weight")
        ), view
    assert got.size(weight="weight") == want.size(weight="weight")


@pytest.mark.parametrize("class_name", CLASSES)
def test_a_non_numeric_weight_raises_like_networkx(class_name):
    got, want = getattr(fnx, class_name)(), getattr(nx, class_name)()
    for graph in (got, want):
        graph.add_edge("a", "b", weight=1.5)
        graph.add_edge("a", "c", weight="not a number")

    def outcome(graph):
        try:
            return ("ok", _typed(graph.degree(weight="weight")))
        except Exception as exc:
            return ("raise", type(exc).__name__, exc.args)

    assert outcome(got) == outcome(want)
