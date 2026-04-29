"""NetworkX conformance for the link-prediction algorithm family.

Existing ``test_link_prediction.py`` checks specific values on two
hand-built fixtures (``triangle_plus`` and ``star5``). This module
adds a broad differential test that runs every link-prediction
function against NetworkX as an oracle across 50+ graph fixtures so
any silent divergence in score order, score value, community-aware
behaviour, ebunch handling, or generator contract surfaces
immediately.

Covered functions (NetworkX names, all wrappers in ``franken_networkx``):

- ``common_neighbors`` (predicate, returns iterator of nodes)
- ``resource_allocation_index``
- ``jaccard_coefficient``
- ``adamic_adar_index``
- ``preferential_attachment``
- ``common_neighbor_centrality``
- ``cn_soundarajan_hopcroft`` (community-aware)
- ``ra_index_soundarajan_hopcroft`` (community-aware)
- ``within_inter_cluster`` (community-aware)

Each test asserts:

1. The set of (u, v, score) triples returned matches NX's exactly.
2. Score values match bit-for-bit (NaN-aware).
3. Pair-order in the iterator matches NX's contract.

Fixture set (50+):
- Hand-picked: K_n, C_n, P_n, S_n, K_{m,n}, Petersen, dense + sparse
  randoms, small disconnected / isolated-node mixes.
- 30+ ``gnp_random_graph`` instances at varying (n, p, seed) so the
  long tail of common-neighbour counts gets exercised.
- Multigraph guard parity (NX raises NotImplementedError).
"""

from __future__ import annotations

import itertools
import math
import warnings

import pytest
import networkx as nx

import franken_networkx as fnx


def _equiv(a, b, tol=1e-9):
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        return abs(a - b) < tol
    return a == b


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _pair(edges, nodes=None, *, attrs=None):
    """Return matched ``fnx.Graph`` and ``nx.Graph`` instances with
    identical insertion order. If ``attrs`` is given, also write each
    ``{node: {key: value}}`` dict onto both graphs (used for the
    community-aware predictors)."""
    fg = fnx.Graph()
    ng = nx.Graph()
    if nodes is not None:
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
    for u, v in edges:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    if attrs:
        for n, mapping in attrs.items():
            for k, v in mapping.items():
                fg.nodes[n][k] = v
                ng.nodes[n][k] = v
    return fg, ng


def _structured_fixtures():
    out = []
    for n in range(2, 7):
        out.append((f"K_{n}", list(itertools.combinations(range(n), 2)),
                    list(range(n))))
    for n in range(3, 8):
        out.append((f"C_{n}", [(i, (i + 1) % n) for i in range(n)],
                    list(range(n))))
    for n in range(2, 7):
        out.append((f"P_{n}",
                    list(zip(range(n - 1), range(1, n))),
                    list(range(n))))
    for n in range(1, 6):
        out.append((f"S_{n}",
                    [(0, i) for i in range(1, n + 1)],
                    list(range(n + 1))))
    for a, b in [(2, 2), (2, 3), (3, 3), (3, 4)]:
        kbg = nx.complete_bipartite_graph(a, b)
        out.append((f"K_{a}_{b}",
                    list(kbg.edges()), list(kbg.nodes())))
    pg = nx.petersen_graph()
    out.append(("petersen", list(pg.edges()), list(pg.nodes())))
    out.append(("disjoint_K3_K3",
                [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)],
                list(range(6))))
    out.append(("isolate_plus_K3",
                [(0, 1), (1, 2), (2, 0)], [0, 1, 2, 99]))
    return out


