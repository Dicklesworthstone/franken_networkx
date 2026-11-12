"""Generator-function exception timing for not-implemented graph types.

Most generator functions decorated ``@not_implemented_for`` raise on CALL in
both fnx and networkx. ``chordal_graph_cliques`` is the lone exception: networkx
defers the check to first iteration, while fnx raises eagerly on call. Both
raise the SAME ``NetworkXNotImplemented`` under the universal ``list(gen)``
usage, so the difference only surfaces if a caller creates the generator and
never iterates — an extremely rare pattern where fnx's fail-fast is, if
anything, preferable. This is a deliberate benign divergence, pinned here so it
is documented rather than mistaken for an undiscovered bug.

No mocks: real fnx and real networkx on a directed graph (chordal/clique
functions are undirected-only).
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx

_DIGRAPH_EDGES = [(0, 1), (1, 2), (2, 0)]

# Generator functions that raise on CALL in BOTH libraries (parity).
_EAGER_BOTH = [
    "find_cliques",
    "enumerate_all_cliques",
    "connected_components",
    "biconnected_components",
    "articulation_points",
]


@pytest.mark.parametrize("name", _EAGER_BOTH)
def test_generator_raises_on_call_in_both(name):
    fd = fnx.DiGraph(_DIGRAPH_EDGES)
    nd = nx.DiGraph(_DIGRAPH_EDGES)
    with pytest.raises(nx.NetworkXNotImplemented):
        getattr(fnx, name)(fd)
    with pytest.raises(nx.NetworkXNotImplemented):
        getattr(nx, name)(nd)


def test_chordal_graph_cliques_same_exception_when_iterated():
    # The benign timing difference: fnx eager, nx lazy — but iterating both
    # yields the identical NetworkXNotImplemented, which is what real code hits.
    fd = fnx.DiGraph(_DIGRAPH_EDGES)
    nd = nx.DiGraph(_DIGRAPH_EDGES)
    with pytest.raises(nx.NetworkXNotImplemented):
        list(fnx.chordal_graph_cliques(fd))
    with pytest.raises(nx.NetworkXNotImplemented):
        list(nx.chordal_graph_cliques(nd))
    # fnx fail-fast: raises on call too (documented, intentional).
    with pytest.raises(nx.NetworkXNotImplemented):
        fnx.chordal_graph_cliques(fd)


def test_directed_find_cycle_allowed_in_both():
    # find_cycle IS implemented for directed graphs — both succeed.
    fd = fnx.DiGraph(_DIGRAPH_EDGES)
    nd = nx.DiGraph(_DIGRAPH_EDGES)
    assert bool(list(fnx.find_cycle(fd))) == bool(list(nx.find_cycle(nd)))
