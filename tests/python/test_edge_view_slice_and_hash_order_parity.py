"""Differential lock for br-r37-c1-60627 — `G.edges[...]` slicing and hash order.

Two divergences, both found by the coverage added for br-r37-c1-y2ww1 and both
on the views that lever did not touch:

1. SLICING. networkx raises ``NetworkXError`` naming the view class and telling
   you to use ``list(G.edges)[...]``. fnx fell through to a tuple unpack and
   raised a bare ``TypeError: cannot unpack non-iterable slice object`` on
   DiGraph, MultiGraph and MultiDiGraph — a different exception type and no
   guidance. The message embeds ``type(self).__name__``, which is why the four
   classes each expect a DIFFERENT string ("EdgeView", "OutEdgeView",
   "MultiEdgeView", "OutMultiEdgeView"); asserting against live networkx rather
   than a literal is what keeps that honest.

2. HASH ORDER on the directed view. ``G.edges[u, v]`` is ``self._adjdict[u][v]``,
   so networkx hashes ``u``, and an ABSENT ``u`` raises KeyError *without ever
   hashing* ``v``. fnx hashed both up front, turning that KeyError into a
   TypeError whenever ``v`` was unhashable — reporting "your key is unhashable"
   for a graph that simply does not contain ``u``.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


class _Unhashable(str):
    __hash__ = None


def _pair(cls_name):
    made = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b", w=1)
        graph.add_edge("b", "c", w=2)
        made.append(graph)
    return made


def _outcome(fn, graph):
    try:
        return ("value", repr(fn(graph)))
    except Exception as exc:  # noqa: BLE001 - the exception IS the contract
        return ("raised", type(exc).__name__, exc.args)


SLICES = {
    "plain": slice(1, 2),
    "with-step": slice(0, 5, 2),
    "open-start": slice(None, 3),
    "open-all": slice(None, None, None),
    "negative": slice(-2, -1),
}


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("slice_name", list(SLICES))
def test_edge_view_slice_matches_networkx(cls_name, slice_name):
    """Exception type AND message, including the per-class view name."""
    gnx, gfx = _pair(cls_name)
    the_slice = SLICES[slice_name]
    assert _outcome(lambda g: g.edges[the_slice], gfx) == _outcome(
        lambda g: g.edges[the_slice], gnx
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_slice_error_names_the_networkx_view_class(cls_name):
    """The message is not a constant — it embeds the view's own class name."""
    gnx, gfx = _pair(cls_name)
    with pytest.raises(Exception) as nx_err:
        gnx.edges[1:2]
    with pytest.raises(Exception) as fnx_err:
        gfx.edges[1:2]
    assert type(fnx_err.value) is type(nx_err.value)
    assert str(fnx_err.value) == str(nx_err.value)
    assert type(gnx.edges).__name__ in str(nx_err.value)


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_absent_u_short_circuits_before_hashing_v(cls_name):
    """The hash-order boundary, asserted from both sides."""
    gnx, gfx = _pair(cls_name)
    # u present, v unhashable -> v IS hashed -> TypeError
    assert _outcome(lambda g: g.edges["a", _Unhashable("b")], gfx) == _outcome(
        lambda g: g.edges["a", _Unhashable("b")], gnx
    )
    # u absent -> KeyError before v is ever hashed
    assert _outcome(lambda g: g.edges["zz", _Unhashable("b")], gfx) == _outcome(
        lambda g: g.edges["zz", _Unhashable("b")], gnx
    )


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize(
    "probe_name",
    ["present", "absent-u", "absent-v", "both-absent", "unhashable-u", "not-a-tuple"],
)
def test_ordinary_subscripts_are_unchanged(cls_name, probe_name):
    """The reordering must not disturb anything else on this surface."""
    gnx, gfx = _pair(cls_name)
    multi = cls_name.startswith("Multi")
    probes = {
        "present": lambda g: dict(g.edges["a", "b", 0] if multi else g.edges["a", "b"]),
        "absent-u": lambda g: g.edges["zz", "b"],
        "absent-v": lambda g: g.edges["a", "zz"],
        "both-absent": lambda g: g.edges["zz", "yy"],
        "unhashable-u": lambda g: g.edges[_Unhashable("a"), "b"],
        "not-a-tuple": lambda g: g.edges[42],
    }
    probe = probes[probe_name]
    assert _outcome(probe, gfx) == _outcome(probe, gnx)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_slice_does_not_mutate_or_dirty_the_graph(cls_name):
    """A rejected subscript must leave the graph exactly as it was."""
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        with pytest.raises(Exception):
            graph.edges[0:1]
    assert sorted(gfx.edges(data=True)) == sorted(gnx.edges(data=True))
    assert sorted(gfx.nodes()) == sorted(gnx.nodes())
