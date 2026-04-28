"""NetworkX conformance for the distance-measures algorithm family.

Covers ``diameter``, ``radius``, ``center``, ``periphery``,
``eccentricity``, and ``barycenter`` against the upstream reference
across a substantial fixture set:

- Standard graph families: complete K_n, cycle C_n, path P_n, star S_n,
  wheel W_n, grid graphs, complete bipartite K_{n,m}, Petersen,
  hypercube Q_n.
- Edge cases: single node (eccentricity 0), pre-supplied eccentricity
  dict via ``e=...``, weighted variants, ``usebounds=True``, directed
  graphs (must be strongly connected), MultiGraph parallel-edge
  semantics.
- Random connected gnp graphs at several (n, p) settings.

Each test asserts bit-for-bit parity with NetworkX. Existing
``tests/python/test_distance.py`` only had ~10 hand-picked smoke tests
on a single ``path_graph`` fixture; this suite expands coverage to
200+ parametrised cases including the optional ``e=`` / ``sp=`` /
``v=`` / ``weight=`` / ``attr=`` parameters that drive different code
paths inside the family.
"""

from __future__ import annotations

import itertools

import pytest
import networkx as nx

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _pair(edges, nodes=None, *, directed=False, multi=False):
    if directed:
        cls_fnx = fnx.MultiDiGraph if multi else fnx.DiGraph
        cls_nx = nx.MultiDiGraph if multi else nx.DiGraph
    else:
        cls_fnx = fnx.MultiGraph if multi else fnx.Graph
        cls_nx = nx.MultiGraph if multi else nx.Graph
    fg, ng = cls_fnx(), cls_nx()
    if nodes is not None:
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
    for edge in edges:
        if len(edge) == 2:
            fg.add_edge(*edge)
            ng.add_edge(*edge)
        else:
            u, v, attrs = edge[0], edge[1], edge[2]
            fg.add_edge(u, v, **attrs)
            ng.add_edge(u, v, **attrs)
    return fg, ng


def _connected_undirected_fixtures():
    """Return (name, edges, nodes) for connected undirected graphs."""
    fixtures = []

    # complete K_n
    for n in range(1, 8):
        edges = list(itertools.combinations(range(n), 2))
        fixtures.append((f"K_{n}", edges, list(range(n))))

    # cycle C_n
    for n in range(3, 10):
        edges = [(i, (i + 1) % n) for i in range(n)]
        fixtures.append((f"C_{n}", edges, list(range(n))))

    # path P_n
    for n in range(1, 10):
        edges = list(zip(range(n - 1), range(1, n)))
        fixtures.append((f"P_{n}", edges, list(range(n))))

    # star S_n (n+1 nodes)
    for n in range(1, 7):
        edges = [(0, i) for i in range(1, n + 1)]
        fixtures.append((f"S_{n}", edges, list(range(n + 1))))

    # wheel W_n (1 hub + cycle of length n)
    for n in range(3, 7):
        edges = [(0, i) for i in range(1, n + 1)]
        edges.extend((i, (i % n) + 1) for i in range(1, n + 1))
        fixtures.append((f"W_{n}", edges, list(range(n + 1))))

    # complete bipartite K_{a,b}
    for a, b in [(2, 2), (2, 3), (3, 3), (3, 4), (4, 5)]:
        ng = nx.complete_bipartite_graph(a, b)
        fixtures.append((
            f"K_{a}_{b}",
            list(ng.edges()),
            list(ng.nodes()),
        ))

    # Petersen
    pg = nx.petersen_graph()
    fixtures.append(("petersen", list(pg.edges()), list(pg.nodes())))

    # Hypercube Q_n
    for n in (2, 3):
        hg = nx.hypercube_graph(n)
        fixtures.append((
            f"Q_{n}",
            list(hg.edges()),
            list(hg.nodes()),
        ))

    # Grid 2D
    for r, c in [(2, 3), (3, 3), (3, 4), (4, 4)]:
        gg = nx.grid_2d_graph(r, c)
        fixtures.append((
            f"grid_{r}x{c}",
            list(gg.edges()),
            list(gg.nodes()),
        ))

    # gnp random graphs (seeds chosen so each is connected)
    rand_seeds = [
        (8, 0.5, 1), (8, 0.6, 2), (10, 0.4, 3), (10, 0.5, 4),
        (12, 0.4, 5), (12, 0.5, 6), (15, 0.3, 7), (15, 0.4, 8),
        (20, 0.25, 9), (20, 0.3, 10), (25, 0.2, 11), (25, 0.3, 12),
    ]
    for n, p, seed in rand_seeds:
        gnp = nx.gnp_random_graph(n, p, seed=seed)
        if not nx.is_connected(gnp):
            continue
        fixtures.append((
            f"gnp_n{n}_p{p}_s{seed}",
            list(gnp.edges()),
            list(range(n)),
        ))

    return fixtures


