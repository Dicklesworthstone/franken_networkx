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


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("kw", [{"u": 5}, {"v": 5}, {"weight": 1, "u": 2}, {"u": 1, "v": 2}])
def test_add_edge_with_attr_named_u_or_v(cls, kw):
    """br-r37-c1-7iria follow-up: add_edge(u, v, **attr) with an attr
    keyed 'u'/'v' collided (raw binding params were bare u/v). nx names
    them u_of_edge/v_of_edge (simple) and u_for_edge/v_for_edge
    (multi); match exactly."""
    gf, gn = getattr(fnx, cls)(), getattr(nx, cls)()

    def run(g):
        try:
            g.add_edge(0, 1, **kw)
        except TypeError:
            return "TypeError"
        e = g[0][1] if not g.is_multigraph() else g[0][1][0]
        return dict(e)

    assert run(gf) == run(gn)


@pytest.mark.parametrize("cls", CLASSES)
def test_add_edge_nx_param_name_collision_matches(cls):
    pname = "u_of_edge" if cls in ("Graph", "DiGraph") else "u_for_edge"
    gf, gn = getattr(fnx, cls)(), getattr(nx, cls)()

    def attempt(g):
        try:
            g.add_edge(0, 1, **{pname: 9})
            return "ok"
        except TypeError:
            return "TypeError"

    assert attempt(gf) == attempt(gn)


def test_read_graphml_with_u_v_edge_attrs():
    g = nx.Graph()
    g.add_edge(0, 1, u=3, v=4, weight=2.5)
    buf = io.BytesIO()
    nx.write_graphml(g, buf)
    buf.seek(0)
    assert dict(fnx.read_graphml(buf)["0"]["1"]) == {"u": 3, "v": 4, "weight": 2.5}
