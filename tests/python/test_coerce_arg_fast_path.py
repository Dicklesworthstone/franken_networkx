"""``_coerce_arg_to_fnx_graph`` short-circuits concrete graphs without changing them.

br-r37-c1-qk4i4. This helper runs at the top of 244 public functions. Its
overwhelmingly common argument is a graph that is ALREADY a concrete fnx class,
for which it is a pass-through - but it reached that conclusion only after three
failed ``isinstance`` view checks, each walking an MRO, plus a fourth
``isinstance`` against a 4-tuple. An exact type check now answers it first.

WHY AN EXACT CHECK IS SAFE HERE AND ``isinstance`` WOULD NOT BE, which is the
entire correctness argument and the reason this file exists: the view classes
DELIBERATELY SUBCLASS the canonical fnx types - they are added as a second base
so views pass ``isinstance`` parity checks. That is precisely why the view
branches have to run before the trailing ``isinstance``. ``type(G) in {...}``
cannot match a subclass, so a view can never take the fast path.

If that ever stops being true - if a view were made an exact instance of a
canonical class, or the fast path were relaxed to ``isinstance`` - a filtered
view would be handed straight to Rust kernels that read the PARENT's adjacency
and silently return answers for the wrong graph. That is the failure this file
guards, and it is a wrong-answer bug, not a slow one.

WHAT IS PINNED:

  * concrete graphs come back BY IDENTITY (the pass-through), all four classes;
  * every view kind - subgraph, restricted_view, as_view, reverse, and the
    to_undirected/to_directed conversion views - is still MATERIALIZED, and the
    materialised graph carries the VIEW's contents rather than the parent's;
  * networkx graphs still convert, with their nodes intact;
  * a user subclass of an fnx class behaves exactly as before (it misses the
    exact-type check, finds the view checks False, and reaches the same
    ``isinstance`` pass-through);
  * non-graph arguments are returned untouched.

The view cases are the load-bearing ones: a byte- or value-level test of some
public algorithm would NOT catch a view leaking through, because the parent and
the view often agree on small fixtures. These assert the materialisation
directly.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx
from franken_networkx import _coerce_arg_to_fnx_graph as _coerce

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(lib, cls, n=6):
    g = getattr(lib, cls)()
    for i in range(n):
        g.add_edge("n%d" % i, "n%d" % ((i + 1) % n), w=i)
    return g


@pytest.mark.parametrize("cls", CLASSES)
def test_a_concrete_graph_is_returned_by_identity(cls):
    graph = _build(fnx, cls)
    assert _coerce(graph) is graph


def _views():
    undirected = _build(fnx, "Graph")
    directed = _build(fnx, "DiGraph")
    return {
        "subgraph": (undirected, undirected.subgraph(["n0", "n1", "n2"])),
        "restricted_view": (undirected, fnx.restricted_view(undirected, ["n0"], [])),
        "as_view": (undirected, undirected.copy(as_view=True)),
        "reverse": (directed, directed.reverse(copy=False)),
        "to_undirected_view": (directed, directed.to_undirected(as_view=True)),
    }


@pytest.mark.parametrize("label", sorted(_views()))
def test_a_view_is_still_materialized(label):
    """The wrong-answer guard: a view must NOT reach Rust as itself."""
    _parent, view = _views()[label]
    coerced = _coerce(view)
    assert coerced is not view, (
        f"{label} passed through unmaterialised - Rust kernels would read the "
        "parent's adjacency and answer for the wrong graph"
    )


@pytest.mark.parametrize("label", sorted(_views()))
def test_the_materialized_graph_carries_the_views_contents(label):
    """Materialised is not enough; it must be the VIEW, not the parent."""
    parent, view = _views()[label]
    coerced = _coerce(view)
    assert sorted(str(n) for n in coerced) == sorted(str(n) for n in view)
    if len(view) < len(parent):
        assert len(coerced) < len(parent), f"{label} materialised the parent"


@pytest.mark.parametrize("cls", CLASSES)
def test_a_networkx_graph_still_converts(cls):
    source = _build(nx, cls)
    coerced = _coerce(source)
    assert isinstance(coerced, (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph))
    assert sorted(str(n) for n in coerced) == sorted(str(n) for n in source)
    assert coerced.number_of_edges() == source.number_of_edges()


def test_a_user_subclass_behaves_as_before():
    """It misses the exact-type check and reaches the isinstance pass-through."""

    class MyGraph(fnx.Graph):
        pass

    graph = MyGraph()
    graph.add_edge("a", "b")
    assert _coerce(graph) is graph


@pytest.mark.parametrize("value", [None, 42, "string", [1, 2], {"a": 1}])
def test_non_graph_arguments_are_untouched(value):
    assert _coerce(value) is value


def test_the_fast_path_set_holds_exactly_the_concrete_classes():
    """Pins the membership of the short-circuit set itself.

    A new concrete graph class added without being listed here would silently
    keep paying the isinstance chain; a VIEW class added to it would silently
    start leaking past the materialisation.
    """
    assert fnx._CONCRETE_FNX_GRAPH_TYPES == frozenset(
        (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph)
    )
    for view_kind in (
        fnx._FilteredGraphView,
        fnx._ReverseDirectedViewBase,
        fnx._ConversionGraphViewBase,
    ):
        assert view_kind not in fnx._CONCRETE_FNX_GRAPH_TYPES


@pytest.mark.parametrize("cls", CLASSES)
def test_public_algorithms_still_respect_views(cls):
    """End-to-end: the guard matters because algorithms coerce their input."""
    graph = _build(fnx, "Graph", n=8)
    view = graph.subgraph(["n0", "n1", "n2"])
    want = nx.number_connected_components(
        nx.Graph(nx.subgraph(_to_nx_graph(graph), ["n0", "n1", "n2"]))
    )
    assert fnx.number_connected_components(view) == want


def _to_nx_graph(graph):
    out = nx.Graph()
    out.add_nodes_from(str(n) for n in graph)
    out.add_edges_from((str(u), str(v)) for u, v in graph.edges())
    return out
