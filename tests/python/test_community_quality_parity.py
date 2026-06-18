"""Differential + golden parity for community partition-quality metrics.

The deterministic community-quality functions — ``modularity``,
``partition_quality`` (returns ``(coverage, performance)``) and
``is_partition`` — score a *given* partition rather than discovering one,
so unlike the randomized detection algorithms they admit exact
differential testing against upstream networkx. ``partition_quality`` and
``is_partition`` had no dedicated test file, and ``modularity``'s
directed / weighted / ``resolution`` paths were thinly covered.

This locks fnx against the real upstream library across random graphs and
partitions, plus the ``NotAPartition`` error contract and ``is_partition``
goldens.

br-r37-c1-xk7jh
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx
from franken_networkx.algorithms.community import (
    modularity as fnx_modularity,
    partition_quality as fnx_partition_quality,
    is_partition as fnx_is_partition,
)
from networkx.algorithms.community import (
    modularity as nx_modularity,
    partition_quality as nx_partition_quality,
    is_partition as nx_is_partition,
)
from networkx.algorithms.community.quality import NotAPartition


def _pair(seed, directed=False, weighted=False, p=0.3):
    rng = random.Random(seed)
    n = rng.randint(6, 14)
    fnx_cls, nx_cls = (
        (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    )
    fg = fnx_cls()
    ng = nx_cls()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u == v:
                continue
            if (directed or u < v) and rng.random() < p:
                if weighted:
                    w = round(rng.uniform(1, 5), 2)
                    fg.add_edge(u, v, weight=w)
                    ng.add_edge(u, v, weight=w)
                else:
                    fg.add_edge(u, v)
                    ng.add_edge(u, v)
    k = rng.randint(2, 3)
    buckets = [set() for _ in range(k)]
    for node in range(n):
        buckets[rng.randint(0, k - 1)].add(node)
    partition = [c for c in buckets if c]
    return fg, ng, partition


# ---------------------------------------------------------------------------
# modularity.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_modularity_matches_networkx(directed, weighted, seed):
    fg, ng, partition = _pair(seed, directed=directed, weighted=weighted)
    kwargs = {"weight": "weight"} if weighted else {}
    fm = fnx_modularity(fg, partition, **kwargs)
    nm = nx_modularity(ng, partition, **kwargs)
    assert fm == pytest.approx(nm, abs=1e-9), f"seed={seed} dir={directed} w={weighted}"


@pytest.mark.parametrize("resolution", [0.5, 1.0, 1.5, 2.0])
@pytest.mark.parametrize("seed", range(30))
def test_modularity_resolution_matches_networkx(resolution, seed):
    fg, ng, partition = _pair(seed)
    fm = fnx_modularity(fg, partition, resolution=resolution)
    nm = nx_modularity(ng, partition, resolution=resolution)
    assert fm == pytest.approx(nm, abs=1e-9), f"seed={seed} res={resolution}"


# ---------------------------------------------------------------------------
# partition_quality (coverage, performance).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_partition_quality_matches_networkx(directed, seed):
    fg, ng, partition = _pair(seed, directed=directed)
    fcov, fperf = fnx_partition_quality(fg, partition)
    ncov, nperf = nx_partition_quality(ng, partition)
    assert fcov == pytest.approx(ncov, abs=1e-9)
    assert fperf == pytest.approx(nperf, abs=1e-9)


# ---------------------------------------------------------------------------
# is_partition.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(40))
def test_is_partition_matches_networkx(seed):
    fg, ng, partition = _pair(seed)
    assert fnx_is_partition(fg, partition) == nx_is_partition(ng, partition)


def test_is_partition_goldens():
    g = fnx.Graph([(0, 1), (1, 2), (2, 3)])
    assert fnx_is_partition(g, [{0, 1}, {2, 3}])
    assert fnx_is_partition(g, [{0, 1, 2, 3}])
    # overlapping communities are not a partition.
    assert not fnx_is_partition(g, [{0, 1}, {1, 2, 3}])
    # missing a node is not a partition.
    assert not fnx_is_partition(g, [{0, 1}])


# ---------------------------------------------------------------------------
# Error contract: scoring an invalid partition raises NotAPartition.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "partition",
    [
        [{0, 1}, {1, 2, 3}],   # overlapping
        [{0, 1}],              # missing nodes
        [{0, 1}, {2, 3, 9}],   # extraneous node
    ],
)
def test_modularity_rejects_invalid_partition_like_networkx(partition):
    fg = fnx.Graph([(0, 1), (1, 2), (2, 3)])
    ng = nx.Graph([(0, 1), (1, 2), (2, 3)])
    with pytest.raises(NotAPartition):
        fnx_modularity(fg, partition)
    with pytest.raises(NotAPartition):
        nx_modularity(ng, partition)
