"""br-r37-c1-wdgb8 — a row held across ``clear()`` must serve its snapshot.

networkx's ``G.adj[u]`` wraps the inner ``_adj[u]`` dict and ``clear()`` rebinds
``_adj`` to a fresh one, so a reference the caller already holds keeps its old
contents: stale, but alive and readable. br-r37-c1-s5pxs made fnx match by
snapshotting held rows at CLEAR time — and it matched for one spelling only.

    after clear(), reading row['vvv']      G.adj[u]        G[u]
      networkx, all four classes           snapshot        snapshot
      fnx before this fix                  snapshot        KeyError('vvv')   <- MultiGraph
                                                                              and MultiDiGraph

WHY IT WAS HALF-DONE, and it is a shape worth recognising: there are TWO row
caches, not one. The adjacency view keeps its rows on itself, under
``_fnx_row_cache`` / ``_fnx_atlas_cache``. But ``G[u]`` is served by
``_multigraph_getitem_from_native_row`` and its siblings, which cache on the
GRAPH's own instance dict under ``_fnx_getitem_atlas_cache``. The detach sweep
walked ``vars(graph)`` calling ``getattr(view, cache_name, None)`` on each
value — and that entry is a plain ``(nodes_seq, {node: row})`` TUPLE, which has
no such attribute, so it was skipped in silence. Nothing raised, nothing warned;
one of the two ways to spell the same lookup simply kept the old behaviour.

The simple classes were already correct on both spellings because their rows are
backed by a Rust-maintained live PyDict that ``clear()`` drops from the map
without emptying the dict object, so they never depended on the sweep.

WHAT THIS FILE PINS: both spellings, all four classes, against networkx — plus
the two contracts the snapshot must not cost, because a detached row is a plain
dict and it would be easy to lose them:

  * an unhashable key still raises networkx's ``TypeError``, not ``KeyError``.
    ``AdjacencyView.__getitem__`` skips its explicit ``hash()`` when it is
    serving a captured row (br-r37-c1-2ndmw), so after a detach the snapshot
    dict is the only thing left to raise, and a plain dict does hash. If that
    ever stops being a dict, this catches it.
  * the row is DETACHED, not merely stale: later mutations to the graph must not
    reach it, matching networkx, whose held dict is no longer in ``_adj``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python"))

import franken_networkx as fnx  # noqa: E402

CLASSES = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")
SPELLINGS = ("G[u]", "G.adj[u]")


def _row(graph, node, spelling):
    return graph[node] if spelling == "G[u]" else graph.adj[node]


def _pair(cls_name):
    out = []
    for module in (nx, fnx):
        graph = getattr(module, cls_name)()
        graph.add_edge("uuu", "vvv", weight=1)
        graph.add_edge("uuu", "www", weight=2)
        out.append(graph)
    return out[0], out[1]


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("spelling", SPELLINGS)
def test_held_row_serves_its_snapshot_after_clear(cls_name, spelling):
    """The defect, on both spellings, asserted against networkx."""
    graph_nx, graph_fnx = _pair(cls_name)
    row_nx = _row(graph_nx, "uuu", spelling)
    row_fnx = _row(graph_fnx, "uuu", spelling)

    before_nx = dict(row_nx["vvv"])
    before_fnx = dict(row_fnx["vvv"])
    assert before_fnx == before_nx

    graph_nx.clear()
    graph_fnx.clear()

    assert dict(row_nx["vvv"]) == before_nx, "networkx changed its own behaviour"
    assert dict(row_fnx["vvv"]) == before_fnx, (
        f"{cls_name} via {spelling}: the held row lost its snapshot across "
        "clear() — networkx still serves it"
    )
    assert sorted(row_fnx) == sorted(row_nx)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("spelling", SPELLINGS)
def test_detached_row_raises_networkxs_typeerror_for_an_unhashable_key(
    cls_name, spelling
):
    """A detached row is a plain dict, and it still has to hash its key.

    `AdjacencyView.__getitem__` skips its explicit `hash()` when serving a
    captured row, so after the detach the snapshot is the only thing that can
    turn an unhashable key into networkx's TypeError instead of a KeyError.
    """
    graph_nx, graph_fnx = _pair(cls_name)
    row_nx = _row(graph_nx, "uuu", spelling)
    row_fnx = _row(graph_fnx, "uuu", spelling)
    row_nx["vvv"], row_fnx["vvv"]

    graph_nx.clear()
    graph_fnx.clear()

    for bad in (["x"], {1: 2}, {"s"}):
        with pytest.raises(TypeError) as nx_exc:
            row_nx[bad]
        with pytest.raises(TypeError) as fnx_exc:
            row_fnx[bad]
        assert str(fnx_exc.value) == str(nx_exc.value)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("spelling", SPELLINGS)
def test_detached_row_is_cut_loose_not_merely_stale(cls_name, spelling):
    """Mutations after the clear must not reach a detached row.

    networkx's held dict is no longer in `_adj`, so a later `add_edge` builds a
    NEW row and the old reference cannot see it. A snapshot that stayed wired to
    the live storage would pass the test above and fail this one.
    """
    graph_nx, graph_fnx = _pair(cls_name)
    row_nx = _row(graph_nx, "uuu", spelling)
    row_fnx = _row(graph_fnx, "uuu", spelling)
    row_nx["vvv"], row_fnx["vvv"]

    graph_nx.clear()
    graph_fnx.clear()
    graph_nx.add_edge("uuu", "later", weight=9)
    graph_fnx.add_edge("uuu", "later", weight=9)

    assert ("later" in row_fnx) == ("later" in row_nx)
    assert sorted(row_fnx) == sorted(row_nx)
    assert dict(row_fnx["vvv"]) == dict(row_nx["vvv"])


@pytest.mark.parametrize("cls_name", CLASSES)
def test_both_spellings_agree_with_each_other_across_clear(cls_name):
    """The two routes to the same row must not diverge from ONE ANOTHER either.

    This is the assertion that would have caught the defect without networkx in
    the room: `G[u]` and `G.adj[u]` are two spellings of one lookup, and before
    the fix one of them raised while the other served.
    """
    _graph_nx, graph_fnx = _pair(cls_name)
    direct = graph_fnx["uuu"]
    via_adj = graph_fnx.adj["uuu"]
    direct["vvv"], via_adj["vvv"]

    graph_fnx.clear()

    assert dict(direct["vvv"]) == dict(via_adj["vvv"])
    assert sorted(direct) == sorted(via_adj)
