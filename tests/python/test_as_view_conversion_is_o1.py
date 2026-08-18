"""``to_undirected(as_view=True)`` / ``to_directed(as_view=True)`` must be O(1).

br-r37-c1-hgmnp. ``_materialize_attrs_before_convert`` wraps both conversion
methods. It is a COPY-path guard: the native conversion walks a lazy edge mirror
that can miss edge attrs on a freshly batch-built graph, so the wrapper probes
the RESULT and, if the source has attrs but the result appears not to, walks
``self.edges(data=True)`` to sync the mirror and redoes the conversion.

On a view that post-check was both pointless and unmeasurable. The conversion
view classes hold an EMPTY Rust base on purpose (br-r37-c1-y2b8t) because every
query is overridden to read through ``self._graph``; the native probe read that
empty base and answered False for every attributed graph. So the guard fired on
EVERY as_view call and never settled - turning a documented O(1) view into an
O(E) walk plus a second conversion:

    n edges     fnx        nx      ratio
       400    42.6us     6.7us    0.1562
      1600   107.7us     6.2us    0.0574
      6400   424.4us     7.7us    0.0181

networkx is flat; ``reverse(copy=False)`` - the sibling that already returns a
lazy view - was flat too, at 0.62x. Skipping the guard when ``as_view is True``
is what this file pins, in three parts:

  * THE VIEW IS STILL CORRECT without the materialization, including on the
    batch-built integer-node shape the guard was written for, because a view
    reads through the parent's public display-key path - the same path the
    materialization used to walk;
  * THE COPY PATH STILL MATERIALIZES. This is the regression that would matter,
    and it is why the skip tests ``as_view is True`` by identity, exactly as
    ``to_undirected_impl`` does, rather than any truthy value;
  * THE COST NO LONGER SCALES, asserted by COUNTING Python calls at two parent
    sizes rather than by timing, so it holds under load.
"""

from __future__ import annotations

import sys

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph"]
CONVERSIONS = ["to_undirected", "to_directed"]


def _batch_built(lib, cls, *, ints, attrs=True):
    """add_edges_from with integer nodes is the shape the guard was written for."""
    graph = getattr(lib, cls)()
    key = (lambda i: i) if ints else (lambda i: f"n{i}")
    if attrs:
        graph.add_edges_from(
            [(key(i), key(i + 1), {"w": i + 1, "c": f"x{i}"}) for i in range(6)]
        )
    else:
        graph.add_edges_from([(key(i), key(i + 1)) for i in range(6)])
    graph.add_node(key(99))
    return graph


def _rows(graph):
    return sorted(
        (str(u), str(v), tuple(sorted(d.items()))) for u, v, d in graph.edges(data=True)
    )


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("conv", CONVERSIONS)
@pytest.mark.parametrize("ints", [True, False])
@pytest.mark.parametrize("attrs", [True, False])
def test_view_matches_networkx_without_materialization(cls, conv, ints, attrs):
    """No read of any kind precedes the conversion, so nothing has synced."""
    got = getattr(_batch_built(fnx, cls, ints=ints, attrs=attrs), conv)(as_view=True)
    want = getattr(_batch_built(nx, cls, ints=ints, attrs=attrs), conv)(as_view=True)
    assert _rows(got) == _rows(want)
    assert sorted(map(str, got.nodes())) == sorted(map(str, want.nodes()))
    assert got.number_of_edges() == want.number_of_edges()


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("conv", CONVERSIONS)
def test_copy_path_still_materializes_attrs(cls, conv):
    """THE REGRESSION GUARD. The copy path must keep the wrapper's protection."""
    got = getattr(_batch_built(fnx, cls, ints=True), conv)()
    want = getattr(_batch_built(nx, cls, ints=True), conv)()
    assert _rows(got) == _rows(want)
    assert _rows(got), "the copy lost every edge attr - the guard stopped firing"


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("conv", CONVERSIONS)
def test_only_the_identity_true_takes_the_view_branch(cls, conv):
    """``as_view=1`` is not ``as_view is True``; it must still copy, as in nx."""
    graph = _batch_built(fnx, cls, ints=True)
    reference = _batch_built(nx, cls, ints=True)
    for spelling in (1, "yes"):
        got = getattr(graph, conv)(as_view=spelling)
        want = getattr(reference, conv)(as_view=spelling)
        assert _rows(got) == _rows(want)
        # A copy, so mutating the source must NOT show through.
        got_edges = got.number_of_edges()
        graph.add_edge(500, 501, w=1)
        assert got.number_of_edges() == got_edges, f"as_view={spelling!r} aliased"
        graph.remove_edge(500, 501)


