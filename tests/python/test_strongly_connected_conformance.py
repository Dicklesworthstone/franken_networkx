"""NetworkX conformance for the strongly-connected-components family.

Existing tests (``test_kosaraju_scc_order_parity.py``,
``test_strongly_connected_components_order_parity.py``) cover specific
emission-order parity points. Add a broad differential test that
exercises the full family across structured + random fixtures so any
silent divergence in component splitting, attractor detection,
condensation, or generator contract surfaces immediately.

Covered functions:

- ``strongly_connected_components(G)`` — Tarjan-based SCC enumeration.
- ``kosaraju_strongly_connected_components(G, source=...)`` —
  Kosaraju-style SCC enumeration (different traversal order from
  Tarjan).
- ``is_strongly_connected(G)`` — predicate.
- ``number_strongly_connected_components(G)`` — count.
- ``attracting_components(G)`` — SCCs with no outgoing arcs to other
  SCCs (terminal/absorbing components in the condensation).
- ``number_attracting_components(G)`` — count.
- ``condensation(G, scc=...)`` — DAG of SCCs.

Cross-relation invariants:

- ``is_strongly_connected(G)`` iff
  ``number_strongly_connected_components(G) == 1`` (and G has nodes).
- ``len(condensation(G).nodes()) == number_strongly_connected_components(G)``.
- Both SCC implementations enumerate the same set of partitions.
- Every attracting component is itself an SCC.
"""

from __future__ import annotations

import itertools
import warnings

import pytest
import networkx as nx

import franken_networkx as fnx


def _pair(edges, nodes=None):
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    if nodes is not None:
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
    for u, v in edges:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    return fg, ng


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _structured_fixtures():
    out = []
    out.append(("dir_C_3", [(0, 1), (1, 2), (2, 0)], list(range(3))))
    for n in range(2, 7):
        out.append((f"dir_C_{n}",
                    [(i, (i + 1) % n) for i in range(n)],
                    list(range(n))))
    out.append(("dir_DAG_chain",
                [(0, 1), (1, 2), (2, 3), (3, 4)], list(range(5))))
    out.append(("dir_DAG_diamond",
                [(0, 1), (0, 2), (1, 3), (2, 3)], list(range(4))))
    out.append(("dir_K3_both",
                [(0, 1), (1, 0), (1, 2), (2, 1), (0, 2), (2, 0)],
                list(range(3))))
    out.append(("dir_K4_one_way",
                list(itertools.combinations(range(4), 2)),
                list(range(4))))
    out.append(("dir_two_cycles_disjoint",
                [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)],
                list(range(6))))
    out.append(("dir_two_cycles_with_bridge",
                [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (2, 3)],
                list(range(6))))
    out.append(("dir_self_loop_only", [(0, 0)], [0]))
    out.append(("dir_isolate_plus_cycle",
                [(0, 1), (1, 2), (2, 0)], [0, 1, 2, 99]))
    out.append(("dir_path_plus_back",
                [(0, 1), (1, 2), (2, 1)], list(range(3))))
    out.append(("dir_petersen_oriented",
                # take petersen and orient lexicographically — gives
                # a tournament-like DAG
                [(min(u, v), max(u, v)) for u, v in nx.petersen_graph().edges()],
                list(nx.petersen_graph().nodes())))
    return out


def _random_fixtures():
    out = []
    for n, p, seed in [
        (6, 0.3, 1), (8, 0.3, 2), (10, 0.25, 3),
        (12, 0.2, 4), (15, 0.15, 5), (15, 0.2, 6),
        (20, 0.15, 7), (25, 0.1, 8),
    ]:
        gnp = nx.gnp_random_graph(n, p, seed=seed, directed=True)
        out.append((f"dir_gnp_n{n}_p{p}_s{seed}",
                    list(gnp.edges()), list(range(n))))
    return out


STRUCTURED = _structured_fixtures()
RANDOM = _random_fixtures()
ALL_FIXTURES = STRUCTURED + RANDOM


# ---------------------------------------------------------------------------
# strongly_connected_components — Tarjan
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_strongly_connected_components_matches_networkx(
    name, edges, nodes,
):
    fg, ng = _pair(edges, nodes)
    fr = list(fnx.strongly_connected_components(fg))
    nr = list(nx.strongly_connected_components(ng))
    # NX yields sets in Tarjan's reverse-finish order; both libs must
    # match exactly per br-r37-c1-2vdtt.
    assert [set(c) for c in fr] == [set(c) for c in nr], (
        f"{name}: fnx={fr} nx={nr}"
    )


