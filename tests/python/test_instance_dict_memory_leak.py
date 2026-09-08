"""Regression test for PyO3 instance dictionary leak (br-r37-c1-839yx).

Verifies that Graph, DiGraph, MultiGraph, and MultiDiGraph do not leak their
CPython instance dictionaries (__dict__) or view caches on deallocation or
during cyclic garbage collection.
"""

import copy
import gc
import os
import sys
import pytest
import franken_networkx as fnx


def _get_rss_mb() -> float:
    """Read VmRSS from /proc/self/status or fallback to resource."""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024.0
    except (OSError, ValueError, IndexError):
        pass
    import resource
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0


@pytest.mark.parametrize("graph_cls", [fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph])
def test_graph_instance_dict_deallocation_zero_leaks(graph_cls):
    """Creating and dropping graph instances must not leak empty or populated instance dicts."""
    gc.collect()
    gc.collect()
    before_dicts = set(id(obj) for obj in gc.get_objects() if isinstance(obj, dict))

    for _ in range(500):
        g = graph_cls()
        g.add_edge("u", "v", weight=42.0)
        _ = g.adj
        _ = vars(g)

    del g
    gc.collect()
    gc.collect()

    after_dicts = [
        obj for obj in gc.get_objects()
        if isinstance(obj, dict) and id(obj) not in before_dicts
    ]
    # Allow at most small constant overhead for one-off interned keys/test frames, but zero per-graph leak
    assert len(after_dicts) <= 10, f"Leaked {len(after_dicts)} dicts for {graph_cls.__name__}"


def test_tight_loop_rss_stays_flat():
    """10,000 graph allocations must maintain a flat memory RSS profile."""
    # Warmup
    for _ in range(1000):
        g = fnx.Graph()
        g.add_edge(1, 2)
        _ = vars(g)
    del g
    gc.collect()

    start_rss = _get_rss_mb()

    for _ in range(10000):
        g = fnx.Graph()
        g.add_edge(1, 2)
        _ = vars(g)
    del g
    gc.collect()

    end_rss = _get_rss_mb()
    rss_growth_mb = end_rss - start_rss
    assert rss_growth_mb < 20.0, f"RSS grew by {rss_growth_mb:.2f} MB across 10,000 graphs"


def test_cyclic_references_are_garbage_collected():
    """Graphs involved in reference cycles must be fully reclaimed by cyclic GC."""
    gc.collect()
    before_graphs = [obj for obj in gc.get_objects() if isinstance(obj, fnx.Graph)]

    def make_cycle():
        g = fnx.Graph()
        g.add_edge("a", "b")
        g.graph["self"] = g
        g.graph["adj"] = g.adj
        vars(g)["cycle"] = g

    for _ in range(200):
        make_cycle()

    gc.collect()
    gc.collect()

    after_graphs = [obj for obj in gc.get_objects() if isinstance(obj, fnx.Graph)]
    surviving = len(after_graphs) - len(before_graphs)
    assert surviving == 0, f"{surviving} cyclic graphs survived garbage collection"


def test_shallow_copy_deallocation_zero_leaks():
    """copy.copy(G) must not leak instance dicts on deallocation."""
    gc.collect()
    before_dicts = set(id(obj) for obj in gc.get_objects() if isinstance(obj, dict))

    for _ in range(500):
        g = fnx.Graph()
        g.add_node("n")
        h = copy.copy(g)
        _ = h.adj
        _ = vars(h)

    del g, h
    gc.collect()
    gc.collect()

    after_dicts = [
        obj for obj in gc.get_objects()
        if isinstance(obj, dict) and id(obj) not in before_dicts
    ]
    assert len(after_dicts) <= 10, f"Leaked {len(after_dicts)} dicts during copy.copy"
