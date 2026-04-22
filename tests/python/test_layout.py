"""Tests for drawing layout delegation helpers."""

import warnings
from unittest import mock

import networkx as nx
import numpy as np
import pytest

import franken_networkx as fnx
from franken_networkx.backend import _fnx_to_nx as _to_nx


def _as_tuples(pos):
    return {node: tuple(np.asarray(coords, dtype=float)) for node, coords in pos.items()}


def _assert_positions_close(left, right):
    assert left.keys() == right.keys()
    for node in left:
        assert np.allclose(left[node], right[node])


def test_bfs_layout_matches_networkx_without_delegation():
    graph = fnx.path_graph(5)
    expected = _as_tuples(
        nx.bfs_layout(
            nx.path_graph(5),
            0,
            align="horizontal",
            scale=2,
            center=[1.0, -1.0],
        )
    )

    with mock.patch(
        "networkx.bfs_layout",
        side_effect=AssertionError("NetworkX bfs_layout should not be used"),
    ):
        actual = _as_tuples(
            fnx.bfs_layout(
                graph,
                0,
                align="horizontal",
                scale=2,
                center=[1.0, -1.0],
            )
        )

    _assert_positions_close(actual, expected)


def test_bfs_layout_tuple_labels_match_networkx_without_delegation():
    mapping = {node: ("bfs", node) for node in range(5)}
    graph = fnx.relabel_nodes(fnx.path_graph(5), mapping)
    expected_graph = nx.relabel_nodes(nx.path_graph(5), mapping)
    expected = _as_tuples(
        nx.bfs_layout(
            expected_graph,
            mapping[0],
            align="horizontal",
            scale=2,
            center=[1.0, -1.0],
        )
    )

    with mock.patch(
        "networkx.bfs_layout",
        side_effect=AssertionError("NetworkX bfs_layout should not be used"),
    ):
        actual = _as_tuples(
            fnx.bfs_layout(
                graph,
                mapping[0],
                align="horizontal",
                scale=2,
                center=[1.0, -1.0],
                store_pos_as="pos",
            )
        )

    _assert_positions_close(actual, expected)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_bipartite_layout_matches_networkx_without_delegation():
    graph = fnx.complete_bipartite_graph(2, 3)
    expected = _as_tuples(nx.bipartite_layout(_to_nx(graph), nodes=[0, 1]))
    path_graph = fnx.path_graph(4)
    expected_inferred = _as_tuples(
        nx.bipartite_layout(
            nx.path_graph(4),
            align="horizontal",
            scale=2,
            center=[1.0, -1.0],
        )
    )

    with mock.patch(
        "networkx.bipartite_layout",
        side_effect=AssertionError("NetworkX bipartite_layout should not be used"),
    ):
        actual = _as_tuples(fnx.bipartite_layout(graph, nodes=[0, 1]))
        actual_inferred = _as_tuples(
            fnx.bipartite_layout(
                path_graph,
                align="horizontal",
                scale=2,
                center=[1.0, -1.0],
            )
        )

    _assert_positions_close(actual, expected)
    _assert_positions_close(actual_inferred, expected_inferred)


def test_bipartite_layout_tuple_labels_match_networkx_without_delegation():
    top_nodes = [("top", index) for index in range(2)]
    bottom_nodes = [("bottom", index) for index in range(3)]
    edges = [
        (top_nodes[0], bottom_nodes[0]),
        (top_nodes[0], bottom_nodes[1]),
        (top_nodes[1], bottom_nodes[1]),
        (top_nodes[1], bottom_nodes[2]),
    ]
    graph = fnx.Graph()
    graph.add_edges_from(edges)
    expected_graph = nx.Graph()
    expected_graph.add_edges_from(edges)
    expected = _as_tuples(
        nx.bipartite_layout(
            expected_graph,
            nodes=top_nodes,
            align="horizontal",
            scale=2,
            center=[1.0, -1.0],
        )
    )

    with mock.patch(
        "networkx.bipartite_layout",
        side_effect=AssertionError("NetworkX bipartite_layout should not be used"),
    ):
        actual = _as_tuples(
            fnx.bipartite_layout(
                graph,
                nodes=top_nodes,
                align="horizontal",
                scale=2,
                center=[1.0, -1.0],
                store_pos_as="pos",
            )
        )

    _assert_positions_close(actual, expected)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_bipartite_layout_inferred_set_errors_match_networkx_without_delegation():
    disconnected_graph = fnx.Graph()
    disconnected_graph.add_edges_from([(0, 1), (2, 3)])
    expected_disconnected_graph = nx.Graph()
    expected_disconnected_graph.add_edges_from([(0, 1), (2, 3)])

    non_bipartite_graph = fnx.cycle_graph(3)
    expected_non_bipartite_graph = nx.cycle_graph(3)

    disconnected_message = "Disconnected graph: Ambiguous solution for bipartite sets."
    non_bipartite_message = "Graph is not bipartite."

    with pytest.raises(nx.AmbiguousSolution, match=disconnected_message):
        nx.bipartite_layout(expected_disconnected_graph)
    with pytest.raises(nx.NetworkXError, match=non_bipartite_message):
        nx.bipartite_layout(expected_non_bipartite_graph)

    with mock.patch(
        "networkx.bipartite_layout",
        side_effect=AssertionError("NetworkX bipartite_layout should not be used"),
    ):
        with pytest.raises(fnx.AmbiguousSolution, match=disconnected_message):
            fnx.bipartite_layout(disconnected_graph)
        with pytest.raises(fnx.NetworkXError, match=non_bipartite_message):
            fnx.bipartite_layout(non_bipartite_graph)


