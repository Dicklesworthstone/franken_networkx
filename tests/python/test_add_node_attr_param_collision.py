"""br-r37-c1-addnoden: add_node(node, **attr) must accept an attr keyed
'n' (the Rust binding's node param was named 'n' and collided). nx
names the param 'node_for_adding', so that key — and only that key —
collides; match it exactly. Regression surfaced via read_graphml/gml/
pajek of graphs carrying an 'n' attribute (_from_nx_graph splats attrs).
"""

import io

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


@pytest.mark.parametrize("cls", CLASSES)
def test_add_node_with_attr_named_n(cls):
    gf, gn = getattr(fnx, cls)(), getattr(nx, cls)()
    gf.add_node(0, n=7, lbl="z")
    gn.add_node(0, n=7, lbl="z")
    assert dict(gf.nodes[0]) == dict(gn.nodes[0]) == {"n": 7, "lbl": "z"}


@pytest.mark.parametrize("cls", CLASSES)
def test_add_node_node_for_adding_collision_matches_nx(cls):
    gf, gn = getattr(fnx, cls)(), getattr(nx, cls)()

    def attempt(g):
        try:
            g.add_node(1, node_for_adding=9)
            return "ok"
        except TypeError:
            return "TypeError"

    assert attempt(gf) == attempt(gn)


def test_read_graphml_with_n_attr_roundtrips():
    g = nx.Graph()
    g.add_node(0, n=7, lbl="zero")
    g.add_edge(0, 1, weight=2.5)
    buf = io.BytesIO()
    nx.write_graphml(g, buf)
    buf.seek(0)
    rf = fnx.read_graphml(buf)
    assert dict(rf.nodes["0"]) == {"n": 7, "lbl": "zero"}
