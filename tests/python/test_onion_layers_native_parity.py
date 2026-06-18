"""Parity for the native onion_layers kernel.

Bead br-r37-c1-l5es6.

onion_layers now runs natively (no nx delegation). The kernel mirrors nx's
onion decomposition exactly: ``current_core`` is a high-water mark of the
minimum degree and every node with ``degree <= current_core`` is peeled per
layer (the old kernel peeled only ``degree == min_deg`` nodes, splitting a
layer and diverging on the karate club graph). Within-layer order is
``(degree, node-insertion-index)`` so the result dict's key order matches nx's
stable ``sorted(degrees, key=degrees.get)``.

These tests pin both the layer values AND the dict key order to nx, plus the
error contracts and view/nx-typed-input handling.
"""

from __future__ import annotations

import importlib
import random

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _fbuild(g):
    f = fnx.Graph()
    for n in g.nodes():
        f.add_node(n)
    for u, v in g.edges():
        f.add_edge(u, v)
    return f


@needs_nx
def test_karate_club_exact():
    k = nx.karate_club_graph()
    f = _fbuild(k)
    a = nx.onion_layers(k)
    b = fnx.onion_layers(f)
    assert a == b
    assert list(a.items()) == list(b.items())  # key order


@needs_nx
@pytest.mark.parametrize("seed", list(range(60)))
def test_random_value_and_key_order(seed):
    rng = random.Random(seed * 71 + 3)
    n = rng.randint(0, 40)
    g = nx.gnm_random_graph(n, rng.randint(0, n * 2), seed=seed)
    # sometimes add isolated nodes (layer-1 contract)
    if rng.random() < 0.4:
        for k in range(rng.randint(1, 4)):
            g.add_node(10_000 + k)
    f = _fbuild(g)
    a = nx.onion_layers(g)
    b = fnx.onion_layers(f)
    assert a == b, f"values seed={seed}"
    assert list(a.items()) == list(b.items()), f"key order seed={seed}"


@needs_nx
def test_empty_and_single():
    assert fnx.onion_layers(fnx.Graph()) == {}
    g = fnx.Graph()
    g.add_node(0)
    assert fnx.onion_layers(g) == {0: 1}


@needs_nx
def test_isolated_nodes_are_layer_one():
    f, g = fnx.Graph(), nx.Graph()
    for x in (f, g):
        x.add_edges_from([(0, 1), (1, 2), (2, 0)])
        x.add_node(9)
        x.add_node(8)
    a, b = nx.onion_layers(g), fnx.onion_layers(f)
    assert a == b and list(a.items()) == list(b.items())
    assert b[9] == 1 and b[8] == 1


@needs_nx
def test_subgraph_view_honours_filter():
    g = nx.gnm_random_graph(20, 40, seed=5)
    f = _fbuild(g)
    a = nx.onion_layers(g.subgraph(range(12)))
    b = fnx.onion_layers(f.subgraph(range(12)))
    assert a == b and list(a.items()) == list(b.items())


@needs_nx
def test_nx_typed_input():
    assert fnx.onion_layers(nx.karate_club_graph()) == nx.onion_layers(
        nx.karate_club_graph()
    )


@needs_nx
def test_error_contracts():
    with pytest.raises(Exception) as e1:
        fnx.onion_layers(fnx.DiGraph([(0, 1)]))
    assert "directed" in str(e1.value).lower()
    with pytest.raises(Exception) as e2:
        fnx.onion_layers(fnx.MultiGraph([(0, 1)]))
    assert "multigraph" in str(e2.value).lower()
    gs = fnx.Graph()
    gs.add_edge(0, 0)
    gs.add_edge(0, 1)
    with pytest.raises(Exception) as e3:
        fnx.onion_layers(gs)
    assert "self loop" in str(e3.value).lower()


@needs_nx
@pytest.mark.parametrize(
    ("graph_factory", "expected_factory"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_not_implemented_guard_order_matches_networkx(
    graph_factory, expected_factory
):
    graph = graph_factory([(0, 1), (1, 2)])
    expected_graph = expected_factory([(0, 1), (1, 2)])

    with pytest.raises(nx.NetworkXNotImplemented) as fnx_exc:
        fnx.onion_layers(graph)
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        nx.onion_layers(expected_graph)

    assert str(fnx_exc.value) == str(nx_exc.value)


@needs_nx
@pytest.mark.parametrize(
    ("graph_factory", "expected_factory"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_core_module_not_implemented_guard_order_matches_networkx(
    graph_factory, expected_factory
):
    module = importlib.import_module("franken_networkx.core")
    graph = graph_factory([(0, 1), (1, 2)])
    expected_graph = expected_factory([(0, 1), (1, 2)])

    with pytest.raises(nx.NetworkXNotImplemented) as fnx_exc:
        module.onion_layers(graph)
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        nx.onion_layers(expected_graph)

    assert str(fnx_exc.value) == str(nx_exc.value)
