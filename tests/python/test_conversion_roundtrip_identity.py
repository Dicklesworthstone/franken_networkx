"""Round-trip identity + networkx parity for graph converters.

A converter pair (to_X / from_X) must round-trip: encoding a graph and decoding
it back reproduces the same node and edge sets (and weights, where the format
carries them). Round-trip identity is an oracle-free correctness check, and the
dense/sparse matrices must additionally match networkx exactly.

No mocks: real fnx (and real networkx for parity) on random weighted graphs.
"""

from __future__ import annotations

import random

import numpy as np
import pytest
import networkx as nx
import franken_networkx as fnx


def _edges(g):
    return sorted(tuple(sorted((u, v))) for u, v in g.edges())


def _random_weighted(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    g = fnx.Graph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if r.random() < 0.45:
                g.add_edge(u, v, weight=r.randint(1, 9))
    return g, n


@pytest.mark.parametrize("seed", range(30))
def test_dict_roundtrips(seed):
    g, _ = _random_weighted(seed)
    g_dod = fnx.from_dict_of_dicts(fnx.to_dict_of_dicts(g))
    assert _edges(g_dod) == _edges(g)
    assert sorted(g_dod.nodes()) == sorted(g.nodes())
    # weights survive the dict-of-dicts round-trip.
    for u, v, w in g.edges(data="weight"):
        assert g_dod[u][v]["weight"] == w

    g_dol = fnx.from_dict_of_lists(fnx.to_dict_of_lists(g))
    assert _edges(g_dol) == _edges(g)


@pytest.mark.parametrize("seed", range(30))
def test_matrix_roundtrips_and_parity(seed):
    g, n = _random_weighted(seed)
    ng = nx.Graph()
    ng.add_nodes_from(range(n))
    for u, v, w in g.edges(data="weight"):
        ng.add_edge(u, v, weight=w)

    # numpy round-trip preserves edge count, and matches nx exactly.
    A = fnx.to_numpy_array(g)
    assert np.allclose(A, nx.to_numpy_array(ng))
    assert fnx.from_numpy_array(A).number_of_edges() == g.number_of_edges()

    # scipy sparse round-trip + parity.
    S = fnx.to_scipy_sparse_array(g)
    assert np.allclose(S.toarray(), nx.to_scipy_sparse_array(ng).toarray())
    assert fnx.from_scipy_sparse_array(S).number_of_edges() == g.number_of_edges()


@pytest.mark.parametrize("seed", range(30))
def test_pandas_edgelist_roundtrip(seed):
    g, _ = _random_weighted(seed)
    df = fnx.to_pandas_edgelist(g)
    g_back = fnx.from_pandas_edgelist(df, edge_attr="weight")
    assert _edges(g_back) == _edges(g)
    for u, v, w in g.edges(data="weight"):
        assert g_back[u][v]["weight"] == w
