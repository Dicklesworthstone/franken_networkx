"""Lock for br-r37-c1-s5pxs — an adjacency row held across ``G.clear()``.

networkx's ``G.adj[u]`` wraps the inner ``_adj[u]`` dict, and ``clear()`` rebinds
``_adj`` to a fresh dict, so a reference someone already holds keeps its old
contents: stale, but alive and readable. fnx's rows read the graph's storage, so
clearing the storage used to empty them (multigraphs) or make them raise
``KeyError`` (simple Graph and DiGraph). The rows are now detached at clear time.

The bead recorded Graph and DiGraph as ALREADY matching. They did not — they
raised ``KeyError``, a worse divergence than the multigraphs' silent empty — so
all four classes are asserted here rather than the two the bead named.

The detach is at CLEAR time, not capture time, and that ordering is the whole
design: a captured row must still see later edge and node churn, which is what
``test_row_stays_live_until_the_clear`` exists to prove. A snapshot taken at
capture would pass the clear tests and silently break every liveness contract
that already matched.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(lib, cls_name):
    graph = getattr(lib, cls_name)()
    graph.add_edge("a", "b", w=1)
    graph.add_edge("a", "c")
    if graph.is_multigraph():
        graph.add_edge("a", "b")  # a parallel edge, so the row value has 2 keys
    return graph


def _read(row):
    try:
        return (
            sorted(row),
            len(row),
            "b" in row,
            "zz" in row,
            {k: dict(v) for k, v in row.items()},
            type(row["b"]).__name__,
        )
    except Exception as exc:  # noqa: BLE001
        return ("raised", type(exc).__name__)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_row_held_across_clear_reads_like_networkx(cls_name):
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    rnx, rfx = gnx.adj["a"], gfx.adj["a"]
    gnx.clear()
    gfx.clear()
    assert _read(rfx) == _read(rnx)
    assert _read(rfx)[0] == ["b", "c"], "the row went empty instead of staying stale"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_row_held_across_clear_matches_whether_or_not_it_was_read_first(cls_name):
    """The answer must not depend on whether the row was materialised already.

    The native row detaches by materialising, so a row that had been iterated
    before the clear was ALREADY correct while an untouched one was not. An
    answer that depends on prior reads is the cache-state bug pattern.
    """
    for pre_read in (False, True):
        gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
        rnx, rfx = gnx.adj["a"], gfx.adj["a"]
        if pre_read:
            list(rnx)
            list(rfx)
        gnx.clear()
        gfx.clear()
        assert _read(rfx) == _read(rnx), f"pre_read={pre_read}"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_row_stays_live_until_the_clear(cls_name):
    """The contracts that already matched must survive the detach.

    Detaching at clear time rather than capture time is what preserves these; a
    capture-time snapshot would pass the tests above and break every one of
    these silently.
    """
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    rnx, rfx = gnx.adj["a"], gfx.adj["a"]

    for graph in (gnx, gfx):
        graph.add_edge("a", "d")
    assert sorted(rfx) == sorted(rnx) == ["b", "c", "d"]

    for graph in (gnx, gfx):
        graph.remove_edge("a", "c")
    assert sorted(rfx) == sorted(rnx) == ["b", "d"]

    for graph in (gnx, gfx):
        graph.add_node("e")
    assert sorted(rfx) == sorted(rnx) == ["b", "d"]

    for graph in (gnx, gfx):
        graph.remove_node("d")
    assert sorted(rfx) == sorted(rnx) == ["b"]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_graph_is_actually_empty_after_the_clear(cls_name):
    """Detaching a row must not resurrect the graph itself."""
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    gfx.adj["a"]  # hand out a row so the detach path runs
    gnx.adj["a"]
    gnx.clear()
    gfx.clear()
    assert len(gfx) == len(gnx) == 0
    assert gfx.number_of_edges() == gnx.number_of_edges() == 0
    assert list(gfx.adj) == list(gnx.adj) == []
    assert dict(gfx.graph) == dict(gnx.graph)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_clear_still_works_with_no_row_ever_handed_out(cls_name):
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    gnx.clear()
    gfx.clear()
    assert len(gfx) == len(gnx) == 0
    gfx.add_edge("x", "y")
    gnx.add_edge("x", "y")
    assert sorted(gfx.adj["x"]) == sorted(gnx.adj["x"]) == ["y"]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_second_clear_after_a_detach_is_still_clean(cls_name):
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    rnx, rfx = gnx.adj["a"], gfx.adj["a"]
    for graph in (gnx, gfx):
        graph.clear()
        graph.add_edge("p", "q")
        graph.clear()
    assert _read(rfx) == _read(rnx)
    assert len(gfx) == len(gnx) == 0
