"""Held keydicts must not make remove_node pay for keydicts it does not touch.

br-r37-c1-rc0923-epic-silent-wrong-answers-nro4w.5. The live key views of
2026-09-21 were scanned in full on every node removal, so a caller holding the
result of get_edge_data for every edge made remove_node O(#held): measured
2026-09-23 at 25.6k nodes, MultiGraph 83 -> 732 us and MultiDiGraph 232 -> 974
us per removal. Since vbneu.3 the keydicts live in a registry with a reverse
index by endpoint, so a removal touches only the keydicts incident to the
removed node.
"""

from __future__ import annotations

import gc
import time

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["MultiGraph", "MultiDiGraph"]


def _graph(cls_name, n):
    G = getattr(fnx, cls_name)()
    for i in range(n - 1):
        G.add_edge(i, i + 1)
        G.add_edge(i, i + 1)
    return G


@pytest.mark.parametrize("cls_name", CLASSES)
def test_removal_detaches_only_incident_keydicts(cls_name):
    G = _graph(cls_name, 40)
    held = {(u, v): G.get_edge_data(u, v) for u, v in G.edges()}
    G.remove_node(10)
    for (u, v), keydict in held.items():
        incident = 10 in (u, v)
        # networkx drops the adjacency entry and leaves the keys in place
        assert len(keydict) == 2
        assert (keydict._fnx_graph is None) is incident
        if not incident:
            assert G.get_edge_data(u, v) is keydict


def _removal_cost(cls_name, n, removals, held_count):
    # Remove from the TAIL: that removal is cheap in fnx, so any per-held-
    # keydict cost is what the timing sees (a head removal pays an O(V) shift).
    tail = range(n - 1, n - 1 - removals, -1)
    best = float("inf")
    for _ in range(5):
        G = _graph(cls_name, n)
        # keydicts for edges NOT incident to the removed tail
        edges = [(u, v) for u, v in G.edges() if v < n - 1 - removals][:held_count]
        held = [G.get_edge_data(u, v) for u, v in edges]
        # Collect first: otherwise a generation-2 pass over the thousands of
        # fresh keydicts lands inside the timed loop and reads as a held tax.
        gc.collect()
        start = time.perf_counter()
        for node in tail:
            G.remove_node(node)
        best = min(best, time.perf_counter() - start)
        del held
    return best


@pytest.mark.parametrize("cls_name", CLASSES)
def test_remove_node_cost_does_not_grow_with_held_keydicts(cls_name):
    """The SCALING is the contract: 200 vs ~19,000 held non-incident keydicts.
    The old per-removal scan over every held view grew linearly with the
    count (83 -> 732 us per removal at 25.6k nodes on 2026-09-23)."""
    n, removals = 20_000, 200
    few = _removal_cost(cls_name, n, removals, held_count=200)
    many = _removal_cost(cls_name, n, removals, held_count=19_000)
    assert many < 1.5 * few, (few, many)


def test_networkx_contract_the_guard_relies_on():
    """networkx keeps a held keydict's keys when a node is removed."""
    G = nx.MultiGraph()
    G.add_edge(0, 1)
    held = G.get_edge_data(0, 1)
    G.remove_node(1)
    assert dict(held) == {0: {}}
