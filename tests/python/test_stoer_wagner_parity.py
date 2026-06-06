"""br-r37-c1-35oum: stoer_wagner must return nx's EXACT min-cut
partition, not just an equal cut value. Kernel mirrors nx's phases
(per-phase lazy-deletion heap with insertion-counter tie-breaks,
copy-order arbitrary_element, row-order contraction merges); the
set-order-dependent recovery tail runs in Python with real CPython
sets."""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _cmp(gn, gf):
    a, b = fnx.stoer_wagner(gf), nx.stoer_wagner(gn)
    assert (a[0], [repr(x) for x in a[1][0]], [repr(x) for x in a[1][1]]) == (
        b[0],
        [repr(x) for x in b[1][0]],
        [repr(x) for x in b[1][1]],
    )


def test_reaudit_repro_partition_exact():
    rnd = random.Random(7)
    gn, gf = nx.Graph(), fnx.Graph()
    for _ in range(40):
        u, v = rnd.randrange(12), rnd.randrange(12)
        if u != v:
            gn.add_edge(u, v, weight=1 + (u + v) % 3)
            gf.add_edge(u, v, weight=1 + (u + v) % 3)
    _cmp(gn, gf)


def test_docstring_example():
    gn, gf = nx.Graph(), fnx.Graph()
    for g in (gn, gf):
        g.add_edge("x", "a", weight=3)
        g.add_edge("x", "b", weight=1)
        g.add_edge("a", "c", weight=3)
        g.add_edge("b", "c", weight=5)
        g.add_edge("b", "d", weight=4)
        g.add_edge("d", "e", weight=2)
        g.add_edge("c", "y", weight=2)
        g.add_edge("e", "y", weight=3)
    _cmp(gn, gf)


@pytest.mark.parametrize("mode", range(4))
def test_tie_rich_corpus(mode):
    rnd = random.Random(41 + mode)
    done = 0
    for _ in range(40):
        gn, gf = nx.Graph(), fnx.Graph()
        n = rnd.randrange(4, 13)
        for i in range(rnd.randrange(n, n * 3)):
            u, v = rnd.randrange(n), rnd.randrange(n)
            if u == v:
                continue
            kw = {}
            if mode == 1:
                kw = {"weight": rnd.randrange(1, 4)}
            elif mode == 2:
                kw = {"weight": rnd.choice([0, 1, 1, 2])}
            elif mode == 3 and i % 2:
                kw = {"weight": 2}
            gn.add_edge(u, v, **kw)
            gf.add_edge(u, v, **kw)
        if gn.number_of_nodes() < 2 or not nx.is_connected(gn):
            continue
        _cmp(gn, gf)
        done += 1
    assert done > 5


def test_integral_cut_value_type():
    gn, gf = nx.Graph([(0, 1), (1, 2), (0, 2)]), fnx.Graph([(0, 1), (1, 2), (0, 2)])
    tn, tf = nx.stoer_wagner(gn)[0], fnx.stoer_wagner(gf)[0]
    assert type(tn) is type(tf) and tn == tf


def test_error_contracts():
    with pytest.raises(fnx.NetworkXError, match="negative-weighted"):
        fnx.stoer_wagner(fnx.Graph([(1, 2, {"weight": -1})]))
    with pytest.raises(fnx.NetworkXError, match="not connected"):
        fnx.stoer_wagner(fnx.Graph([(1, 2), (3, 4)]))
