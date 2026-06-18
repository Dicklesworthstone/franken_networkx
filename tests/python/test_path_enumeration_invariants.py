"""Oracle-free path-enumeration invariants.

* every ``all_simple_paths`` result is a valid simple path (distinct nodes,
  real edges, correct endpoints)
* ``has_path(s, t)`` is True iff at least one simple path exists
* ``shortest_path`` is a valid path no longer than any simple path
* ``all_simple_paths`` is monotonic in ``cutoff`` (paths at cutoff k are a
  subset of paths at cutoff k+1)
* relabeling nodes relabels every generated path in lockstep
* relabeling nodes relabels every generated edge path in lockstep
* relabeling nodes preserves path predicates

br-r37-c1-6btnh
br-r37-c1-grld5
br-r37-c1-vn4yh
br-r37-c1-q2c7r
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _graph(seed, directed=False, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(5, 9)
    g = (fnx.DiGraph if directed else fnx.Graph)()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u == v:
                continue
            if (directed or u < v) and rng.random() < p:
                g.add_edge(u, v)
    return g, n


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_path_enumeration_self_consistency(directed, seed):
    g, n = _graph(seed, directed=directed)
    for s in range(min(3, n)):
        for t in range(n):
            if s == t:
                continue
            paths = list(fnx.all_simple_paths(g, s, t))
            for p in paths:
                assert len(set(p)) == len(p)            # simple (no repeats)
                assert p[0] == s and p[-1] == t          # correct endpoints
                assert all(g.has_edge(p[i], p[i + 1]) for i in range(len(p) - 1))
            # has_path iff at least one simple path exists.
            assert fnx.has_path(g, s, t) == (len(paths) > 0)
            if paths:
                sp = fnx.shortest_path(g, s, t)
                assert all(g.has_edge(sp[i], sp[i + 1]) for i in range(len(sp) - 1))
                # Shortest path is no longer than any simple path.
                assert len(sp) - 1 <= min(len(p) - 1 for p in paths)


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_all_simple_paths_cutoff_monotonic(directed, seed):
    g, n = _graph(seed, directed=directed)
    for s in range(min(2, n)):
        for t in range(n):
            if s == t:
                continue
            lo = {tuple(p) for p in fnx.all_simple_paths(g, s, t, cutoff=2)}
            hi = {tuple(p) for p in fnx.all_simple_paths(g, s, t, cutoff=3)}
            assert lo <= hi


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_all_simple_paths_relabeling_equivariant(directed, seed):
    g, n = _graph(seed, directed=directed)
    mapping = {node: f"path-node-{seed}-{node}" for node in range(n)}
    relabelled = fnx.relabel_nodes(g, mapping)
    source = 0

    for target in range(1, min(n, 5)):
        base_paths = list(fnx.all_simple_paths(g, source, target, cutoff=4))
        relabelled_paths = list(
            fnx.all_simple_paths(
                relabelled, mapping[source], mapping[target], cutoff=4
            )
        )
        expected = [
            [mapping[node] for node in path]
            for path in base_paths
        ]

        assert relabelled_paths == expected


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_all_simple_edge_paths_relabeling_equivariant(directed, seed):
    g, n = _graph(seed, directed=directed)
    mapping = {node: f"edge-path-node-{seed}-{node}" for node in range(n)}
    relabelled = fnx.relabel_nodes(g, mapping)
    source = 0

    for target in range(1, min(n, 5)):
        base_paths = list(fnx.all_simple_edge_paths(g, source, target, cutoff=4))
        relabelled_paths = list(
            fnx.all_simple_edge_paths(
                relabelled, mapping[source], mapping[target], cutoff=4
            )
        )
        expected = [
            [(mapping[u], mapping[v]) for u, v in path]
            for path in base_paths
        ]

        assert relabelled_paths == expected


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_path_predicates_relabeling_invariant(directed, seed):
    g, n = _graph(seed, directed=directed)
    mapping = {node: f"predicate-node-{seed}-{node}" for node in range(n)}
    relabelled = fnx.relabel_nodes(g, mapping)
    source = 0

    for target in range(n):
        has_base = fnx.has_path(g, source, target)
        assert fnx.has_path(relabelled, mapping[source], mapping[target]) == has_base
        if has_base:
            path = fnx.shortest_path(g, source, target)
            mapped_path = [mapping[node] for node in path]
            assert fnx.is_simple_path(g, path)
            assert fnx.is_simple_path(relabelled, mapped_path)
