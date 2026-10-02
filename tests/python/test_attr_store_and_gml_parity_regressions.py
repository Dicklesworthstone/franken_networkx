"""Parity regressions found in the v0.2.3 release review.

* A node whose attributes live only in the Rust store (every attributed node
  from the native ``add_nodes_from`` batch, relabel, union, convert) lost them
  when ``add_node(n, **attr)`` or ``set_node_attributes`` created an empty
  Python mirror for it: the mirror is what every reader trusts.
* ``read_gml``'s default call took the native parser, which drops repeated-key
  lists, backslashes and ``+INF`` typing.
* ``keydict[k] = keydict[k]`` cleared the live dict before copying from it.
* An undirected MultiGraph handed out a weight-cache token that a synced write
  through a held attr dict could not move, so a negative weight went unseen.
"""

import contextlib

import networkx as nx
import pytest

import franken_networkx as fnx

CLASS_NAMES = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")


def _attributed_nodes():
    # Eight or more (node, dict) pairs with several keys take the native batch.
    return [(i, {"a": i, "b": -i}) for i in range(10)]


def _both(cls_name):
    g = getattr(fnx, cls_name)()
    h = getattr(nx, cls_name)()
    g.add_nodes_from(_attributed_nodes())
    h.add_nodes_from(_attributed_nodes())
    return g, h


def _node_data(graph):
    return {n: dict(d) for n, d in graph.nodes(data=True)}


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_add_node_with_attrs_keeps_store_only_attrs(cls_name):
    g, h = _both(cls_name)
    g.add_node(0, c=1)
    h.add_node(0, c=1)
    assert g.nodes[0] == h.nodes[0] == {"a": 0, "b": 0, "c": 1}
    assert _node_data(g) == _node_data(h)


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_set_node_attributes_keeps_store_only_attrs(cls_name):
    g, h = _both(cls_name)
    fnx.set_node_attributes(g, {1: 9}, "c")
    nx.set_node_attributes(h, {1: 9}, "c")
    fnx.set_node_attributes(g, {2: {"d": 4}})
    nx.set_node_attributes(h, {2: {"d": 4}})
    assert g.nodes[1] == h.nodes[1] == {"a": 1, "b": -1, "c": 9}
    assert g.nodes[2] == h.nodes[2] == {"a": 2, "b": -2, "d": 4}
    assert _node_data(g) == _node_data(h)


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_node_view_get_returns_store_only_attrs(cls_name):
    g, h = _both(cls_name)
    assert g.nodes.get(3) == h.nodes.get(3) == {"a": 3, "b": -3}
    g.nodes[3]["e"] = 5
    assert g.nodes[3] == {"a": 3, "b": -3, "e": 5}


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_relabelled_graph_keeps_attrs_through_add_node(cls_name):
    g, h = _both(cls_name)
    g2 = fnx.relabel_nodes(g, {i: f"n{i}" for i in range(10)})
    h2 = nx.relabel_nodes(h, {i: f"n{i}" for i in range(10)})
    g2.add_node("n4", z=0)
    h2.add_node("n4", z=0)
    assert _node_data(g2) == _node_data(h2)


def _edge_data(graph):
    if graph.is_multigraph():
        return sorted((repr(u), repr(v), k, dict(d)) for u, v, k, d in graph.edges(keys=True, data=True))
    return sorted((repr(u), repr(v), dict(d)) for u, v, d in graph.edges(data=True))


def test_read_gml_default_roundtrips_like_networkx(tmp_path):
    source = nx.Graph()
    source.add_node("C:\\tmp", pos=[0.5, 1.5], tags=[1, 2, 3])
    source.add_node("plain", label_like=5)
    source.add_edge("C:\\tmp", "plain", w=float("inf"), many=[0.25, 0.75])
    path = tmp_path / "roundtrip.gml"
    nx.write_gml(source, path)

    expected = nx.read_gml(path)
    got = fnx.read_gml(path)
    assert got.is_multigraph() == expected.is_multigraph()
    assert got.is_directed() == expected.is_directed()
    assert _node_data(got) == _node_data(expected)
    assert _edge_data(got) == _edge_data(expected)


def test_read_gml_default_honours_multigraph_flag(tmp_path):
    source = nx.MultiGraph()
    source.add_edge(0, 1, w=1)
    source.add_edge(0, 1, w=2)
    path = tmp_path / "multi.gml"
    text = "\n".join(nx.generate_gml(source)).replace("multigraph 1", "multigraph\t1")
    path.write_text(text)

    expected = nx.read_gml(path)
    got = fnx.read_gml(path)
    assert got.is_multigraph() and expected.is_multigraph()
    assert got.number_of_edges() == expected.number_of_edges() == 2


@pytest.mark.parametrize("cls_name", ("MultiGraph", "MultiDiGraph"))
def test_keydict_self_assignment_keeps_edge_attrs(cls_name):
    for lib in (fnx, nx):
        g = getattr(lib, cls_name)()
        g.add_edge(0, 1, w=1)
        kd = g.get_edge_data(0, 1)
        d = kd[0]
        d["w"] = 5
        kd[0] = d
        assert g[0][1][0] == {"w": 5}, lib.__name__
        kd.update(kd)
        assert g[0][1][0] == {"w": 5}, lib.__name__


def _outcome(call):
    try:
        return ("ok", call())
    except Exception as exc:  # noqa: BLE001 - the exception type is the outcome
        return ("raise", type(exc))


def test_multigraph_negative_weight_written_after_sync_is_seen():
    results = []
    for lib in (fnx, nx):
        g = lib.MultiGraph([(0, 1, {"weight": 1}), (1, 2, {"weight": 1}), (0, 2, {"weight": 5})])
        lib.dijkstra_path(g, 0, 1, weight="weight")
        g[0][2][0]["weight"] = -10
        with contextlib.suppress(Exception):
            lib.average_shortest_path_length(g, weight="weight")
        results.append(_outcome(lambda: lib.dijkstra_path(g, 0, 1, weight="weight")))
    assert results[0] == results[1]
