"""Output stability for the index-based maximal_independent_set kernel.

Bead br-r37-c1-dxm71.

The native MIS binding peeled nodes with a HashSet<String> ``blocked`` and
cloned the whole remaining candidate list into a Python list every iteration to
feed ``random.choice`` — ~7x slower than nx. The kernel now runs on node
INDICES (Vec<bool> blocking, adjacency-by-index) and calls
``random._randbelow(len)`` directly (``random.choice(seq) == seq[_randbelow(
len(seq))]``), which keeps the exact RNG sequence while never materialising the
node list in Python.

This is a pure perf change: the chosen set + ordering must be byte-identical to
the previous behaviour. These tests pin the output deterministically per seed
and confirm the result really is a maximal independent set.
"""

from __future__ import annotations

import random

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _fbuild(g):
    f = fnx.Graph()
    for n in g.nodes():
        f.add_node(n)
    for u, v in g.edges():
        f.add_edge(u, v)
    return f


def _is_maximal_independent_set(g, mis):
    s = set(mis)
    # independent
    for u in s:
        for v in g.neighbors(u):
            assert v not in s, f"{u}-{v} both in MIS"
    # maximal: every non-set node has a neighbor in the set
    for n in g.nodes():
        if n not in s:
            assert any(nb in s for nb in g.neighbors(n)), f"{n} could be added"


@needs_nx
@pytest.mark.parametrize("seed", [None, 0, 1, 7, 42, -5, 123456789])
@pytest.mark.parametrize("gseed", list(range(15)))
def test_result_is_maximal_independent_set(seed, gseed):
    g = nx.gnm_random_graph(40, 80, seed=gseed)
    f = _fbuild(g)
    mis = fnx.maximal_independent_set(f, seed=seed)
    _is_maximal_independent_set(g, mis)


@needs_nx
def test_deterministic_per_seed():
    g = nx.gnm_random_graph(60, 150, seed=3)
    f = _fbuild(g)
    for seed in (0, 1, 99):
        a = fnx.maximal_independent_set(f, seed=seed)
        b = fnx.maximal_independent_set(f, seed=seed)
        assert a == b  # same order, same nodes


@needs_nx
def test_random_random_instance_accepted():
    # nx accepts a random.Random instance via @py_random_state; fnx mirrors it,
    # and the index path must use it for _randbelow.
    g = nx.gnm_random_graph(30, 60, seed=5)
    f = _fbuild(g)
    r1 = random.Random(11)
    r2 = random.Random(11)
    a = fnx.maximal_independent_set(f, seed=r1)
    b = fnx.maximal_independent_set(f, seed=r2)
    assert a == b
    _is_maximal_independent_set(g, a)


@needs_nx
def test_nodes_argument_and_errors():
    g = nx.Graph()
    g.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (0, 2)])
    f = _fbuild(g)
    mis = fnx.maximal_independent_set(f, nodes=[0, 3], seed=2)
    assert {0, 3}.issubset(set(mis))
    _is_maximal_independent_set(g, mis)
    # adjacent seed nodes -> NetworkXUnfeasible
    with pytest.raises(Exception) as e:
        fnx.maximal_independent_set(f, nodes=[0, 1])
    assert "independent set" in str(e.value)
    # node not in graph -> NetworkXUnfeasible
    with pytest.raises(Exception) as e2:
        fnx.maximal_independent_set(f, nodes=[99])
    assert "subset" in str(e2.value)


@needs_nx
def test_selfloop_unfeasible():
    f = fnx.Graph()
    f.add_edge(0, 0)
    f.add_edge(0, 1)
    with pytest.raises(Exception):
        fnx.maximal_independent_set(f, seed=3)