def test_spiral_layout_matches_networkx_without_delegation():
    graph = fnx.path_graph(6)
    expected = _as_tuples(nx.spiral_layout(nx.path_graph(6), resolution=0.2))

    with mock.patch(
        "networkx.spiral_layout",
        side_effect=AssertionError("NetworkX spiral_layout should not be used"),
    ):
        actual = _as_tuples(fnx.spiral_layout(graph, resolution=0.2))

    _assert_positions_close(actual, expected)


def test_spiral_layout_tuple_labels_match_networkx_without_delegation():
    mapping = {node: ("spiral", node) for node in range(5)}
    graph = fnx.relabel_nodes(fnx.path_graph(5), mapping)
    expected_graph = nx.relabel_nodes(nx.path_graph(5), mapping)
    expected = _as_tuples(
        nx.spiral_layout(
            expected_graph,
            resolution=0.25,
            scale=1.5,
            center=[1.0, -1.0],
        )
    )

    with mock.patch(
        "networkx.spiral_layout",
        side_effect=AssertionError("NetworkX spiral_layout should not be used"),
    ):
        actual = _as_tuples(
            fnx.spiral_layout(
                graph,
                resolution=0.25,
                scale=1.5,
                center=[1.0, -1.0],
                store_pos_as="pos",
            )
        )

    _assert_positions_close(actual, expected)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_circular_layout_matches_networkx_without_delegation():
    graph = fnx.path_graph(4)
    expected = _as_tuples(
        nx.circular_layout(
            nx.path_graph(4),
            scale=2,
            center=[1.0, -1.0, 0.5],
            dim=3,
        )
    )

    with mock.patch(
        "networkx.circular_layout",
        side_effect=AssertionError("NetworkX circular_layout should not be used"),
    ):
        actual = _as_tuples(
            fnx.circular_layout(
                graph,
                scale=2,
                center=[1.0, -1.0, 0.5],
                dim=3,
            )
        )

    _assert_positions_close(actual, expected)


def test_circular_layout_tuple_labels_match_networkx_without_delegation():
    mapping = {node: ("circular", node) for node in range(4)}
    graph = fnx.relabel_nodes(fnx.path_graph(4), mapping)
    expected_graph = nx.relabel_nodes(nx.path_graph(4), mapping)
    expected = _as_tuples(
        nx.circular_layout(
            expected_graph,
            scale=2,
            center=[1.0, -1.0, 0.5],
            dim=3,
        )
    )

    with mock.patch(
        "networkx.circular_layout",
        side_effect=AssertionError("NetworkX circular_layout should not be used"),
    ):
        actual = _as_tuples(
            fnx.circular_layout(
                graph,
                scale=2,
                center=[1.0, -1.0, 0.5],
                dim=3,
                store_pos_as="pos",
            )
        )

    _assert_positions_close(actual, expected)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_random_layout_matches_networkx_without_delegation():
    graph = fnx.path_graph(4)
    expected = _as_tuples(nx.random_layout(nx.path_graph(4), seed=11, center=[2.0, -2.0]))

    with mock.patch(
        "networkx.random_layout",
        side_effect=AssertionError("NetworkX random_layout should not be used"),
    ):
        actual = _as_tuples(fnx.random_layout(graph, seed=11, center=[2.0, -2.0]))

    _assert_positions_close(actual, expected)


def test_random_layout_tuple_labels_match_networkx_without_delegation():
    mapping = {node: ("random", node) for node in range(4)}
    graph = fnx.relabel_nodes(fnx.path_graph(4), mapping)
    expected_graph = nx.relabel_nodes(nx.path_graph(4), mapping)
    expected = _as_tuples(
        nx.random_layout(expected_graph, seed=11, center=[2.0, -2.0])
    )

    with mock.patch(
        "networkx.random_layout",
        side_effect=AssertionError("NetworkX random_layout should not be used"),
    ):
        actual = _as_tuples(
            fnx.random_layout(
                graph,
                seed=11,
                center=[2.0, -2.0],
                store_pos_as="pos",
            )
        )

    _assert_positions_close(actual, expected)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_shell_layout_matches_networkx_without_delegation():
    graph = fnx.path_graph(4)
    shells = [[0], [1, 2, 3]]
    expected = _as_tuples(
        nx.shell_layout(
            nx.path_graph(4),
            nlist=shells,
            rotate=0.0,
            scale=2.0,
            center=[1.0, 1.0],
        )
    )

    with mock.patch(
        "networkx.shell_layout",
        side_effect=AssertionError("NetworkX shell_layout should not be used"),
    ):
        actual = _as_tuples(
            fnx.shell_layout(
                graph,
                nlist=shells,
                rotate=0.0,
                scale=2.0,
                center=[1.0, 1.0],
            )
        )

    _assert_positions_close(actual, expected)