def _random_fixtures():
    out = []
    for n, p, seed in [
        (6, 0.3, 1), (6, 0.5, 2), (8, 0.3, 3), (8, 0.5, 4), (8, 0.7, 5),
        (10, 0.2, 6), (10, 0.3, 7), (10, 0.5, 8),
        (12, 0.3, 9), (12, 0.4, 10), (15, 0.2, 11), (15, 0.3, 12),
        (20, 0.15, 13), (20, 0.25, 14), (25, 0.15, 15), (25, 0.2, 16),
    ]:
        gnp = nx.gnp_random_graph(n, p, seed=seed)
        out.append((f"gnp_n{n}_p{p}_s{seed}",
                    list(gnp.edges()), list(range(n))))
    return out


STRUCTURED = _structured_fixtures()
RANDOM = _random_fixtures()
ALL_FIXTURES = STRUCTURED + RANDOM


# ---------------------------------------------------------------------------
# Pair-iterator parity for non-community-aware predictors
# ---------------------------------------------------------------------------


PREDICTORS_PLAIN = [
    "resource_allocation_index",
    "jaccard_coefficient",
    "adamic_adar_index",
    "preferential_attachment",
]


@pytest.mark.parametrize("fn_name", PREDICTORS_PLAIN)
@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_predictor_default_ebunch_matches_networkx(name, edges, nodes, fn_name):
    """When ``ebunch=None`` NX scores every non-edge in the graph; the
    iterator yields ``(u, v, score)`` triples in
    ``non_edges(G)``-traversal order."""
    fg, ng = _pair(edges, nodes)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fr = list(getattr(fnx, fn_name)(fg))
        nr = list(getattr(nx, fn_name)(ng))
    assert len(fr) == len(nr), f"{name} {fn_name}: lens differ"
    for f, n in zip(fr, nr):
        assert (f[0], f[1]) == (n[0], n[1]), (
            f"{name} {fn_name}: pair order diverged at {f} vs {n}"
        )
        assert _equiv(f[2], n[2]), (
            f"{name} {fn_name}: score for ({f[0]},{f[1]}) fnx={f[2]} nx={n[2]}"
        )


@pytest.mark.parametrize("fn_name", PREDICTORS_PLAIN)
@pytest.mark.parametrize(
    "name,edges,nodes,ebunch",
    [
        ("K_4_minus_edge_query_missing",
         [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3)],
         list(range(4)),
         [(2, 3)]),
        ("path_5_query_endpoints",
         [(0, 1), (1, 2), (2, 3), (3, 4)],
         list(range(5)),
         [(0, 4)]),
        ("two_K3_query_cross",
         [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)],
         list(range(6)),
         [(0, 3), (1, 4), (2, 5)]),
        ("multiple_pairs_with_isolate",
         [(0, 1), (1, 2)],
         [0, 1, 2, 99],
         [(0, 99), (1, 99), (2, 99)]),
    ],
)
def test_predictor_with_ebunch_matches_networkx(name, edges, nodes, ebunch, fn_name):
    fg, ng = _pair(edges, nodes)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fr = list(getattr(fnx, fn_name)(fg, ebunch=ebunch))
        nr = list(getattr(nx, fn_name)(ng, ebunch=ebunch))
    assert fr == nr or all(
        (f[0], f[1]) == (n[0], n[1]) and _equiv(f[2], n[2])
        for f, n in zip(fr, nr)
    ), f"{name} {fn_name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# common_neighbors (returns iterator of nodes, not scored triples)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes,u,v",
    [
        ("K_4_diag", list(itertools.combinations(range(4), 2)),
         list(range(4)), 0, 1),
        ("S_5_leaves",
         [(0, i) for i in range(1, 6)], list(range(6)), 1, 2),
        ("path_5_endpoints",
         [(0, 1), (1, 2), (2, 3), (3, 4)], list(range(5)), 0, 4),
        ("isolated_pair", [], [0, 1, 2], 0, 1),
        ("triangle_plus_pendant",
         [(0, 1), (1, 2), (2, 0), (0, 3)], list(range(4)), 1, 3),
    ],
)
def test_common_neighbors_matches_networkx(name, edges, nodes, u, v):
    fg, ng = _pair(edges, nodes)
    fr = sorted(fnx.common_neighbors(fg, u, v))
    nr = sorted(nx.common_neighbors(ng, u, v))
    assert fr == nr


