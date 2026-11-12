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


def _nx_twin(g, n):
    ng = nx.Graph()
    ng.add_nodes_from(range(n))
    for u, v, w in g.edges(data="weight"):
        ng.add_edge(u, v, weight=w)
    return ng


@pytest.mark.parametrize("seed", range(30))
def test_matrix_roundtrip_preserves_content_not_just_count(seed):
    """br-r37-c1-ud0lj: the matrix round-trips asserted only
    ``from_X(to_X(g)).number_of_edges() == g.number_of_edges()``. A codec that
    returned a completely different graph of the same size would pass that, on a
    bead whose premise is oracle-free CODEC correctness. The decoded edge set and
    every weight are checked here, and the decoded graph is compared against
    networkx's own round-trip rather than only against the source.

    Verified equal across all 30 seeds before being asserted.
    """
    g, n = _random_weighted(seed)
    ng = _nx_twin(g, n)

    for decode, encode, nx_decode, nx_encode in (
        (fnx.from_numpy_array, fnx.to_numpy_array, nx.from_numpy_array, nx.to_numpy_array),
        (
            fnx.from_scipy_sparse_array,
            fnx.to_scipy_sparse_array,
            nx.from_scipy_sparse_array,
            nx.to_scipy_sparse_array,
        ),
    ):
        back = decode(encode(g))
        # the edge SET survives, not merely its size
        assert _edges(back) == _edges(g)
        # and so does every weight
        for u, v, w in g.edges(data="weight"):
            assert back[u][v]["weight"] == w
        # and the decoded graph matches networkx's own round-trip, in order
        nx_back = nx_decode(nx_encode(ng))
        assert list(back.nodes()) == list(nx_back.nodes())
        assert list(back.edges()) == list(nx_back.edges())


@pytest.mark.parametrize("seed", range(30))
def test_dict_roundtrip_preserves_iteration_order(seed):
    """br-r37-c1-ud0lj: the dict round-trips compare ``sorted(...)`` node lists
    and a sorted edge set, so a codec that permuted node or edge order would
    pass. Order survives both dict round-trips exactly; locked here.
    """
    g, _ = _random_weighted(seed)
    dod = fnx.from_dict_of_dicts(fnx.to_dict_of_dicts(g))
    assert list(dod.nodes()) == list(g.nodes())
    assert list(dod.edges()) == list(g.edges())
    dol = fnx.from_dict_of_lists(fnx.to_dict_of_lists(g))
    assert list(dol.nodes()) == list(g.nodes())


@pytest.mark.parametrize("seed", range(30))
def test_pandas_edgelist_matches_networkx(seed):
    """br-r37-c1-ud0lj: nothing compared the DataFrame itself, or the decoded
    graph, against networkx — only against the source graph.

    Note the round-trip legitimately DROPS isolated nodes (an edgelist cannot
    carry them): on 6 of these 30 seeds the decoded graph has fewer nodes than
    the source. Both libraries do that identically, which is why the comparison
    here is fnx-vs-nx rather than round-trip-vs-source.
    """
    g, n = _random_weighted(seed)
    ng = _nx_twin(g, n)

    fdf = fnx.to_pandas_edgelist(g)
    ndf = nx.to_pandas_edgelist(ng)
    assert list(fdf.columns) == list(ndf.columns)
    assert fdf.equals(ndf)

    fback = fnx.from_pandas_edgelist(fdf, edge_attr="weight")
    nback = nx.from_pandas_edgelist(ndf, edge_attr="weight")
    assert list(fback.nodes()) == list(nback.nodes())
    assert list(fback.edges()) == list(nback.edges())
