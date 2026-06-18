"""Conformance guard for gutman_index / schultz_index native-kernel routing.

br-r37-c1-distidx routes the weight=None path of gutman_index and schultz_index to
the byte-exact native kernels (_fnx.gutman_index_rust / schultz_index_rust),
replacing an all-pairs shortest_path_length dict materialization + an O(V^2)
Python double-loop. This locks the full contract vs networkx so the routing stays
byte-exact:

  * connected simple graphs: value matches nx (weight=None);
  * weighted path still matches nx;
  * disconnected -> inf; multigraph/directed -> NetworkXNotImplemented.

No mocks: real fnx vs real networkx.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


@pytest.mark.parametrize("fn", ["gutman_index", "schultz_index"])
@pytest.mark.parametrize("seed", range(25))
def test_unweighted_matches_networkx(fn, seed):
    r = random.Random(seed)
    n = r.randint(5, 12)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.5]
    fg = fnx.Graph(list(edges))
    ng = nx.Graph(list(edges))
    ffn, nfn = getattr(fnx, fn), getattr(nx, fn)
    if not nx.is_connected(ng):
        assert ffn(fg) == float("inf")
    else:
        assert ffn(fg) == pytest.approx(nfn(ng))


@pytest.mark.parametrize("fn", ["gutman_index", "schultz_index"])
@pytest.mark.parametrize("seed", range(10))
def test_weighted_matches_networkx(fn, seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    fg, ng = fnx.Graph(), nx.Graph()
    fg.add_nodes_from(range(n)); ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if r.random() < 0.6:
                w = r.randint(1, 9)
                fg.add_edge(u, v, weight=w); ng.add_edge(u, v, weight=w)
    if not nx.is_connected(ng):
        pytest.skip("disconnected")
    ffn, nfn = getattr(fnx, fn), getattr(nx, fn)
    assert ffn(fg, weight="weight") == pytest.approx(nfn(ng, weight="weight"))


@pytest.mark.parametrize("fn", ["gutman_index", "schultz_index"])
def test_multigraph_directed_rejected(fn):
    ffn = getattr(fnx, fn)
    with pytest.raises(fnx.NetworkXNotImplemented):
        ffn(fnx.MultiGraph([(0, 1), (1, 2)]))
    with pytest.raises(fnx.NetworkXNotImplemented):
        ffn(fnx.DiGraph([(0, 1), (1, 2)]))
