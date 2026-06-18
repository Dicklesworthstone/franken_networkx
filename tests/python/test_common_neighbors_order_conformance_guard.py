"""Set conformance guard for common_neighbors (the link-prediction base).

common_neighbors underpins jaccard/AA/RA/CCPA/Soundarajan scoring. The swarm
optimized its raw path to integer adjacency-row intersection (ledger 9144). The
RESULT SET must match networkx exactly (the scorers sum over it, so the set — not
the iteration order — is what is contractual; fnx's intersection order differs
from nx's adjacency order, by design). This locks the set + the missing-node +
disjoint-neighborhood contracts (by value or same-exception parity).

No dedicated common_neighbors test existed. No mocks: real fnx vs real networkx.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


@pytest.mark.parametrize("seed", range(25))
def test_common_neighbors_set_matches_networkx(seed):
    r = random.Random(seed)
    n = r.randint(5, 12)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.45]
    fg = fnx.Graph(list(edges)); fg.add_nodes_from(range(n))
    ng = nx.Graph(list(edges)); ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            assert set(fnx.common_neighbors(fg, u, v)) == set(nx.common_neighbors(ng, u, v))


def test_common_neighbors_disjoint_and_missing():
    fg = fnx.Graph([(0, 1), (2, 3)]); fg.add_nodes_from(range(4))
    ng = nx.Graph([(0, 1), (2, 3)]); ng.add_nodes_from(range(4))
    # disjoint neighborhoods -> empty.
    assert set(fnx.common_neighbors(fg, 0, 2)) == set(nx.common_neighbors(ng, 0, 2))
    # missing node -> fnx must match nx's exception behavior.
    try:
        nr = list(nx.common_neighbors(ng, 0, 99))
    except Exception as ne:
        with pytest.raises(type(ne)):
            list(fnx.common_neighbors(fg, 0, 99))
    else:
        assert list(fnx.common_neighbors(fg, 0, 99)) == nr
