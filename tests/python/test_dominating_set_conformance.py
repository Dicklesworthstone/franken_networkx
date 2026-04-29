"""NetworkX conformance for the dominating-set + cover algorithm family.

Existing scattered tests (``test_coverage_gaps.py``,
``test_untested_coverage.py``) check ``dominating_set`` and
``is_dominating_set`` on a couple of hand-built graphs. Add a broad
differential test that exercises the whole family across structured
+ random fixtures so any silent divergence in scoring, ebunch /
start_with handling, or validity invariants surfaces immediately.

Covered functions:

- ``dominating_set(G, start_with=...)`` — exact parity when
  ``start_with`` is supplied (the no-start-with case picks an
  arbitrary node, so we only check validity there).
- ``is_dominating_set(G, ds)`` — predicate, exact bit parity.
- ``connected_dominating_set(G)`` — validity (the algorithm picks
  arbitrary tie-breaks so we don't require exact equality, but the
  result must be a valid connected dominating set).
- ``min_edge_cover(G)`` — exact parity for matching-based covers.
- ``is_edge_cover(G, cover)`` — predicate, exact bit parity.
- ``min_weighted_vertex_cover(G, weight=...)`` — validity; fnx and NX
  may return different approximation covers.

The ``start_with`` parameter is the cleanest way to make
``dominating_set`` deterministic for parity testing — both libraries
follow the same greedy expansion from the supplied node.
"""

from __future__ import annotations

import itertools

import pytest
import networkx as nx
from networkx.algorithms.approximation import (
    min_weighted_vertex_cover as _nx_min_weighted_vertex_cover,
)

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _pair(edges, nodes=None):
    fg = fnx.Graph()
    ng = nx.Graph()
    if nodes is not None:
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
    for u, v in edges:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    return fg, ng


def _structured_fixtures():
    out = []
    for n in range(2, 7):
        out.append((f"K_{n}", list(itertools.combinations(range(n), 2)),
                    list(range(n))))
    for n in range(3, 9):
        out.append((f"C_{n}", [(i, (i + 1) % n) for i in range(n)],
                    list(range(n))))
    for n in range(2, 9):
        out.append((f"P_{n}",
                    list(zip(range(n - 1), range(1, n))),
                    list(range(n))))
    for n in range(1, 7):
        out.append((f"S_{n}",
                    [(0, i) for i in range(1, n + 1)],
                    list(range(n + 1))))
    pg = nx.petersen_graph()
    out.append(("petersen", list(pg.edges()), list(pg.nodes())))
    out.append(("two_triangles_bridge",
                [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)],
                list(range(6))))
    return out


def _random_fixtures():
    out = []
    for n, p, seed in [
        (8, 0.3, 1), (10, 0.3, 2), (12, 0.3, 3), (15, 0.25, 4),
        (15, 0.4, 5), (20, 0.2, 6), (20, 0.3, 7),
    ]:
        gnp = nx.gnp_random_graph(n, p, seed=seed)
        if not nx.is_connected(gnp):
            continue
        out.append((f"gnp_n{n}_p{p}_s{seed}",
                    list(gnp.edges()), list(range(n))))
    return out


STRUCTURED = _structured_fixtures()
RANDOM = _random_fixtures()
ALL_FIXTURES = STRUCTURED + RANDOM


# ---------------------------------------------------------------------------
# dominating_set with explicit start_with — exact parity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in ALL_FIXTURES if 2 <= len(fx[2]) <= 12],
    ids=[fx[0] for fx in ALL_FIXTURES if 2 <= len(fx[2]) <= 12],
)
def test_dominating_set_with_explicit_start_matches_networkx(name, edges, nodes):
    """For each node as the explicit start_with, fnx and NX must
    return the identical greedy-expansion dominating set (same node
    iteration order from the chosen start)."""
    fg, ng = _pair(edges, nodes)
    for start in nodes:
        fr = fnx.dominating_set(fg, start_with=start)
        nr = nx.dominating_set(ng, start_with=start)
        assert fr == nr, f"{name} start={start}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in ALL_FIXTURES if 2 <= len(fx[2]) <= 20],
    ids=[fx[0] for fx in ALL_FIXTURES if 2 <= len(fx[2]) <= 20],
)
def test_dominating_set_default_is_valid(name, edges, nodes):
    """Without an explicit ``start_with`` both libraries pick an
    arbitrary starting node — the chosen ds may differ but must be
    valid in both."""
    fg, _ = _pair(edges, nodes)
    ds = fnx.dominating_set(fg)
    assert fnx.is_dominating_set(fg, ds)


def test_dominating_set_invalid_start_with_raises_matching_networkx():
    fg, ng = _pair([(0, 1), (1, 2)], list(range(3)))
    with pytest.raises(nx.NetworkXError) as nx_exc:
        nx.dominating_set(ng, start_with=99)
    with pytest.raises(fnx.NetworkXError) as fnx_exc:
        fnx.dominating_set(fg, start_with=99)
    assert str(fnx_exc.value) == str(nx_exc.value)


