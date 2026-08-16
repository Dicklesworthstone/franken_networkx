"""Core Graph/DiGraph surface parity WITHOUT normalising the answers.

br-r37-c1-2zsnw asks for foundation parity across views, data access, mutation
and subgraph views. ``test_graph_class_method_parity.py`` already covers those
four areas — but every assertion in it runs the result through ``sorted()``,
``dict()`` or ``tuple(sorted(...))`` first, so it compares CONTENT and discards
three things the drop-in contract depends on:

* iteration ORDER — networkx's views iterate in insertion order and algorithms
  built on them inherit that order, so a reordering changes tie-breaks in
  everything downstream while a sorted comparison stays green;
* view IDENTITY — ``type(view).__name__`` and ``repr(view)``, both of which this
  repo already treats as parity surface;
* LIVENESS — whether a view bound before a mutation reflects it.

That gap is not hypothetical. Five parity defects on exactly this surface were
found and fixed on 2026-08-15 (br-r37-c1-1x6aq, p1uro, i89jx, af0ig, k4nsd),
and every one of them would have passed a sorted/dict comparison.

So this file compares raw: no sorting, no dict() round-trip, and it holds views
across mutations. It is a complement to the existing file, not a replacement.

ONE DELIBERATE DEVIATION, asserted rather than skipped: ``repr(G)`` differs.
networkx defines no ``__repr__`` for graphs, so it falls back to
``<networkx.classes.graph.Graph object at 0x...>``, which embeds a memory
address and cannot be matched meaningfully. fnx returns ``Graph(nodes=5,
edges=3)``. ``__str__`` IS networkx's documented contract and matches exactly on
all four classes; that is what is asserted here.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph"]
DIRECTED = ["DiGraph"]


def _setup(lib, cls_name):
    graph = getattr(lib, cls_name)()
    graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
    graph.add_node(5, color="red")
    graph.nodes[0]["x"] = 1
    graph[0][1]["w"] = 9
    return graph


def _pair(cls_name):
    return _setup(nx, cls_name), _setup(fnx, cls_name)


# Every probe returns something ORDER-SENSITIVE or IDENTITY-SENSITIVE.
ORDERED_VIEWS = {
    "list(g)": lambda g: list(g),
    "list(nodes)": lambda g: list(g.nodes),
    "list(nodes(data=True))": lambda g: list(g.nodes(data=True)),
    "list(nodes(data='color'))": lambda g: list(g.nodes(data="color")),
    "list(nodes(data='color',default=1))": lambda g: list(g.nodes(data="color", default=1)),
    "list(edges)": lambda g: list(g.edges),
    "list(edges(data=True))": lambda g: list(g.edges(data=True)),
    "list(edges(data='w'))": lambda g: list(g.edges(data="w")),
    "list(adj)": lambda g: list(g.adj),
    "list(adj[1])": lambda g: list(g.adj[1]),
    "list(g[1])": lambda g: list(g[1]),
    "list(neighbors(1))": lambda g: list(g.neighbors(1)),
    "list(degree)": lambda g: list(g.degree),
    "list(degree(weight='w'))": lambda g: list(g.degree(weight="w")),
    "list(nbunch_iter([0,1,99]))": lambda g: list(g.nbunch_iter([0, 1, 99])),
}
DIRECTED_ORDERED_VIEWS = {
    "list(in_degree)": lambda g: list(g.in_degree),
    "list(out_degree)": lambda g: list(g.out_degree),
    "list(successors(1))": lambda g: list(g.successors(1)),
    "list(predecessors(1))": lambda g: list(g.predecessors(1)),
    "list(in_edges)": lambda g: list(g.in_edges),
    "list(out_edges)": lambda g: list(g.out_edges),
    "list(pred)": lambda g: list(g.pred),
    "list(succ)": lambda g: list(g.succ),
    "list(reverse().edges)": lambda g: list(g.reverse().edges),
}

VIEW_IDENTITY = {
    "nodes": lambda g: g.nodes,
    "edges": lambda g: g.edges,
    "adj": lambda g: g.adj,
    "degree": lambda g: g.degree,
}
DIRECTED_VIEW_IDENTITY = {
    "pred": lambda g: g.pred,
    "succ": lambda g: g.succ,
    "in_degree": lambda g: g.in_degree,
    "out_degree": lambda g: g.out_degree,
    "in_edges": lambda g: g.in_edges,
    "out_edges": lambda g: g.out_edges,
}

DATA_ACCESS = {
    "get_edge_data(0,1)": lambda g: g.get_edge_data(0, 1),
    "get_edge_data(9,9)": lambda g: g.get_edge_data(9, 9),
    "get_edge_data(9,9,default)": lambda g: g.get_edge_data(9, 9, "dflt"),
    "nodes[0]": lambda g: dict(g.nodes[0]),
    "size()": lambda g: g.size(),
    "size(weight='w')": lambda g: g.size(weight="w"),
    "order()": lambda g: g.order(),
    "number_of_edges()": lambda g: g.number_of_edges(),
    "number_of_edges(0,1)": lambda g: g.number_of_edges(0, 1),
    "has_edge(0,1)": lambda g: g.has_edge(0, 1),
    "has_node(5)": lambda g: g.has_node(5),
    "is_directed()": lambda g: g.is_directed(),
    "is_multigraph()": lambda g: g.is_multigraph(),
    "str(g)": lambda g: str(g),
}


def _ordered_for(cls_name):
    probes = dict(ORDERED_VIEWS)
    if cls_name in DIRECTED:
        probes.update(DIRECTED_ORDERED_VIEWS)
    return probes


def _identity_for(cls_name):
    probes = dict(VIEW_IDENTITY)
    if cls_name in DIRECTED:
        probes.update(DIRECTED_VIEW_IDENTITY)
    return probes


@pytest.mark.parametrize("cls_name", CLASSES)
def test_view_iteration_order_matches_networkx_exactly(cls_name):
    """No sorting: the order itself is the assertion."""
    gnx, gfx = _pair(cls_name)
    for name, probe in _ordered_for(cls_name).items():
        assert probe(gfx) == probe(gnx), name


@pytest.mark.parametrize("cls_name", CLASSES)
def test_view_class_names_and_reprs_match_networkx(cls_name):
    gnx, gfx = _pair(cls_name)
    for name, probe in _identity_for(cls_name).items():
        view_nx, view_fx = probe(gnx), probe(gfx)
        assert type(view_fx).__name__ == type(view_nx).__name__, name
        assert repr(view_fx) == repr(view_nx), name
        assert len(view_fx) == len(view_nx), name


@pytest.mark.parametrize("cls_name", CLASSES)
def test_data_access_matches_networkx(cls_name):
    gnx, gfx = _pair(cls_name)
    for name, probe in DATA_ACCESS.items():
        assert probe(gfx) == probe(gnx), name


@pytest.mark.parametrize("cls_name", CLASSES)
def test_graph_str_is_networkxs_documented_contract(cls_name):
    """__str__ matches; __repr__ deliberately does not — see module docstring."""
    gnx, gfx = _pair(cls_name)
    assert str(gfx) == str(gnx)
    assert repr(gfx) != repr(gnx)
    assert repr(gfx).startswith(f"{cls_name}(nodes=")
    assert "object at 0x" in repr(gnx)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_views_bound_before_mutation_stay_live(cls_name):
    """Views are live in networkx; hold them ACROSS the mutation.

    The existing coverage rebinds after mutating, which cannot detect a
    snapshot. This is how br-r37-c1-af0ig's frozen edge view went unnoticed.
    """
    gnx, gfx = _pair(cls_name)
    held_nx = {name: probe(gnx) for name, probe in _identity_for(cls_name).items()}
    held_fx = {name: probe(gfx) for name, probe in _identity_for(cls_name).items()}
    for graph in (gnx, gfx):
        graph.add_edge(3, 4)
        graph.remove_edge(0, 1)
        graph.add_node(7, color="blue")
        graph.remove_node(5)
    for name in held_nx:
        assert list(held_fx[name]) == list(held_nx[name]), name
        assert len(held_fx[name]) == len(held_nx[name]), name


# The CALLED forms, which are separate objects from the bare attributes above
# and are where the 2026-08-15 defects actually lived. Holding the bare
# attribute across a mutation proves nothing: it was always live.
CALLED_VIEWS = {
    "edges(data=True)": lambda g: g.edges(data=True),
    "edges(data='w')": lambda g: g.edges(data="w"),
    "edges(nbunch)": lambda g: g.edges([0, 1]),
    "nodes(data=True)": lambda g: g.nodes(data=True),
}
DIRECTED_CALLED_VIEWS = {
    "in_edges(data=True)": lambda g: g.in_edges(data=True),
    "out_edges(data=True)": lambda g: g.out_edges(data=True),
    "in_degree(nbunch)": lambda g: g.in_degree([0, 1]),
}
# NOT in the liveness set above: degree(nbunch) and out_degree(nbunch) are
# frozen snapshots on HEAD and report pre-mutation degrees — br-r37-c1-vfc2t,
# found by this very file. Named here rather than quietly omitted, so the gap
# is visible and the exclusion can be deleted when that bead lands.
KNOWN_STALE_CALLED_VIEWS = {
    "degree(nbunch)": lambda g: g.degree([0, 1]),
    "out_degree(nbunch)": lambda g: g.out_degree([0, 1]),
    # The UNRESTRICTED weighted view is a snapshot too: its per-node values are
    # taken from a native accumulator at construction. Pre-existing, verified
    # against the commit before br-r37-c1-z4iod, which changed only whether the
    # result was re-iterable.
    "degree(weight='w')": lambda g: g.degree(weight="w"),
}


@pytest.mark.parametrize("cls_name", CLASSES)
def test_known_stale_degree_views_are_still_stale(cls_name):
    """Pins the OPEN defect so the exclusion above cannot go quietly wrong.

    br-r37-c1-vfc2t is not fixed yet. If someone fixes it, this test fails and
    tells them to move these entries back into the live set rather than leaving
    a silent hole in the coverage. It is deliberately an assertion about a bug,
    not a skip.
    """
    gnx, gfx = _pair(cls_name)
    stale = []
    for name, probe in KNOWN_STALE_CALLED_VIEWS.items():
        if cls_name not in DIRECTED and name.startswith("out_degree"):
            continue
        held_nx, held_fx = probe(gnx), probe(gfx)
        for graph in (gnx, gfx):
            graph.add_edge(0, 3, w=5)
        if list(held_fx) != list(held_nx):
            stale.append(name)
    assert stale, (
        "br-r37-c1-vfc2t appears FIXED: move these back into CALLED_VIEWS "
        "and delete KNOWN_STALE_CALLED_VIEWS"
    )


def _called_for(cls_name):
    probes = dict(CALLED_VIEWS)
    if cls_name in DIRECTED:
        probes.update(DIRECTED_CALLED_VIEWS)
    return probes


@pytest.mark.parametrize("cls_name", CLASSES)
def test_called_views_bound_before_mutation_stay_live(cls_name):
    """br-r37-c1-af0ig: the called form was a frozen snapshot.

    Deliberately separate from the bare-attribute test above, because the bare
    attributes were live all along — holding only those is what let a frozen
    ``G.edges(data=True)`` survive review.
    """
    gnx, gfx = _pair(cls_name)
    held_nx = {name: probe(gnx) for name, probe in _called_for(cls_name).items()}
    held_fx = {name: probe(gfx) for name, probe in _called_for(cls_name).items()}
    for graph in (gnx, gfx):
        graph.add_edge(3, 4)
        graph.add_edge(0, 3, w=5)
    for name in held_nx:
        assert list(held_fx[name]) == list(held_nx[name]), name
        assert len(held_fx[name]) == len(held_nx[name]), name


@pytest.mark.parametrize("cls_name", CLASSES)
def test_called_view_class_names_match_networkx(cls_name):
    """br-r37-c1-1x6aq: restricted views reported the wrong class name."""
    gnx, gfx = _pair(cls_name)
    for name, probe in _called_for(cls_name).items():
        assert type(probe(gfx)).__name__ == type(probe(gnx)).__name__, name


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("key", ["zzz", 99, (1, 2)], ids=["str", "int", "tuple"])
def test_missing_key_lookups_match_networkx_exactly(cls_name, key):
    """br-r37-c1-i89jx / k4nsd: wrong value, wrong type, wrong message.

    Compares exception ARGS, not just the type — the message wording is a
    separate contract from the class, and comparing only the type reported
    these rows as matching while they diverged.
    """
    lookups = {
        "adj[miss]": lambda g: g.adj[key],
        "getitem[miss]": lambda g: g[key],
        "nodes[miss]": lambda g: g.nodes[key],
        "degree[miss]": lambda g: g.degree[key],
    }
    if cls_name in DIRECTED:
        lookups["in_degree[miss]"] = lambda g: g.in_degree[key]
        lookups["out_degree[miss]"] = lambda g: g.out_degree[key]
        lookups["pred[miss]"] = lambda g: g.pred[key]
        lookups["succ[miss]"] = lambda g: g.succ[key]

    for kind, make in (
        ("plain", lambda g: g),
        ("subgraph", lambda g: g.subgraph([0, 1, 2])),
    ):
        gnx, gfx = _pair(cls_name)
        view_nx, view_fx = make(gnx), make(gfx)
        for name, lookup in lookups.items():
            try:
                lookup(view_nx)
            except Exception as exc:  # noqa: BLE001
                expected = (type(exc).__name__, exc.args)
            else:
                pytest.fail(f"networkx did not raise: {kind}/{name}")
            try:
                lookup(view_fx)
            except Exception as exc:  # noqa: BLE001
                got = (type(exc).__name__, exc.args)
            else:
                got = ("no-raise", None)
            assert got == expected, (kind, name)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_degree_called_with_a_missing_node_matches_networkx(cls_name):
    """br-r37-c1-1x6aq: this raised where networkx returns an empty view."""
    gnx, gfx = _pair(cls_name)
    for probe in (
        lambda g: (type(g.degree("zzz")).__name__, list(g.degree("zzz")), len(g.degree("zzz"))),
        lambda g: (type(g.degree([99])).__name__, list(g.degree([99]))),
    ):
        assert probe(gfx) == probe(gnx)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_membership_on_degree_views_matches_networkx(cls_name):
    """br-r37-c1-p1uro: `in` tested nodes where networkx tests pairs."""
    gnx, gfx = _pair(cls_name)
    for build in (lambda g: g.degree, lambda g: g.degree([0, 1])):
        view_nx, view_fx = build(gnx), build(gfx)
        for probe in (0, (0, 1), (0, 99), "absent"):
            assert (probe in view_fx) == (probe in view_nx), probe


@pytest.mark.parametrize("cls_name", CLASSES)
def test_mutation_lockstep_preserves_order(cls_name):
    """Same mutations, compared without sorting at every step."""
    gnx, gfx = _pair(cls_name)
    steps = [
        lambda g: g.remove_node(5),
        lambda g: g.remove_edge(0, 1),
        lambda g: g.add_edge(3, 4, w=2),
        lambda g: g.update(edges=[(4, 5)], nodes=[6]),
        lambda g: g.remove_nodes_from([6]),
        lambda g: g.add_node(0, x=99),
        lambda g: g.clear_edges(),
    ]
    for index, step in enumerate(steps):
        step(gnx)
        step(gfx)
        assert list(gfx.nodes(data=True)) == list(gnx.nodes(data=True)), index
        assert list(gfx.edges(data=True)) == list(gnx.edges(data=True)), index
        assert list(gfx.degree) == list(gnx.degree), index


@pytest.mark.parametrize("cls_name", CLASSES)
def test_subgraph_view_is_live_and_ordered(cls_name):
    gnx, gfx = _pair(cls_name)
    sub_nx, sub_fx = gnx.subgraph([0, 1, 2]), gfx.subgraph([0, 1, 2])
    assert type(sub_fx).__name__ == type(sub_nx).__name__
    assert list(sub_fx.nodes) == list(sub_nx.nodes)
    assert list(sub_fx.edges) == list(sub_nx.edges)
    assert nx.is_frozen(sub_fx) == nx.is_frozen(sub_nx)
    # Live: mutate the PARENT, then read the held subgraph view.
    gnx.add_edge(0, 2)
    gfx.add_edge(0, 2)
    assert list(sub_fx.edges) == list(sub_nx.edges)
    gnx.remove_node(1)
    gfx.remove_node(1)
    assert list(sub_fx.nodes) == list(sub_nx.nodes)
    assert list(sub_fx.edges) == list(sub_nx.edges)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_edge_subgraph_view_is_live_and_ordered(cls_name):
    gnx, gfx = _pair(cls_name)
    sub_nx = gnx.edge_subgraph([(0, 1), (1, 2)])
    sub_fx = gfx.edge_subgraph([(0, 1), (1, 2)])
    assert type(sub_fx).__name__ == type(sub_nx).__name__
    assert list(sub_fx.nodes) == list(sub_nx.nodes)
    assert list(sub_fx.edges) == list(sub_nx.edges)
    gnx[0][1]["w"] = 42
    gfx[0][1]["w"] = 42
    assert list(sub_fx.edges(data=True)) == list(sub_nx.edges(data=True))


@pytest.mark.parametrize("cls_name", CLASSES)
def test_conversions_preserve_class_and_order(cls_name):
    gnx, gfx = _pair(cls_name)
    for name, convert in (
        ("copy", lambda g: g.copy()),
        ("to_directed", lambda g: g.to_directed()),
        ("to_undirected", lambda g: g.to_undirected()),
    ):
        out_nx, out_fx = convert(gnx), convert(gfx)
        assert type(out_fx).__name__ == type(out_nx).__name__, name
        assert list(out_fx.nodes(data=True)) == list(out_nx.nodes(data=True)), name
        assert list(out_fx.edges(data=True)) == list(out_nx.edges(data=True)), name


@pytest.mark.parametrize("cls_name", DIRECTED)
def test_reverse_view_is_live_and_ordered(cls_name):
    gnx, gfx = _pair(cls_name)
    rev_nx, rev_fx = gnx.reverse(copy=False), gfx.reverse(copy=False)
    assert type(rev_fx).__name__ == type(rev_nx).__name__
    assert list(rev_fx.edges) == list(rev_nx.edges)
    gnx.add_edge(9, 0)
    gfx.add_edge(9, 0)
    assert list(rev_fx.edges) == list(rev_nx.edges)
    assert list(rev_fx.nodes) == list(rev_nx.nodes)
