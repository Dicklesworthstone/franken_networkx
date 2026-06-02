"""Parity lock: weighted degree counts a self-loop's weight twice.

NetworkX's ``DegreeView.__getitem__`` adds the self-loop edge weight a second
time for undirected total degree (``+ nbrs[n].get(weight, 1)`` when ``n in
nbrs``).  fnx's ``_WeightAwareDegreeView._weighted_value`` summed each adjacency
entry once, so an undirected node with a self-loop reported half the loop's
weight.  Directed total degree (succ + pred), in/out degree, and the multigraph
views were already correct; this locks the undirected single-graph fix and
guards the others against regression.
"""

import networkx as nx
import franken_networkx as fnx
import pytest


def _build(cls, multi=False):
    g = cls()
    edges = [(2, 3, 4.0), (3, 3, 5.0)]
    if multi:
        edges.append((3, 3, 7.0))
    for u, v, w in edges:
        g.add_edge(u, v, weight=w)
    return g


@pytest.mark.parametrize("cls_n,cls_f", [(nx.Graph, fnx.Graph)])
def test_undirected_weighted_degree_selfloop(cls_n, cls_f):
    Gn, Gf = _build(cls_n), _build(cls_f)
    assert dict(Gf.degree(weight="weight")) == dict(Gn.degree(weight="weight"))
    # node 3 has one ordinary edge (w=4) and a self-loop (w=5): 4 + 2*5 = 14
    assert Gf.degree(3, weight="weight") == 14.0
    assert Gf.degree(3, weight="weight") == Gn.degree(3, weight="weight")


@pytest.mark.parametrize(
    "cls_n,cls_f,multi",
    [
        (nx.DiGraph, fnx.DiGraph, False),
        (nx.MultiGraph, fnx.MultiGraph, True),
        (nx.MultiDiGraph, fnx.MultiDiGraph, True),
    ],
)
def test_other_views_weighted_degree_selfloop(cls_n, cls_f, multi):
    Gn, Gf = _build(cls_n, multi), _build(cls_f, multi)
    assert dict(Gf.degree(weight="weight")) == dict(Gn.degree(weight="weight"))
    if Gf.is_directed():
        assert dict(Gf.in_degree(weight="weight")) == dict(Gn.in_degree(weight="weight"))
        assert dict(Gf.out_degree(weight="weight")) == dict(Gn.out_degree(weight="weight"))


def test_size_weighted_with_selfloops():
    edges = [(0, 1, 2.0), (1, 2, 3.0), (2, 2, 5.0), (0, 0, 1.5)]
    Gn, Gf = nx.Graph(), fnx.Graph()
    for u, v, w in edges:
        Gn.add_edge(u, v, weight=w)
        Gf.add_edge(u, v, weight=w)
    # size = sum of all edge weights = 2 + 3 + 5 + 1.5
    assert Gf.size(weight="weight") == Gn.size(weight="weight") == 11.5


def test_unweighted_degree_selfloop_unchanged():
    Gn, Gf = _build(nx.Graph), _build(fnx.Graph)
    # self-loop still counts twice for the unweighted degree
    assert dict(Gf.degree()) == dict(Gn.degree())
    assert Gf.degree(3) == Gn.degree(3) == 3
