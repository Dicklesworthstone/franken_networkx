"""br-r37-c1-9p30c: regression tests for relabel_gexf_graph strict
missing-label check matching nx."""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def test_missing_label_raises_networkx_error():
    g = fnx.Graph()
    g.add_edge(0, 1)
    with pytest.raises(fnx.NetworkXError, match="missing node labels"):
        fnx.readwrite.relabel_gexf_graph(g)


def test_missing_label_directed_raises():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    with pytest.raises(fnx.NetworkXError, match="missing node labels"):
        fnx.readwrite.relabel_gexf_graph(g)


def test_partial_labels_raises():
    """If ONE node has a label but another doesn't, still raises."""
    g = fnx.Graph()
    g.add_node(0, label="a")
    g.add_node(1)  # no label
    g.add_edge(0, 1)
    with pytest.raises(fnx.NetworkXError, match="missing node labels"):
        fnx.readwrite.relabel_gexf_graph(g)


def test_all_labels_present_relabels():
    g = fnx.Graph()
    g.add_node(0, label="a")
    g.add_node(1, label="b")
    g.add_edge(0, 1)
    relabeled = fnx.readwrite.relabel_gexf_graph(g)
    assert set(relabeled.nodes()) == {"a", "b"}
    # Original ids should be stored on the relabeled nodes.
    assert relabeled.nodes["a"]["id"] == 0
    assert relabeled.nodes["b"]["id"] == 1


@needs_nx
def test_matches_nx_exception_class_on_missing():
    fg = fnx.Graph()
    fg.add_edge(0, 1)
    ng = nx.Graph()
    ng.add_edge(0, 1)
    with pytest.raises(nx.NetworkXError):
        nx.relabel_gexf_graph(ng)
    with pytest.raises(fnx.NetworkXError):
        fnx.readwrite.relabel_gexf_graph(fg)