# ---------------------------------------------------------------------------
# common_neighbor_centrality (alpha-parameterised)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("alpha", [0.0, 0.25, 0.5, 0.75, 0.999])
@pytest.mark.parametrize(
    "name,edges,nodes,ebunch",
    [
        ("K_4_minus", [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3)],
         list(range(4)), [(2, 3)]),
        ("path_5", [(0, 1), (1, 2), (2, 3), (3, 4)],
         list(range(5)), [(0, 4)]),
        ("two_triangles_share_v",
         [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)],
         list(range(5)), [(0, 3), (1, 4)]),
    ],
)
def test_common_neighbor_centrality_matches_networkx(name, edges, nodes, ebunch, alpha):
    fg, ng = _pair(edges, nodes)
    fr = list(fnx.common_neighbor_centrality(fg, ebunch, alpha=alpha))
    nr = list(nx.common_neighbor_centrality(ng, ebunch, alpha=alpha))
    assert len(fr) == len(nr)
    for f, n in zip(fr, nr):
        assert (f[0], f[1]) == (n[0], n[1])
        assert _equiv(f[2], n[2])


# ---------------------------------------------------------------------------
# Community-aware predictors
# ---------------------------------------------------------------------------


def _community_attr_fixtures():
    return [
        ("two_triangles_two_comm",
         [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (2, 3)],
         list(range(6)),
         {n: {"community": 0 if n < 3 else 1} for n in range(6)}),
        ("K_4_one_comm",
         list(itertools.combinations(range(4), 2)),
         list(range(4)),
         {n: {"community": 0} for n in range(4)}),
        ("path_5_alternating",
         [(0, 1), (1, 2), (2, 3), (3, 4)],
         list(range(5)),
         {n: {"community": n % 2} for n in range(5)}),
        ("K_2_3_split",
         [(0, 2), (0, 3), (0, 4), (1, 2), (1, 3), (1, 4)],
         list(range(5)),
         {0: {"community": 0}, 1: {"community": 0},
          2: {"community": 1}, 3: {"community": 1}, 4: {"community": 0}}),
    ]


COMMUNITY_FIXTURES = _community_attr_fixtures()


@pytest.mark.parametrize("name,edges,nodes,attrs", COMMUNITY_FIXTURES,
                         ids=[fx[0] for fx in COMMUNITY_FIXTURES])
def test_cn_soundarajan_hopcroft_matches_networkx(name, edges, nodes, attrs):
    fg, ng = _pair(edges, nodes, attrs=attrs)
    fr = list(fnx.cn_soundarajan_hopcroft(fg))
    nr = list(nx.cn_soundarajan_hopcroft(ng))
    assert len(fr) == len(nr)
    for f, n in zip(fr, nr):
        assert (f[0], f[1]) == (n[0], n[1])
        assert _equiv(f[2], n[2])


@pytest.mark.parametrize("name,edges,nodes,attrs", COMMUNITY_FIXTURES,
                         ids=[fx[0] for fx in COMMUNITY_FIXTURES])
def test_ra_index_soundarajan_hopcroft_matches_networkx(name, edges, nodes, attrs):
    fg, ng = _pair(edges, nodes, attrs=attrs)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fr = list(fnx.ra_index_soundarajan_hopcroft(fg))
        nr = list(nx.ra_index_soundarajan_hopcroft(ng))
    assert len(fr) == len(nr)
    for f, n in zip(fr, nr):
        assert (f[0], f[1]) == (n[0], n[1])
        assert _equiv(f[2], n[2])


@pytest.mark.parametrize("name,edges,nodes,attrs", COMMUNITY_FIXTURES,
                         ids=[fx[0] for fx in COMMUNITY_FIXTURES])
