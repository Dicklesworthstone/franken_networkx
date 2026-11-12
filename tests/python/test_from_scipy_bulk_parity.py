"""br-r37-c1-scipybulk: from_scipy_sparse_array's simple-graph bulk
path (routes COO triples through add_edges_from) must stay
byte-identical to nx — across graph types, float/int dtype,
edge_attribute names, int-preservation, and edge_attribute=None.
"""
import random

import numpy as np
import networkx as nx
import pytest
from scipy import sparse

import franken_networkx as fnx


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph"])
def test_from_scipy_float_parity(cls):
    for trial in range(8):
        n = random.Random(trial).randrange(5, 30)
        A = sparse.random(n, n, density=0.3, random_state=trial, dtype=float)
        gf = fnx.from_scipy_sparse_array(A, create_using=getattr(fnx, cls)())
        gn = nx.from_scipy_sparse_array(A, create_using=getattr(nx, cls)())
        assert [repr(x) for x in gf] == [repr(x) for x in gn], (cls, trial)
        assert sorted((repr(u), repr(v), round(d.get("weight"), 9)) for u, v, d in gf.edges(data=True)) == sorted(
            (repr(u), repr(v), round(d.get("weight"), 9)) for u, v, d in gn.edges(data=True)
        ), (cls, trial)


def _int_matrix():
    return sparse.csr_matrix(np.array([[0, 2, 0], [2, 0, 3], [0, 3, 0]], dtype=int))


@pytest.mark.parametrize("edge_attribute", ["weight", "cost", None])
def test_from_scipy_int_preservation_and_edge_attribute(edge_attribute):
    A = _int_matrix()
    gf = fnx.from_scipy_sparse_array(A, edge_attribute=edge_attribute)
    gn = nx.from_scipy_sparse_array(A, edge_attribute=edge_attribute)
    af = sorted((u, v, d.get(edge_attribute), type(d.get(edge_attribute)).__name__) for u, v, d in gf.edges(data=True))
    bf = sorted((u, v, d.get(edge_attribute), type(d.get(edge_attribute)).__name__) for u, v, d in gn.edges(data=True))
    assert af == bf


def test_from_scipy_multigraph_unchanged():
    A = _int_matrix()
    mgf = fnx.from_scipy_sparse_array(A, create_using=fnx.MultiGraph())
    mgn = nx.from_scipy_sparse_array(A, create_using=nx.MultiGraph())
    assert sorted((u, v, d.get("weight")) for u, v, d in mgf.edges(data=True)) == sorted(
        (u, v, d.get("weight")) for u, v, d in mgn.edges(data=True)
    )
