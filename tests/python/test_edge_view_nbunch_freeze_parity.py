"""Differential lock for br-r37-c1-2pia7 — how a called view treats its nbunch.

networkx resolves an nbunch exactly once, in the data view's ``__init__``::

    nbunch = dict.fromkeys(viewer._graph.nbunch_iter(nbunch))
    self._nodes_nbrs = lambda: [(n, adjdict[n]) for n in nbunch]

Two consequences, and fnx got each one wrong on a different set of classes.
Both are asserted here for all four.

* The node SET is frozen at construction. A node the caller named that was not
  in the graph then is dropped permanently, so adding it later must NOT make
  its edges appear. fnx's Graph kept the caller's RAW nbunch and re-resolved it
  on every read — which, once br-r37-c1-af0ig made these views live, meant a
  later-added node started contributing edges networkx never yields.

* The adjacency behind that frozen set stays LIVE, and it is indexed per node
  on every iteration — so removing one of the frozen nodes makes a later read
  raise ``KeyError`` rather than quietly returning the survivors. fnx's walks
  skip absent nodes, which is right for a node that never existed and wrong for
  one that was resolved into the frozen set and has since been removed.

The two pull in opposite directions, which is why both sides are pinned: a fix
that froze harder would break liveness, and one that re-resolved would
resurrect the dropped node.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
FORMS = {
    "edges(nbunch)": lambda g, nb: g.edges(nb),
    "edges(nbunch,data=True)": lambda g, nb: g.edges(nb, data=True),
}


def _pair(cls_name):
    made = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b", weight=1.0)
        graph.add_edge("b", "c", weight=2.0)
        made.append(graph)
    return made


def _read(view):
    return sorted(map(str, view))


def _outcome(fn):
    try:
        return ("ok", fn())
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__, exc.args)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("form_name", list(FORMS))
def test_absent_node_named_in_nbunch_never_joins_later(cls_name, form_name):
    """The frozen-set half: 'x' is not a node yet, so it never counts."""
    form = FORMS[form_name]
    outcomes = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b")
        view = form(graph, ["a", "b", "x"])
        graph.add_edge("x", "y")
        outcomes.append(_read(view))
    assert outcomes[1] == outcomes[0]
    assert not any("'x', 'y'" in entry for entry in outcomes[1])


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("form_name", list(FORMS))
@pytest.mark.parametrize(
    "removal",
    ["remove_node", "clear"],
)
def test_removing_a_frozen_nbunch_node_raises_like_networkx(cls_name, form_name, removal):
    """The live-adjacency half: nx indexes each frozen node and raises."""
    form = FORMS[form_name]
    outcomes = []
    for lib in (nx, fnx):
        gnx, gfx = None, None
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        view = form(graph, ["a", "b"])
        if removal == "clear":
            graph.clear()
        else:
            graph.remove_node("a")
        outcomes.append(_outcome(lambda v=view: _read(v)))
        outcomes.append(_outcome(lambda v=view: len(v)))
    assert outcomes[2:] == outcomes[:2]
    assert outcomes[0][0] == "KeyError"


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("form_name", list(FORMS))
def test_edges_among_frozen_nodes_stay_live(cls_name, form_name):
    """Freezing the node set must not have frozen the adjacency with it."""
    form = FORMS[form_name]
    outcomes = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        view = form(graph, ["a", "b"])
        graph.add_edge("a", "c")  # both endpoints already present
        outcomes.append(_read(view))
    assert outcomes[1] == outcomes[0]


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("form_name", list(FORMS))
def test_removing_a_node_outside_the_nbunch_does_not_raise(cls_name, form_name):
    """Only the view's OWN frozen nodes make it raise."""
    form = FORMS[form_name]
    outcomes = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b")
        graph.add_edge("c", "d")
        view = form(graph, ["a", "b"])
        graph.remove_node("d")
        outcomes.append(_outcome(lambda v=view: _read(v)))
    assert outcomes[1] == outcomes[0]
    assert outcomes[0][0] == "ok"


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("form_name", list(FORMS))
def test_a_node_that_never_existed_does_not_make_reads_raise(cls_name, form_name):
    """It was dropped at construction, so it cannot later trigger the raise.

    This is the boundary between the two halves: 'ghost' is filtered out by
    nbunch resolution, whereas 'a' is resolved IN and its later removal raises.
    """
    form = FORMS[form_name]
    outcomes = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b")
        view = form(graph, ["a", "ghost"])
        graph.add_edge("b", "c")
        outcomes.append(_outcome(lambda v=view: _read(v)))
    assert outcomes[1] == outcomes[0]
    assert outcomes[0][0] == "ok"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_unrestricted_views_are_unaffected_by_the_freeze(cls_name):
    """No nbunch means no frozen set; those views stay fully live."""
    outcomes = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b")
        view = graph.edges(data=True)
        graph.remove_node("a")
        graph.add_edge("x", "y")
        outcomes.append((_read(view), len(view)))
    assert outcomes[1] == outcomes[0]
