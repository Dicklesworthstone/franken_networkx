"""Differential lock for br-r37-c1-vfc2t — degree views are LIVE.

networkx's degree views reflect mutations made after the view is bound. fnx's
built their answers at construction and never refreshed, so a held view
reported pre-mutation degrees — and a degree is a number, so a stale one is
indistinguishable from a correct one::

    g.add_edges_from([(0,1),(1,2),(2,3)])
    v = g.degree([0, 1])
    g.add_edge(0, 3)

    list(v)   networkx -> [(0,2), (1,2)]
    list(v)   fnx      -> [(0,1), (1,2)]

Two shapes were affected and both are covered here: the nbunch-restricted views
(``degree(nbunch)``, ``out_degree(nbunch)``) and the unrestricted WEIGHTED one,
whose per-node values come from a native accumulator. The unweighted
unrestricted ``G.degree`` was live all along and is asserted alongside as the
control.

The two differ in what "live" means for the node SET, and the distinction is
asserted:

* an unrestricted view spans whatever the graph holds NOW, so nodes added after
  it was bound appear in it;
* an nbunch-restricted view keeps the node set it resolved at construction,
  because that is what networkx does with an nbunch (br-r37-c1-2pia7) — only
  the degrees go live.

KNOWN RESIDUE, excluded by name: after ``clear()``, a restricted view whose
frozen nodes are all gone should raise KeyError (networkx indexes each frozen
node), where fnx returns an empty result. That is the degree-view counterpart
of br-r37-c1-2pia7's first clause, it reaches proxy classes this fix does not
touch, and it is filed as br-r37-c1-ta5wq.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
DIRECTED = ["DiGraph", "MultiDiGraph"]

RESTRICTED = {
    "degree(nbunch)": lambda g: g.degree([0, 1]),
    "degree(nbunch,weight)": lambda g: g.degree([0, 1], weight="w"),
}
DIRECTED_RESTRICTED = {
    "in_degree(nbunch)": lambda g: g.in_degree([0, 1]),
    "out_degree(nbunch)": lambda g: g.out_degree([0, 1]),
    "out_degree(nbunch,weight)": lambda g: g.out_degree([0, 1], weight="w"),
}
UNRESTRICTED = {
    "degree": lambda g: g.degree,
    "degree(weight)": lambda g: g.degree(weight="w"),
}
DIRECTED_UNRESTRICTED = {
    "in_degree": lambda g: g.in_degree,
    "out_degree": lambda g: g.out_degree,
}

# `clear` is deliberately absent — see the module docstring (br-r37-c1-ta5wq).
MUTATIONS = {
    "add_edge_existing_nodes": lambda g: g.add_edge(0, 3),
    "add_edge_new_nodes": lambda g: g.add_edge(8, 9),
    "remove_edge": lambda g: g.remove_edge(0, 1),
    "add_node": lambda g: g.add_node(9),
    "remove_node": lambda g: g.remove_node(3),
    "swap_edge": lambda g: (g.remove_edge(0, 1), g.add_edge(0, 1)),
}


def _build(lib, cls_name):
    graph = getattr(lib, cls_name)()
    graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
    if graph.is_multigraph():
        graph[0][1][0]["w"] = 9
    else:
        graph[0][1]["w"] = 9
    return graph


def _forms(cls_name, restricted):
    if restricted:
        forms = dict(RESTRICTED)
        if cls_name in DIRECTED:
            forms.update(DIRECTED_RESTRICTED)
    else:
        forms = dict(UNRESTRICTED)
        if cls_name in DIRECTED:
            forms.update(DIRECTED_UNRESTRICTED)
    return forms


def _read(view):
    """Contents, length and dict — never the length alone."""
    return sorted(map(str, view)), len(view), sorted(dict(view).items(), key=str)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("restricted", [True, False], ids=["restricted", "unrestricted"])
@pytest.mark.parametrize("mutation", list(MUTATIONS), ids=list(MUTATIONS))
def test_degree_views_reflect_mutations_like_networkx(cls_name, restricted, mutation):
    mutate = MUTATIONS[mutation]
    for name, form in _forms(cls_name, restricted).items():
        readings = []
        for lib in (nx, fnx):
            graph = _build(lib, cls_name)
            view = form(graph)
            mutate(graph)
            readings.append(_read(view))
        assert readings[1] == readings[0], f"{cls_name} {name} after {mutation}"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_the_reported_case(cls_name):
    """The headline: a held restricted view reported a pre-mutation degree."""
    outcomes = []
    for lib in (nx, fnx):
        graph = _build(lib, cls_name)
        view = graph.degree([0, 1])
        graph.add_edge(0, 3)
        outcomes.append(sorted(view))
    assert outcomes[1] == outcomes[0]
    assert dict(outcomes[1])[0] == 2


@pytest.mark.parametrize("cls_name", CLASSES)
def test_unrestricted_views_pick_up_new_nodes(cls_name):
    """An unrestricted view spans the graph's CURRENT nodes."""
    for name, form in _forms(cls_name, restricted=False).items():
        outcomes = []
        for lib in (nx, fnx):
            graph = _build(lib, cls_name)
            view = form(graph)
            graph.add_node(42)
            outcomes.append((sorted(map(str, view)), len(view)))
        assert outcomes[1] == outcomes[0], name
        assert "('42', 0)" in str(outcomes[1][0]) or "(42, 0)" in str(outcomes[1][0]), name


@pytest.mark.parametrize("cls_name", CLASSES)
def test_restricted_views_keep_their_frozen_node_set(cls_name):
    """br-r37-c1-2pia7: the nbunch is resolved once; only degrees go live.

    A node added after the view was bound must NOT join it, even though the
    degrees of the nodes already in it do update.
    """
    for name, form in _forms(cls_name, restricted=True).items():
        outcomes = []
        for lib in (nx, fnx):
            graph = _build(lib, cls_name)
            view = form(graph)
            graph.add_edge(0, 42)
            outcomes.append(sorted(map(str, view)))
        assert outcomes[1] == outcomes[0], name
        assert not any("42" in entry for entry in outcomes[1]), name


@pytest.mark.parametrize("cls_name", CLASSES)
def test_repeated_reads_are_stable(cls_name):
    """Refreshing must be idempotent, not accumulate or drift."""
    for restricted in (True, False):
        for name, form in _forms(cls_name, restricted).items():
            graph = _build(fnx, cls_name)
            view = form(graph)
            baseline = _read(view)
            for _ in range(3):
                assert _read(view) == baseline, name
            graph.add_edge(0, 3)
            moved = _read(view)
            for _ in range(3):
                assert _read(view) == moved, name


@pytest.mark.parametrize("cls_name", CLASSES)
def test_indexing_and_class_name_survive_a_mutation(cls_name):
    """The other contracts on these views must not regress while going live."""
    for restricted in (True, False):
        for name, form in _forms(cls_name, restricted).items():
            gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
            view_nx, view_fx = form(gnx), form(gfx)
            assert type(view_fx).__name__ == type(view_nx).__name__, name
            for graph in (gnx, gfx):
                graph.add_edge(0, 3)
            for node in (0, 1, 2):
                assert view_fx[node] == view_nx[node], (name, node)
            assert type(view_fx).__name__ == type(view_nx).__name__, name
