"""Differential parity for pandas import/export.

Covers ``from_pandas_edgelist``, ``from_pandas_adjacency`` and
``to_pandas_adjacency`` (``to_pandas_edgelist`` already has coverage).

br-r37-c1-6xrz7
"""

from __future__ import annotations

import random

import pandas as pd
import pytest
import networkx as nx
import franken_networkx as fnx


def _graph_signature(G):
    nodes = sorted(map(str, G.nodes()))
    if G.is_directed():
        edges = sorted(
            (str(u), str(v), tuple(sorted(d.items()))) for u, v, d in G.edges(data=True)
        )
    else:
        edges = sorted(
            (tuple(sorted((str(u), str(v)))), tuple(sorted(d.items())))
            for u, v, d in G.edges(data=True)
        )
    return nodes, edges


def _edge_df(seed):
    rng = random.Random(seed)
    n = rng.randint(4, 7)
    rows = [
        (u, v, rng.randint(1, 9), rng.choice(["x", "y"]))
        for u in range(n)
        for v in range(u + 1, n)
        if rng.random() < 0.4
    ]
    return pd.DataFrame(rows, columns=["src", "dst", "weight", "kind"])


@pytest.mark.parametrize("edge_attr", [True, ["weight", "kind"], "weight"])
@pytest.mark.parametrize("seed", range(30))
def test_from_pandas_edgelist_matches_networkx(edge_attr, seed):
    df = _edge_df(seed)
    fg = fnx.from_pandas_edgelist(df, "src", "dst", edge_attr=edge_attr)
    ng = nx.from_pandas_edgelist(df, "src", "dst", edge_attr=edge_attr)
    assert _graph_signature(fg) == _graph_signature(ng)


@pytest.mark.parametrize("seed", range(20))
def test_from_pandas_edgelist_create_using_matches_networkx(seed):
    df = _edge_df(seed)
    fg = fnx.from_pandas_edgelist(df, "src", "dst", edge_attr="weight",
                                  create_using=fnx.DiGraph)
    ng = nx.from_pandas_edgelist(df, "src", "dst", edge_attr="weight",
                                 create_using=nx.DiGraph)
    assert _graph_signature(fg) == _graph_signature(ng)


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(20))
def test_pandas_adjacency_roundtrip_matches_networkx(directed, seed):
    rng = random.Random(seed)
    n = rng.randint(4, 7)
    fnx_cls, nx_cls = (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    fg = fnx_cls()
    ng = nx_cls()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and (directed or u < v) and rng.random() < 0.4:
                w = rng.randint(1, 9)
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    fadj = fnx.to_pandas_adjacency(fg)
    nadj = nx.to_pandas_adjacency(ng)
    assert fadj.sort_index().sort_index(axis=1).equals(
        nadj.sort_index().sort_index(axis=1)
    )
    fr = fnx.from_pandas_adjacency(fadj, create_using=fnx_cls)
    nr = nx.from_pandas_adjacency(nadj, create_using=nx_cls)
    assert _graph_signature(fr) == _graph_signature(nr)


def test_edgelist_roundtrip_preserves_edges():
    g = fnx.Graph()
    g.add_edge(0, 1, weight=2)
    g.add_edge(1, 2, weight=3)
    df = fnx.to_pandas_edgelist(g)
    back = fnx.from_pandas_edgelist(df, edge_attr=True)
    assert sorted(map(lambda e: tuple(sorted(e)), back.edges())) == sorted(
        map(lambda e: tuple(sorted(e)), g.edges())
    )
