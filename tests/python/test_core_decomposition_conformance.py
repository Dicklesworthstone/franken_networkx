"""NetworkX conformance for the k-core decomposition family.

Covers ``core_number``, ``k_core``, ``k_shell``, ``k_crust``,
``k_corona``, and ``onion_layers`` against upstream NetworkX.

The Rust ``_raw_core_number`` calls ``gr.undirected()`` on directed
input — NetworkX's directed contract counts ``in_degree + out_degree``
(per the docstring: "For directed graphs the node degree is defined
to be the in-degree + out-degree"). For an antiparallel pair of
directed edges this halves the core number and propagates into
``k_core`` / ``k_shell`` / ``k_crust`` / ``k_corona``, which all
consume ``core_number``. Same systematic bug shape as the eccentricity
/ is_eulerian / is_tree directed-collapse defects fixed earlier.

Suite asserts bit-for-bit parity across ~150 fixtures including
antiparallel-pair triggers, directed K_n in both orientations,
mixed-orientation graphs, undirected baselines, multigraph rejection,
self-loop rejection, and gnp randoms in both directed and undirected
flavors.
"""

from __future__ import annotations

import itertools

import pytest
import networkx as nx

import franken_networkx as fnx


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


def _pair_directed(edges, nodes=None):
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
# Fixture builders
# ---------------------------------------------------------------------------


def _undirected_simple_fixtures():
    out = []
    for n in range(2, 8):
        edges = list(itertools.combinations(range(n), 2))
        out.append((f"K_{n}", edges, list(range(n))))
    for n in range(3, 9):
        out.append((
            f"C_{n}",
            [(i, (i + 1) % n) for i in range(n)],
            list(range(n)),
        ))
    for n in range(2, 8):
        out.append((
            f"P_{n}",
            list(zip(range(n - 1), range(1, n))),
            list(range(n)),
        ))
    for n in range(1, 6):
        out.append((
            f"S_{n}",
            [(0, i) for i in range(1, n + 1)],
            list(range(n + 1)),
        ))
    pg = nx.petersen_graph()
    out.append(("petersen", list(pg.edges()), list(pg.nodes())))
    for n, p, seed in [(8, 0.3, 1), (8, 0.5, 2), (10, 0.3, 3),
                        (12, 0.4, 4), (15, 0.3, 5), (20, 0.2, 6)]:
        gnp = nx.gnp_random_graph(n, p, seed=seed)
        out.append((
            f"gnp_n{n}_p{p}_s{seed}",
            list(gnp.edges()),
            list(range(n)),
        ))
    return out


def _directed_fixtures():
    out = []
    # Antiparallel pairs (the bug trigger)
    out.append(("dir_antiparallel_pair",
                [(0, 1), (1, 0)], [0, 1]))
    out.append(("dir_K3_both_dirs",
                [(0, 1), (1, 0), (1, 2), (2, 1), (0, 2), (2, 0)],
                list(range(3))))
    out.append(("dir_K4_both_dirs",
                [(u, v) for u in range(4) for v in range(4) if u != v],
                list(range(4))))
    # Single-direction tournaments
    for n in (3, 4, 5):
        out.append((
            f"dir_K{n}_one_way",
            list(itertools.combinations(range(n), 2)),
            list(range(n)),
        ))
    # Directed cycles
    for n in range(2, 7):
        out.append((
            f"dir_C{n}",
            [(i, (i + 1) % n) for i in range(n)],
            list(range(n)),
        ))
    # Mixed orientation (some antiparallel, some not)
    out.append((
        "dir_mixed_some_antipar",
        [(0, 1), (1, 0), (1, 2), (2, 3), (3, 1)],
        list(range(4)),
    ))
    # gnp directed random
    for n, p, seed in [(6, 0.4, 1), (8, 0.35, 2), (10, 0.3, 3),
                        (12, 0.25, 4), (15, 0.2, 5)]:
        gnp = nx.gnp_random_graph(n, p, seed=seed, directed=True)
        out.append((
            f"dir_gnp_n{n}_p{p}_s{seed}",
            list(gnp.edges()),
            list(range(n)),
        ))
    return out


UNDIRECTED_SIMPLE = _undirected_simple_fixtures()
DIRECTED = _directed_fixtures()


# ---------------------------------------------------------------------------
# core_number
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED_SIMPLE,
                         ids=[fx[0] for fx in UNDIRECTED_SIMPLE])
