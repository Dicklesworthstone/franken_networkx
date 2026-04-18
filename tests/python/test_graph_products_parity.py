"""Parity coverage for graph product wrappers."""

import networkx as nx
import pytest

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


def _canonical_edges_with_keys(graph):
    if graph.is_multigraph():
        return sorted(
            (tuple(sorted((repr(u), repr(v)))), repr(key), dict(attrs))
            for u, v, key, attrs in graph.edges(keys=True, data=True)
        )
    return _canonical_edges(graph)


def _normalize_graph_product_edges_with_keys(graph):
    if graph.is_multigraph():
        edges = []
        for u, v, key, attrs in graph.edges(keys=True, data=True):
            if not graph.is_directed():
                endpoints = tuple(sorted((repr(u), repr(v))))
            else:
                endpoints = (repr(u), repr(v))
            edges.append((endpoints, repr(key), dict(attrs)))
        return sorted(edges)
    return _canonical_edges(graph)


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


def test_corona_product_directed_error_contract_matches_nx():
    cases = (
        (fnx.DiGraph, fnx.Graph, nx.DiGraph, nx.Graph),
        (fnx.Graph, fnx.DiGraph, nx.Graph, nx.DiGraph),
        (fnx.DiGraph, fnx.DiGraph, nx.DiGraph, nx.DiGraph),
    )

    for fnx_left_type, fnx_right_type, nx_left_type, nx_right_type in cases:
        left = fnx_left_type()
        left.add_edge("g0", "g1")
        right = fnx_right_type()
        right.add_edge("h0", "h1")

        left_nx = nx_left_type()
        left_nx.add_edge("g0", "g1")
        right_nx = nx_right_type()
        right_nx.add_edge("h0", "h1")

        with pytest.raises(Exception) as nx_exc:
            nx.corona_product(left_nx, right_nx)
        with pytest.raises(Exception) as fnx_exc:
            fnx.corona_product(left, right)

        assert type(fnx_exc.value).__name__ == type(nx_exc.value).__name__
        assert str(fnx_exc.value) == str(nx_exc.value)


def test_corona_product_multigraph_error_precedence_matches_nx():
    cases = (
        (fnx.MultiGraph, fnx.DiGraph, nx.MultiGraph, nx.DiGraph),
        (fnx.MultiGraph, fnx.MultiDiGraph, nx.MultiGraph, nx.MultiDiGraph),
        (fnx.MultiDiGraph, fnx.Graph, nx.MultiDiGraph, nx.Graph),
        (fnx.MultiDiGraph, fnx.DiGraph, nx.MultiDiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, fnx.MultiGraph, nx.MultiDiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, fnx.MultiDiGraph, nx.MultiDiGraph, nx.MultiDiGraph),
    )

    for fnx_left_type, fnx_right_type, nx_left_type, nx_right_type in cases:
        left = fnx_left_type()
        left.add_edge("g0", "g1", key=1)
        right = fnx_right_type()
        if right.is_multigraph():
            right.add_edge("h0", "h1", key=1)
        else:
            right.add_edge("h0", "h1")

        left_nx = nx_left_type()
        left_nx.add_edge("g0", "g1", key=1)
        right_nx = nx_right_type()
        if right_nx.is_multigraph():
            right_nx.add_edge("h0", "h1", key=1)
        else:
            right_nx.add_edge("h0", "h1")

        with pytest.raises(Exception) as nx_exc:
            nx.corona_product(left_nx, right_nx)
        with pytest.raises(Exception) as fnx_exc:
            fnx.corona_product(left, right)

        assert type(fnx_exc.value).__name__ == type(nx_exc.value).__name__
        assert str(fnx_exc.value) == str(nx_exc.value)


def test_corona_product_multigraph_outer_edge_keys_match_nx():
    left = fnx.path_graph(2)
    right = fnx.MultiGraph()
    right.add_edge("h0", "h1", key=7, weight=2)
    right.add_edge("h0", "h1", key=11, weight=3)

    left_nx = nx.path_graph(2)
    right_nx = nx.MultiGraph()
    right_nx.add_edge("h0", "h1", key=7, weight=2)
    right_nx.add_edge("h0", "h1", key=11, weight=3)

    product = fnx.corona_product(left, right)
    expected = nx.corona_product(left_nx, right_nx)

    assert product.is_multigraph() is expected.is_multigraph()
    assert _canonical_nodes(product) == _canonical_nodes(expected)
    assert _canonical_edges_with_keys(product) == _canonical_edges_with_keys(expected)


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


