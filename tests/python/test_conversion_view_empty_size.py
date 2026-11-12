"""Regression coverage for conversion live-view empty and size semantics."""

import networkx as nx
import pytest

import franken_networkx as fnx


def _expect_equal(actual, expected):
    if actual != expected:
        raise AssertionError(f"{actual!r} != {expected!r}")


def _edge_list(graph):
    if graph.is_multigraph():
        return list(graph.edges(keys=True))
    return list(graph.edges)


@pytest.mark.parametrize(
    ("direction", "fnx_ctor", "nx_ctor"),
    [
        ("to_directed", fnx.Graph, nx.Graph),
        ("to_undirected", fnx.DiGraph, nx.DiGraph),
        ("to_directed", fnx.MultiGraph, nx.MultiGraph),
        ("to_undirected", fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_empty_conversion_live_view_accessors_match_networkx(direction, fnx_ctor, nx_ctor):
    """br-r37-c1-djc86: empty conversion views must not fall through to base views."""
    fv = getattr(fnx_ctor(), direction)(as_view=True)
    nv = getattr(nx_ctor(), direction)(as_view=True)

    _expect_equal(list(fv.nodes), list(nv.nodes))
    _expect_equal(_edge_list(fv), _edge_list(nv))
    _expect_equal(dict(fv.adj), dict(nv.adj))
    _expect_equal(fv.number_of_nodes(), nv.number_of_nodes())
    _expect_equal(fv.number_of_edges(), nv.number_of_edges())
    _expect_equal(fv.size(), nv.size())
    _expect_equal(fv.size(weight="weight"), nv.size(weight="weight"))
    _expect_equal(type(fv.size(weight="weight")), type(nv.size(weight="weight")))


@pytest.mark.parametrize(
    ("direction", "fnx_ctor", "nx_ctor", "edges"),
    [
        (
            "to_directed",
            fnx.Graph,
            nx.Graph,
            [("a", "b", {"weight": 2}), ("b", "c", {"weight": 3})],
        ),
        (
            "to_undirected",
            fnx.DiGraph,
            nx.DiGraph,
            [
                ("a", "b", {"weight": 2}),
                ("b", "a", {"weight": 5}),
                ("b", "c", {"weight": 3}),
            ],
        ),
        (
            "to_directed",
            fnx.MultiGraph,
            nx.MultiGraph,
            [
                ("a", "b", "x", {"weight": 2}),
                ("a", "b", "y", {"weight": 3}),
                ("b", "c", "z", {}),
            ],
        ),
        (
            "to_undirected",
            fnx.MultiDiGraph,
            nx.MultiDiGraph,
            [
                ("a", "b", "x", {"weight": 2}),
                ("b", "a", "x", {"weight": 5}),
                ("b", "c", "z", {"weight": 3}),
            ],
        ),
    ],
)
def test_conversion_live_view_weighted_size_matches_networkx(direction, fnx_ctor, nx_ctor, edges):
    """br-r37-c1-djc86: conversion views compute weighted size from the source view."""
    fg = fnx_ctor()
    ng = nx_ctor()
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)

    fv = getattr(fg, direction)(as_view=True)
    nv = getattr(ng, direction)(as_view=True)

    _expect_equal(fv.size(), nv.size())
    _expect_equal(fv.size(weight="weight"), nv.size(weight="weight"))
    _expect_equal(type(fv.size(weight="weight")), type(nv.size(weight="weight")))