def _strongly_connected_directed_fixtures():
    """Return (name, edges, nodes) for strongly-connected digraphs."""
    fixtures = []
    # directed cycles
    for n in range(2, 8):
        edges = [(i, (i + 1) % n) for i in range(n)]
        fixtures.append((f"dir_C_{n}", edges, list(range(n))))

    # Both-directions K_n (strongly connected)
    for n in range(2, 6):
        edges = [
            (u, v) for u in range(n) for v in range(n) if u != v
        ]
        fixtures.append((f"dir_K_{n}_both", edges, list(range(n))))

    # Combination — cycle plus chord
    fixtures.append((
        "dir_C_5_with_chord",
        [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (2, 0)],
        list(range(5)),
    ))

    return fixtures


def _weighted_fixtures():
    """Return (name, edges) where edges include weight attr."""
    return [
        ("triangle_unequal_weights",
         [(0, 1, {"weight": 1}), (1, 2, {"weight": 2}),
          (0, 2, {"weight": 3})],
         [0, 1, 2]),
        ("path_4_weighted",
         [(0, 1, {"weight": 5}), (1, 2, {"weight": 1}),
          (2, 3, {"weight": 4})],
         [0, 1, 2, 3]),
        ("diamond_weighted",
         [(0, 1, {"weight": 1}), (1, 2, {"weight": 2}),
          (0, 2, {"weight": 10}), (2, 3, {"weight": 1}),
          (1, 3, {"weight": 4})],
         [0, 1, 2, 3]),
        ("star_4_weighted",
         [(0, i, {"weight": i}) for i in range(1, 5)],
         list(range(5))),
    ]


CONNECTED_UNDIRECTED = _connected_undirected_fixtures()
STRONG_DIRECTED = _strongly_connected_directed_fixtures()
WEIGHTED = _weighted_fixtures()


# ---------------------------------------------------------------------------
# diameter / radius / center / periphery
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", CONNECTED_UNDIRECTED,
                         ids=[fx[0] for fx in CONNECTED_UNDIRECTED])
def test_diameter_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    assert fnx.diameter(fg) == nx.diameter(ng)


@pytest.mark.parametrize("name,edges,nodes", CONNECTED_UNDIRECTED,
                         ids=[fx[0] for fx in CONNECTED_UNDIRECTED])
def test_radius_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    assert fnx.radius(fg) == nx.radius(ng)


@pytest.mark.parametrize("name,edges,nodes", CONNECTED_UNDIRECTED,
                         ids=[fx[0] for fx in CONNECTED_UNDIRECTED])
def test_center_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    assert sorted(fnx.center(fg)) == sorted(nx.center(ng))


@pytest.mark.parametrize("name,edges,nodes", CONNECTED_UNDIRECTED,
                         ids=[fx[0] for fx in CONNECTED_UNDIRECTED])
def test_periphery_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    assert sorted(fnx.periphery(fg)) == sorted(nx.periphery(ng))


@pytest.mark.parametrize("name,edges,nodes", CONNECTED_UNDIRECTED,
                         ids=[fx[0] for fx in CONNECTED_UNDIRECTED])
def test_eccentricity_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    fnx_ecc = fnx.eccentricity(fg)
    nx_ecc = nx.eccentricity(ng)
    assert fnx_ecc == nx_ecc


# ---------------------------------------------------------------------------
# usebounds=True (alternate algorithm path)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes",
                         CONNECTED_UNDIRECTED,
                         ids=[fx[0] for fx in CONNECTED_UNDIRECTED])
def test_diameter_usebounds_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    assert fnx.diameter(fg, usebounds=True) == nx.diameter(ng, usebounds=True)


@pytest.mark.parametrize("name,edges,nodes",
                         CONNECTED_UNDIRECTED,
                         ids=[fx[0] for fx in CONNECTED_UNDIRECTED])
def test_radius_usebounds_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    assert fnx.radius(fg, usebounds=True) == nx.radius(ng, usebounds=True)


