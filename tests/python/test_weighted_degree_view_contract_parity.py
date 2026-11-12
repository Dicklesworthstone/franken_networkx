"""Differential lock for br-r37-c1-z4iod — ``G.degree(weight=...)`` is a VIEW.

networkx returns a DegreeView from the weighted accessor. On Graph and DiGraph
fnx returned a raw ``generator`` / ``zip``, which breaks three contracts at
once, the first of them silently::

    deg = G.degree(weight='w')
    total = sum(d for _, d in deg)
    top   = max(deg, key=lambda kv: kv[1])   # empty: the generator is spent

    len(G.degree(weight='w'))                # TypeError: zip has no len()
    type(G.degree(weight='w')).__name__      # 'zip', not 'DiDegreeView'

MultiGraph and MultiDiGraph already returned proper views from the same
accessor with the same argument, so two of the four family members were the
in-tree control.

Re-iterability is asserted by consuming the view TWICE and requiring the same
answer both times — the assertion the old behaviour actually fails. A test that
iterated once would have passed against a spent generator.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
DIRECTED = ["DiGraph", "MultiDiGraph"]
# int / float / absent weights take different native accumulators.
WEIGHT_KINDS = ["int", "float", "missing"]


def _build(lib, cls_name, weight_kind):
    graph = getattr(lib, cls_name)()
    graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
    graph.add_edge(3, 3)  # self-loop: counted twice in an undirected degree
    graph.add_node(7)  # isolated
    if weight_kind != "missing":
        for u, v in [(0, 1), (1, 2), (2, 3), (3, 3)]:
            value = (u + v) if weight_kind == "int" else (u + v) / 2.0
            if graph.is_multigraph():
                graph[u][v][0]["w"] = value
            else:
                graph[u][v]["w"] = value
    return graph


def _pair(cls_name, weight_kind):
    return _build(nx, cls_name, weight_kind), _build(fnx, cls_name, weight_kind)


def _accessors(cls_name):
    accessors = {"degree": lambda g: g.degree(weight="w")}
    if cls_name in DIRECTED:
        accessors["in_degree"] = lambda g: g.in_degree(weight="w")
        accessors["out_degree"] = lambda g: g.out_degree(weight="w")
    return accessors


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("weight_kind", WEIGHT_KINDS)
def test_weighted_degree_view_is_reiterable(cls_name, weight_kind):
    """The defect: the second pass was silently empty."""
    gnx, gfx = _pair(cls_name, weight_kind)
    for name, accessor in _accessors(cls_name).items():
        view_nx, view_fx = accessor(gnx), accessor(gfx)
        first_nx, second_nx = list(view_nx), list(view_nx)
        first_fx, second_fx = list(view_fx), list(view_fx)
        assert first_fx == first_nx, name
        assert second_fx == second_nx, name
        assert second_fx == first_fx, f"{name}: view was one-shot"


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("weight_kind", WEIGHT_KINDS)
def test_weighted_degree_view_supports_len_and_names_its_class(cls_name, weight_kind):
    gnx, gfx = _pair(cls_name, weight_kind)
    for name, accessor in _accessors(cls_name).items():
        view_nx, view_fx = accessor(gnx), accessor(gfx)
        assert type(view_fx).__name__ == type(view_nx).__name__, name
        assert len(view_fx) == len(view_nx), name
        # len() must not consume it either.
        assert list(view_fx) == list(view_nx), name


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("weight_kind", WEIGHT_KINDS)
def test_weighted_degree_view_mapping_contracts(cls_name, weight_kind):
    """dict(), indexing and membership, each after a prior full iteration."""
    gnx, gfx = _pair(cls_name, weight_kind)
    for name, accessor in _accessors(cls_name).items():
        view_nx, view_fx = accessor(gnx), accessor(gfx)
        list(view_nx), list(view_fx)  # spend one pass first
        assert dict(view_fx) == dict(view_nx), name
        for node in (0, 3, 7):
            assert view_fx[node] == view_nx[node], (name, node)
        assert ((0, view_nx[0]) in view_fx) == ((0, view_nx[0]) in view_nx), name
        assert (0 in view_fx) == (0 in view_nx), name


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("weight_kind", WEIGHT_KINDS)
def test_weighted_values_are_identical_to_networkx(cls_name, weight_kind):
    """Self-loops and isolated nodes are where weighted degree usually differs."""
    gnx, gfx = _pair(cls_name, weight_kind)
    for name, accessor in _accessors(cls_name).items():
        assert list(accessor(gfx)) == list(accessor(gnx)), name
        assert sum(d for _, d in accessor(gfx)) == sum(d for _, d in accessor(gnx)), name


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("weight_kind", WEIGHT_KINDS)
def test_unweighted_and_single_node_paths_are_unchanged(cls_name, weight_kind):
    """The neighbouring forms must not have been dragged along.

    A single-node weighted call returns a NUMBER in networkx, not a view, and
    the unweighted view was correct all along.
    """
    gnx, gfx = _pair(cls_name, weight_kind)
    assert gfx.degree(0, weight="w") == gnx.degree(0, weight="w")
    assert isinstance(gfx.degree(0, weight="w"), (int, float))
    assert list(gfx.degree) == list(gnx.degree)
    assert type(gfx.degree).__name__ == type(gnx.degree).__name__
    assert len(gfx.degree) == len(gnx.degree)
    assert list(gfx.degree([0, 1], weight="w")) == list(gnx.degree([0, 1], weight="w"))


def test_the_reported_usage_pattern_works_end_to_end():
    """The concrete two-pass pattern from the bead.

    The second consumer is the one that broke: it saw a spent generator and
    raised ValueError("max() arg is an empty sequence"). Compared against
    networkx rather than against literals, so the expected numbers cannot
    drift away from what networkx actually computes.
    """
    results = []
    for lib in (nx, fnx):
        graph = lib.Graph()
        graph.add_edges_from([(0, 1), (1, 2)])
        graph[0][1]["w"] = 9
        deg = graph.degree(weight="w")
        total = sum(d for _, d in deg)  # first consumer
        top = max(deg, key=lambda kv: kv[1])  # second consumer
        results.append((total, top))
    assert results[1] == results[0]
    # An unweighted edge contributes networkx's default of 1, so the totals are
    # not merely equal-and-empty.
    assert results[0][0] > 0 and results[0][1][1] > 0
