"""Bipartite algorithm parity + projection validity invariant.

Beyond matching, the bipartite module has projection (projected_graph,
weighted_projected_graph), density, clustering, two-sided degrees, and
spectral_bipartivity. Projection has an oracle-free invariant: in the one-mode
projection onto the top set, two top nodes are adjacent iff they share a common
neighbor in the bottom set. This checks that invariant plus networkx parity.

No mocks: real fnx and real networkx on identically-built bipartite graphs.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx.algorithms import bipartite as fbp
from networkx.algorithms import bipartite as nbp


def _bipartite(seed):
    r = random.Random(seed)
    n1, n2 = r.randint(3, 5), r.randint(3, 5)
    top = list(range(n1))
    bot = list(range(n1, n1 + n2))
    edges = [(u, v) for u in top for v in bot if r.random() < 0.45]
    fg = fnx.Graph(); fg.add_nodes_from(top); fg.add_nodes_from(bot); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(top); ng.add_nodes_from(bot); ng.add_edges_from(edges)
    return fg, ng, top, bot, edges


@pytest.mark.parametrize("seed", range(30))
def test_projection_parity_and_validity(seed):
    fg, ng, top, bot, edges = _bipartite(seed)
    if not edges:
        pytest.skip("empty")

    fpr = fbp.projected_graph(fg, top)
    npr = nbp.projected_graph(ng, top)
    fe = sorted(tuple(sorted((u, v))) for u, v in fpr.edges())
    assert fe == sorted(tuple(sorted((u, v))) for u, v in npr.edges())

    # Validity: top u,w adjacent in projection iff they share a bottom neighbor.
    adj = {u: {v for v in bot if fg.has_edge(u, v)} for u in top}
    expected = sorted(
        (min(u, w), max(u, w))
        for i, u in enumerate(top) for w in top[i + 1:]
        if adj[u] & adj[w]
    )
    assert fe == expected


@pytest.mark.parametrize("seed", range(30))
def test_weighted_projection_and_density(seed):
    fg, ng, top, bot, edges = _bipartite(seed)
    if not edges:
        pytest.skip("empty")
    fwp = fbp.weighted_projected_graph(fg, top)
    nwp = nbp.weighted_projected_graph(ng, top)
    fw = {tuple(sorted((u, v))): d["weight"] for u, v, d in fwp.edges(data=True)}
    nw = {tuple(sorted((u, v))): d["weight"] for u, v, d in nwp.edges(data=True)}
    assert fw == nw
    assert round(fbp.density(fg, top), 6) == round(nbp.density(ng, top), 6)


@pytest.mark.parametrize("seed", range(30))
def test_clustering_degrees_spectral(seed):
    fg, ng, top, bot, edges = _bipartite(seed)
    if not edges:
        pytest.skip("empty")
    fc = {k: round(v, 6) for k, v in fbp.clustering(fg).items()}
    nc = {k: round(v, 6) for k, v in nbp.clustering(ng).items()}
    assert fc == nc
    fd, fdd = fbp.degrees(fg, bot)
    nd, ndd = nbp.degrees(ng, bot)
    assert dict(fd) == dict(nd) and dict(fdd) == dict(ndd)
    assert round(fbp.spectral_bipartivity(fg), 5) == round(
        nbp.spectral_bipartivity(ng), 5
    )
