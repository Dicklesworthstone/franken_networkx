"""br-r37-c1-fcdir: directed find_cycle now delegates to nx — the
native kernel checked successors for an on-stack target before
recursing, returning a valid but different DFS cycle than nx's
edge_dfs (the parity contract). nx's specific cycle is required for
drop-in compatibility.
"""
import random

import networkx as nx
import pytest

import franken_networkx as fnx


def test_known_divergence_case():
    R = random.Random(41)
    [(R.randrange(10), R.randrange(10)) for _ in range(28)]  # advance to probe's stream
    de = [(u, v) for u, v in ((R.randrange(10), R.randrange(10)) for _ in range(28)) if u != v]
    gf, gn = fnx.DiGraph(de), nx.DiGraph(de)
    assert [(repr(u), repr(v)) for u, v, *_ in fnx.find_cycle(gf)] == [
        (repr(u), repr(v)) for u, v, *_ in nx.find_cycle(gn)
    ]


def test_random_directed_corpus():
    rnd = random.Random(99)
    for trial in range(25):
        n = rnd.randrange(4, 14)
        de = [(u, v) for u, v in ((rnd.randrange(n), rnd.randrange(n)) for _ in range(rnd.randrange(4, 40))) if u != v]
        gf, gn = fnx.DiGraph(de), nx.DiGraph(de)

        def run(g, m):
            try:
                return [(repr(u), repr(v)) for u, v, *_ in m.find_cycle(g)]
            except Exception as e:  # noqa: BLE001
                return ("ERR", type(e).__name__)

        assert run(gf, fnx) == run(gn, nx), trial


@pytest.mark.parametrize("kw", [{"source": 1}, {"orientation": "reverse"}, {"orientation": "ignore"}])
def test_source_and_orientation(kw):
    gf = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3)])
    gn = nx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3)])
    assert [(repr(u), repr(v)) for u, v, *_ in fnx.find_cycle(gf, **kw)] == [
        (repr(u), repr(v)) for u, v, *_ in nx.find_cycle(gn, **kw)
    ]
