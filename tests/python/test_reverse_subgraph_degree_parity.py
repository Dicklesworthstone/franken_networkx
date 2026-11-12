"""Differential lock for br-r37-c1-nvm5i — degree on a subgraph OF a reverse view.

The bead was filed about a KeyError wording residue. Probing it turned up
something much worse sharing the same root cause: ``G.degree`` on
``reverse(copy=False).subgraph(nodes)`` answered from the UNFILTERED parent, so
it reported the parent's nodes at the parent's degrees while the same object's
``nodes()`` and ``edges()`` were correct. Silent wrong values, not just a
message.

Cause: ``_ReverseDirectedViewBase`` short-circuits ``degree`` to
``self._graph.degree`` because total degree is invariant under edge reversal
(br-r37-c1-r3gjb, a 54x win). That holds only while self and the parent share a
node set. ``reverse(...).subgraph(...)`` keeps that class in its MRO *and*
filters, which breaks the premise.

The three shapes are pinned together on purpose, because the fix has to keep the
shortcut for the two where it is sound:

    reverse()                 not filtered by self -> shortcut valid
    subgraph().reverse()      parent already filtered -> shortcut valid
    reverse().subgraph()      SELF filters -> shortcut invalid
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

DIRECTED = ["DiGraph", "MultiDiGraph"]
EDGES = [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a"), ("a", "c")]

SHAPES = {
    "reverse": lambda g: g.reverse(copy=False),
    "reverse-then-subgraph": lambda g: g.reverse(copy=False).subgraph(["a", "b"]),
    "subgraph-then-reverse": lambda g: g.subgraph(["a", "b", "c"]).reverse(copy=False),
    "plain-subgraph": lambda g: g.subgraph(["a", "b"]),
    "reverse-of-reverse": lambda g: g.reverse(copy=False).reverse(copy=False),
    "subgraph-of-subgraph": lambda g: g.subgraph(["a", "b", "c"]).subgraph(["a", "b"]),
}


def _pair(cls_name):
    made = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edges_from(EDGES)
        made.append(graph)
    return made


@pytest.mark.parametrize("cls_name", DIRECTED)
@pytest.mark.parametrize("shape", list(SHAPES))
def test_degree_values_match_networkx(cls_name, shape):
    """The values are the point: a filtered view must not answer for the parent."""
    gnx, gfx = _pair(cls_name)
    view_nx, view_fx = SHAPES[shape](gnx), SHAPES[shape](gfx)
    assert sorted(view_fx.degree) == sorted(view_nx.degree)
    # The degree view must agree with the object's own node set.
    assert {n for n, _ in view_fx.degree} == set(view_fx.nodes())


@pytest.mark.parametrize("cls_name", DIRECTED)
@pytest.mark.parametrize("shape", list(SHAPES))
def test_degree_view_agrees_with_nodes_and_edges(cls_name, shape):
    gnx, gfx = _pair(cls_name)
    view_nx, view_fx = SHAPES[shape](gnx), SHAPES[shape](gfx)
    assert sorted(view_fx.nodes()) == sorted(view_nx.nodes())
    assert sorted(view_fx.edges()) == sorted(view_nx.edges())
    assert len(view_fx.degree) == len(view_nx.degree)


@pytest.mark.parametrize("cls_name", DIRECTED)
@pytest.mark.parametrize("shape", list(SHAPES))
@pytest.mark.parametrize("key", ["zzz", 999, (1, 2)], ids=["str", "int", "tuple"])
def test_degree_missing_key_error_matches_networkx(cls_name, shape, key):
    """The original bead: nx has two wordings and they must not be swapped."""
    gnx, gfx = _pair(cls_name)
    view_nx, view_fx = SHAPES[shape](gnx), SHAPES[shape](gfx)
    with pytest.raises(KeyError) as nx_err:
        view_nx.degree[key]
    with pytest.raises(KeyError) as fnx_err:
        view_fx.degree[key]
    assert fnx_err.value.args == nx_err.value.args


@pytest.mark.parametrize("cls_name", DIRECTED)
@pytest.mark.parametrize("shape", list(SHAPES))
def test_present_node_degree_lookup_matches(cls_name, shape):
    gnx, gfx = _pair(cls_name)
    view_nx, view_fx = SHAPES[shape](gnx), SHAPES[shape](gfx)
    for node in view_nx.nodes():
        assert view_fx.degree[node] == view_nx.degree[node]


@pytest.mark.parametrize("cls_name", DIRECTED)
def test_directional_degree_views_are_unaffected(cls_name):
    """in_degree / out_degree keep the swapped reverse path — no regression."""
    gnx, gfx = _pair(cls_name)
    for shape in SHAPES:
        view_nx, view_fx = SHAPES[shape](gnx), SHAPES[shape](gfx)
        for accessor in ("in_degree", "out_degree"):
            assert sorted(getattr(view_fx, accessor)) == sorted(
                getattr(view_nx, accessor)
            ), (shape, accessor)
            assert (
                type(getattr(view_fx, accessor)).__name__
                == type(getattr(view_nx, accessor)).__name__
            ), (shape, accessor)


@pytest.mark.parametrize("cls_name", DIRECTED)
def test_degree_is_live_over_the_underlying_graph(cls_name):
    """A view must keep tracking the graph after the shortcut change."""
    gnx, gfx = _pair(cls_name)
    view_nx = gnx.reverse(copy=False).subgraph(["a", "b"])
    view_fx = gfx.reverse(copy=False).subgraph(["a", "b"])
    for graph in (gnx, gfx):
        graph.add_edge("a", "b")
    assert sorted(view_fx.degree) == sorted(view_nx.degree)
