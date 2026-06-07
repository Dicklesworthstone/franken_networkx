"""br-r37-c1-lextopo: lexicographical_topological_sort's default
tie-break is the NODE ITSELF (identity), not str(node). Integer nodes
must order numerically (2 before 10), not lexicographically.
"""
import random

import networkx as nx
import pytest

import franken_networkx as fnx


def test_integer_nodes_numeric_order():
    g = fnx.DiGraph([(0, 2), (0, 10), (1, 2), (10, 3)])
    gn = nx.DiGraph([(0, 2), (0, 10), (1, 2), (10, 3)])
    assert list(fnx.lexicographical_topological_sort(g)) == list(
        nx.lexicographical_topological_sort(gn)
    )


def test_random_int_dag_corpus():
    rnd = random.Random(11)
    for trial in range(15):
        de = sorted({(u, v) for u, v in ((rnd.randrange(20), rnd.randrange(20)) for _ in range(60)) if u < v})
        gf, gn = fnx.DiGraph(), nx.DiGraph()
        for u, v in de:
            gf.add_edge(u, v)
            gn.add_edge(u, v)
        assert [repr(n) for n in fnx.lexicographical_topological_sort(gf)] == [
            repr(n) for n in nx.lexicographical_topological_sort(gn)
        ], trial


def test_custom_key_matches():
    gf = fnx.DiGraph([(0, 3), (1, 3), (2, 3)])
    gn = nx.DiGraph([(0, 3), (1, 3), (2, 3)])
    assert list(fnx.lexicographical_topological_sort(gf, key=lambda x: -x)) == list(
        nx.lexicographical_topological_sort(gn, key=lambda x: -x)
    )


def test_mixed_type_simultaneous_raises_like_nx():
    gf, gx = fnx.DiGraph(), nx.DiGraph()
    for g in (gf, gx):
        g.add_node(1)
        g.add_node("a")

    def attempt(g, mod):
        try:
            list(mod.lexicographical_topological_sort(g))
            return "ok"
        except TypeError:
            return "TypeError"

    assert attempt(gf, fnx) == attempt(gx, nx)


def test_string_nodes_match():
    gf, gn = fnx.DiGraph(), nx.DiGraph()
    for e in [("b", "d"), ("a", "d"), ("c", "a")]:
        gf.add_edge(*e)
        gn.add_edge(*e)
    assert list(fnx.lexicographical_topological_sort(gf)) == list(
        nx.lexicographical_topological_sort(gn)
    )