@pytest.mark.parametrize(
    ("fnx_left_type", "fnx_right_type", "nx_left_type", "nx_right_type"),
    [
        (fnx.DiGraph, fnx.DiGraph, nx.DiGraph, nx.DiGraph),
        (fnx.DiGraph, fnx.Graph, nx.DiGraph, nx.Graph),
        (fnx.Graph, fnx.DiGraph, nx.Graph, nx.DiGraph),
        (fnx.MultiGraph, fnx.Graph, nx.MultiGraph, nx.Graph),
        (fnx.Graph, fnx.MultiGraph, nx.Graph, nx.MultiGraph),
        (fnx.MultiDiGraph, fnx.MultiDiGraph, nx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_modular_product_error_contract_matches_nx(
    fnx_left_type, fnx_right_type, nx_left_type, nx_right_type
):
    left = fnx_left_type()
    right = fnx_right_type()
    left_nx = nx_left_type()
    right_nx = nx_right_type()

    if left.is_multigraph():
        left.add_edge(0, 1, key="k")
        left_nx.add_edge(0, 1, key="k")
    else:
        left.add_edge(0, 1)
        left_nx.add_edge(0, 1)

    if right.is_multigraph():
        right.add_edge("a", "b", key="x")
        right_nx.add_edge("a", "b", key="x")
    else:
        right.add_edge("a", "b")
        right_nx.add_edge("a", "b")

    with pytest.raises(Exception) as nx_exc:
        nx.modular_product(left_nx, right_nx)
    with pytest.raises(Exception) as fnx_exc:
        fnx.modular_product(left, right)

    assert type(fnx_exc.value).__name__ == type(nx_exc.value).__name__
    assert str(fnx_exc.value) == str(nx_exc.value)


def test_rooted_product_matches_nx():
    product = fnx.rooted_product(fnx.path_graph(3), fnx.path_graph(2), 0)
    expected = nx.rooted_product(nx.path_graph(3), nx.path_graph(2), 0)

    assert _canonical_nodes(product) == _canonical_nodes(expected)
    assert _canonical_edges(product) == _canonical_edges(expected)


def test_rooted_product_directed_inputs_match_nx():
    left = fnx.DiGraph()
    left.add_edge("g0", "g1")
    right = fnx.DiGraph()
    right.add_edge("r", "x")
    right.add_edge("x", "y")

    left_nx = nx.DiGraph()
    left_nx.add_edge("g0", "g1")
    right_nx = nx.DiGraph()
    right_nx.add_edge("r", "x")
    right_nx.add_edge("x", "y")

    product = fnx.rooted_product(left, right, "r")
    expected = nx.rooted_product(left_nx, right_nx, "r")

    assert product.is_directed() is expected.is_directed()
    assert _canonical_nodes(product) == _canonical_nodes(expected)
    assert _canonical_edges(product) == _canonical_edges(expected)


def test_rooted_product_mixed_directedness_matches_nx():
    cases = (
        (fnx.DiGraph, fnx.Graph, nx.DiGraph, nx.Graph),
        (fnx.Graph, fnx.DiGraph, nx.Graph, nx.DiGraph),
    )

    for fnx_left_type, fnx_right_type, nx_left_type, nx_right_type in cases:
        left = fnx_left_type()
        left.add_edge("g0", "g1")
        right = fnx_right_type()
        right.add_edge("r", "x")
        right.add_edge("x", "y")

        left_nx = nx_left_type()
        left_nx.add_edge("g0", "g1")
        right_nx = nx_right_type()
        right_nx.add_edge("r", "x")
        right_nx.add_edge("x", "y")

        product = fnx.rooted_product(left, right, "r")
        expected = nx.rooted_product(left_nx, right_nx, "r")

        assert product.is_directed() is expected.is_directed()
        assert _canonical_nodes(product) == _canonical_nodes(expected)
        assert _canonical_edges(product) == _canonical_edges(expected)


def test_rooted_product_right_hand_multigraph_matches_nx():
    cases = (
        (fnx.Graph, fnx.MultiGraph, nx.Graph, nx.MultiGraph),
        (fnx.DiGraph, fnx.MultiDiGraph, nx.DiGraph, nx.MultiDiGraph),
    )

    for fnx_left_type, fnx_right_type, nx_left_type, nx_right_type in cases:
        left = fnx_left_type()
        left.add_edge("g0", "g1")
        right = fnx_right_type()
        right.add_edge("r", "x", key=1)
        right.add_edge("x", "y", key=2)
        right.add_edge("x", "y", key=3)

        left_nx = nx_left_type()
        left_nx.add_edge("g0", "g1")
        right_nx = nx_right_type()
        right_nx.add_edge("r", "x", key=1)
        right_nx.add_edge("x", "y", key=2)
        right_nx.add_edge("x", "y", key=3)

        product = fnx.rooted_product(left, right, "r")
        expected = nx.rooted_product(left_nx, right_nx, "r")

        assert product.is_directed() is expected.is_directed()
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


@pytest.mark.parametrize("product_name", ["tensor_product", "strong_product"])
@pytest.mark.parametrize(
    ("fnx_left_type", "fnx_right_type", "nx_left_type", "nx_right_type"),
    [
        (fnx.Graph, fnx.MultiGraph, nx.Graph, nx.MultiGraph),
        (fnx.MultiGraph, fnx.Graph, nx.MultiGraph, nx.Graph),
        (fnx.MultiGraph, fnx.MultiGraph, nx.MultiGraph, nx.MultiGraph),
        (fnx.DiGraph, fnx.MultiDiGraph, nx.DiGraph, nx.MultiDiGraph),
        (fnx.MultiDiGraph, fnx.DiGraph, nx.MultiDiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, fnx.MultiDiGraph, nx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_product_cross_edge_keys_match_nx(
    product_name, fnx_left_type, fnx_right_type, nx_left_type, nx_right_type
):
    left = fnx_left_type()
    right = fnx_right_type()
    left_nx = nx_left_type()
    right_nx = nx_right_type()

    if left.is_multigraph():
        left.add_edge("g0", "g1", key=7, weight=2)
        left_nx.add_edge("g0", "g1", key=7, weight=2)
    else:
        left.add_edge("g0", "g1", weight=2)
        left_nx.add_edge("g0", "g1", weight=2)

    if right.is_multigraph():
        right.add_edge("h0", "h1", key=11, cost=3)
        right_nx.add_edge("h0", "h1", key=11, cost=3)
    else:
        right.add_edge("h0", "h1", cost=3)
        right_nx.add_edge("h0", "h1", cost=3)

    product = getattr(fnx, product_name)(left, right)
    expected = getattr(nx, product_name)(left_nx, right_nx)

    assert product.is_directed() is expected.is_directed()
    assert product.is_multigraph() is expected.is_multigraph()
    assert _canonical_nodes(product) == _canonical_nodes(expected)
    assert _normalize_graph_product_edges_with_keys(product) == _normalize_graph_product_edges_with_keys(expected)
