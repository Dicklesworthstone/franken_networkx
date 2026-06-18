"""Community-detection parity + modularity invariants.

Modularity has a closed-form definition (so a given partition yields a fixed
value, matchable against networkx), partition_quality and is_partition are
deterministic, and greedy_modularity_communities is deterministic. This checks
parity plus modularity's structural invariants (a single all-nodes community
has modularity 0; modularity lies in [-1, 1]).

No mocks: real fnx and real networkx on random graphs + partitions.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx
import franken_networkx.algorithms.community as fcom
import networkx.algorithms.community as ncom


def _graph_and_partition(seed):
    r = random.Random(seed)
    n = r.randint(6, 12)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    k = r.randint(2, 3)
    parts = [set() for _ in range(k)]
    for node in range(n):
        parts[r.randrange(k)].add(node)
    parts = [p for p in parts if p]
    return fg, ng, n, parts


@pytest.mark.parametrize("seed", range(40))
def test_modularity_and_partition_quality_parity(seed):
    fg, ng, n, parts = _graph_and_partition(seed)
    if fg.number_of_edges() == 0:
        pytest.skip("no edges")
    assert round(fcom.modularity(fg, parts), 9) == round(ncom.modularity(ng, parts), 9)
    assert round(fcom.modularity(fg, parts, resolution=2.0), 9) == round(
        ncom.modularity(ng, parts, resolution=2.0), 9
    )
    fq = tuple(round(x, 9) for x in fcom.partition_quality(fg, parts))
    nq = tuple(round(x, 9) for x in ncom.partition_quality(ng, parts))
    assert fq == nq
    assert fcom.is_partition(fg, parts) == ncom.is_partition(ng, parts)


@pytest.mark.parametrize("seed", range(40))
def test_greedy_modularity_communities_parity(seed):
    fg, ng, n, parts = _graph_and_partition(seed)
    if fg.number_of_edges() == 0:
        pytest.skip("no edges")
    fc = sorted(sorted(c) for c in fcom.greedy_modularity_communities(fg))
    nc = sorted(sorted(c) for c in ncom.greedy_modularity_communities(ng))
    assert fc == nc


@pytest.mark.parametrize("seed", range(20))
def test_modularity_invariants(seed):
    fg, ng, n, parts = _graph_and_partition(seed)
    if fg.number_of_edges() == 0:
        pytest.skip("no edges")
    # The single all-nodes community has modularity exactly 0.
    single = [set(range(n))]
    assert abs(fcom.modularity(fg, single)) < 1e-9
    # Modularity of any valid partition is bounded in [-1, 1].
    q = fcom.modularity(fg, parts)
    assert -1.0 - 1e-9 <= q <= 1.0 + 1e-9
