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


def _make_directed_pair(multigraph):
    if multigraph:
        gf, gn = fnx.MultiDiGraph(), nx.MultiDiGraph()
        for idx, (u, v) in enumerate(
            [(0, 1), (1, 2), (2, 0), (1, 3), (3, 1), (2, 4), (4, 2)]
        ):
            key = f"k{idx % 3}"
            gf.add_edge(u, v, key=key)
            gn.add_edge(u, v, key=key)
        return gf, gn
    edges = [(0, 1), (1, 2), (2, 0), (1, 3), (3, 1), (2, 4), (4, 2)]
    return fnx.DiGraph(edges), nx.DiGraph(edges)


def _repr_edges(edges):
    return [tuple(repr(item) for item in edge) for edge in edges]


@pytest.mark.parametrize("multigraph", [False, True])
@pytest.mark.parametrize("orientation", [None, "original", "reverse", "ignore"])
def test_directed_edge_dfs_and_find_cycle_order_contract(multigraph, orientation):
    gf, gn = _make_directed_pair(multigraph)
    assert _repr_edges(fnx.edge_dfs(gf, orientation=orientation)) == _repr_edges(
        nx.edge_dfs(gn, orientation=orientation)
    )
    assert _repr_edges(fnx.find_cycle(gf, orientation=orientation)) == _repr_edges(
        nx.find_cycle(gn, orientation=orientation)
    )


def test_directed_find_cycle_avoids_fnx_to_nx_conversion(monkeypatch):
    import franken_networkx.backend as backend

    def fail_conversion(_graph):
        raise AssertionError("directed find_cycle must not convert the whole graph")

    monkeypatch.setattr(backend, "_fnx_to_nx", fail_conversion)
    graph = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3)])
    assert list(fnx.find_cycle(graph)) == [(0, 1), (1, 2), (2, 0)]