# ---------------------------------------------------------------------------
# kosaraju_strongly_connected_components
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_kosaraju_scc_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    fr = list(fnx.kosaraju_strongly_connected_components(fg))
    nr = list(nx.kosaraju_strongly_connected_components(ng))
    assert [set(c) for c in fr] == [set(c) for c in nr], (
        f"{name}: fnx={fr} nx={nr}"
    )


@pytest.mark.parametrize(
    "name,edges,nodes,source",
    [
        ("dir_two_cycles_src_0",
         [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)],
         list(range(6)), 0),
        ("dir_two_cycles_src_3",
         [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)],
         list(range(6)), 3),
        ("dir_DAG_src_0",
         [(0, 1), (1, 2), (2, 3)], list(range(4)), 0),
    ],
)
def test_kosaraju_scc_with_source_matches_networkx(name, edges, nodes, source):
    fg, ng = _pair(edges, nodes)
    fr = list(fnx.kosaraju_strongly_connected_components(fg, source=source))
    nr = list(nx.kosaraju_strongly_connected_components(ng, source=source))
    assert [set(c) for c in fr] == [set(c) for c in nr]


# ---------------------------------------------------------------------------
# is_strongly_connected / number_strongly_connected_components
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_is_strongly_connected_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    if fg.number_of_nodes() == 0:
        # NX raises on empty graph
        with pytest.raises(nx.NetworkXPointlessConcept):
            nx.is_strongly_connected(ng)
        with pytest.raises(fnx.NetworkXPointlessConcept):
            fnx.is_strongly_connected(fg)
        return
    assert fnx.is_strongly_connected(fg) == nx.is_strongly_connected(ng)


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_number_strongly_connected_components_matches_networkx(
    name, edges, nodes,
):
    fg, ng = _pair(edges, nodes)
    assert (
        fnx.number_strongly_connected_components(fg)
        == nx.number_strongly_connected_components(ng)
    )


# ---------------------------------------------------------------------------
# attracting_components / number_attracting_components
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_attracting_components_matches_networkx(name, edges, nodes):
    """Both libs enumerate the same set of attracting components; the
    yield order is implementation-defined (different SCC traversal
    orders). Compare as a set of frozensets — ``sorted`` on frozensets
    is unreliable since ``<=`` is subset relation, not a total order."""
    fg, ng = _pair(edges, nodes)
    fr = {frozenset(c) for c in fnx.attracting_components(fg)}
    nr = {frozenset(c) for c in nx.attracting_components(ng)}
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_number_attracting_components_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    assert (
        fnx.number_attracting_components(fg)
        == nx.number_attracting_components(ng)
    )


# ---------------------------------------------------------------------------
# condensation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_condensation_matches_networkx(name, edges, nodes):
    """``condensation(G)`` returns a DAG with one node per SCC. The
    node-relabeling is deterministic in NX (matches SCC enumeration
    order) — assert exact node + edge equality."""
    fg, ng = _pair(edges, nodes)
    fr = fnx.condensation(fg)
    nr = nx.condensation(ng)
    assert sorted(fr.nodes()) == sorted(nr.nodes()), (
        f"{name}: fnx_nodes={sorted(fr.nodes())} nx_nodes={sorted(nr.nodes())}"
    )
    assert sorted(fr.edges()) == sorted(nr.edges()), (
        f"{name}: fnx_edges={sorted(fr.edges())} nx_edges={sorted(nr.edges())}"
    )


def test_condensation_with_provided_scc_preserves_members_contract():
    fg, ng = _pair([(0, 1), (1, 0), (1, 2)], [0, 1, 2])
    scc = [[0, 1], [2]]

    fr = fnx.condensation(fg, scc=scc)
    nr = nx.condensation(ng, scc=scc)

    assert sorted(fr.nodes(data=True)) == sorted(nr.nodes(data=True))
    assert sorted(fr.edges()) == sorted(nr.edges())
    assert fr.graph["mapping"] == nr.graph["mapping"]


def test_condensation_with_provided_scc_ignores_missing_isolates_like_networkx():
    fg, ng = _pair([(0, 1)], [0, 1, 2])
    scc = [[0], [1]]

    fr = fnx.condensation(fg, scc=scc)
    nr = nx.condensation(ng, scc=scc)

    assert sorted(fr.nodes(data=True)) == sorted(nr.nodes(data=True))
    assert sorted(fr.edges()) == sorted(nr.edges())
    assert fr.graph["mapping"] == nr.graph["mapping"] == {0: 0, 1: 1}


