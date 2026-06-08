"""br-r37-c1-vbwpl: remove_edge uses swap_remove (O(1)) not shift_remove
(O(|E|)), turning remove-edge-in-a-loop from O(k*|E|) into O(k). The
edges-map storage order changes, but all user-visible output orders off
adjacency, so results stay byte-for-byte equal to nx. This guards that
invariant across heavy interleaved add/remove on both simple classes.
"""
import random

import networkx as nx
import numpy as np
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_remove_edge_loop_parity(cls):
    rnd = random.Random(3)
    for trial in range(20):
        edges = [
            (u, v)
            for u, v in ((rnd.randrange(15), rnd.randrange(15)) for _ in range(rnd.randrange(5, 50)))
            if u != v
        ]
        gf, gn = getattr(fnx, cls)(edges), getattr(nx, cls)(edges)
        removed = [e for i, e in enumerate(list(gn.edges())) if i % 3 == 0]
        for e in removed:
            if gf.has_edge(*e):
                gf.remove_edge(*e)
                gn.remove_edge(*e)
        assert [repr(n) for n in gf] == [repr(n) for n in gn], trial
        assert [(repr(u), repr(v)) for u, v in gf.edges()] == [
            (repr(u), repr(v)) for u, v in gn.edges()
        ], trial
        assert {repr(n): [repr(k) for k in gf[n]] for n in gf} == {
            repr(n): [repr(k) for k in gn[n]] for n in gn
        }, trial


def test_remove_edge_then_scipy_matrix_unaffected():
    edges = [(0, 1), (1, 2), (2, 3), (0, 3), (1, 3), (0, 2)]
    gf, gn = fnx.Graph(edges), nx.Graph(edges)
    gf.remove_edge(0, 1)
    gn.remove_edge(0, 1)
    # storage order changed by swap_remove, but the matrix is identical
    assert (fnx.to_scipy_sparse_array(gf).toarray() == nx.to_scipy_sparse_array(gn).toarray()).all()
    assert (fnx.adjacency_matrix(gf).toarray() == nx.adjacency_matrix(gn).toarray()).all()