def test_shell_layout_tuple_labels_match_networkx_without_delegation():
    mapping = {node: ("shell", node) for node in range(4)}
    graph = fnx.relabel_nodes(fnx.path_graph(4), mapping)
    expected_graph = nx.relabel_nodes(nx.path_graph(4), mapping)
    shells = [[mapping[0]], [mapping[1], mapping[2], mapping[3]]]
    expected = _as_tuples(
        nx.shell_layout(
            expected_graph,
            nlist=shells,
            rotate=0.0,
            scale=2.0,
            center=[1.0, 1.0],
        )
    )

    with mock.patch(
        "networkx.shell_layout",
        side_effect=AssertionError("NetworkX shell_layout should not be used"),
    ):
        actual = _as_tuples(
            fnx.shell_layout(
                graph,
                nlist=shells,
                rotate=0.0,
                scale=2.0,
                center=[1.0, 1.0],
                store_pos_as="pos",
            )
        )

    _assert_positions_close(actual, expected)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_spectral_layout_matches_networkx_without_delegation():
    graph = fnx.path_graph(5)
    graph.add_edge(0, 2, weight=2)
    expected = _as_tuples(
        nx.spectral_layout(
            _to_nx(graph),
            weight="weight",
            scale=2,
            center=[1.0, -1.0],
        )
    )
    directed = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    expected_directed = _as_tuples(
        nx.spectral_layout(
            nx.DiGraph([(0, 1), (1, 2), (2, 0)]),
            weight=None,
            scale=1.5,
            center=[-1.0, 2.0],
        )
    )

    with mock.patch(
        "networkx.spectral_layout",
        side_effect=AssertionError("NetworkX spectral_layout should not be used"),
    ):
        actual = _as_tuples(
            fnx.spectral_layout(
                graph,
                weight="weight",
                scale=2,
                center=[1.0, -1.0],
                store_pos_as="pos",
            )
        )
        actual_directed = _as_tuples(
            fnx.spectral_layout(
                directed,
                weight=None,
                scale=1.5,
                center=[-1.0, 2.0],
            )
        )

    _assert_positions_close(actual, expected)
    _assert_positions_close(actual_directed, expected_directed)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_spectral_layout_tuple_labels_match_networkx_without_delegation():
    mapping = {node: ("spectral", node) for node in range(5)}
    graph = fnx.relabel_nodes(fnx.path_graph(5), mapping)
    graph.add_edge(mapping[0], mapping[2], weight=2)
    expected_graph = nx.relabel_nodes(nx.path_graph(5), mapping)
    expected_graph.add_edge(mapping[0], mapping[2], weight=2)
    expected = _as_tuples(
        nx.spectral_layout(
            expected_graph,
            weight="weight",
            scale=2,
            center=[1.0, -1.0],
        )
    )

    with mock.patch(
        "networkx.spectral_layout",
        side_effect=AssertionError("NetworkX spectral_layout should not be used"),
    ):
        actual = _as_tuples(
            fnx.spectral_layout(
                graph,
                weight="weight",
                scale=2,
                center=[1.0, -1.0],
                store_pos_as="pos",
            )
        )

    _assert_positions_close(actual, expected)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_spring_layout_matches_networkx_without_delegation():
    graph = fnx.cycle_graph(5)
    graph.add_edge(0, 2, weight=2)
    expected = _as_tuples(
        nx.spring_layout(
            _to_nx(graph),
            seed=7,
            iterations=20,
            weight="weight",
            scale=2,
            center=[1.0, -1.0],
        )
    )
    expected_fruchterman = _as_tuples(
        nx.fruchterman_reingold_layout(
            _to_nx(graph),
            seed=7,
            iterations=20,
            weight="weight",
            scale=2,
            center=[1.0, -1.0],
        )
    )

    fixed_graph = fnx.path_graph(4)
    initial_pos = {0: np.array([0.0, 0.0]), 3: np.array([1.0, 1.0])}
    expected_fixed = _as_tuples(
        nx.spring_layout(
            nx.path_graph(4),
            pos=initial_pos,
            fixed=[0, 3],
            seed=3,
            iterations=5,
        )
    )
    expected_energy = _as_tuples(
        nx.spring_layout(
            nx.path_graph(4),
            seed=4,
            iterations=3,
            method="energy",
        )
    )

    with (
        mock.patch(
            "networkx.spring_layout",
            side_effect=AssertionError("NetworkX spring_layout should not be used"),
        ),
        mock.patch(
            "networkx.fruchterman_reingold_layout",
            side_effect=AssertionError(
                "NetworkX fruchterman_reingold_layout should not be used"
            ),
        ),
    ):
        actual = _as_tuples(
            fnx.spring_layout(
                graph,
                seed=7,
                iterations=20,
                weight="weight",
                scale=2,
                center=[1.0, -1.0],
                store_pos_as="pos",
            )
        )
        actual_fruchterman = _as_tuples(
            fnx.fruchterman_reingold_layout(
                graph,
                seed=7,
                iterations=20,
                weight="weight",
                scale=2,
                center=[1.0, -1.0],
            )
        )
        actual_fixed = _as_tuples(
            fnx.spring_layout(
                fixed_graph,
                pos=initial_pos,
                fixed=[0, 3],
                seed=3,
                iterations=5,
            )
        )
        actual_energy = _as_tuples(
            fnx.spring_layout(
                fnx.path_graph(4),
                seed=4,
                iterations=3,
                method="energy",
            )
        )

    _assert_positions_close(actual, expected)
    _assert_positions_close(actual_fruchterman, expected_fruchterman)
    _assert_positions_close(actual_fixed, expected_fixed)
    _assert_positions_close(actual_energy, expected_energy)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_spring_layout_tuple_labels_match_networkx_without_delegation():
    mapping = {node: ("spring", node) for node in range(5)}
    graph = fnx.relabel_nodes(fnx.cycle_graph(5), mapping)
    graph.add_edge(mapping[0], mapping[2], weight=2)
    expected_graph = nx.relabel_nodes(nx.cycle_graph(5), mapping)
    expected_graph.add_edge(mapping[0], mapping[2], weight=2)
    expected = _as_tuples(
        nx.spring_layout(
            expected_graph,
            seed=7,
            iterations=20,
            weight="weight",
            scale=2,
            center=[1.0, -1.0],
        )
    )

    with (
        mock.patch(
            "networkx.spring_layout",
            side_effect=AssertionError("NetworkX spring_layout should not be used"),
        ),
        mock.patch(
            "networkx.fruchterman_reingold_layout",
            side_effect=AssertionError(
                "NetworkX fruchterman_reingold_layout should not be used"
            ),
        ),
    ):
        actual = _as_tuples(
            fnx.spring_layout(
                graph,
                seed=7,
                iterations=20,
                weight="weight",
                scale=2,
                center=[1.0, -1.0],
                store_pos_as="pos",
            )
        )

    _assert_positions_close(actual, expected)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_kamada_kawai_layout_matches_networkx_without_delegation():
    graph = fnx.path_graph(4)
    graph.add_edge(0, 2, weight=2)
    expected = _as_tuples(
        nx.kamada_kawai_layout(
            _to_nx(graph),
            weight="weight",
            scale=2,
            center=[1.0, -1.0],
        )
    )

    custom_dist = {
        0: {0: 0, 1: 1, 2: 2},
        1: {0: 1, 1: 0, 2: 1},
        2: {0: 2, 1: 1, 2: 0},
    }
    initial_pos = {
        0: np.array([0.0, 0.0]),
        1: np.array([0.5, 0.5]),
        2: np.array([1.0, 0.0]),
    }
    expected_custom = _as_tuples(
        nx.kamada_kawai_layout(
            nx.path_graph(3),
            dist=custom_dist,
            pos=initial_pos,
            scale=1.5,
            center=[-1.0, 2.0],
        )
    )

    with mock.patch(
        "networkx.kamada_kawai_layout",
        side_effect=AssertionError("NetworkX kamada_kawai_layout should not be used"),
    ):
        actual = _as_tuples(
            fnx.kamada_kawai_layout(
                graph,
                weight="weight",
                scale=2,
                center=[1.0, -1.0],
                store_pos_as="pos",
            )
        )
        actual_custom = _as_tuples(
            fnx.kamada_kawai_layout(
                fnx.path_graph(3),
                dist=custom_dist,
                pos=initial_pos,
                scale=1.5,
                center=[-1.0, 2.0],
            )
        )

    _assert_positions_close(actual, expected)
    _assert_positions_close(actual_custom, expected_custom)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_kamada_kawai_layout_tuple_labels_match_networkx_without_delegation():
    mapping = {node: ("kamada", node) for node in range(4)}
    graph = fnx.relabel_nodes(fnx.path_graph(4), mapping)
    graph.add_edge(mapping[0], mapping[2], weight=2)
    expected_graph = nx.relabel_nodes(nx.path_graph(4), mapping)
    expected_graph.add_edge(mapping[0], mapping[2], weight=2)
    expected = _as_tuples(
        nx.kamada_kawai_layout(
            expected_graph,
            weight="weight",
            scale=2,
            center=[1.0, -1.0],
        )
    )

    with mock.patch(
        "networkx.kamada_kawai_layout",
        side_effect=AssertionError("NetworkX kamada_kawai_layout should not be used"),
    ):
        actual = _as_tuples(
            fnx.kamada_kawai_layout(
                graph,
                weight="weight",
                scale=2,
                center=[1.0, -1.0],
                store_pos_as="pos",
            )
        )

    _assert_positions_close(actual, expected)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_arf_layout_matches_networkx_without_delegation():
    graph = fnx.path_graph(4)
    expected = _as_tuples(
        nx.arf_layout(
            nx.path_graph(4),
            seed=7,
            max_iter=20,
            scaling=1.5,
            a=1.2,
        )
    )

    partial_pos = {0: np.array([0.0, 0.0])}
    expected_partial = _as_tuples(
        nx.arf_layout(
            nx.path_graph(3),
            pos=partial_pos,
            seed=5,
            max_iter=10,
        )
    )

    with mock.patch(
        "networkx.arf_layout",
        side_effect=AssertionError("NetworkX arf_layout should not be used"),
    ):
        actual = _as_tuples(
            fnx.arf_layout(
                graph,
                seed=7,
                max_iter=20,
                scaling=1.5,
                a=1.2,
                store_pos_as="pos",
            )
        )
        actual_partial = _as_tuples(
            fnx.arf_layout(
                fnx.path_graph(3),
                pos=partial_pos,
                seed=5,
                max_iter=10,
            )
        )

    _assert_positions_close(actual, expected)
    _assert_positions_close(actual_partial, expected_partial)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)

    with pytest.raises(ValueError, match="The parameter a should be larger than 1"):
        fnx.arf_layout(fnx.path_graph(2), a=1)


