"""Randomized community-detection algorithms produce valid partitions.

louvain_communities, label_propagation_communities, and asyn_lpa_communities
are randomized (and greedy_modularity_communities is deterministic), so they are
validated by the PROPERTIES every community structure must satisfy rather than
by value parity:
  - the communities form a partition of the node set (disjoint and covering);
  - the modularity of any partition lies in [-1/2, 1].
These hold for whatever clustering the random run produces. (The modularity
formula itself is pinned separately in br-r37-c1-b9c1r.)

Two qualifications to "randomized, so no value parity". First, it is not true of
label_propagation_communities, which takes no seed and is fully deterministic —
it matches networkx exactly, so it is parity-tested here rather than only
property-checked. Second, the seeded algorithms are reproducible WITHIN a seed,
which is what makes every seeded assertion here meaningful, and that is pinned
too.

The partition predicate below is hand-rolled while the library ships its own
`is_partition`; both are asserted, so the helper cannot drift away from the
function it is standing in for.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import networkx as nx
import networkx.algorithms.community as ncom
import pytest
import franken_networkx as fnx
import franken_networkx.algorithms.community as fcom


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(8, 14)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.35]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g


def _is_partition(communities, nodes):
    seen = set()
    for c in communities:
        cs = set(c)
        if seen & cs:
            return False
        seen |= cs
    return seen == set(nodes)


_ALGORITHMS = [
    ("louvain", lambda g, s: fcom.louvain_communities(g, seed=s)),
    ("label_propagation", lambda g, s: list(fcom.label_propagation_communities(g))),
    ("asyn_lpa", lambda g, s: list(fcom.asyn_lpa_communities(g, seed=s))),
    ("greedy_modularity", lambda g, s: fcom.greedy_modularity_communities(g)),
]


@pytest.mark.parametrize("name,algo", _ALGORITHMS)
@pytest.mark.parametrize("seed", range(20))
def test_community_result_is_valid_partition(name, algo, seed):
    g = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    communities = algo(g, seed)
    assert _is_partition(communities, set(g.nodes()))
    # The library ships its own predicate; keep the local helper honest.
    assert fcom.is_partition(g, [set(c) for c in communities])
    # Every community is a nonempty set of THIS graph's nodes. An empty
    # community breaks neither disjointness nor covering, so _is_partition
    # accepts one.
    for community in communities:
        assert len(set(community)) > 0
        assert set(community) <= set(g.nodes())
    # Modularity of any valid partition is bounded.
    mod = fcom.modularity(g, communities)
    assert -0.5 - 1e-6 <= mod <= 1 + 1e-6


@pytest.mark.parametrize("seed", range(20))
def test_seeded_algorithms_are_reproducible(seed):
    """Randomized across seeds, exactly determined within one."""
    g = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    for name, algo in _ALGORITHMS:
        first = sorted(sorted(c) for c in algo(g, seed))
        second = sorted(sorted(c) for c in algo(g, seed))
        assert first == second, name


@pytest.mark.parametrize("seed", range(20))
def test_label_propagation_is_deterministic_and_matches_networkx(seed):
    """This one takes no seed and is NOT randomized, so value parity applies."""
    g = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    ng = nx.Graph(); ng.add_nodes_from(g.nodes()); ng.add_edges_from(g.edges())

    ours = sorted(sorted(c) for c in fcom.label_propagation_communities(g))
    theirs = sorted(sorted(c) for c in ncom.label_propagation_communities(ng))
    assert ours == theirs


def test_singleton_and_whole_graph_partitions_are_valid():
    # karate_club_graph is present, so the previous `hasattr` fallback to
    # complete_graph(6) was dead code that made this read as conditional.
    g = fnx.karate_club_graph()
    nodes = set(g.nodes())
    singletons = [{v} for v in g]
    whole = [set(g.nodes())]
    assert _is_partition(singletons, nodes)
    assert _is_partition(whole, nodes)
    # Singleton partition has modularity <= 0 (no intra-community edges).
    assert fcom.modularity(g, singletons) <= 1e-9
