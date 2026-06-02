"""Value parity for spanning-structure algorithm variants at small & medium scale.

The flow/cut/matching value net (br-r37-c1-m4kt1) covers default-kruskal MST,
arborescence, and steiner. This complements it by pinning the ``algorithm=``
variants (kruskal / prim / boruvka) of minimum/maximum_spanning_edges — which
route through different code paths (Rust kruskal fast path vs nx delegation) —
plus maximum_branching and gomory_hu_tree, at both small and medium (n≈200)
scale. The MST *weight* must be identical across all three algorithms and equal
networkx's; a refactor that broke one algorithm or drifted at scale trips here.
"""

import networkx as nx
import franken_networkx as fnx

import pytest


def _wgraph(mod, n, deg):
    g = mod.Graph()
    for i in range(n):
        for k in range(1, deg + 1):
            j = (i * 7 + k * k) % n
            if i == j:
                continue
            g.add_edge(i, j, weight=float(1 + ((i * k) % 17)))
    return g


def _mst_weight(edges):
    return round(sum(d["weight"] for *_, d in edges), 4)


@pytest.mark.parametrize("n,deg", [(6, 3), (40, 4), (200, 5)])
@pytest.mark.parametrize("algorithm", ["kruskal", "prim", "boruvka"])
def test_minimum_spanning_edges_weight_matches_networkx(n, deg, algorithm):
    gn, gf = _wgraph(nx, n, deg), _wgraph(fnx, n, deg)
    wn = _mst_weight(nx.minimum_spanning_edges(gn, algorithm=algorithm, data=True))
    wf = _mst_weight(fnx.minimum_spanning_edges(gf, algorithm=algorithm, data=True))
    assert wf == wn, f"{algorithm} n={n}: nx={wn} fnx={wf}"


@pytest.mark.parametrize("n,deg", [(6, 3), (40, 4), (200, 5)])
@pytest.mark.parametrize("algorithm", ["kruskal", "prim", "boruvka"])
def test_maximum_spanning_edges_weight_matches_networkx(n, deg, algorithm):
    gn, gf = _wgraph(nx, n, deg), _wgraph(fnx, n, deg)
    wn = _mst_weight(nx.maximum_spanning_edges(gn, algorithm=algorithm, data=True))
    wf = _mst_weight(fnx.maximum_spanning_edges(gf, algorithm=algorithm, data=True))
    assert wf == wn, f"{algorithm} n={n}: nx={wn} fnx={wf}"


def test_all_mst_algorithms_agree_internally():
    # The three algorithms must all yield the same MST weight (sanity, no nx).
    gf = _wgraph(fnx, 120, 5)
    weights = {
        alg: _mst_weight(fnx.minimum_spanning_edges(gf, algorithm=alg, data=True))
        for alg in ("kruskal", "prim", "boruvka")
    }
    assert len(set(weights.values())) == 1, weights


def _dgraph(mod, n):
    g = mod.DiGraph()
    for i in range(n):
        g.add_edge(i, (i + 1) % n, weight=float(1 + (i % 13)))
        j = (i * 3 + 1) % n
        if j != i:
            g.add_edge(i, j, weight=float(1 + (i % 7)))
    return g


@pytest.mark.parametrize("n", [8, 120])
def test_min_arborescence_and_max_branching_weight_matches_networkx(n):
    gn, gf = _dgraph(nx, n), _dgraph(fnx, n)
    an = round(sum(d["weight"] for _, _, d in nx.minimum_spanning_arborescence(gn).edges(data=True)), 4)
    af = round(sum(d["weight"] for _, _, d in fnx.minimum_spanning_arborescence(gf).edges(data=True)), 4)
    assert af == an
    bn = round(sum(d["weight"] for _, _, d in nx.maximum_branching(gn).edges(data=True)), 4)
    bf = round(sum(d["weight"] for _, _, d in fnx.maximum_branching(gf).edges(data=True)), 4)
    assert bf == bn


@pytest.mark.parametrize("n,deg", [(10, 4), (60, 5)])
def test_gomory_hu_tree_edge_count_matches_networkx(n, deg):
    if not (hasattr(nx, "gomory_hu_tree") and hasattr(fnx, "gomory_hu_tree")):
        pytest.skip("gomory_hu_tree unavailable")
    gn, gf = _wgraph(nx, n, deg), _wgraph(fnx, n, deg)
    # A Gomory-Hu tree always has exactly n-1 edges; also assert it matches nx.
    # The edge attribute is 'weight' here, so use it as the capacity.
    tn, tf = nx.gomory_hu_tree(gn, capacity="weight"), fnx.gomory_hu_tree(gf, capacity="weight")
    assert tf.number_of_edges() == tn.number_of_edges() == gn.number_of_nodes() - 1
