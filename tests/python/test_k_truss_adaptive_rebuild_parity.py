"""br-r37-c1-at6zf: k_truss adaptive-rebuild byte parity.

The ``_k_truss_via_parity`` rebuild was construction-tax-bound for low ``k``
(it rebuilt every surviving edge via per-edge ``add_edge``), running ~2.1x
slower than genuine networkx on e.g. ``BA(800,4) k=2``. The adaptive rebuild
mirrors nx's own structure (``G.copy()`` + drop the few non-truss edges and
resulting isolates) when most edges survive, and only builds a fresh survivor
graph when most edges are dropped. Both branches must stay byte-identical to
networkx: same node order, same edge order, and all node/edge/graph attributes.
"""

import itertools

import networkx as nx
import pytest

import franken_networkx as fnx


def _signature(R):
    return (
        list(R.nodes(data=True)),
        list(R.edges(data=True)),
        dict(R.graph),
    )


def _shuffled_attr(lib):
    """Non-sorted node insertion order + node/edge/graph attributes."""
    G = lib.Graph()
    G.graph["name"] = "shuffled"
    G.graph["meta"] = {"src": "test"}
    order = [5, 3, 9, 1, 7, 2, 8, 0, 4, 6, 11, 10, 13, 12]
    for i, nd in enumerate(order):
        G.add_node(nd, w=i, color=str(nd % 3))
    for a, b in itertools.combinations(order, 2):
        if (a + b) % 2 == 0 or (a * b) % 5 == 0:
            G.add_edge(a, b, weight=float((a + b) % 7) + 0.5)
    return G


@pytest.mark.parametrize("k", [2, 3, 4, 5, 6])
def test_shuffled_attr_byte_parity(k):
    rn = nx.k_truss(_shuffled_attr(nx), k)
    rf = fnx.k_truss(_shuffled_attr(fnx), k)
    assert _signature(rf) == _signature(rn)


@pytest.mark.parametrize("k", [2, 3, 4, 5, 6])
@pytest.mark.parametrize("seed", [7, 11, 23])
def test_barabasi_albert_byte_parity(k, seed):
    # k=2 exercises the copy-and-prune branch (most edges survive);
    # larger k exercises the fresh-batch-build branch.
    gn = nx.barabasi_albert_graph(120, 3, seed=seed)
    gf = fnx.barabasi_albert_graph(120, 3, seed=seed)
    rn = nx.k_truss(gn, k)
    rf = fnx.k_truss(gf, k)
    assert _signature(rf) == _signature(rn)


def test_isolated_nodes_dropped_like_nx():
    # nodes that fall out of every triangle become isolates and must be
    # dropped in both branches, exactly as nx does.
    gn = nx.Graph()
    gf = fnx.Graph()
    for G in (gn, gf):
        G.add_edges_from([(0, 1), (1, 2), (2, 0)])  # triangle
        G.add_edge(2, 3)  # pendant -> 3 isolated for k=3
        G.add_node(99, tag="lonely")  # pre-existing isolate
    rn = nx.k_truss(gn, 3)
    rf = fnx.k_truss(gf, 3)
    assert _signature(rf) == _signature(rn)


def test_error_contract_preserved():
    for L in (nx, fnx):
        with pytest.raises(Exception):
            L.k_truss(L.MultiGraph([(0, 1)]), 2)
        with pytest.raises(Exception):
            L.k_truss(L.DiGraph([(0, 1)]), 2)