# Every conversion takes ``as_view`` first EXCEPT ``DiGraph.to_undirected``,
# whose signature is ``(reciprocal=False, as_view=False)`` - in fnx and in nx.
POSITIONAL_AS_VIEW_FIRST = [
    ("Graph", "to_undirected"),
    ("Graph", "to_directed"),
    ("DiGraph", "to_directed"),
]


@pytest.mark.parametrize("cls,conv", POSITIONAL_AS_VIEW_FIRST)
def test_positional_as_view_is_honoured(cls, conv):
    """``as_view`` is positional-legal, so the skip must not be keyword-only."""
    graph = _batch_built(fnx, cls, ints=True)
    view = getattr(graph, conv)(True)
    before = view.number_of_edges()
    graph.add_edge(500, 501, w=7)
    assert view.number_of_edges() > before, "positional as_view=True did not alias"


def test_digraph_to_undirected_first_positional_is_reciprocal_not_as_view():
    """THE TRAP the result-type predicate exists to avoid.

    An ``args[0] if args else False`` reading of ``as_view`` would treat
    ``G.to_undirected(True)`` as a view request. It is not: the first positional
    is ``reciprocal``, so that call is a COPY that keeps only mutually-reciprocal
    edges. networkx behaves identically - both libraries return zero edges for a
    directed path graph. Skipping the attr guard there would have reintroduced,
    on a genuine copy, the silent attr loss the guard was written to prevent.
    """
    graph = _batch_built(fnx, "DiGraph", ints=True)
    reference = _batch_built(nx, "DiGraph", ints=True)

    got, want = graph.to_undirected(True), reference.to_undirected(True)
    assert _rows(got) == _rows(want)
    assert got.number_of_edges() == 0, "reciprocal=True kept non-reciprocal edges"

    # A copy, not a view: mutating the source must not show through.
    graph.add_edge(500, 501, w=1)
    assert got.number_of_edges() == 0, "reciprocal copy aliased the source"

    # ``as_view`` is reachable positionally here too - as the SECOND argument.
    view = graph.to_undirected(False, True)
    before = view.number_of_edges()
    graph.add_edge(800, 801, w=2)
    assert view.number_of_edges() > before, "to_undirected(False, True) did not alias"


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("conv", CONVERSIONS)
def test_view_is_live(cls, conv):
    """A view reads through; the removed materialization must not have frozen it."""
    graph = _batch_built(fnx, cls, ints=True)
    view = getattr(graph, conv)(as_view=True)
    graph.add_edge(700, 701, w=42)
    assert ("700", "701", (("w", 42),)) in _rows(view) or (
        "701",
        "700",
        (("w", 42),),
    ) in _rows(view)
    graph[0][1]["w"] = 999
    assert any(dict(d).get("w") == 999 for _u, _v, d in view.edges(data=True))


def _python_calls(fn):
    calls = 0

    def prof(_frame, event, _arg):
        nonlocal calls
        if event == "call":
            calls += 1

    fn()  # warm any lazily built caches so they are not counted
    sys.setprofile(prof)
    try:
        fn()
    finally:
        sys.setprofile(None)
    return calls


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("conv", CONVERSIONS)
def test_cost_does_not_scale_with_parent_size(cls, conv):
    """Counted, not timed: the whole defect was a per-edge walk of the parent."""
    counts = {}
    for n in (50, 1600):
        graph = getattr(fnx, cls)()
        graph.add_edges_from([(i, i + 1, {"w": i}) for i in range(n)])
        counts[n] = _python_calls(lambda g=graph: getattr(g, conv)(as_view=True))

    growth = counts[1600] - counts[50]
    assert growth < 50, (
        f"{cls}.{conv}(as_view=True) still scales with the parent: "
        f"{counts[50]} calls at 50 edges vs {counts[1600]} at 1600 "
        f"(+{growth}); the O(E) materialization is back"
    )
