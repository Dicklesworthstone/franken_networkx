"""Closed-form invariants for undirected effective resistance."""

from __future__ import annotations

import math

import franken_networkx as fnx
import numpy as np
import pytest

pytest.importorskip("scipy")


def _laplacian_pinv_resistance(graph, source, target):
    nodes = list(graph)
    index = {node: position for position, node in enumerate(nodes)}
    laplacian = np.zeros((len(nodes), len(nodes)))
    for source_node, target_node in graph.edges():
        source_index = index[source_node]
        target_index = index[target_node]
        laplacian[source_index, source_index] += 1
        laplacian[target_index, target_index] += 1
        laplacian[source_index, target_index] -= 1
        laplacian[target_index, source_index] -= 1
    pseudo_inverse = np.linalg.pinv(laplacian, hermitian=True)
    source_index = index[source]
    target_index = index[target]
    return (
        pseudo_inverse[source_index, source_index]
        + pseudo_inverse[target_index, target_index]
        - 2 * pseudo_inverse[source_index, target_index]
    )


@pytest.mark.parametrize("size", range(2, 7))
@pytest.mark.parametrize("source,target", [(0, 1), (0, -1)])
def test_resistance_matches_laplacian_pseudoinverse(size, source, target):
    graph = fnx.path_graph(size)
    target = size - 1 if target == -1 else target
    observed = fnx.resistance_distance(graph, source, target)
    expected = _laplacian_pinv_resistance(graph, source, target)
    assert math.isclose(observed, expected, rel_tol=1e-12, abs_tol=1e-12)
    assert math.isclose(observed, fnx.resistance_distance(graph, target, source))


@pytest.mark.parametrize("size", range(3, 8))
@pytest.mark.parametrize("source,target", [(0, 1), (0, -1), (1, -1)])
def test_tree_and_complete_graph_closed_forms(size, source, target):
    target = size - 1 if target == -1 else target
    tree = fnx.path_graph(size)
    assert fnx.resistance_distance(tree, source, target) == abs(source - target)

    complete = fnx.complete_graph(size)
    assert math.isclose(
        fnx.resistance_distance(complete, source, target),
        2 / size,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )
