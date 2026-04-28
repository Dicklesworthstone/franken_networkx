"""NetworkX conformance for the Eulerian algorithm family.

Covers ``is_eulerian``, ``is_semieulerian``, ``has_eulerian_path``,
``eulerian_circuit``, ``eulerian_path``, and ``eulerize`` against the
upstream reference. Exercises the family across:

- complete graphs K_n (Eulerian iff n is odd)
- cycles C_n (always Eulerian)
- paths P_n (Eulerian path iff n >= 2, never circuit)
- stars (Eulerian path iff n_leaves == 2)
- multigraphs with parallel edges
- directed graphs (out-degree == in-degree per node)
- self-loops (NX counts +2 to degree per loop; the Rust binding
  mishandled this — fnx delegates to NX whenever any self-loop exists)
- disconnected components
- empty graph (raises NetworkXPointlessConcept)
- single-node graphs

Each test asserts bit-for-bit parity with NetworkX. ``eulerian_circuit``
and ``eulerian_path`` parity is exact-edge-sequence parity since fnx
delegates traversal to NX's Hierholzer implementation; that delegation
is itself a contract this suite locks in.
"""

from __future__ import annotations

import itertools

import pytest
import networkx as nx

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Pair builders
# ---------------------------------------------------------------------------


def _pair_undirected(edges, nodes=None, multi=False):
    fg = fnx.MultiGraph() if multi else fnx.Graph()
    ng = nx.MultiGraph() if multi else nx.Graph()
    if nodes is not None:
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
    for u, v in edges:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    return fg, ng


def _pair_directed(edges, nodes=None, multi=False):
    fg = fnx.MultiDiGraph() if multi else fnx.DiGraph()
    ng = nx.MultiDiGraph() if multi else nx.DiGraph()
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


def _undirected_simple_fixtures():
    """Return list of (name, edges, nodes) — undirected simple graphs."""
    fixtures = []

    # complete graphs K_n
    for n in range(1, 8):
        edges = list(itertools.combinations(range(n), 2))
        fixtures.append((f"K_{n}", edges, list(range(n))))

    # cycles C_n
    for n in range(3, 9):
        edges = [(i, (i + 1) % n) for i in range(n)]
        fixtures.append((f"C_{n}", edges, list(range(n))))

    # paths P_n
    for n in range(2, 9):
        edges = list(zip(range(n - 1), range(1, n)))
        fixtures.append((f"P_{n}", edges, list(range(n))))

    # stars S_n (n leaves)
    for n in range(1, 6):
        edges = [(0, i) for i in range(1, n + 1)]
        fixtures.append((f"S_{n}", edges, list(range(n + 1))))

    # K_n with one extra edge subdivision
    fixtures.append((
        "K_4_plus_pendant",
        [*itertools.combinations(range(4), 2), (3, 4)],
        list(range(5)),
    ))

    # disjoint union of two cycles (Eulerian iff each is Eulerian + no
    # cross — which means False for is_eulerian since not connected)
    fixtures.append((
        "C_3_plus_C_3_disconnected",
        [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)],
        list(range(6)),
    ))

    # bowtie (two triangles sharing a vertex)
    fixtures.append((
        "bowtie",
        [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)],
        list(range(5)),
    ))

    # graph with two odd-degree vertices (Eulerian path, not circuit)
    fixtures.append((
        "two_odd_degree",
        [(0, 1), (1, 2), (2, 3), (1, 3)],  # 0 and 2 are odd
        list(range(4)),
    ))

    # single-node graphs
    fixtures.append(("single_node", [], [0]))
    fixtures.append(("two_isolated", [], [0, 1]))

    # gnp random graphs
    for n, p, seed in [
        (6, 0.4, 1), (8, 0.4, 2), (10, 0.3, 3), (12, 0.4, 4),
        (15, 0.3, 5), (20, 0.2, 6),
    ]:
        gnp = nx.gnp_random_graph(n, p, seed=seed)
        fixtures.append((
            f"gnp_n{n}_p{p}_s{seed}",
            list(gnp.edges()),
            list(range(n)),
        ))

    return fixtures


def _undirected_multi_fixtures():
    """Return list of (name, edges, nodes) — undirected multigraphs."""
    return [
        ("multi_triple_edge", [(0, 1), (0, 1), (0, 1)], [0, 1]),
        ("multi_double_edge", [(0, 1), (0, 1)], [0, 1]),
        ("multi_K3_with_double", [(0, 1), (1, 2), (2, 0), (0, 1)], [0, 1, 2]),
        # parallel edges in C_4 → all degrees become 4 (even)
        ("multi_C4_doubled", [(0, 1), (1, 2), (2, 3), (3, 0),
                              (0, 1), (1, 2), (2, 3), (3, 0)],
         [0, 1, 2, 3]),
    ]


def _directed_fixtures():
    """Return list of (name, edges, nodes) — directed simple graphs."""
    return [
        ("dir_C_3", [(0, 1), (1, 2), (2, 0)], [0, 1, 2]),
        ("dir_C_4", [(0, 1), (1, 2), (2, 3), (3, 0)], [0, 1, 2, 3]),
        ("dir_C_5", [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)], list(range(5))),
        # complete oriented K_3 (each pair has both directions)
        ("dir_K_3_both", [(0, 1), (1, 0), (1, 2), (2, 1), (0, 2), (2, 0)],
         [0, 1, 2]),
        # directed path
        ("dir_path_4", [(0, 1), (1, 2), (2, 3)], [0, 1, 2, 3]),
        # path with mismatched degree balance
        ("dir_unbalanced",
         [(0, 1), (1, 2), (2, 0), (0, 3)],
         list(range(4))),
        # tournament on 3 nodes (acyclic): 0→1, 1→2, 0→2
        ("dir_tournament_3", [(0, 1), (1, 2), (0, 2)], [0, 1, 2]),
        # single self-loop in directed
        ("dir_self_loop", [(0, 0)], [0]),
        # gnp directed random
        *(
            (f"dir_gnp_n{n}_p{p}_s{seed}",
             list(nx.gnp_random_graph(n, p, seed=seed, directed=True).edges()),
             list(range(n)))
            for n, p, seed in [
                (5, 0.4, 1), (7, 0.4, 2), (10, 0.3, 3),
            ]
        ),
    ]


def _self_loop_fixtures():
    """Self-loop fixtures — fnx delegates these entirely to NX."""
    return [
        ("self_loop_only", [(0, 0)], [0]),
        ("triangle_plus_self_loop",
         [(0, 1), (1, 2), (2, 0), (0, 0)], [0, 1, 2]),
        ("path_plus_self_loop",
         [(0, 1), (1, 2), (1, 1)], [0, 1, 2]),
        ("two_self_loops",
         [(0, 0), (1, 1), (0, 1)], [0, 1]),
    ]


UNDIRECTED_SIMPLE = _undirected_simple_fixtures()
UNDIRECTED_MULTI = _undirected_multi_fixtures()
DIRECTED = _directed_fixtures()
SELF_LOOP = _self_loop_fixtures()


# ---------------------------------------------------------------------------
# is_eulerian / is_semieulerian / has_eulerian_path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED_SIMPLE,
                         ids=[fx[0] for fx in UNDIRECTED_SIMPLE])
def test_is_eulerian_undirected_simple_matches_networkx(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    assert fnx.is_eulerian(fg) == nx.is_eulerian(ng)


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED_MULTI,
                         ids=[fx[0] for fx in UNDIRECTED_MULTI])
def test_is_eulerian_multigraph_matches_networkx(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes, multi=True)
    assert fnx.is_eulerian(fg) == nx.is_eulerian(ng)


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_is_eulerian_directed_matches_networkx(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    assert fnx.is_eulerian(fg) == nx.is_eulerian(ng)


@pytest.mark.parametrize("name,edges,nodes", SELF_LOOP,
                         ids=[fx[0] for fx in SELF_LOOP])
def test_is_eulerian_with_self_loops_matches_networkx(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    assert fnx.is_eulerian(fg) == nx.is_eulerian(ng)


@pytest.mark.parametrize("name,edges,nodes",
                         UNDIRECTED_SIMPLE + UNDIRECTED_MULTI + DIRECTED,
                         ids=[fx[0] for fx in
                              UNDIRECTED_SIMPLE + UNDIRECTED_MULTI + DIRECTED])
def test_has_eulerian_path_matches_networkx(name, edges, nodes):
    """``has_eulerian_path(G, source=None)`` parity across all simple,
    multigraph, and directed fixtures."""
    if any(isinstance(n, str) and n.startswith("dir_") for n in [name]):
        fg, ng = _pair_directed(edges, nodes)
    elif name.startswith("multi_"):
        fg, ng = _pair_undirected(edges, nodes, multi=True)
    elif name.startswith("dir_"):
        fg, ng = _pair_directed(edges, nodes)
    else:
        fg, ng = _pair_undirected(edges, nodes)
    assert fnx.has_eulerian_path(fg) == nx.has_eulerian_path(ng)


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED_SIMPLE,
                         ids=[fx[0] for fx in UNDIRECTED_SIMPLE])
def test_is_semieulerian_undirected_matches_networkx(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    assert fnx.is_semieulerian(fg) == nx.is_semieulerian(ng)


# ---------------------------------------------------------------------------
# eulerian_circuit — exact edge-sequence parity (NX delegation contract)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED_SIMPLE,
                         ids=[fx[0] for fx in UNDIRECTED_SIMPLE])
def test_eulerian_circuit_matches_networkx_when_eulerian(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    if not nx.is_eulerian(ng):
        with pytest.raises(nx.NetworkXError):
            list(fnx.eulerian_circuit(fg))
        return
    assert list(fnx.eulerian_circuit(fg)) == list(nx.eulerian_circuit(ng))


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_eulerian_circuit_directed_matches_networkx_when_eulerian(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    if not nx.is_eulerian(ng):
        with pytest.raises(nx.NetworkXError):
            list(fnx.eulerian_circuit(fg))
        return
    assert list(fnx.eulerian_circuit(fg)) == list(nx.eulerian_circuit(ng))


# Source-specific eulerian_circuit (start vertex fixed)
@pytest.mark.parametrize(
    "name,edges,nodes,source",
    [
        ("K_3_src0", list(itertools.combinations(range(3), 2)),
         list(range(3)), 0),
        ("K_3_src1", list(itertools.combinations(range(3), 2)),
         list(range(3)), 1),
        ("K_3_src2", list(itertools.combinations(range(3), 2)),
         list(range(3)), 2),
        ("C_5_src0", [(i, (i + 1) % 5) for i in range(5)],
         list(range(5)), 0),
        ("C_5_src3", [(i, (i + 1) % 5) for i in range(5)],
         list(range(5)), 3),
        ("K_5_src2", list(itertools.combinations(range(5), 2)),
         list(range(5)), 2),
    ],
)
def test_eulerian_circuit_with_source_matches_networkx(name, edges, nodes, source):
    fg, ng = _pair_undirected(edges, nodes)
    assert (
        list(fnx.eulerian_circuit(fg, source=source))
        == list(nx.eulerian_circuit(ng, source=source))
    )


# ---------------------------------------------------------------------------
# eulerian_path — exact edge-sequence parity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED_SIMPLE,
                         ids=[fx[0] for fx in UNDIRECTED_SIMPLE])
def test_eulerian_path_matches_networkx_when_path_exists(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    if not nx.has_eulerian_path(ng):
        with pytest.raises(nx.NetworkXError):
            list(fnx.eulerian_path(fg))
        return
    assert list(fnx.eulerian_path(fg)) == list(nx.eulerian_path(ng))


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_eulerian_path_directed_matches_networkx(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    if not nx.has_eulerian_path(ng):
        with pytest.raises(nx.NetworkXError):
            list(fnx.eulerian_path(fg))
        return
    assert list(fnx.eulerian_path(fg)) == list(nx.eulerian_path(ng))


# ---------------------------------------------------------------------------
# eulerize — edge-multiset parity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [
        # eulerize requires the input to be connected and simple
        ("P_3", [(0, 1), (1, 2)], [0, 1, 2]),
        ("P_4", [(0, 1), (1, 2), (2, 3)], list(range(4))),
        ("P_5", list(zip(range(4), range(1, 5))), list(range(5))),
        ("K_4", list(itertools.combinations(range(4), 2)), list(range(4))),
        ("K_6", list(itertools.combinations(range(6), 2)), list(range(6))),
        ("S_3", [(0, i) for i in range(1, 4)], list(range(4))),
        ("S_5", [(0, i) for i in range(1, 6)], list(range(6))),
        ("two_odd_in_K4_minus_edge",
         [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3)], list(range(4))),
    ],
)
def test_eulerize_matches_networkx(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    fnx_result = fnx.eulerize(fg)
    nx_result = nx.eulerize(ng)
    assert sorted(fnx_result.edges()) == sorted(nx_result.edges())
    # Result must be Eulerian (every degree even, connected)
    assert nx.is_eulerian(nx_result)
    assert fnx.is_eulerian(fnx_result)


def test_eulerize_already_eulerian_returns_equivalent_graph():
    fg, ng = _pair_undirected([(0, 1), (1, 2), (2, 0)], [0, 1, 2])
    fnx_result = fnx.eulerize(fg)
    nx_result = nx.eulerize(ng)
    assert sorted(fnx_result.edges()) == sorted(nx_result.edges())


# ---------------------------------------------------------------------------
# Empty / disconnected dispatch
# ---------------------------------------------------------------------------


def test_is_eulerian_empty_graph_raises_pointless_concept():
    """NX raises NetworkXPointlessConcept on the null graph; fnx must too."""
    with pytest.raises(nx.NetworkXPointlessConcept) as nx_exc:
        nx.is_eulerian(nx.Graph())
    with pytest.raises(fnx.NetworkXPointlessConcept) as fnx_exc:
        fnx.is_eulerian(fnx.Graph())
    assert str(fnx_exc.value) == str(nx_exc.value)


def test_is_eulerian_empty_directed_graph_raises_pointless_concept():
    with pytest.raises(nx.NetworkXPointlessConcept):
        nx.is_eulerian(nx.DiGraph())
    with pytest.raises(fnx.NetworkXPointlessConcept):
        fnx.is_eulerian(fnx.DiGraph())


def test_is_eulerian_single_node_no_edges_returns_true():
    assert fnx.is_eulerian(fnx.Graph([(0, 0)])) is True
    g = fnx.Graph(); g.add_node(0)
    assert fnx.is_eulerian(g) is nx.is_eulerian(nx.empty_graph(1)) is True


def test_eulerian_circuit_on_non_eulerian_graph_raises():
    """``eulerian_circuit`` raises when the graph isn't Eulerian."""
    fg, ng = _pair_undirected([(0, 1), (1, 2)], [0, 1, 2])  # P_3 is not Eulerian
    with pytest.raises(nx.NetworkXError) as nx_exc:
        list(nx.eulerian_circuit(ng))
    with pytest.raises(fnx.NetworkXError) as fnx_exc:
        list(fnx.eulerian_circuit(fg))
    assert str(fnx_exc.value) == str(nx_exc.value)


def test_eulerian_path_on_no_path_graph_raises():
    """``eulerian_path`` raises when the graph has no Eulerian path.
    A graph with 4 odd-degree vertices has no Eulerian path
    (existence requires exactly 0 or 2 odd-degree vertices)."""
    # K_4: every vertex has degree 3 → 4 odd-degree vertices.
    fg, ng = _pair_undirected(
        list(itertools.combinations(range(4), 2)), list(range(4)),
    )
    with pytest.raises(nx.NetworkXError) as nx_exc:
        list(nx.eulerian_path(ng))
    with pytest.raises(fnx.NetworkXError) as fnx_exc:
        list(fnx.eulerian_path(fg))
    assert str(fnx_exc.value) == str(nx_exc.value)


# ---------------------------------------------------------------------------
# Path traversal correctness — every edge visited exactly once
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [
        ("K_3", list(itertools.combinations(range(3), 2)), [0, 1, 2]),
        ("K_5", list(itertools.combinations(range(5), 2)), list(range(5))),
        ("C_4", [(i, (i + 1) % 4) for i in range(4)], list(range(4))),
        ("C_8", [(i, (i + 1) % 8) for i in range(8)], list(range(8))),
        ("bowtie",
         [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)], list(range(5))),
    ],
)
def test_eulerian_circuit_visits_every_edge_exactly_once(name, edges, nodes):
    fg, _ng = _pair_undirected(edges, nodes)
    if not fnx.is_eulerian(fg):
        return
    circuit = list(fnx.eulerian_circuit(fg))
    # Each edge should appear exactly once (as unordered pair)
    visited = sorted(tuple(sorted(e)) for e in circuit)
    expected = sorted(tuple(sorted(e)) for e in edges)
    assert visited == expected


def test_eulerian_path_endpoints_are_odd_degree_vertices():
    """Eulerian path must start and end at the two odd-degree vertices
    (when the graph isn't already Eulerian)."""
    edges = [(0, 1), (1, 2), (2, 3), (1, 3)]  # 0 and 2 are odd degree
    fg, _ = _pair_undirected(edges, list(range(4)))
    path = list(fnx.eulerian_path(fg))
    start = path[0][0]
    end = path[-1][1]
    odd_vertices = {n for n, d in fg.degree() if d % 2 == 1}
    assert {start, end} == odd_vertices
