"""Differential + metamorphic parity for the clique algorithm family.

Covers ``find_cliques`` (maximal cliques, Bron-Kerbosch),
``enumerate_all_cliques`` (every clique), ``node_clique_number``,
``number_of_cliques`` and ``make_max_clique_graph``. The family had only
scattered coverage.

This locks fnx against the real upstream networkx with:

* differential parity (order-invariant set/dict comparison) across
  random graphs,
* metamorphic invariants independent of the reference — every
  ``find_cliques`` output is an actual complete subgraph, and the largest
  ``node_clique_number`` equals the largest maximal-clique size, and
* hand-computed goldens on complete, path, and cycle graphs.

br-r37-c1-han3d
"""

from __future__ import annotations

import importlib
import random
import sys

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, p=0.45):
    rng = random.Random(seed)
    n = rng.randint(5, 11)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng, n


def _clique_set(cliques):
    return {frozenset(c) for c in cliques}


def test_clique_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.clique")
    expected = importlib.import_module("networkx.algorithms.clique")

    assert set(module.__all__) == set(expected.__all__)


# ---------------------------------------------------------------------------
# Differential parity.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(50))
def test_find_cliques_matches_networkx(seed):
    fg, ng, _ = _pair(seed)
    assert _clique_set(fnx.find_cliques(fg)) == _clique_set(nx.find_cliques(ng))


@pytest.mark.parametrize("seed", range(50))
def test_enumerate_all_cliques_matches_networkx(seed):
    fg, ng, _ = _pair(seed)
    assert _clique_set(fnx.enumerate_all_cliques(fg)) == _clique_set(
        nx.enumerate_all_cliques(ng)
    )


