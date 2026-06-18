"""Metamorphic write-to-disk / read-back round-trips.

Distinct from the in-memory codecs: these actually serialise to a file and
parse it back, exercising the filesystem read/write paths.

* ``read_edgelist(write_edgelist(G))`` preserves the edge set (and weights)
* ``read_adjlist(write_adjlist(G))`` preserves the edge set
* ``read_gml(write_gml(G))`` / ``read_graphml(write_graphml(G))`` preserve
  the edge set

br-r37-c1-bcioo
"""

from __future__ import annotations

import os
import random
import tempfile

import pytest
import franken_networkx as fnx


def _graph(seed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    g = fnx.Graph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                g.add_edge(u, v, weight=rng.randint(1, 9))
    return g


def _edges(g):
    return sorted(tuple(sorted(e)) for e in g.edges())


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.mark.parametrize("seed", range(30))
def test_edgelist_round_trip(seed, tmpdir):
    g = _graph(seed)
    path = os.path.join(tmpdir, "g.edgelist")
    fnx.write_edgelist(g, path, data=False)
    assert _edges(fnx.read_edgelist(path, nodetype=int)) == _edges(g)


@pytest.mark.parametrize("seed", range(30))
def test_weighted_edgelist_round_trip(seed, tmpdir):
    g = _graph(seed)
    path = os.path.join(tmpdir, "g.weighted")
    fnx.write_weighted_edgelist(g, path)
    rg = fnx.read_weighted_edgelist(path, nodetype=int)
    got = sorted((min(u, v), max(u, v), rg[u][v]["weight"]) for u, v in rg.edges())
    want = sorted((min(u, v), max(u, v), float(g[u][v]["weight"])) for u, v in g.edges())
    assert got == want


@pytest.mark.parametrize("seed", range(30))
def test_adjlist_round_trip(seed, tmpdir):
    g = _graph(seed)
    path = os.path.join(tmpdir, "g.adjlist")
    fnx.write_adjlist(g, path)
    assert _edges(fnx.read_adjlist(path, nodetype=int)) == _edges(g)


@pytest.mark.parametrize("seed", range(30))
def test_gml_round_trip(seed, tmpdir):
    g = _graph(seed)
    path = os.path.join(tmpdir, "g.gml")
    fnx.write_gml(g, path)
    assert _edges(fnx.read_gml(path, destringizer=int)) == _edges(g)


@pytest.mark.parametrize("seed", range(30))
def test_graphml_round_trip(seed, tmpdir):
    g = _graph(seed)
    path = os.path.join(tmpdir, "g.graphml")
    fnx.write_graphml(g, path)
    assert _edges(fnx.read_graphml(path, node_type=int)) == _edges(g)
