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


# br-r37-c1-6ncq6: networkx labels the tree with minimum_cut values - ints over
# int capacities, and a zero cut (to an isolated node) is the int 0 whatever the
# capacities are; its residual network drops selfloops, so a float selfloop does
# not make an int graph's labels floats. 4 == 4.0, so compare (value, type).
def _ght_graph(mod, caps, isolated):
    g = mod.Graph()
    for u, v, c in [(0, 1, 3), (1, 2, 2), (2, 0, 1), (2, 3, 4), (3, 4, 2), (4, 1, 5)]:
        g.add_edge(u, v, capacity=float(c) if caps == "float" else c)
    if caps == "int_float_selfloop":
        g.add_edge(2, 2, capacity=0.5)
    if isolated:
        g.add_node(9)
    return g


def _typed_tree(tree):
    return sorted(
        (min(u, v), max(u, v), d["weight"], type(d["weight"]).__name__)
        for u, v, d in tree.edges(data=True)
    )


@pytest.mark.parametrize("spelling", ["gomory_hu_tree", "algorithms.gomory_hu_tree", "flow.gomory_hu_tree"])
@pytest.mark.parametrize("caps", ["int", "float", "int_float_selfloop"])
@pytest.mark.parametrize("isolated", [False, True], ids=["connected", "isolated"])
def test_gomory_hu_tree_weight_types_match_networkx(spelling, caps, isolated):
    fn = fnx
    for part in spelling.split("."):
        fn = getattr(fn, part)
    expected = _typed_tree(nx.gomory_hu_tree(_ght_graph(nx, caps, isolated)))
    assert _typed_tree(fn(_ght_graph(fnx, caps, isolated))) == expected
