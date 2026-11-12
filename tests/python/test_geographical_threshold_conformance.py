"""NetworkX parity for geographical_threshold_graph,
thresholded_random_geometric_graph, and soft_random_geometric_graph.

Covers three parity points that the position-attribute fix in
72e4acb addressed for ``random_geometric_graph`` /
``soft_random_geometric_graph``:

1. Auto-generated positions are stored as lists (NetworkX uses
   ``[seed.random() for _ in range(dim)]``).
2. User-supplied positions are preserved by identity (NetworkX uses
   ``set_node_attributes`` which does not deep-copy values).
3. With a fixed ``seed`` and no user-supplied ``pos`` / ``weight``, the
   position values themselves match NetworkX bit-for-bit, which in
   turn means the edge set matches.
"""

import pytest
import networkx as nx

import franken_networkx as fnx


GENERATORS = [
    ("geographical_threshold_graph", (5, 0.001)),
    ("thresholded_random_geometric_graph", (5, 0.5, 0.0001)),
    ("soft_random_geometric_graph", (8, 0.5)),
]

# Subset that takes a ``weight`` parameter — used for the
# user-supplied-pos identity test which holds weights constant.
WEIGHTED = {
    "geographical_threshold_graph",
    "thresholded_random_geometric_graph",
}


@pytest.mark.parametrize("name,args", GENERATORS)
def test_generated_positions_are_lists_matching_networkx(name, args):
    actual = getattr(fnx, name)(*args, seed=7)
    expected = getattr(nx, name)(*args, seed=7)

    assert isinstance(actual.nodes[0]["pos"], list)
    assert isinstance(expected.nodes[0]["pos"], list)


@pytest.mark.parametrize("name,args", GENERATORS)
def test_supplied_positions_are_preserved_by_identity(name, args):
    pos = {i: [0.1 * i, 0.2 * i] for i in range(args[0])}
    kwargs = {"pos": pos, "seed": 7}
    if name in WEIGHTED:
        kwargs["weight"] = {i: 1.0 for i in range(args[0])}

    actual = getattr(fnx, name)(*args, **kwargs)
    expected = getattr(nx, name)(*args, **kwargs)

    assert actual.nodes[0]["pos"] is pos[0]
    assert expected.nodes[0]["pos"] is pos[0]


@pytest.mark.parametrize("name,args", GENERATORS)
def test_seeded_position_values_match_networkx(name, args):
    actual = getattr(fnx, name)(*args, seed=7)
    expected = getattr(nx, name)(*args, seed=7)

    for node in expected.nodes:
        assert actual.nodes[node]["pos"] == expected.nodes[node]["pos"]


@pytest.mark.parametrize("name,args", GENERATORS)
def test_seeded_edge_set_matches_networkx(name, args):
    actual = getattr(fnx, name)(*args, seed=7)
    expected = getattr(nx, name)(*args, seed=7)

    assert sorted(actual.edges()) == sorted(expected.edges())


@pytest.mark.parametrize("p", [1, 2, 3, float("inf")])
def test_soft_random_geometric_graph_seeded_edges_match_for_each_p(p):
    """soft_random_geometric_graph must match NetworkX for every Minkowski
    ``p`` — including ``float('inf')`` (Chebyshev), which NetworkX routes
    through scipy's KDTree when scipy is available."""
    actual = fnx.soft_random_geometric_graph(40, 0.3, p=p, seed=11)
    expected = nx.soft_random_geometric_graph(40, 0.3, p=p, seed=11)

    assert sorted(actual.edges()) == sorted(expected.edges())
