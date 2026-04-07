"""Parity coverage for graph product wrappers."""

import networkx as nx

import franken_networkx as fnx


def _canonical_nodes(graph):
    return sorted((repr(node), dict(attrs)) for node, attrs in graph.nodes(data=True))


def _canonical_edges(graph):
    if graph.is_multigraph():
        return sorted(
            (tuple(sorted((repr(u), repr(v)))), dict(attrs))
            for u, v, _key, attrs in graph.edges(keys=True, data=True)
        )
    return sorted(
        (tuple(sorted((repr(u), repr(v)))), dict(attrs)) for u, v, attrs in graph.edges(data=True)
    )


def test_cartesian_product_matches_nx():
    product = fnx.cartesian_product(fnx.path_graph(2), fnx.path_graph(3))
    expected = nx.cartesian_product(nx.path_graph(2), nx.path_graph(3))

    assert _canonical_nodes(product) == _canonical_nodes(expected)
    assert _canonical_edges(product) == _canonical_edges(expected)


def test_tensor_product_matches_nx():
    product = fnx.tensor_product(fnx.complete_graph(3), fnx.path_graph(3))
    expected = nx.tensor_product(nx.complete_graph(3), nx.path_graph(3))

    assert _canonical_nodes(product) == _canonical_nodes(expected)
    assert _canonical_edges(product) == _canonical_edges(expected)


def test_strong_product_matches_nx():
    product = fnx.strong_product(fnx.path_graph(2), fnx.path_graph(3))
    expected = nx.strong_product(nx.path_graph(2), nx.path_graph(3))

    assert _canonical_nodes(product) == _canonical_nodes(expected)
    assert _canonical_edges(product) == _canonical_edges(expected)


def test_lexicographic_product_matches_nx():
    product = fnx.lexicographic_product(fnx.path_graph(3), fnx.path_graph(2))
    expected = nx.lexicographic_product(nx.path_graph(3), nx.path_graph(2))

    assert _canonical_nodes(product) == _canonical_nodes(expected)
    assert _canonical_edges(product) == _canonical_edges(expected)


def test_corona_product_matches_nx():
    product = fnx.corona_product(fnx.path_graph(2), fnx.path_graph(2))
    expected = nx.corona_product(nx.path_graph(2), nx.path_graph(2))

    assert _canonical_nodes(product) == _canonical_nodes(expected)
    assert _canonical_edges(product) == _canonical_edges(expected)


def test_modular_product_matches_nx():
    left = fnx.Graph()
    left.add_edge(0, 1, weight=2)
    right = fnx.Graph()
    right.add_edge("a", "b", cost=3)
    left_nx = nx.Graph()
    left_nx.add_edge(0, 1, weight=2)
    right_nx = nx.Graph()
    right_nx.add_edge("a", "b", cost=3)

    product = fnx.modular_product(left, right)
    expected = nx.modular_product(left_nx, right_nx)

    assert _canonical_nodes(product) == _canonical_nodes(expected)
    assert _canonical_edges(product) == _canonical_edges(expected)


def test_rooted_product_matches_nx():
    product = fnx.rooted_product(fnx.path_graph(3), fnx.path_graph(2), 0)
    expected = nx.rooted_product(nx.path_graph(3), nx.path_graph(2), 0)

    assert _canonical_nodes(product) == _canonical_nodes(expected)
    assert _canonical_edges(product) == _canonical_edges(expected)


def test_product_nodes_are_tuples():
    product = fnx.cartesian_product(fnx.path_graph(2), fnx.path_graph(2))
    assert all(isinstance(node, tuple) for node in product.nodes())


def test_multigraph_attributes_match_nx_for_tuple_products():
    left = fnx.MultiGraph()
    left.add_node(0, a1=True)
    left.add_edge(0, 1, key=7, w=2)
    right = fnx.MultiGraph()
    right.add_node("a", a2="Spam")
    right.add_edge("a", "b", key=3, c=4)

    left_nx = nx.MultiGraph()
    left_nx.add_node(0, a1=True)
    left_nx.add_edge(0, 1, key=7, w=2)
    right_nx = nx.MultiGraph()
    right_nx.add_node("a", a2="Spam")
    right_nx.add_edge("a", "b", key=3, c=4)

    for name in ("cartesian_product", "tensor_product", "strong_product", "lexicographic_product"):
        product = getattr(fnx, name)(left, right)
        expected = getattr(nx, name)(left_nx, right_nx)
        assert _canonical_nodes(product) == _canonical_nodes(expected)
        assert _canonical_edges(product) == _canonical_edges(expected)
