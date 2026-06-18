"""Attribute-preserving round-trips for GML and GraphML.

Richer than the structural file-IO round-trip: GML and GraphML retain typed
node/edge/graph attributes, so a write+read cycle must recover their values.

br-r37-c1-fxrd4
"""

from __future__ import annotations

import os
import random
import tempfile

import pytest
import franken_networkx as fnx


def _attributed_graph(seed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(4, 7)
    g = fnx.Graph()
    g.graph["name"] = "test"
    g.graph["level"] = 3
    for i in range(n):
        g.add_node(i, color=rng.choice(["red", "blue"]), size=rng.randint(1, 10))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                g.add_edge(u, v, weight=rng.randint(1, 9), kind=rng.choice(["a", "b"]))
    return g


@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _node_attrs(g):
    return {str(n): (d.get("color"), d.get("size")) for n, d in g.nodes(data=True)}


def _edge_attrs(g):
    return {
        (min(int(u), int(v)), max(int(u), int(v))): (d.get("weight"), d.get("kind"))
        for u, v, d in g.edges(data=True)
    }


@pytest.mark.parametrize("seed", range(30))
def test_gml_preserves_attributes(seed, tmpdir):
    g = _attributed_graph(seed)
    path = os.path.join(tmpdir, "g.gml")
    fnx.write_gml(g, path)
    rg = fnx.read_gml(path, destringizer=int)
    assert _node_attrs(rg) == _node_attrs(g)
    assert _edge_attrs(rg) == _edge_attrs(g)
    assert rg.graph.get("name") == "test"
    assert rg.graph.get("level") == 3


@pytest.mark.parametrize("seed", range(30))
def test_graphml_preserves_attributes(seed, tmpdir):
    g = _attributed_graph(seed)
    path = os.path.join(tmpdir, "g.graphml")
    fnx.write_graphml(g, path)
    rg = fnx.read_graphml(path, node_type=int)
    assert _node_attrs(rg) == _node_attrs(g)
    assert _edge_attrs(rg) == _edge_attrs(g)
    assert rg.graph.get("name") == "test"
    assert rg.graph.get("level") == 3