# ---------------------------------------------------------------------------
# is_dominating_set — exact predicate parity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes,candidates",
    [
        ("P_5_endpoints", [(0, 1), (1, 2), (2, 3), (3, 4)], list(range(5)),
         [{0, 4}, {2}, {1, 3}, {0, 2, 4}, {1}, set()]),
        ("K_4_singletons", list(itertools.combinations(range(4), 2)),
         list(range(4)), [{0}, {1}, {2}, {3}, {0, 1}, set()]),
        ("S_4", [(0, i) for i in range(1, 5)], list(range(5)),
         [{0}, {1}, {1, 2}, {1, 2, 3, 4}, set()]),
        ("petersen", list(nx.petersen_graph().edges()),
         list(nx.petersen_graph().nodes()),
         [{0, 2, 6}, {0}, {0, 1, 2, 3, 4}]),
    ],
)
def test_is_dominating_set_predicate_matches_networkx(
    name, edges, nodes, candidates,
):
    fg, ng = _pair(edges, nodes)
    for cand in candidates:
        assert fnx.is_dominating_set(fg, cand) == nx.is_dominating_set(ng, cand), (
            f"{name} cand={cand}: predicate diverged"
        )


# ---------------------------------------------------------------------------
# connected_dominating_set — validity (non-deterministic tie-breaks)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in STRUCTURED + RANDOM if 2 <= len(fx[2]) <= 15],
    ids=[fx[0] for fx in STRUCTURED + RANDOM if 2 <= len(fx[2]) <= 15],
)
def test_connected_dominating_set_is_valid(name, edges, nodes):
    """fnx and NX may pick different connected dominating sets due to
    arbitrary tie-breaks, but both results must be valid: a dominating
    set whose induced subgraph is connected."""
    fg, _ = _pair(edges, nodes)
    if not fnx.is_connected(fg):
        return  # NX rejects disconnected input
    cds = fnx.connected_dominating_set(fg)
    assert fnx.is_dominating_set(fg, cds), (
        f"{name}: connected_dominating_set is not a dominating set: {cds}"
    )
    if cds:
        # Build a fresh Graph from the induced subgraph so is_connected
        # gets a Graph instance rather than a subgraph view (the Rust
        # binding type-checks for the concrete classes).
        induced_view = fg.subgraph(cds)
        induced = fnx.Graph()
        induced.add_nodes_from(induced_view.nodes())
        induced.add_edges_from(induced_view.edges())
        assert fnx.is_connected(induced), (
            f"{name}: cds {cds} does not induce a connected subgraph"
        )


# ---------------------------------------------------------------------------
# min_edge_cover
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in ALL_FIXTURES if 2 <= len(fx[2]) <= 15],
    ids=[fx[0] for fx in ALL_FIXTURES if 2 <= len(fx[2]) <= 15],
)
def test_min_edge_cover_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    if any(d == 0 for _, d in fg.degree()):
        # NX raises on graphs with isolated nodes (no possible cover).
        with pytest.raises(nx.NetworkXException):
            nx.min_edge_cover(ng)
        with pytest.raises(fnx.NetworkXException):
            fnx.min_edge_cover(fg)
        return
    fr = fnx.min_edge_cover(fg)
    nr = nx.min_edge_cover(ng)
    # Edge cover is a SET of edges; both libraries must return the
    # same matching-derived cover.
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# is_edge_cover predicate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes,candidate",
    [
        ("P_5_full",
         [(0, 1), (1, 2), (2, 3), (3, 4)], list(range(5)),
         [(0, 1), (1, 2), (2, 3), (3, 4)]),
        ("P_5_partial",
         [(0, 1), (1, 2), (2, 3), (3, 4)], list(range(5)),
         [(0, 1), (2, 3)]),
        ("K_4_perfect_match",
         list(itertools.combinations(range(4), 2)), list(range(4)),
         [(0, 1), (2, 3)]),
        ("S_4_star_full",
         [(0, i) for i in range(1, 5)], list(range(5)),
         [(0, 1), (0, 2), (0, 3), (0, 4)]),
    ],
)
def test_is_edge_cover_predicate_matches_networkx(name, edges, nodes, candidate):
    fg, ng = _pair(edges, nodes)
    assert fnx.is_edge_cover(fg, candidate) == nx.is_edge_cover(ng, candidate)


# ---------------------------------------------------------------------------
# min_weighted_vertex_cover (re-exported NX approximation)
# ---------------------------------------------------------------------------


def _is_vertex_cover(G, cover):
    """Every edge has at least one endpoint in the cover."""
    cover_set = set(cover)
    for u, v in G.edges():
        if u not in cover_set and v not in cover_set:
            return False
    return True


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in ALL_FIXTURES if 2 <= len(fx[2]) <= 15],
    ids=[fx[0] for fx in ALL_FIXTURES if 2 <= len(fx[2]) <= 15],
)
def test_min_weighted_vertex_cover_unit_weights_is_valid(name, edges, nodes):
    """``min_weighted_vertex_cover`` is an approximation algorithm; fnx
    and NX use different heuristics and may return different (both
    valid) covers. Test the validity invariant rather than exact
    equality so the harness doesn't break when one side picks a
    different but equally-correct cover."""
    fg, _ = _pair(edges, nodes)
    fr = set(fnx.min_weighted_vertex_cover(fg))
    assert _is_vertex_cover(fg, fr), f"{name}: fnx cover {fr} is not a vertex cover"