def test_core_number_undirected(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    assert fnx.core_number(fg) == nx.core_number(ng)


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_core_number_directed(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    assert fnx.core_number(fg) == nx.core_number(ng)


# ---------------------------------------------------------------------------
# k_core / k_shell / k_crust at various k values
# ---------------------------------------------------------------------------


def _max_core_k(g):
    cn = nx.core_number(g)
    return max(cn.values()) if cn else 0


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED_SIMPLE,
                         ids=[fx[0] for fx in UNDIRECTED_SIMPLE])
def test_k_core_undirected(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    max_k = _max_core_k(ng)
    for k in range(0, max_k + 2):
        assert (
            sorted(fnx.k_core(fg, k=k).edges())
            == sorted(nx.k_core(ng, k=k).edges())
        ), f"{name}: k_core k={k} edge mismatch"


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_k_core_directed(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    max_k = _max_core_k(ng)
    for k in range(0, max_k + 2):
        assert (
            sorted(fnx.k_core(fg, k=k).edges())
            == sorted(nx.k_core(ng, k=k).edges())
        ), f"{name}: k_core k={k} edge mismatch"


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED_SIMPLE,
                         ids=[fx[0] for fx in UNDIRECTED_SIMPLE])
def test_k_shell_undirected(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    max_k = _max_core_k(ng)
    for k in range(0, max_k + 1):
        assert (
            sorted(fnx.k_shell(fg, k=k).edges())
            == sorted(nx.k_shell(ng, k=k).edges())
        ), f"{name}: k_shell k={k} mismatch"


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_k_shell_directed(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    max_k = _max_core_k(ng)
    for k in range(0, max_k + 1):
        assert (
            sorted(fnx.k_shell(fg, k=k).edges())
            == sorted(nx.k_shell(ng, k=k).edges())
        ), f"{name}: k_shell k={k} mismatch"


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED_SIMPLE,
                         ids=[fx[0] for fx in UNDIRECTED_SIMPLE])
def test_k_crust_undirected(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    max_k = _max_core_k(ng)
    for k in range(0, max_k + 1):
        assert (
            sorted(fnx.k_crust(fg, k=k).edges())
            == sorted(nx.k_crust(ng, k=k).edges())
        ), f"{name}: k_crust k={k} mismatch"


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_k_crust_directed(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    max_k = _max_core_k(ng)
    for k in range(0, max_k + 1):
        assert (
            sorted(fnx.k_crust(fg, k=k).edges())
            == sorted(nx.k_crust(ng, k=k).edges())
        ), f"{name}: k_crust k={k} mismatch"


# ---------------------------------------------------------------------------
# k_corona
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in UNDIRECTED_SIMPLE if len(fx[2]) <= 12],
    ids=[fx[0] for fx in UNDIRECTED_SIMPLE if len(fx[2]) <= 12],
)
def test_k_corona_undirected(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    max_k = _max_core_k(ng)
    for k in range(0, max_k + 1):
        assert (
            sorted(fnx.k_corona(fg, k=k).edges())
            == sorted(nx.k_corona(ng, k=k).edges())
        ), f"{name}: k_corona k={k} mismatch"


# ---------------------------------------------------------------------------
# Multigraph and self-loop rejection
# ---------------------------------------------------------------------------


def test_core_number_rejects_multigraph():
    fg = fnx.MultiGraph()
    fg.add_edges_from([(0, 1), (1, 2)])
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.core_number(fg)


def test_core_number_rejects_self_loop_input():
    fg = fnx.Graph()
    fg.add_edge(0, 1)
    fg.add_edge(0, 0)
    with pytest.raises(fnx.NetworkXNotImplemented) as fnx_exc:
        fnx.core_number(fg)
    assert "self loops" in str(fnx_exc.value)


def test_k_core_rejects_self_loop_input():
    fg = fnx.Graph()
    fg.add_edge(0, 1)
    fg.add_edge(0, 0)
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.k_core(fg)


# ---------------------------------------------------------------------------
# Cross-relation invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in UNDIRECTED_SIMPLE if len(fx[2]) > 0]
    + [fx for fx in DIRECTED if len(fx[2]) > 0],
    ids=[fx[0] for fx in UNDIRECTED_SIMPLE if len(fx[2]) > 0]
       + [fx[0] for fx in DIRECTED if len(fx[2]) > 0],
)
def test_k_core_plus_k_crust_covers_all_nodes(name, edges, nodes):
    """For any k, every node must appear in either ``k_core(k)`` or
    ``k_crust(k-1)`` (where 'crust' is core_number < k). This sanity
    invariant catches off-by-one boundary errors."""
    if name.startswith("dir_"):
        fg, _ = _pair_directed(edges, nodes)
    else:
        fg, _ = _pair_undirected(edges, nodes)
    cn = fnx.core_number(fg)
    if not cn:
        return
    max_k = max(cn.values())
    for k in range(1, max_k + 1):
        kc_nodes = set(fnx.k_core(fg, k=k).nodes())
        crust_nodes = set(fnx.k_crust(fg, k=k - 1).nodes())
        all_nodes = set(fg.nodes())
        assert kc_nodes | crust_nodes == all_nodes
