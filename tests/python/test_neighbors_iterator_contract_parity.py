"""Lock for br-r37-c1-do7g5 — `G.neighbors(n)` and `iter(G[n])`.

Three redundancies were removed from the neighbours path: two Python-level
``__iter__`` calls replaced by the C iterator protocol, and a duplicate
``has_node`` probe in front of the row cache. All three are equivalence claims,
so what matters is that the OBSERVABLE contract is untouched:

* the returned object is a real iterator of the right type,
* it yields the same neighbours in the same ORDER as networkx,
* it is LAZY — networkx's is a live view over the adjacency, and code depends on
  the RuntimeError you get for mutating during iteration,
* absent and unhashable keys raise exactly what networkx raises,
* the cache-first reordering cannot serve a stale row after a node is removed
  and re-added, which is the one way that change could go wrong.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
EDGES = [("a", "b"), ("a", "c"), ("a", "d"), ("b", "c"), ("e", "f")]


def _pair(cls_name):
    made = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edges_from(EDGES)
        graph.add_node("lonely")
        made.append(graph)
    return made


@pytest.mark.parametrize("cls_name", CLASSES)
def test_neighbors_order_and_type_match_networkx(cls_name):
    gnx, gfx = _pair(cls_name)
    for node in gnx.nodes():
        itn, itf = gnx.neighbors(node), gfx.neighbors(node)
        assert type(itf).__name__ == type(itn).__name__, node
        assert list(itf) == list(itn), node


@pytest.mark.parametrize("cls_name", CLASSES)
def test_neighbors_result_is_an_exhaustible_iterator(cls_name):
    """Not a list: it must exhaust, like networkx's dict_keyiterator."""
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        it = graph.neighbors("a")
        first = list(it)
        assert first  # non-empty
        assert list(it) == []  # exhausted


@pytest.mark.parametrize("cls_name", CLASSES)
def test_iter_of_getitem_matches_networkx(cls_name):
    """`iter(G[n])` shares the changed __iter__ on the AtlasView."""
    gnx, gfx = _pair(cls_name)
    for node in gnx.nodes():
        assert list(iter(gfx[node])) == list(iter(gnx[node])), node
        assert list(gfx.adj[node]) == list(gnx.adj[node]), node


@pytest.mark.parametrize("cls_name", CLASSES)
def test_neighbors_is_live_not_a_snapshot(cls_name):
    """networkx's neighbours iterate the live adjacency; mutation must be seen."""
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        graph.add_edge("a", "zzz")
    assert sorted(gfx.neighbors("a")) == sorted(gnx.neighbors("a"))
    for graph in (gnx, gfx):
        graph.remove_edge("a", "zzz")
    assert sorted(gfx.neighbors("a")) == sorted(gnx.neighbors("a"))


@pytest.mark.parametrize(
    "cls_name",
    [
        "Graph",
        "DiGraph",
        # br-r37-c1-dwy1n FIXED for MultiGraph: `neighbor_key_rows` is now
        # maintained IN PLACE by add_edge/remove_edge instead of being dropped
        # wholesale on a generation change, so an outstanding iterator walks the
        # row that actually mutated and CPython raises the same RuntimeError.
        "MultiGraph",
        pytest.param(
            "MultiDiGraph",
            marks=pytest.mark.xfail(
                strict=True,
                reason="br-r37-c1-dwy1n: MultiGraph is fixed; MultiDiGraph keeps "
                "its succ/pred rows in digraph.rs and still needs the same "
                "in-place maintenance",
            ),
        ),
    ],
)
def test_mutation_during_iteration_raises_like_networkx(cls_name):
    """The laziness is observable: a live iterator must notice a resize.

    networkx raises ``RuntimeError: dictionary changed size during iteration``
    on all four classes. fnx does so on the simple classes only — the multigraph
    ones iterate a copy, so the mutation is silently invisible and a traversal
    that adds edges gets a partial, wrong neighbour set instead of an error.
    Marked xfail-STRICT so that fixing br-r37-c1-dwy1n turns this green loudly
    rather than leaving a passing test nobody re-reads.
    """
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        it = graph.neighbors("a")
        next(it)
        graph.add_edge("a", "new_during_iteration")
        with pytest.raises(RuntimeError):
            list(it)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_absent_node_raises_like_networkx(cls_name):
    gnx, gfx = _pair(cls_name)
    with pytest.raises(Exception) as nx_err:
        list(gnx.neighbors("missing"))
    with pytest.raises(Exception) as fnx_err:
        list(gfx.neighbors("missing"))
    assert type(fnx_err.value) is type(nx_err.value)
    assert str(fnx_err.value) == str(nx_err.value)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_unhashable_node_raises_typeerror_like_networkx(cls_name):
    """`self._adj[n]` hashes n first, so this must be a TypeError, not absence."""

    class Unhashable(str):
        __hash__ = None

    gnx, gfx = _pair(cls_name)
    with pytest.raises(TypeError) as nx_err:
        list(gnx.neighbors(Unhashable("a")))
    with pytest.raises(TypeError) as fnx_err:
        list(gfx.neighbors(Unhashable("a")))
    assert str(fnx_err.value) == str(nx_err.value)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_isolated_node_yields_nothing(cls_name):
    gnx, gfx = _pair(cls_name)
    assert list(gfx.neighbors("lonely")) == list(gnx.neighbors("lonely")) == []


@pytest.mark.parametrize("cls_name", CLASSES)
def test_row_cache_is_not_served_after_remove_and_readd(cls_name):
    """The cache-first reordering's one real hazard.

    The `has_node` probe now runs only on a cache MISS, so a stale row surviving
    a removal would be served as if the node were still present.
    """
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        list(graph.neighbors("a"))  # populate any row cache
        graph.remove_node("a")
    for graph, name in ((gnx, "nx"), (gfx, "fnx")):
        with pytest.raises(Exception):
            list(graph.neighbors("a"))
    for graph in (gnx, gfx):
        graph.add_node("a")
    assert list(gfx.neighbors("a")) == list(gnx.neighbors("a")) == []
    for graph in (gnx, gfx):
        graph.add_edge("a", "b")
    assert sorted(gfx.neighbors("a")) == sorted(gnx.neighbors("a")) == ["b"]