def test_arf_layout_tuple_labels_match_networkx_without_delegation():
    mapping = {node: ("arf", node) for node in range(4)}
    graph = fnx.relabel_nodes(fnx.path_graph(4), mapping)
    expected_graph = nx.relabel_nodes(nx.path_graph(4), mapping)
    expected = _as_tuples(
        nx.arf_layout(
            expected_graph,
            seed=7,
            max_iter=20,
            scaling=1.5,
            a=1.2,
        )
    )

    with mock.patch(
        "networkx.arf_layout",
        side_effect=AssertionError("NetworkX arf_layout should not be used"),
    ):
        actual = _as_tuples(
            fnx.arf_layout(
                graph,
                seed=7,
                max_iter=20,
                scaling=1.5,
                a=1.2,
                store_pos_as="pos",
            )
        )

    _assert_positions_close(actual, expected)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_forceatlas2_layout_matches_networkx_without_delegation():
    graph = fnx.path_graph(4)
    graph.add_edge(0, 2, weight=2)
    node_mass = {0: 2.5, 2: 3.0}
    node_size = {1: 0.1, 3: 0.2}
    expected = _as_tuples(
        nx.forceatlas2_layout(
            _to_nx(graph),
            seed=7,
            max_iter=5,
            weight="weight",
            node_mass=node_mass,
            node_size=node_size,
            distributed_action=True,
            strong_gravity=True,
            linlog=True,
        )
    )

    partial_pos = {0: np.array([0.0, 0.0]), 1: np.array([1.0, 0.5])}
    expected_partial = _as_tuples(
        nx.forceatlas2_layout(
            nx.path_graph(4),
            pos=partial_pos,
            seed=5,
            max_iter=3,
        )
    )

    with mock.patch(
        "networkx.forceatlas2_layout",
        side_effect=AssertionError("NetworkX forceatlas2_layout should not be used"),
    ):
        actual = _as_tuples(
            fnx.forceatlas2_layout(
                graph,
                seed=7,
                max_iter=5,
                weight="weight",
                node_mass=node_mass,
                node_size=node_size,
                distributed_action=True,
                strong_gravity=True,
                linlog=True,
                store_pos_as="pos",
            )
        )
        actual_partial = _as_tuples(
            fnx.forceatlas2_layout(
                fnx.path_graph(4),
                pos=partial_pos,
                seed=5,
                max_iter=3,
            )
        )

    _assert_positions_close(actual, expected)
    _assert_positions_close(actual_partial, expected_partial)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_forceatlas2_layout_empty_pos_matches_default_seeded_layout():
    graph = fnx.path_graph(4)
    expected = _as_tuples(nx.forceatlas2_layout(nx.path_graph(4), seed=5, max_iter=3))

    with mock.patch(
        "networkx.forceatlas2_layout",
        side_effect=AssertionError("NetworkX forceatlas2_layout should not be used"),
    ):
        actual = _as_tuples(
            fnx.forceatlas2_layout(
                graph,
                pos={},
                seed=5,
                max_iter=3,
            )
        )

    _assert_positions_close(actual, expected)


