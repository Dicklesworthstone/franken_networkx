"""Assortativity parity + the degree-assortativity == Pearson invariant.

Degree assortativity is, by definition, the Pearson correlation coefficient of
the degree sequence over the graph's edges, so
``degree_assortativity_coefficient`` and
``degree_pearson_correlation_coefficient`` must agree exactly — an oracle-free
invariant. This also pins numeric/attribute assortativity and
average_neighbor_degree against networkx.

No mocks: real fnx and real networkx on attributed graphs.
"""

from __future__ import annotations

import math
import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _attributed(seed):
    r = random.Random(seed)
    n = r.randint(8, 14)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    for node in range(n):
        for g in (fg, ng):
            g.nodes[node]["c"] = node % 3
            g.nodes[node]["val"] = float(node)
    return fg, ng, n


def _close(a, b, tol=1e-6):
    if math.isnan(a) and math.isnan(b):
        return True
    return abs(a - b) <= tol


@pytest.mark.parametrize("seed", range(30))
def test_degree_assortativity_equals_pearson_and_matches_nx(seed):
    fg, ng, n = _attributed(seed)
    if fg.number_of_edges() < 2:
        pytest.skip("too few edges")
    fa = fnx.degree_assortativity_coefficient(fg)
    na = nx.degree_assortativity_coefficient(ng)
    assert _close(fa, na, 1e-7)
    fp = fnx.degree_pearson_correlation_coefficient(fg)
    assert _close(fp, nx.degree_pearson_correlation_coefficient(ng), 1e-7)
    # Invariant: degree assortativity IS the Pearson correlation of degrees.
    assert _close(fa, fp)


@pytest.mark.parametrize("seed", range(30))
def test_numeric_and_attribute_assortativity(seed):
    fg, ng, n = _attributed(seed)
    if fg.number_of_edges() < 2:
        pytest.skip("too few edges")
    assert _close(
        fnx.numeric_assortativity_coefficient(fg, "val"),
        nx.numeric_assortativity_coefficient(ng, "val"),
        1e-7,
    )
    assert _close(
        fnx.attribute_assortativity_coefficient(fg, "c"),
        nx.attribute_assortativity_coefficient(ng, "c"),
        1e-7,
    )


@pytest.mark.parametrize("seed", range(30))
def test_average_neighbor_degree(seed):
    fg, ng, n = _attributed(seed)
    fand = {k: round(v, 6) for k, v in fnx.average_neighbor_degree(fg).items()}
    nand = {k: round(v, 6) for k, v in nx.average_neighbor_degree(ng).items()}
    assert fand == nand


def _weighted_pair():
    """Non-regular and weighted, so neither coefficient collapses to NaN."""
    fg, ng = fnx.Graph(), nx.Graph()
    for u, v, w in [(0, 1, 5), (1, 2, 1), (2, 3, 9), (3, 0, 1), (0, 2, 3)]:
        fg.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)
    return fg, ng


@pytest.mark.parametrize("x", ["out", "in"])
@pytest.mark.parametrize("y", ["out", "in"])
def test_directed_degree_assortativity_x_y(x, y):
    """The x/y parameters select four distinct directed coefficients.

    Nothing in this file builds a DiGraph, so all four paths were unexercised;
    they give four different values on the same graph.
    """
    d = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (0, 2), (3, 0)])
    nd = nx.DiGraph([(0, 1), (1, 2), (2, 0), (0, 2), (3, 0)])
    assert _close(
        fnx.degree_assortativity_coefficient(d, x=x, y=y),
        nx.degree_assortativity_coefficient(nd, x=x, y=y),
        1e-7,
    )


def test_the_four_directed_settings_are_distinct():
    """Guards the test above: parity on four aliases of one value proves little."""
    d = fnx.DiGraph([(0, 1), (1, 2), (2, 0), (0, 2), (3, 0)])
    values = {
        (x, y): round(fnx.degree_assortativity_coefficient(d, x=x, y=y), 9)
        for x in ("out", "in")
        for y in ("out", "in")
    }
    assert len(set(values.values())) == 4


def test_weight_parameter_changes_both_coefficients():
    """`weight` is untested, and parity alone could not see it being ignored."""
    fg, ng = _weighted_pair()

    weighted = fnx.degree_assortativity_coefficient(fg, weight="weight")
    assert _close(weighted, nx.degree_assortativity_coefficient(ng, weight="weight"), 1e-7)
    # ...and it is genuinely a different number from the unweighted coefficient.
    assert not _close(weighted, fnx.degree_assortativity_coefficient(fg))

    weighted_neighbours = fnx.average_neighbor_degree(fg, weight="weight")
    assert {k: round(v, 9) for k, v in weighted_neighbours.items()} == {
        k: round(v, 9) for k, v in nx.average_neighbor_degree(ng, weight="weight").items()
    }
    assert weighted_neighbours != fnx.average_neighbor_degree(fg)


@pytest.mark.parametrize("seed", range(30))
def test_average_neighbor_degree_nodes_subset(seed):
    """The `nodes` parameter restricts the result and was never passed."""
    fg, ng, _ = _attributed(seed)
    subset = [0, 1]

    restricted = fnx.average_neighbor_degree(fg, nodes=subset)
    assert set(restricted) == set(subset)
    assert {k: round(v, 9) for k, v in restricted.items()} == {
        k: round(v, 9) for k, v in nx.average_neighbor_degree(ng, nodes=subset).items()
    }
    assert restricted != fnx.average_neighbor_degree(fg)