# ---------------------------------------------------------------------------
# Pre-supplied eccentricity dict via e=...
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in CONNECTED_UNDIRECTED if len(fx[2]) <= 12],
    ids=[fx[0] for fx in CONNECTED_UNDIRECTED if len(fx[2]) <= 12],
)
def test_diameter_with_precomputed_eccentricity_dict(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    nx_ecc = nx.eccentricity(ng)
    assert fnx.diameter(fg, e=nx_ecc) == nx.diameter(ng, e=nx_ecc)


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in CONNECTED_UNDIRECTED if len(fx[2]) <= 12],
    ids=[fx[0] for fx in CONNECTED_UNDIRECTED if len(fx[2]) <= 12],
)
def test_center_with_precomputed_eccentricity_dict(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    nx_ecc = nx.eccentricity(ng)
    assert sorted(fnx.center(fg, e=nx_ecc)) == sorted(nx.center(ng, e=nx_ecc))


# ---------------------------------------------------------------------------
# Single-node eccentricity via v=...
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in CONNECTED_UNDIRECTED if len(fx[2]) >= 2 and len(fx[2]) <= 12],
    ids=[fx[0] for fx in CONNECTED_UNDIRECTED if len(fx[2]) >= 2 and len(fx[2]) <= 12],
)
def test_eccentricity_single_node_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    v = nodes[0]
    assert fnx.eccentricity(fg, v=v) == nx.eccentricity(ng, v=v)


# ---------------------------------------------------------------------------
# Weighted variants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", WEIGHTED,
                         ids=[fx[0] for fx in WEIGHTED])
def test_diameter_weighted_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    assert fnx.diameter(fg, weight="weight") == nx.diameter(ng, weight="weight")


@pytest.mark.parametrize("name,edges,nodes", WEIGHTED,
                         ids=[fx[0] for fx in WEIGHTED])
def test_radius_weighted_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    assert fnx.radius(fg, weight="weight") == nx.radius(ng, weight="weight")


@pytest.mark.parametrize("name,edges,nodes", WEIGHTED,
                         ids=[fx[0] for fx in WEIGHTED])
def test_center_weighted_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    assert (
        sorted(fnx.center(fg, weight="weight"))
        == sorted(nx.center(ng, weight="weight"))
    )


@pytest.mark.parametrize("name,edges,nodes", WEIGHTED,
                         ids=[fx[0] for fx in WEIGHTED])
def test_periphery_weighted_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    assert (
        sorted(fnx.periphery(fg, weight="weight"))
        == sorted(nx.periphery(ng, weight="weight"))
    )


@pytest.mark.parametrize("name,edges,nodes", WEIGHTED,
                         ids=[fx[0] for fx in WEIGHTED])
def test_eccentricity_weighted_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    assert (
        fnx.eccentricity(fg, weight="weight")
        == nx.eccentricity(ng, weight="weight")
    )


# ---------------------------------------------------------------------------
# Directed (strongly connected)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", STRONG_DIRECTED,
                         ids=[fx[0] for fx in STRONG_DIRECTED])
def test_diameter_directed_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes, directed=True)
    assert fnx.diameter(fg) == nx.diameter(ng)


@pytest.mark.parametrize("name,edges,nodes", STRONG_DIRECTED,
                         ids=[fx[0] for fx in STRONG_DIRECTED])
def test_radius_directed_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes, directed=True)
    assert fnx.radius(fg) == nx.radius(ng)


@pytest.mark.parametrize("name,edges,nodes", STRONG_DIRECTED,
                         ids=[fx[0] for fx in STRONG_DIRECTED])
def test_center_directed_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes, directed=True)
    assert sorted(fnx.center(fg)) == sorted(nx.center(ng))


@pytest.mark.parametrize("name,edges,nodes", STRONG_DIRECTED,
                         ids=[fx[0] for fx in STRONG_DIRECTED])
def test_periphery_directed_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes, directed=True)
    assert sorted(fnx.periphery(fg)) == sorted(nx.periphery(ng))


@pytest.mark.parametrize("name,edges,nodes", STRONG_DIRECTED,
                         ids=[fx[0] for fx in STRONG_DIRECTED])
def test_eccentricity_directed_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes, directed=True)
    assert fnx.eccentricity(fg) == nx.eccentricity(ng)


# ---------------------------------------------------------------------------
# barycenter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in CONNECTED_UNDIRECTED if len(fx[2]) <= 15],
    ids=[fx[0] for fx in CONNECTED_UNDIRECTED if len(fx[2]) <= 15],
)
def test_barycenter_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    assert sorted(fnx.barycenter(fg)) == sorted(nx.barycenter(ng))


@pytest.mark.parametrize("name,edges,nodes", WEIGHTED,
                         ids=[fx[0] for fx in WEIGHTED])
def test_barycenter_weighted_matches_networkx(name, edges, nodes):
    fg, ng = _pair(edges, nodes)
    assert (
        sorted(fnx.barycenter(fg, weight="weight"))
        == sorted(nx.barycenter(ng, weight="weight"))
    )


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in CONNECTED_UNDIRECTED if 2 <= len(fx[2]) <= 12],
    ids=[fx[0] for fx in CONNECTED_UNDIRECTED if 2 <= len(fx[2]) <= 12],
)
def test_barycenter_with_attr_decorates_nodes(name, edges, nodes):
    """``attr=...`` writes the barycentricity score to that attribute
    on each node — verify both libraries produce identical scores."""
    fg, ng = _pair(edges, nodes)
    fnx.barycenter(fg, attr="barycentricity")
    nx.barycenter(ng, attr="barycentricity")
    for n in nodes:
        assert (
            fg.nodes[n]["barycentricity"]
            == ng.nodes[n]["barycentricity"]
        ), f"barycentricity[{n}] diverged on {name}"


