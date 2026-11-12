"""br-r37-c1-tq78w: regression — nx.relabel_nodes, nx.contracted_nodes,
nx.contracted_edge, nx.identified_nodes must dispatch through fnx's
backend when called on fnx graphs (in particular the ``copy=False``
mutation-preserving mode that the dispatcher refuses to auto-convert).

Same dispatch-coverage family as br-r37-c1-l2j31 (set/get attrs) and
br-r37-c1-0epvo (tree-submodule). The fix is to register these
helpers in ``franken_networkx.backend._SUPPORTED_ALGORITHMS`` so the
dispatcher routes the fnx graph through fnx's own implementation
rather than raising ``NotImplementedError``.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_relabel_nodes_copy_false_via_nx_namespace():
    g = fnx.path_graph(3)
    nx.relabel_nodes(g, {0: "a"}, copy=False)
    assert "a" in list(g.nodes())
    assert 0 not in list(g.nodes())


@needs_nx
def test_relabel_nodes_copy_true_via_nx_namespace():
    g = fnx.path_graph(3)
    g2 = nx.relabel_nodes(g, {0: "a"}, copy=True)
    # original unchanged
    assert 0 in list(g.nodes())
    assert "a" in list(g2.nodes())


@needs_nx
def test_contracted_nodes_copy_false_via_nx_namespace():
    g = fnx.path_graph(5)
    nx.contracted_nodes(g, 0, 1, copy=False)
    # Node 1 should be gone; merged into 0
    assert 1 not in list(g.nodes())
    assert 0 in list(g.nodes())


@needs_nx
def test_contracted_nodes_copy_true_via_nx_namespace():
    g = fnx.path_graph(5)
    g2 = nx.contracted_nodes(g, 0, 1, copy=True)
    # original unchanged
    assert set(g.nodes()) == {0, 1, 2, 3, 4}
    assert 1 not in g2.nodes()


@needs_nx
def test_contracted_edge_via_nx_namespace():
    g = fnx.path_graph(5)
    result = nx.contracted_edge(g, (0, 1))
    assert 1 not in result.nodes()


@needs_nx
def test_identified_nodes_via_nx_namespace():
    g = fnx.path_graph(5)
    result = nx.identified_nodes(g, 0, 1)
    assert 1 not in result.nodes()


@needs_nx
def test_backend_registers_relabel_and_contraction():
    from franken_networkx.backend import _SUPPORTED_ALGORITHMS

    for fname in (
        "relabel_nodes",
        "contracted_nodes",
        "contracted_edge",
        "identified_nodes",
    ):
        assert fname in _SUPPORTED_ALGORITHMS, f"{fname} missing"
