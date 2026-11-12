"""NetworkX parity for geometric-generator position attributes."""

import pytest
import networkx as nx

import franken_networkx as fnx


@pytest.mark.parametrize(
    "name,args",
    [
        ("random_geometric_graph", (4, 0.5)),
        ("soft_random_geometric_graph", (4, 0.5)),
    ],
)
def test_generated_positions_are_lists_matching_networkx(name, args):
    actual = getattr(fnx, name)(*args, seed=5)
    expected = getattr(nx, name)(*args, seed=5)

    assert actual.nodes[0]["pos"] == expected.nodes[0]["pos"]
    assert isinstance(actual.nodes[0]["pos"], list)


@pytest.mark.parametrize(
    "name,args",
    [
        ("random_geometric_graph", (3, 0.5)),
        ("soft_random_geometric_graph", (3, 0.5)),
    ],
)
def test_supplied_positions_are_preserved_by_identity(name, args):
    pos = {0: [0.0, 0.0], 1: [1.0, 0.0], 2: [0.0, 1.0]}

    actual = getattr(fnx, name)(*args, pos=pos, seed=5)
    expected = getattr(nx, name)(*args, pos=pos, seed=5)

    assert actual.nodes[0]["pos"] is pos[0]
    assert expected.nodes[0]["pos"] is pos[0]