def test_forceatlas2_layout_tuple_labels_match_networkx_without_delegation():
    mapping = {node: ("forceatlas", node) for node in range(4)}
    graph = fnx.relabel_nodes(fnx.path_graph(4), mapping)
    graph.add_edge(mapping[0], mapping[2], weight=2)
    node_mass = {mapping[0]: 2.5, mapping[2]: 3.0}
    node_size = {mapping[1]: 0.1, mapping[3]: 0.2}
    expected_graph = nx.relabel_nodes(nx.path_graph(4), mapping)
    expected_graph.add_edge(mapping[0], mapping[2], weight=2)
    expected = _as_tuples(
        nx.forceatlas2_layout(
            expected_graph,
            seed=7,
            max_iter=5,
            weight="weight",
            node_mass=node_mass,
            node_size=node_size,
            distributed_action=True,
            strong_gravity=True,
            linlog=True,
        )
    )

    with mock.patch(
        "networkx.forceatlas2_layout",
        side_effect=AssertionError("NetworkX forceatlas2_layout should not be used"),
    ):
        actual = _as_tuples(
            fnx.forceatlas2_layout(
                graph,
                seed=7,
                max_iter=5,
                weight="weight",
                node_mass=node_mass,
                node_size=node_size,
                distributed_action=True,
                strong_gravity=True,
                linlog=True,
                store_pos_as="pos",
            )
        )

    _assert_positions_close(actual, expected)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_planar_layout_matches_networkx_without_delegation():
    graph = fnx.path_graph(4)
    expected = _as_tuples(
        nx.planar_layout(
            nx.path_graph(4),
            scale=2,
            center=[1.0, -1.0],
        )
    )
    _, embedding = nx.check_planarity(nx.cycle_graph(4))
    expected_embedding = _as_tuples(nx.planar_layout(embedding))

    with (
        mock.patch(
            "networkx.planar_layout",
            side_effect=AssertionError("NetworkX planar_layout should not be used"),
        ),
        mock.patch(
            "networkx.combinatorial_embedding_to_pos",
            side_effect=AssertionError(
                "NetworkX combinatorial_embedding_to_pos should not be used"
            ),
        ),
    ):
        actual = _as_tuples(
            fnx.planar_layout(
                graph,
                scale=2,
                center=[1.0, -1.0],
                store_pos_as="pos",
            )
        )
        actual_embedding = _as_tuples(fnx.planar_layout(embedding))

    _assert_positions_close(actual, expected)
    _assert_positions_close(actual_embedding, expected_embedding)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)

    with pytest.raises(nx.NetworkXException, match="G is not planar."):
        fnx.planar_layout(fnx.complete_graph(5))


@pytest.mark.parametrize(
    ("actual_graph", "expected_graph"),
    [
        (fnx.path_graph(5), nx.path_graph(5)),
        (fnx.cycle_graph(6), nx.cycle_graph(6)),
        (fnx.complete_graph(4), nx.complete_graph(4)),
        (fnx.wheel_graph(6), nx.wheel_graph(6)),
    ],
)
def test_planar_layout_graph_families_match_networkx_certificates(
    actual_graph,
    expected_graph,
):
    options = {"scale": 2, "center": [1.0, -1.0]}
    expected = _as_tuples(nx.planar_layout(expected_graph, **options))

    actual = _as_tuples(fnx.planar_layout(actual_graph, **options))
    _, embedding = fnx.check_planarity(actual_graph)
    from_certificate = _as_tuples(fnx.planar_layout(embedding, **options))

    _assert_positions_close(actual, expected)
    _assert_positions_close(from_certificate, expected)


