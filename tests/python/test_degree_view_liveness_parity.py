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

A restricted view whose frozen nodes have since been REMOVED raises KeyError on
iteration, because networkx indexes the adjacency per frozen node — that is
br-r37-c1-pejo5, now fixed, and ``clear`` is covered below. Note the asymmetry
it turned on: ``len()`` does NOT raise, because networkx's ``__len__`` answers
``len(self._nodes)`` without touching the adjacency at all. Both halves are
asserted, since a check placed in ``__len__`` passes the iteration test while
breaking the length one.
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

MUTATIONS = {
    "clear": lambda g: g.clear(),
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
    """Contents, length and dict — never the length alone.

    Returns the exception signature instead of raising, because after a
    ``clear()`` a restricted view is SUPPOSED to raise on iteration
    (br-r37-c1-pejo5) while still answering ``len()`` — so the comparison has
    to cover both outcomes rather than blow up on the first.
    """
    try:
        contents = sorted(map(str, view))
    except Exception as exc:  # noqa: BLE001
        contents = (type(exc).__name__, exc.args)
    try:
        length = len(view)
    except Exception as exc:  # noqa: BLE001
        length = (type(exc).__name__, exc.args)
    try:
        mapping = sorted(dict(view).items(), key=str)
    except Exception as exc:  # noqa: BLE001
        mapping = (type(exc).__name__, exc.args)
    return contents, length, mapping


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
@pytest.mark.parametrize("restricted", [False, True], ids=["whole", "nbunch"])
@pytest.mark.parametrize("weighted", [False, True], ids=["plain", "weighted"])
def test_degree_iterator_defers_snapshot_until_first_next(cls_name, restricted, weighted):
    """`iter(view)` itself must not freeze degree values.

    This is deliberately broader than the original restricted/unweighted repro:
    a fix that only defers Graph's raw iterator misses multigraph native paths;
    a fix that only changes whole views misses `_FilteredDegreeView`; and a fix
    that only changes counts misses the weighted native accumulator.  In every
    case NetworkX sees the edge added *after* `iter()` but before `next()`.
    """
    outcomes = []
    for lib in (nx, fnx):
        graph = _build(lib, cls_name)
        if restricted:
            view = graph.degree([0, 1, 2, 3], weight="w" if weighted else None)
        else:
            view = graph.degree(weight="w") if weighted else graph.degree
        iterator = iter(view)
        graph.add_edge(0, 3, w=7)
        outcomes.append(list(iterator))

    assert outcomes[1] == outcomes[0]
    assert dict(outcomes[1])[0] == (16 if weighted else 2)


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


@pytest.mark.parametrize("cls_name", CLASSES)
def test_removing_a_frozen_node_raises_on_iteration_but_not_on_len(cls_name):
    """br-r37-c1-pejo5, including the asymmetry that makes it easy to get wrong.

    networkx's degree view indexes the adjacency for each frozen nbunch node
    when it iterates, so a removed one raises; its ``__len__`` answers from the
    frozen node list and never touches the adjacency, so it does NOT raise.
    """
    for name, form in _forms(cls_name, restricted=True).items():
        outcomes = []
        for lib in (nx, fnx):
            graph = _build(lib, cls_name)
            view = form(graph)
            graph.remove_node(0)
            try:
                outcomes.append(("iter", sorted(map(str, view))))
            except Exception as exc:  # noqa: BLE001
                outcomes.append(("iter", type(exc).__name__, exc.args))
            try:
                outcomes.append(("len", len(view)))
            except Exception as exc:  # noqa: BLE001
                outcomes.append(("len", type(exc).__name__, exc.args))
        assert outcomes[2:] == outcomes[:2], name
        assert outcomes[0][1] == "KeyError", (name, outcomes[0])
        assert outcomes[1][0] == "len" and not isinstance(outcomes[1][1], str), name


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_never_existing_nbunch_node_does_not_raise(cls_name):
    """The boundary: it was dropped at resolution, so it is not frozen IN."""
    outcomes = []
    for lib in (nx, fnx):
        graph = _build(lib, cls_name)
        view = graph.degree([0, "ghost"])
        graph.add_edge(5, 6)
        outcomes.append(sorted(map(str, view)))
    assert outcomes[1] == outcomes[0]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_removing_a_node_outside_the_nbunch_does_not_raise(cls_name):
    outcomes = []
    for lib in (nx, fnx):
        graph = _build(lib, cls_name)
        view = graph.degree([0, 1])
        graph.remove_node(3)
        outcomes.append(sorted(map(str, view)))
    assert outcomes[1] == outcomes[0]