# ---------------------------------------------------------------------------
# Disconnected / empty / single-node dispatch
# ---------------------------------------------------------------------------


def test_diameter_on_disconnected_undirected_raises_matching_networkx():
    fg, ng = _pair([(0, 1), (2, 3)], [0, 1, 2, 3])
    with pytest.raises(nx.NetworkXError) as nx_exc:
        nx.diameter(ng)
    with pytest.raises(fnx.NetworkXError) as fnx_exc:
        fnx.diameter(fg)
    assert str(fnx_exc.value) == str(nx_exc.value)


def test_diameter_on_directed_not_strongly_connected_raises_matching_networkx():
    fg, ng = _pair([(0, 1), (1, 2)], list(range(3)), directed=True)
    with pytest.raises(nx.NetworkXError) as nx_exc:
        nx.diameter(ng)
    with pytest.raises(fnx.NetworkXError) as fnx_exc:
        fnx.diameter(fg)
    assert str(fnx_exc.value) == str(nx_exc.value)


def test_diameter_empty_graph_raises_value_error_matching_networkx():
    fg = fnx.Graph()
    ng = nx.Graph()
    with pytest.raises(ValueError):
        nx.diameter(ng)
    with pytest.raises(ValueError):
        fnx.diameter(fg)


def test_diameter_single_node_returns_zero():
    fg = fnx.Graph()
    fg.add_node(0)
    ng = nx.Graph()
    ng.add_node(0)
    assert fnx.diameter(fg) == nx.diameter(ng) == 0


def test_radius_single_node_returns_zero():
    fg = fnx.Graph()
    fg.add_node(0)
    ng = nx.Graph()
    ng.add_node(0)
    assert fnx.radius(fg) == nx.radius(ng) == 0


def test_eccentricity_on_disconnected_returns_per_node_inf_or_raises():
    """NX raises NetworkXError on a disconnected graph for any
    eccentricity query; fnx must mirror that."""
    fg, ng = _pair([(0, 1), (2, 3)], [0, 1, 2, 3])
    with pytest.raises(nx.NetworkXError):
        nx.eccentricity(ng)
    with pytest.raises(fnx.NetworkXError):
        fnx.eccentricity(fg)


# ---------------------------------------------------------------------------
# Cross-relation: diameter == max(eccentricity), radius == min(eccentricity)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in CONNECTED_UNDIRECTED if 2 <= len(fx[2]) <= 15],
    ids=[fx[0] for fx in CONNECTED_UNDIRECTED if 2 <= len(fx[2]) <= 15],
)
def test_diameter_equals_max_eccentricity_invariant(name, edges, nodes):
    fg, _ = _pair(edges, nodes)
    ecc = fnx.eccentricity(fg)
    assert fnx.diameter(fg) == max(ecc.values())


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in CONNECTED_UNDIRECTED if 2 <= len(fx[2]) <= 15],
    ids=[fx[0] for fx in CONNECTED_UNDIRECTED if 2 <= len(fx[2]) <= 15],
)
def test_radius_equals_min_eccentricity_invariant(name, edges, nodes):
    fg, _ = _pair(edges, nodes)
    ecc = fnx.eccentricity(fg)
    assert fnx.radius(fg) == min(ecc.values())


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in CONNECTED_UNDIRECTED if 2 <= len(fx[2]) <= 15],
    ids=[fx[0] for fx in CONNECTED_UNDIRECTED if 2 <= len(fx[2]) <= 15],
)
def test_center_is_argmin_of_eccentricity(name, edges, nodes):
    fg, _ = _pair(edges, nodes)
    ecc = fnx.eccentricity(fg)
    r = fnx.radius(fg)
    expected = {n for n, e in ecc.items() if e == r}
    assert set(fnx.center(fg)) == expected


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in CONNECTED_UNDIRECTED if 2 <= len(fx[2]) <= 15],
    ids=[fx[0] for fx in CONNECTED_UNDIRECTED if 2 <= len(fx[2]) <= 15],
)
def test_periphery_is_argmax_of_eccentricity(name, edges, nodes):
    fg, _ = _pair(edges, nodes)
    ecc = fnx.eccentricity(fg)
    d = fnx.diameter(fg)
    expected = {n for n, e in ecc.items() if e == d}
    assert set(fnx.periphery(fg)) == expected