def test_planar_layout_self_loop_matches_networkx_without_delegation():
    graph = fnx.cycle_graph(4)
    expected_graph = nx.cycle_graph(4)
    graph.add_edge(0, 0)
    expected_graph.add_edge(0, 0)
    options = {"scale": 2, "center": [1.0, -1.0]}
    expected = _as_tuples(nx.planar_layout(expected_graph, **options))

    with (
        mock.patch(
            "networkx.planar_layout",
            side_effect=AssertionError("NetworkX planar_layout should not be used"),
        ),
        mock.patch(
            "networkx.combinatorial_embedding_to_pos",
            side_effect=AssertionError(
                "NetworkX combinatorial_embedding_to_pos should not be used"
            ),
        ),
    ):
        actual = _as_tuples(fnx.planar_layout(graph, **options, store_pos_as="pos"))

    _assert_positions_close(actual, expected)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_planar_layout_tuple_labels_match_networkx_without_delegation():
    mapping = {node: ("cycle-node", node) for node in range(4)}
    graph = fnx.relabel_nodes(fnx.cycle_graph(4), mapping)
    expected_graph = nx.relabel_nodes(nx.cycle_graph(4), mapping)
    options = {"scale": 2, "center": [1.0, -1.0]}
    expected = _as_tuples(nx.planar_layout(expected_graph, **options))

    with (
        mock.patch(
            "networkx.planar_layout",
            side_effect=AssertionError("NetworkX planar_layout should not be used"),
        ),
        mock.patch(
            "networkx.combinatorial_embedding_to_pos",
            side_effect=AssertionError(
                "NetworkX combinatorial_embedding_to_pos should not be used"
            ),
        ),
    ):
        actual = _as_tuples(fnx.planar_layout(graph, **options, store_pos_as="pos"))

    _assert_positions_close(actual, expected)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_planar_layout_edge_subdivision_matches_networkx_without_delegation():
    graph = fnx.cycle_graph(4)
    expected_graph = nx.cycle_graph(4)
    graph.remove_edge(0, 1)
    expected_graph.remove_edge(0, 1)
    graph.add_edges_from([(0, "subdivision-node"), ("subdivision-node", 1)])
    expected_graph.add_edges_from([(0, "subdivision-node"), ("subdivision-node", 1)])
    options = {"scale": 2, "center": [1.0, -1.0]}
    expected = _as_tuples(nx.planar_layout(expected_graph, **options))

    with (
        mock.patch(
            "networkx.planar_layout",
            side_effect=AssertionError("NetworkX planar_layout should not be used"),
        ),
        mock.patch(
            "networkx.combinatorial_embedding_to_pos",
            side_effect=AssertionError(
                "NetworkX combinatorial_embedding_to_pos should not be used"
            ),
        ),
    ):
        actual = _as_tuples(fnx.planar_layout(graph, **options, store_pos_as="pos"))

    _assert_positions_close(actual, expected)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_planar_layout_disconnected_components_match_networkx_without_delegation():
    graph = fnx.Graph()
    expected_graph = nx.Graph()
    component_edges = [
        (0, 1),
        (1, 2),
        (2, 0),
        ("path-a", "path-b"),
        ("path-b", "path-c"),
    ]
    graph.add_edges_from(component_edges)
    expected_graph.add_edges_from(component_edges)
    options = {"scale": 2, "center": [1.0, -1.0]}
    expected = _as_tuples(nx.planar_layout(expected_graph, **options))

    with (
        mock.patch(
            "networkx.planar_layout",
            side_effect=AssertionError("NetworkX planar_layout should not be used"),
        ),
        mock.patch(
            "networkx.combinatorial_embedding_to_pos",
            side_effect=AssertionError(
                "NetworkX combinatorial_embedding_to_pos should not be used"
            ),
        ),
    ):
        actual = _as_tuples(fnx.planar_layout(graph, **options, store_pos_as="pos"))

    _assert_positions_close(actual, expected)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_planar_layout_uses_check_planarity_certificate(monkeypatch):
    graph = fnx.path_graph(4)
    _, embedding = nx.check_planarity(nx.path_graph(4))
    calls = []

    def fake_check_planarity(candidate):
        calls.append(candidate)
        return True, embedding

    monkeypatch.setattr(fnx, "check_planarity", fake_check_planarity)

    actual = _as_tuples(fnx.planar_layout(graph))
    expected = _as_tuples(fnx.planar_layout(embedding))

    assert calls == [graph]
    _assert_positions_close(actual, expected)


def test_layout_helpers_store_positions_without_delegation():
    graph = fnx.path_graph(3)

    with mock.patch(
        "networkx.circular_layout",
        side_effect=AssertionError("NetworkX circular_layout should not be used"),
    ):
        pos = fnx.circular_layout(graph, store_pos_as="pos")

    for node, coords in pos.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_layout_dimension_errors_match_networkx():
    with pytest.raises(ValueError, match="cannot handle dimensions < 2"):
        fnx.circular_layout(fnx.path_graph(2), dim=1)

    with pytest.raises(ValueError, match="can only handle 2 dimensions"):
        fnx.shell_layout(fnx.path_graph(2), dim=3)


