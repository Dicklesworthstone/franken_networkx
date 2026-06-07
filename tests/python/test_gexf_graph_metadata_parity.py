"""readwrite-matrix 2026-06-06: fnx's native read_gexf dropped ALL
graph-level attrs; nx's GEXFReader populates mode (always),
node_default (only when a class=node attributes element exists),
edge_default (always — the Gephi-0.7beta hack), plus name/start/end
when present, in that key order.
"""

import os
import tempfile

import networkx as nx
import pytest

import franken_networkx as fnx


def _cmp(gn, tmp, label, **wkw):
    p = os.path.join(tmp, label.replace(" ", "_") + ".gexf")
    nx.write_gexf(gn, p, **wkw)
    gf, gx = fnx.read_gexf(p), nx.read_gexf(p)
    assert {k: (repr(v), type(v).__name__) for k, v in gf.graph.items()} == {
        k: (repr(v), type(v).__name__) for k, v in gx.graph.items()
    }, label
    assert list(gf.graph) == list(gx.graph), label  # key ORDER too


@pytest.fixture()
def tmp():
    return tempfile.mkdtemp(dir="/data/tmp")


def test_plain_graph_metadata(tmp):
    g = nx.Graph()
    g.add_edge(1, 2)
    _cmp(g, tmp, "plain")


def test_named_graph_with_attrs(tmp):
    g = nx.Graph(name="Named")
    g.add_edge(1, 2, weight=2.5)
    g.add_node(1, color="red", size=4)
    _cmp(g, tmp, "named attrs")


def test_digraph_typed_attrs(tmp):
    g = nx.DiGraph()
    g.add_edge("a", "b", w=1.5, flag=True)
    _cmp(g, tmp, "digraph")