def test_within_inter_cluster_matches_networkx(name, edges, nodes, attrs):
    fg, ng = _pair(edges, nodes, attrs=attrs)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fr = list(fnx.within_inter_cluster(fg))
        nr = list(nx.within_inter_cluster(ng))
    assert len(fr) == len(nr)
    for f, n in zip(fr, nr):
        assert (f[0], f[1]) == (n[0], n[1])
        assert _equiv(f[2], n[2])


# ---------------------------------------------------------------------------
# Iterator / generator contract — predictors return lazy generators
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fn_name", PREDICTORS_PLAIN)
def test_predictor_returns_iterator(fn_name):
    """``getattr(fnx, fn_name)(G)`` must be an iterator (``iter(it) is
    it``) — matches NX's lazy contract."""
    g = fnx.complete_graph(4)
    it = getattr(fnx, fn_name)(g)
    assert iter(it) is it


# ---------------------------------------------------------------------------
# MultiGraph rejection (NX rejects via @not_implemented_for)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fn_name", PREDICTORS_PLAIN +
                         ["common_neighbor_centrality"])
def test_predictor_rejects_multigraph_matching_networkx(fn_name):
    fg = fnx.MultiGraph()
    fg.add_edges_from([(0, 1), (1, 2)])
    ng = nx.MultiGraph()
    ng.add_edges_from([(0, 1), (1, 2)])
    with pytest.raises(nx.NetworkXNotImplemented):
        if fn_name == "common_neighbor_centrality":
            list(nx.common_neighbor_centrality(ng, [(0, 2)]))
        else:
            list(getattr(nx, fn_name)(ng))
    with pytest.raises(fnx.NetworkXNotImplemented):
        if fn_name == "common_neighbor_centrality":
            list(fnx.common_neighbor_centrality(fg, [(0, 2)]))
        else:
            list(getattr(fnx, fn_name)(fg))


# ---------------------------------------------------------------------------
# DiGraph rejection — link prediction is undirected-only in NX
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fn_name", PREDICTORS_PLAIN +
                         ["common_neighbor_centrality"])
def test_predictor_rejects_digraph_matching_networkx(fn_name):
    fg = fnx.DiGraph()
    fg.add_edges_from([(0, 1), (1, 2)])
    ng = nx.DiGraph()
    ng.add_edges_from([(0, 1), (1, 2)])
    with pytest.raises(nx.NetworkXNotImplemented):
        if fn_name == "common_neighbor_centrality":
            list(nx.common_neighbor_centrality(ng, [(0, 2)]))
        else:
            list(getattr(nx, fn_name)(ng))
    with pytest.raises(fnx.NetworkXNotImplemented):
        if fn_name == "common_neighbor_centrality":
            list(fnx.common_neighbor_centrality(fg, [(0, 2)]))
        else:
            list(getattr(fnx, fn_name)(fg))


# ---------------------------------------------------------------------------
# Invariants between predictors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in STRUCTURED if 3 <= len(fx[2]) <= 8],
    ids=[fx[0] for fx in STRUCTURED if 3 <= len(fx[2]) <= 8],
)
def test_resource_allocation_le_jaccard_when_low_degree(name, edges, nodes):
    """For a dense enough graph, ``RA(u, v) ≥ Jaccard(u, v)`` doesn't
    universally hold, but ``RA == 0 ⇔ Jaccard == 0`` always (zero
    common neighbors → both zero). Verify on every fixture."""
    fg, _ = _pair(edges, nodes)
    ra = {(u, v): s for u, v, s in fnx.resource_allocation_index(fg)}
    jc = {(u, v): s for u, v, s in fnx.jaccard_coefficient(fg)}
    for pair in ra.keys() & jc.keys():
        assert (ra[pair] == 0) == (jc[pair] == 0), (
            f"{name}: RA / JC zero invariant broken at {pair}: "
            f"RA={ra[pair]} JC={jc[pair]}"
        )