@pytest.mark.parametrize(
    "name,edges,nodes,weights",
    [
        ("P_5_skew",
         [(0, 1), (1, 2), (2, 3), (3, 4)], list(range(5)),
         {0: 5.0, 1: 1.0, 2: 5.0, 3: 1.0, 4: 5.0}),
        ("K_4_uniform_then_skew",
         list(itertools.combinations(range(4), 2)), list(range(4)),
         {0: 1.0, 1: 10.0, 2: 1.0, 3: 1.0}),
        ("petersen_uniform",
         list(nx.petersen_graph().edges()),
         list(nx.petersen_graph().nodes()),
         {n: 1.0 for n in nx.petersen_graph().nodes()}),
    ],
)
def test_min_weighted_vertex_cover_weighted_is_valid(name, edges, nodes, weights):
    """Weighted approximation: each library may return a different
    cover; assert validity in fnx and that NX's cover (computed
    independently) is also a valid one — bounding the parity check
    to the contract both libraries actually promise."""
    fg, ng = _pair(edges, nodes)
    for n, w in weights.items():
        fg.nodes[n]["weight"] = w
        ng.nodes[n]["weight"] = w
    fr = set(fnx.min_weighted_vertex_cover(fg, weight="weight"))
    nr = set(_nx_min_weighted_vertex_cover(ng, weight="weight"))
    assert _is_vertex_cover(fg, fr), f"{name}: fnx cover {fr} is invalid"
    assert _is_vertex_cover(ng, nr), f"{name}: nx cover {nr} is invalid"


# ---------------------------------------------------------------------------
# Empty / edge-cases
# ---------------------------------------------------------------------------


def test_dominating_set_empty_graph_returns_empty_set():
    """fnx returns ``set()`` on the empty graph; NX raises
    ``StopIteration`` from its ``arbitrary_element(set())`` call. The
    fnx behaviour is more user-friendly — lock the empty-result
    contract in for fnx and document NX's exception."""
    assert fnx.dominating_set(fnx.Graph()) == set()
    with pytest.raises(StopIteration):
        nx.dominating_set(nx.Graph())


def test_dominating_set_single_node_returns_singleton():
    fg = fnx.Graph()
    fg.add_node(0)
    ng = nx.Graph()
    ng.add_node(0)
    assert fnx.dominating_set(fg) == nx.dominating_set(ng) == {0}


def test_is_dominating_set_empty_candidate_on_non_empty_graph_is_false():
    fg, ng = _pair([(0, 1), (1, 2)], list(range(3)))
    assert not fnx.is_dominating_set(fg, set())
    assert not nx.is_dominating_set(ng, set())


def test_min_edge_cover_isolated_nodes_raises_matching_networkx():
    """Both libraries raise on graphs with isolated nodes (no possible
    cover). NX raises ``NetworkXException`` directly; fnx raises
    ``NetworkXError`` (a subclass of ``NetworkXException``) — both
    catchable by ``except NetworkXException``. Lock in the message
    parity since callers do match on it."""
    fg = fnx.Graph()
    fg.add_nodes_from([0, 1])  # no edges
    ng = nx.Graph()
    ng.add_nodes_from([0, 1])
    with pytest.raises(nx.NetworkXException) as nx_exc:
        nx.min_edge_cover(ng)
    with pytest.raises(fnx.NetworkXException) as fnx_exc:
        fnx.min_edge_cover(fg)
    assert str(fnx_exc.value) == str(nx_exc.value)


# ---------------------------------------------------------------------------
# Cross-relation invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in ALL_FIXTURES if 2 <= len(fx[2]) <= 15],
    ids=[fx[0] for fx in ALL_FIXTURES if 2 <= len(fx[2]) <= 15],
)
def test_min_edge_cover_is_valid_edge_cover(name, edges, nodes):
    """The result of ``min_edge_cover`` must satisfy ``is_edge_cover``."""
    fg, _ = _pair(edges, nodes)
    if any(d == 0 for _, d in fg.degree()):
        return
    cover = fnx.min_edge_cover(fg)
    assert fnx.is_edge_cover(fg, cover)


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in ALL_FIXTURES if 2 <= len(fx[2]) <= 15],
    ids=[fx[0] for fx in ALL_FIXTURES if 2 <= len(fx[2]) <= 15],
)
def test_dominating_set_default_is_valid_dominating_set(name, edges, nodes):
    """Whatever ``dominating_set(G)`` returns, ``is_dominating_set(G, ds)``
    must report True."""
    fg, _ = _pair(edges, nodes)
    ds = fnx.dominating_set(fg)
    assert fnx.is_dominating_set(fg, ds)