def test_multipartite_layout_matches_networkx_without_delegation():
    graph = fnx.Graph()
    graph.add_node("a", subset=0)
    graph.add_node("b", subset=1)
    graph.add_node("c", subset=1)
    graph.add_node("d", subset=2)
    graph.add_edges_from([("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")])

    expected_graph = nx.Graph()
    expected_graph.add_node("a", subset=0)
    expected_graph.add_node("b", subset=1)
    expected_graph.add_node("c", subset=1)
    expected_graph.add_node("d", subset=2)
    expected_graph.add_edges_from([("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")])

    expected = _as_tuples(nx.multipartite_layout(expected_graph))
    explicit_layers = {"left": ["a"], "middle": ["b", "c"], "right": ["d"]}
    expected_explicit = _as_tuples(
        nx.multipartite_layout(
            expected_graph,
            subset_key=explicit_layers,
            align="horizontal",
            scale=2,
            center=[1.0, -1.0],
        )
    )

    with mock.patch(
        "networkx.multipartite_layout",
        side_effect=AssertionError("NetworkX multipartite_layout should not be used"),
    ):
        actual = _as_tuples(fnx.multipartite_layout(graph))
        actual_explicit = _as_tuples(
            fnx.multipartite_layout(
                graph,
                subset_key=explicit_layers,
                align="horizontal",
                scale=2,
                center=[1.0, -1.0],
            )
        )

    _assert_positions_close(actual, expected)
    _assert_positions_close(actual_explicit, expected_explicit)


def test_multipartite_layout_tuple_labels_match_networkx_without_delegation():
    left = ("multipartite", "left")
    middle_a = ("multipartite", "middle-a")
    middle_b = ("multipartite", "middle-b")
    right = ("multipartite", "right")
    edges = [(left, middle_a), (left, middle_b), (middle_a, right), (middle_b, right)]

    graph = fnx.Graph()
    graph.add_node(left, subset=0)
    graph.add_node(middle_a, subset=1)
    graph.add_node(middle_b, subset=1)
    graph.add_node(right, subset=2)
    graph.add_edges_from(edges)

    expected_graph = nx.Graph()
    expected_graph.add_node(left, subset=0)
    expected_graph.add_node(middle_a, subset=1)
    expected_graph.add_node(middle_b, subset=1)
    expected_graph.add_node(right, subset=2)
    expected_graph.add_edges_from(edges)

    expected = _as_tuples(nx.multipartite_layout(expected_graph))
    explicit_layers = {"left": [left], "middle": [middle_a, middle_b], "right": [right]}
    expected_explicit = _as_tuples(
        nx.multipartite_layout(
            expected_graph,
            subset_key=explicit_layers,
            align="horizontal",
            scale=2,
            center=[1.0, -1.0],
        )
    )

    with mock.patch(
        "networkx.multipartite_layout",
        side_effect=AssertionError("NetworkX multipartite_layout should not be used"),
    ):
        actual = _as_tuples(fnx.multipartite_layout(graph, store_pos_as="pos"))
        actual_explicit = _as_tuples(
            fnx.multipartite_layout(
                graph,
                subset_key=explicit_layers,
                align="horizontal",
                scale=2,
                center=[1.0, -1.0],
            )
        )

    _assert_positions_close(actual, expected)
    _assert_positions_close(actual_explicit, expected_explicit)
    for node, coords in actual.items():
        assert np.allclose(graph.nodes[node]["pos"], coords)


def test_multipartite_layout_error_paths_match_networkx_without_delegation():
    missing_subset_graph = fnx.Graph()
    missing_subset_graph.add_node("a", subset=0)
    missing_subset_graph.add_node("b")
    expected_missing_subset_graph = nx.Graph()
    expected_missing_subset_graph.add_node("a", subset=0)
    expected_missing_subset_graph.add_node("b")

    incomplete_graph = fnx.path_graph(3)
    expected_incomplete_graph = nx.path_graph(3)
    incomplete_layers = {"left": [0], "right": [1]}

    missing_subset_message = "all nodes need a subset_key attribute: subset"
    incomplete_layers_message = "all nodes must be in one subset of `subset_key` dict"
    bad_align_message = "align must be either vertical or horizontal."

    with pytest.raises(nx.NetworkXError, match=missing_subset_message):
        nx.multipartite_layout(expected_missing_subset_graph)
    with pytest.raises(nx.NetworkXError, match=incomplete_layers_message):
        nx.multipartite_layout(expected_incomplete_graph, subset_key=incomplete_layers)
    with pytest.raises(ValueError, match=bad_align_message):
        nx.multipartite_layout(nx.Graph(), align="diagonal")

    with mock.patch(
        "networkx.multipartite_layout",
        side_effect=AssertionError("NetworkX multipartite_layout should not be used"),
    ):
        with pytest.raises(fnx.NetworkXError, match=missing_subset_message):
            fnx.multipartite_layout(missing_subset_graph)
        with pytest.raises(fnx.NetworkXError, match=incomplete_layers_message):
            fnx.multipartite_layout(incomplete_graph, subset_key=incomplete_layers)
        with pytest.raises(ValueError, match=bad_align_message):
            fnx.multipartite_layout(fnx.Graph(), align="diagonal")


