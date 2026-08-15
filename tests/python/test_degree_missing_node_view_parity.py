"""Differential lock for br-r37-c1-1x6aq — `G.degree(<missing node>)`.

networkx's ``DegreeView.__call__`` answers with an int ONLY when the node is
present::

    if nbunch in self._nodes:
        return <int degree>
    return self.__class__(self._graph, nbunch, weight)

and that fallback runs ``nbunch_iter``, which ITERATES its argument. Two
consequences this file pins, both of which fnx got wrong:

* A missing ``str``/``bytes``/``tuple`` argument yields an EMPTY VIEW, not an
  error. fnx raised ``NetworkXError`` on Graph and DiGraph, so ordinary
  defensive code (``if G.degree(n):``) crashed under fnx where it runs under
  networkx. A missing NON-iterable (``99``) does still raise, because
  ``nbunch_iter`` raises on it — both sides of that boundary are asserted.
* The restricted view must report the SAME CLASS as the view it restricts.
  networkx has eight; fnx returned a single hardcoded ``DegreeView`` for all of
  them, so 6 of the 8 names were wrong.

Every assertion here is differential against the live networkx in the
environment rather than against a copied literal, so the file cannot drift into
asserting fnx's own behaviour back at itself.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
DIRECTED = ["DiGraph", "MultiDiGraph"]


def _pair(cls_name, edges=(("n0", "n1"),), nodes=()):
    made = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_nodes_from(nodes)
        for left, right in edges:
            graph.add_edge(left, right)
        made.append(graph)
    return made


def _outcome(fn, graph):
    """Return a comparable description of a call's result OR its exception."""
    try:
        result = fn(graph)
    except Exception as exc:  # noqa: BLE001 - the exception IS the contract
        return ("raised", type(exc).__name__, str(exc))
    if isinstance(result, (int, float)):
        # The weighted path answers with a number, not a view.
        return ("number", type(result).__name__, result)
    return ("view", type(result).__name__, repr(result), sorted(dict(result).items()))


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize(
    ("label", "probe"),
    [
        ("missing-str", lambda g: g.degree("nope")),
        ("missing-bytes", lambda g: g.degree(b"nope")),
        ("missing-tuple", lambda g: g.degree((1, 2))),
        ("missing-int-raises", lambda g: g.degree(99)),
        ("present-node-int", lambda g: g.degree("n0")),
        ("missing-empty-str", lambda g: g.degree("")),
    ],
)
def test_degree_single_argument_matches_networkx(cls_name, label, probe):
    gnx, gfx = _pair(cls_name)
    assert _outcome(probe, gfx) == _outcome(probe, gnx)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_degree_string_argument_iterates_elements_like_networkx(cls_name):
    """The chars of the argument ARE the nbunch when it is not a node."""
    gnx, gfx = _pair(cls_name, edges=(("n", "o"),), nodes=("p", "e"))
    assert _outcome(lambda g: g.degree("nope"), gfx) == _outcome(
        lambda g: g.degree("nope"), gnx
    )


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize(
    "nbunch",
    [["n0"], ["n0", "n1"], ["n0", "absent"], ["absent"], []],
    ids=["one", "both", "mixed", "all-absent", "empty"],
)
def test_degree_list_nbunch_is_unchanged(cls_name, nbunch):
    """The list form already matched; it must not regress."""
    gnx, gfx = _pair(cls_name)
    assert _outcome(lambda g: g.degree(nbunch), gfx) == _outcome(
        lambda g: g.degree(nbunch), gnx
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_restricted_degree_view_reports_networkx_class_name(cls_name):
    gnx, gfx = _pair(cls_name)
    view_nx, view_fx = gnx.degree(["n0"]), gfx.degree(["n0"])
    assert type(view_fx).__name__ == type(view_nx).__name__
    assert repr(view_fx) == repr(view_nx)


@pytest.mark.parametrize("cls_name", DIRECTED)
@pytest.mark.parametrize("accessor", ["in_degree", "out_degree"])
def test_restricted_directional_degree_view_class_name(cls_name, accessor):
    gnx, gfx = _pair(cls_name)
    view_nx = getattr(gnx, accessor)(["n0"])
    view_fx = getattr(gfx, accessor)(["n0"])
    assert type(view_fx).__name__ == type(view_nx).__name__
    assert repr(view_fx) == repr(view_nx)
    assert _outcome(lambda g: getattr(g, accessor)("nope"), gfx) == _outcome(
        lambda g: getattr(g, accessor)("nope"), gnx
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_restricted_degree_view_still_indexes_and_iterates(cls_name):
    """The proxy's other contracts must survive the class-name change.

    br-degnbnview: callers such as ``bipartite.degrees`` iterate the view AND
    index it by node, including nodes outside the restriction.
    """
    gnx, gfx = _pair(cls_name)
    view_nx, view_fx = gnx.degree(["n0"]), gfx.degree(["n0"])
    assert list(view_fx) == list(view_nx) == [("n0", 1)]
    assert len(view_fx) == len(view_nx) == 1
    # Indexing a node OUTSIDE the restriction still answers, in both.
    assert view_fx["n1"] == view_nx["n1"] == 1
    # NOTE: `node in view` is deliberately NOT asserted here. networkx's degree
    # views have no __contains__, so `in` falls back to __iter__ and tests
    # (node, degree) TUPLES; fnx's restricted proxy defines __contains__ over
    # NODES and inverts both answers on 3 of the 4 classes. That is a real
    # divergence, out of scope for this bead, tracked in br-r37-c1-p1uro.


@pytest.mark.parametrize("cls_name", CLASSES)
def test_degree_weighted_single_and_nbunch_match_networkx(cls_name):
    """The weighted path builds the same proxy and must stay in parity."""
    gnx, gfx = [], []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("n0", "n1", weight=2.5)
        (gnx if lib is nx else gfx).append(graph)
    graph_nx, graph_fx = gnx[0], gfx[0]
    for probe in (
        lambda g: g.degree("n0", weight="weight"),
        lambda g: g.degree(["n0"], weight="weight"),
        lambda g: g.degree("nope", weight="weight"),
    ):
        assert _outcome(probe, graph_fx) == _outcome(probe, graph_nx)


def test_missing_node_degree_is_falsy_not_an_exception():
    """The concrete drop-in pattern that motivated the bead."""
    gnx, gfx = _pair("Graph")
    for graph in (gnx, gfx):
        assert not graph.degree("absent")
        assert list(graph.degree("absent")) == []
        assert len(graph.degree("absent")) == 0
