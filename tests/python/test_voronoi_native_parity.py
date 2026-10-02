"""Parity for the native (delegation-free) voronoi_cells.

br-voronoinative: `voronoi_cells` previously delegated to networkx (the Rust
`voronoi_cells_rust` ignored `weight` and mis-assigned centers). It is now
rebuilt on fnx's own `multi_source_dijkstra_path` + the standard
nearest-center inversion, dropping the `_fnx_to_nx` conversion. These tests
pin it bit-identical to nx across the parameter matrix.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _mk(*, directed=False, weighted=True, seed=3, disconnected=False, n=80):
    Gx = nx.connected_watts_strogatz_graph(n, 4, 0.3, seed=seed)
    if directed:
        Gx = Gx.to_directed()
    rnd = random.Random(seed)
    if weighted:
        for u, v in Gx.edges():
            Gx[u][v]["weight"] = rnd.randint(1, 10)
    if disconnected:
        Gx.add_nodes_from([900, 901, 902])
    Gf = (fnx.DiGraph if directed else fnx.Graph)()
    Gf.add_nodes_from(Gx.nodes())
    for u, v, d in Gx.edges(data=True):
        Gf.add_edge(u, v, **({"weight": d["weight"]} if weighted else {}))
    return Gx, Gf


def _eq(vx, vf):
    return vx == vf and list(vx) == list(vf)


def test_parameter_matrix_parity():
    for directed in (False, True):
        for weighted in (True, False):
            for disconnected in (False, True):
                Gx, Gf = _mk(
                    directed=directed, weighted=weighted, disconnected=disconnected
                )
                w = "weight" if weighted else None
                assert _eq(
                    nx.voronoi_cells(Gx, {0, 40}, weight=w),
                    fnx.voronoi_cells(Gf, {0, 40}, weight=w),
                ), (directed, weighted, disconnected)


def test_single_center():
    Gx, Gf = _mk(seed=5)
    assert _eq(
        nx.voronoi_cells(Gx, {0}, weight="weight"),
        fnx.voronoi_cells(Gf, {0}, weight="weight"),
    )


def test_unreachable_nodes_grouped():
    Gx, Gf = _mk(disconnected=True)
    vf = fnx.voronoi_cells(Gf, {0, 40}, weight="weight")
    assert "unreachable" in vf
    assert {900, 901, 902} <= vf["unreachable"]
    assert vf == nx.voronoi_cells(Gx, {0, 40}, weight="weight")


def test_empty_centers_raises_valueerror():
    _, Gf = _mk()
    try:
        fnx.voronoi_cells(Gf, [], weight="weight")
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for empty center_nodes")


def test_bad_center_raises_node_not_found():
    Gx, Gf = _mk()
    nx_exc = fnx_exc = None
    try:
        nx.voronoi_cells(Gx, {99999}, weight="weight")
    except Exception as e:  # noqa: BLE001
        nx_exc = type(e).__name__
    try:
        fnx.voronoi_cells(Gf, {99999}, weight="weight")
    except Exception as e:  # noqa: BLE001
        fnx_exc = type(e).__name__
    assert nx_exc == fnx_exc == "NodeNotFound"


def test_weighted_tie_break_matches_nx():
    # 4-cycle 0-1-2-3-0 with a heavier 0-2 shortcut; node 3 is closer to 2.
    Gx = nx.Graph()
    Gf = fnx.Graph()
    for u, v, w in [(0, 1, 1), (1, 2, 1), (2, 3, 1), (3, 0, 1), (0, 2, 2)]:
        Gx.add_edge(u, v, weight=w)
        Gf.add_edge(u, v, weight=w)
    assert _eq(
        nx.voronoi_cells(Gx, {0, 2}, weight="weight"),
        fnx.voronoi_cells(Gf, {0, 2}, weight="weight"),
    )


def _collision_twins(cls_name, scale, seed, weighted):
    # Three BA pieces, scattered edges and isolated nodes, labels scaled so
    # hashes collide (x1024 lands every label in slot 0 of any table under 1024).
    r = random.Random(seed)
    edges, off = [], 0
    for size in (50, 30, 20):
        for a, b in nx.barabasi_albert_graph(size, 2, seed=seed + size).edges():
            edges.append((scale * (a + off), scale * (b + off)))
        off += size
    edges += [(scale * r.randrange(120), scale * r.randrange(120)) for _ in range(10)]
    r.shuffle(edges)
    nodes = [scale * x for x in r.sample(range(130), 130)]
    Gx, Gf = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for g in (Gx, Gf):
        g.add_nodes_from(nodes)
        for u, v in edges:
            if weighted:
                g.add_edge(u, v, weight=(u + 3 * v) % 5 + 1)
            else:
                g.add_edge(u, v)
    return Gx, Gf


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph", "MultiGraph"])
@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("scale", [1, 37, 1024])
@pytest.mark.parametrize("seed", range(3))
def test_each_cell_iterates_in_networkx_order(cls_name, weighted, scale, seed):
    # br-r37-c1-ygt3z: each cell is a set networkx grows in its paths dict's
    # (settle) order; list() of it is observable, and a kernel settling equal
    # distances in another order put 12 of 36 graphs' cells in another order.
    Gx, Gf = _collision_twins(cls_name, scale, seed, weighted)
    centers = list(Gx)[:4]
    want = nx.voronoi_cells(Gx, centers, weight="weight")
    got = fnx.voronoi_cells(Gf, centers, weight="weight")
    assert [(k, list(v)) for k, v in got.items()] == [(k, list(v)) for k, v in want.items()]