def test_forceatlas2_layout_accepts_backend_keyword_surface():
    """Public forceatlas2_layout must accept backend / backend_kwargs.

    Upstream NetworkX accepts both kwargs and raises ImportError when
    a non-installed backend is requested. fnx must match the public
    keyword contract instead of TypeError'ing on backend/backend_kwargs.
    """
    G = fnx.path_graph(4)
    # Default + explicit "networkx" both run the in-tree implementation.
    fnx.forceatlas2_layout(G)
    fnx.forceatlas2_layout(G, backend="networkx")
    fnx.forceatlas2_layout(G, backend=None)
    # Unknown backend → ImportError (matches nx dispatch path).
    nG = nx.path_graph(4)
    with pytest.raises(ImportError):
        fnx.forceatlas2_layout(G, backend="nonexistent")
    with pytest.raises(ImportError):
        nx.forceatlas2_layout(nG, backend="nonexistent")
    # **backend_kwargs accepts arbitrary trailing kwargs without TypeError.
    fnx.forceatlas2_layout(G, foo="bar")


def test_rescale_layout_accepts_numpy_array_input():
    """Public rescale_layout helper must accept ndarray and return upstream values.

    Regression: previously the wrapper evaluated array truthiness before
    delegating, raising "The truth value of an array with more than one
    element is ambiguous", instead of running the actual rescaling logic.
    """
    arr = np.array([[3.0, 4.0]])
    fnx_out = fnx.rescale_layout(arr)
    nx_out = nx.rescale_layout(arr)
    np.testing.assert_allclose(fnx_out, nx_out)
    # Two-row case used in the bead description
    arr2 = np.array([[0.0, 2.0], [2.0, 0.0]])
    np.testing.assert_allclose(fnx.rescale_layout(arr2), nx.rescale_layout(arr2))
    # scale kwarg parity
    np.testing.assert_allclose(
        fnx.rescale_layout(arr2, scale=5),
        nx.rescale_layout(arr2, scale=5),
    )


def test_rescale_layout_preserves_integer_array_dtype_error_contract():
    """Integer-array input must reach the same UFuncTypeError as upstream.

    Regression: rescale_layout previously failed too early on integer
    coordinate arrays with an ambiguous truthiness ValueError, instead of
    matching upstream's dtype-sensitive UFuncTypeError raised inside the
    in-place subtract.
    """
    arr = np.array([[0, 2], [2, 0]])
    with pytest.raises(np._core._exceptions._UFuncOutputCastingError):
        nx.rescale_layout(arr)
    with pytest.raises(np._core._exceptions._UFuncOutputCastingError):
        fnx.rescale_layout(arr)


def test_rescale_layout_dict_matches_networkx():
    pos = {"a": np.array([0.0, 0.0]), "b": np.array([2.0, 4.0]), "c": np.array([4.0, 8.0])}
    expected = _as_tuples(nx.rescale_layout_dict(pos, scale=3))

    with mock.patch(
        "networkx.rescale_layout_dict",
        side_effect=AssertionError("NetworkX rescale_layout_dict should not be used"),
    ):
        actual = _as_tuples(fnx.rescale_layout_dict(pos, scale=3))

    _assert_positions_close(actual, expected)


@pytest.mark.parametrize(
    "pos",
    [
        np.array([]),
        np.empty((0, 2)),
        np.empty((0, 3), dtype=np.float32),
    ],
)
def test_rescale_layout_empty_arrays_preserve_networkx_error_contract_without_delegation(
    pos,
):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with pytest.raises(Exception) as expected_exc:
            nx.rescale_layout(pos.copy())

    with mock.patch(
        "networkx.rescale_layout",
        side_effect=AssertionError("NetworkX rescale_layout should not be used"),
    ):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            with pytest.raises(Exception) as actual_exc:
                fnx.rescale_layout(pos.copy())

    assert type(actual_exc.value).__name__ == type(expected_exc.value).__name__
    assert str(actual_exc.value) == str(expected_exc.value)


def test_rescale_layout_dict_tuple_keys_match_networkx_without_delegation():
    pos = {
        ("rescale", "origin"): np.array([0.0, 0.0]),
        ("rescale", "middle"): np.array([2.0, 4.0]),
        ("rescale", "far"): np.array([4.0, 8.0]),
    }
    expected = _as_tuples(nx.rescale_layout_dict(pos, scale=3))

    with mock.patch(
        "networkx.rescale_layout_dict",
        side_effect=AssertionError("NetworkX rescale_layout_dict should not be used"),
    ):
        actual = _as_tuples(fnx.rescale_layout_dict(pos, scale=3))

    _assert_positions_close(actual, expected)


def test_layout_module_has_no_direct_delegation_helper():
    import inspect

    import franken_networkx.drawing.layout as layout

    assert "_delegate_layout" not in inspect.getsource(layout)


def test_force_directed_layout_exports_are_usable():
    graph = fnx.cycle_graph(5)

    spring = _as_tuples(fnx.fruchterman_reingold_layout(graph, seed=7))
    expected_spring = _as_tuples(
        nx.fruchterman_reingold_layout(nx.cycle_graph(5), seed=7)
    )
    _assert_positions_close(spring, expected_spring)

    arf = _as_tuples(fnx.arf_layout(graph, seed=7, max_iter=20))
    expected_arf = _as_tuples(nx.arf_layout(nx.cycle_graph(5), seed=7, max_iter=20))
    _assert_positions_close(arf, expected_arf)

    forceatlas = _as_tuples(fnx.forceatlas2_layout(graph, seed=7, max_iter=10))
    expected_forceatlas = _as_tuples(nx.forceatlas2_layout(nx.cycle_graph(5), seed=7, max_iter=10))
    _assert_positions_close(forceatlas, expected_forceatlas)