def test_condensation_with_provided_scc_unmapped_edge_raises_keyerror():
    fg, ng = _pair([(0, 1), (1, 2)], [0, 1, 2])
    scc = [[0], [1]]

    with pytest.raises(KeyError) as nx_exc:
        nx.condensation(ng, scc=scc)
    with pytest.raises(KeyError) as fnx_exc:
        fnx.condensation(fg, scc=scc)

    assert fnx_exc.value.args == nx_exc.value.args


# ---------------------------------------------------------------------------
# Cross-relation invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_is_strongly_connected_iff_one_component(name, edges, nodes):
    fg, _ = _pair(edges, nodes)
    if fg.number_of_nodes() == 0:
        return
    n_components = fnx.number_strongly_connected_components(fg)
    is_sc = fnx.is_strongly_connected(fg)
    assert is_sc == (n_components == 1), (
        f"{name}: is_strongly_connected={is_sc} but #SCC={n_components}"
    )


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_condensation_node_count_equals_scc_count(name, edges, nodes):
    fg, _ = _pair(edges, nodes)
    cond = fnx.condensation(fg)
    assert (
        cond.number_of_nodes()
        == fnx.number_strongly_connected_components(fg)
    )


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_condensation_is_dag(name, edges, nodes):
    """The condensation is always a DAG (collapses cycles into nodes)."""
    fg, _ = _pair(edges, nodes)
    cond = fnx.condensation(fg)
    assert fnx.is_directed_acyclic_graph(cond), (
        f"{name}: condensation has a cycle"
    )


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_tarjan_and_kosaraju_partition_into_same_components(
    name, edges, nodes,
):
    """Both algorithms must enumerate the same set of components — the
    enumeration *order* may differ, but the set of frozensets is
    identical. ``sorted`` on frozensets is unreliable since ``<=`` is
    subset relation, not a total order — compare as a set instead."""
    fg, _ = _pair(edges, nodes)
    tarjan = {frozenset(c) for c in fnx.strongly_connected_components(fg)}
    kosaraju = {
        frozenset(c) for c in fnx.kosaraju_strongly_connected_components(fg)
    }
    assert tarjan == kosaraju, (
        f"{name}: tarjan={tarjan} kosaraju={kosaraju}"
    )


@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_attracting_components_subset_of_sccs(name, edges, nodes):
    """Every attracting component is an SCC."""
    fg, _ = _pair(edges, nodes)
    sccs = {frozenset(c) for c in fnx.strongly_connected_components(fg)}
    attracting = {frozenset(c) for c in fnx.attracting_components(fg)}
    assert attracting <= sccs, (
        f"{name}: attracting {attracting} not subset of SCCs {sccs}"
    )


# ---------------------------------------------------------------------------
# Generator contract
# ---------------------------------------------------------------------------


def test_strongly_connected_components_returns_generator():
    fg = fnx.DiGraph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 0)])
    it = fnx.strongly_connected_components(fg)
    assert iter(it) is it


def test_kosaraju_scc_returns_generator():
    fg = fnx.DiGraph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 0)])
    it = fnx.kosaraju_strongly_connected_components(fg)
    assert iter(it) is it


def test_attracting_components_returns_generator():
    fg = fnx.DiGraph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 0)])
    it = fnx.attracting_components(fg)
    assert iter(it) is it


# ---------------------------------------------------------------------------
# Undirected rejection
# ---------------------------------------------------------------------------


def test_strongly_connected_components_rejects_undirected_matching_networkx():
    fg = fnx.Graph(); fg.add_edge(0, 1)
    ng = nx.Graph(); ng.add_edge(0, 1)
    with pytest.raises(nx.NetworkXNotImplemented):
        list(nx.strongly_connected_components(ng))
    with pytest.raises(fnx.NetworkXNotImplemented):
        list(fnx.strongly_connected_components(fg))


def test_kosaraju_scc_rejects_undirected_matching_networkx():
    fg = fnx.Graph(); fg.add_edge(0, 1)
    ng = nx.Graph(); ng.add_edge(0, 1)
    with pytest.raises(nx.NetworkXNotImplemented):
        list(nx.kosaraju_strongly_connected_components(ng))
    with pytest.raises(fnx.NetworkXNotImplemented):
        list(fnx.kosaraju_strongly_connected_components(fg))