@pytest.mark.skipif(sys.platform != "linux", reason="memory bound requires Linux /proc")
def test_enumerate_all_cliques_yields_bounded_prefix_of_dense_graph():
    import subprocess
    import textwrap

    # A complete 32-node graph has billions of cliques, but a caller may only
    # request its first few. Bound the child so an eager implementation cannot
    # exhaust the test runner while trying to materialize the entire result.
    script = textwrap.dedent(
        """
        from itertools import islice
        from pathlib import Path
        import os
        import resource

        import franken_networkx as fnx
        import networkx as nx

        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        vm_pages = int(Path("/proc/self/statm").read_text().split()[0])
        memory_limit = vm_pages * os.sysconf("SC_PAGE_SIZE") + 256 * 1024 * 1024
        _, hard_limit = resource.getrlimit(resource.RLIMIT_AS)
        if hard_limit != resource.RLIM_INFINITY:
            memory_limit = min(memory_limit, hard_limit)
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit, hard_limit))

        expected = list(islice(nx.enumerate_all_cliques(nx.complete_graph(32)), 40))
        actual = list(islice(fnx.enumerate_all_cliques(fnx.complete_graph(32)), 40))
        assert actual == expected
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("cls", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("seed", range(8))
def test_enumerate_all_cliques_preserves_order_with_mixed_labels(cls, seed):
    rng = random.Random(seed)
    labels = [0, 1024, "a", "b", (1, "x"), (2, "y"), -4096, "isolated"]
    rng.shuffle(labels)
    edges = [
        (u, v)
        for index, u in enumerate(labels)
        for v in labels[index + 1:]
        if rng.random() < 0.5
    ]
    fg, ng = getattr(fnx, cls)(), getattr(nx, cls)()
    for graph in (fg, ng):
        graph.add_nodes_from(labels)
        graph.add_edges_from(edges)
        graph.add_edge(labels[0], labels[0])
        graph.remove_node(labels[2])
        graph.add_edge(labels[2], labels[-1])
        if edges:
            graph.add_edge(*edges[-1])

    assert list(fnx.enumerate_all_cliques(fg)) == list(nx.enumerate_all_cliques(ng))


@pytest.mark.parametrize("cls", ["Graph", "MultiGraph"])
def test_enumerate_all_cliques_keeps_snapshot_after_first_yield(cls):
    a, b, c, d, new = (object() for _ in range(5))
    edges = [(a, b), (b, c), (c, a), (c, d)]
    fg, ng = getattr(fnx, cls)(edges), getattr(nx, cls)(edges)
    actual = fnx.enumerate_all_cliques(fg)
    expected = nx.enumerate_all_cliques(ng)
    assert next(actual) == next(expected)
    for graph in (fg, ng):
        graph.clear()
        graph.add_edge(a, new)
    assert list(actual) == list(expected)


@pytest.mark.parametrize("cls", ["Graph", "MultiGraph"])
def test_enumerate_all_cliques_native_iterator_owns_keys_and_preserves_collector(cls):
    class Label(str):
        pass

    a, b = Label("a"), Label("b")
    graph = getattr(fnx, cls)([(a, b)])
    expected = [[a], [b], [a, b]]
    collected = fnx._fnx.enumerate_all_cliques(graph)
    assert isinstance(collected, list)
    assert collected == expected

    iterator = fnx._fnx.enumerate_all_cliques_iter(graph)
    assert iter(iterator) is iterator
    graph.clear()
    actual = list(iterator)
    assert actual == expected
    for clique, wanted in zip(actual, expected, strict=True):
        assert all(node is original for node, original in zip(clique, wanted, strict=True))
    assert next(iterator, None) is None
    assert next(iterator, None) is None


def test_enumerate_all_cliques_native_iterator_empty_snapshot_stays_empty():
    graph = fnx.Graph()
    iterator = fnx._fnx.enumerate_all_cliques_iter(graph)
    graph.add_edge("later", "node")
    assert next(iterator, None) is None
    assert next(iterator, None) is None


def test_enumerate_all_cliques_native_iterator_collects_node_reference_cycle():
    import gc
    import weakref

    class Label(str):
        pass

    node = Label("cycle-node")
    graph = fnx.Graph([(node, "other")])
    iterator = fnx._fnx.enumerate_all_cliques_iter(graph)
    yielded = next(iterator)
    assert yielded[0] is node
    del yielded
    node.iterator = iterator
    reference = weakref.ref(node)
    del node, graph, iterator
    gc.collect()
    assert reference() is None


@pytest.mark.parametrize("seed", range(50))
def test_node_and_number_of_cliques_match_networkx(seed):
    fg, ng, _ = _pair(seed)
    assert fnx.node_clique_number(fg) == nx.node_clique_number(ng)
    assert fnx.number_of_cliques(fg) == nx.number_of_cliques(ng)


@pytest.mark.parametrize("seed", range(40))
def test_make_max_clique_graph_matches_networkx(seed):
    fg, ng, _ = _pair(seed)
    fm = fnx.make_max_clique_graph(fg)
    nm = nx.make_max_clique_graph(ng)
    assert fm.number_of_nodes() == nm.number_of_nodes()
    assert fm.number_of_edges() == nm.number_of_edges()


# ---------------------------------------------------------------------------
# Metamorphic invariants.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(50))
def test_find_cliques_yields_complete_subgraphs(seed):
    fg, _, _ = _pair(seed)
    for clique in fnx.find_cliques(fg):
        members = list(clique)
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                assert fg.has_edge(members[i], members[j]), (
                    f"seed={seed}: find_cliques returned a non-clique"
                )


@pytest.mark.parametrize("seed", range(50))
def test_node_clique_number_consistent_with_max_clique(seed):
    fg, _, _ = _pair(seed)
    cliques = list(fnx.find_cliques(fg))
    if not cliques:
        pytest.skip("empty graph")
    max_clique_size = max(len(c) for c in cliques)
    assert max(fnx.node_clique_number(fg).values()) == max_clique_size


# ---------------------------------------------------------------------------
# Hand-computed goldens.
# ---------------------------------------------------------------------------


def test_complete_graph_golden():
    k5 = fnx.complete_graph(5)
    cliques = list(fnx.find_cliques(k5))
    assert len(cliques) == 1
    assert set(cliques[0]) == {0, 1, 2, 3, 4}
    assert max(fnx.node_clique_number(k5).values()) == 5


def test_path_and_cycle_goldens():
    # A path's maximal cliques are its edges.
    p4 = fnx.path_graph(4)
    assert _clique_set(fnx.find_cliques(p4)) == {
        frozenset({0, 1}), frozenset({1, 2}), frozenset({2, 3})
    }
    # A 4-cycle's maximal cliques are its edges too (no triangle).
    c4 = fnx.cycle_graph(4)
    assert all(len(c) == 2 for c in fnx.find_cliques(c4))
