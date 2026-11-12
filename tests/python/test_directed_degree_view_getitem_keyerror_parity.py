"""Differential lock for br-r37-c1-i89jx — indexing a directed degree view.

networkx's ``DiDegreeView.__getitem__`` reads ``self._succ[n]`` / ``self._pred[n]``,
so indexing a node that is not in the graph raises ``KeyError``. fnx's unweighted
native fast path (``_native_out_degree`` / ``_native_in_degree``) answered ``0``
for an absent node instead — and 0 is a perfectly plausible degree, so the caller
got a real-looking number and kept computing where networkx would have raised.

The other paths through the same accessor already agreed with networkx (weighted,
subgraph-filtered, and reverse views all reach the adjacency lookup rather than the
native counter), so they are asserted here too: they are the in-tree control that
located the defect, and they must not regress while the fast path is changed.

NOTE on exception ARGUMENTS: this file compares exception TYPE only for the
subgraph and reverse views. Their KeyError *messages* diverge from networkx —
exactly swapped, nx saying "Key zzz not found" where fnx says "zzz" on a subgraph
and the reverse on a reverse view. That is a separate, pre-existing defect
(reproduced against a tree predating this fix) tracked in br-r37-c1-k4nsd, and
deliberately not conflated with this one. For the plain-graph rows the fix is
responsible for, the args ARE compared.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

DIRECTED = ["DiGraph", "MultiDiGraph"]
ACCESSORS = ["in_degree", "out_degree"]
MISSING = ["zzz", 99, (1, 2)]


def _pair(cls_name):
    made = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b", weight=2.0)
        graph.add_node("iso")
        made.append(graph)
    return made


def _view(graph, accessor, weighted):
    return getattr(graph, accessor)(weight="weight") if weighted else getattr(graph, accessor)


@pytest.mark.parametrize("cls_name", DIRECTED)
@pytest.mark.parametrize("accessor", ACCESSORS)
@pytest.mark.parametrize("weighted", [False, True], ids=["unweighted", "weighted"])
@pytest.mark.parametrize("missing", MISSING, ids=["str", "int", "tuple"])
def test_missing_node_raises_keyerror_like_networkx(cls_name, accessor, weighted, missing):
    """The defect: the unweighted rows answered 0 instead of raising."""
    gnx, gfx = _pair(cls_name)
    with pytest.raises(KeyError) as caught_nx:
        _view(gnx, accessor, weighted)[missing]
    with pytest.raises(KeyError) as caught_fx:
        _view(gfx, accessor, weighted)[missing]
    assert caught_fx.value.args == caught_nx.value.args


@pytest.mark.parametrize("cls_name", DIRECTED)
@pytest.mark.parametrize("accessor", ACCESSORS)
@pytest.mark.parametrize("weighted", [False, True], ids=["unweighted", "weighted"])
@pytest.mark.parametrize("node", ["a", "b", "iso"], ids=["source", "target", "isolated"])
def test_present_node_still_answers_the_same_number(cls_name, accessor, weighted, node):
    """The isolated node is the one that matters: its degree IS 0.

    The fix charges a membership probe only when the answer is 0, so an
    in-graph node with no edges is exactly the case that must keep answering
    0 rather than starting to raise.
    """
    gnx, gfx = _pair(cls_name)
    assert _view(gfx, accessor, weighted)[node] == _view(gnx, accessor, weighted)[node]


@pytest.mark.parametrize("cls_name", DIRECTED)
@pytest.mark.parametrize("accessor", ACCESSORS)
@pytest.mark.parametrize("weighted", [False, True], ids=["unweighted", "weighted"])
@pytest.mark.parametrize("kind", ["subgraph", "reverse"])
def test_view_backed_graphs_still_raise(cls_name, accessor, weighted, kind):
    """The in-tree control paths: already correct, must stay correct.

    Type only — see the module docstring on br-r37-c1-k4nsd for the message
    divergence these two paths carry independently of this bead.
    """
    gnx, gfx = _pair(cls_name)
    if kind == "subgraph":
        gnx, gfx = gnx.subgraph(["a", "b", "iso"]), gfx.subgraph(["a", "b", "iso"])
    else:
        gnx, gfx = gnx.reverse(copy=False), gfx.reverse(copy=False)
    with pytest.raises(KeyError):
        _view(gnx, accessor, weighted)["zzz"]
    with pytest.raises(KeyError):
        _view(gfx, accessor, weighted)["zzz"]


@pytest.mark.parametrize("cls_name", DIRECTED)
@pytest.mark.parametrize("accessor", ACCESSORS)
def test_iteration_len_and_the_total_degree_sibling_are_unchanged(cls_name, accessor):
    """Iteration must not have picked up the membership probe.

    ``degree`` is the sibling that was already correct and is what the fix was
    modelled on, so it is re-asserted alongside.
    """
    gnx, gfx = _pair(cls_name)
    view_nx, view_fx = getattr(gnx, accessor), getattr(gfx, accessor)
    assert sorted(view_fx) == sorted(view_nx)
    assert len(view_fx) == len(view_nx)
    assert dict(view_fx) == dict(view_nx)
    with pytest.raises(KeyError):
        gfx.degree["zzz"]
    assert gfx.degree["iso"] == gnx.degree["iso"] == 0


@pytest.mark.parametrize("cls_name", DIRECTED)
def test_unhashable_index_still_raises_typeerror_not_keyerror(cls_name):
    """A dict lookup on an unhashable key raises TypeError in both libraries."""
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        with pytest.raises(TypeError):
            graph.in_degree[["not", "hashable"]]
