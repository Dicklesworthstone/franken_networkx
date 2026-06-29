"""Parity for the TOP-LEVEL `adjacency_data` / `node_link_data` native paths.

br-r37-c1-9kpev: the top-level `fnx.adjacency_data` and `fnx.node_link_data`
(what `nx.adjacency_data` / `nx.node_link_data` resolve to) now route exact
simple `Graph` / `DiGraph` through the same native `_fnx.adjacency_data_simple`
/ `_fnx.node_link_data_simple` kernels used by the json_graph module wrappers,
instead of the per-edge AdjacencyView / EdgeView Python loops.

These tests pin the top-level functions to networkx and to the json_graph
module path, and confirm multigraphs still fall back.
"""

import random

import networkx as nx

import franken_networkx as fnx


def _build_pair(n, m, seed, *, directed=False, attrs=True):
    rnd = random.Random(seed)
    edges, seen = [], set()
    while len(edges) < m:
        a, b = rnd.randrange(n), rnd.randrange(n)
        if a == b:
            continue
        if directed:
            if (a, b) in seen:
                continue
        elif (a, b) in seen or (b, a) in seen:
            continue
        seen.add((a, b))
        edges.append((a, b))
    Gx = (nx.DiGraph if directed else nx.Graph)()
    Gf = (fnx.DiGraph if directed else fnx.Graph)()
    Gx.add_nodes_from(range(n))
    Gf.add_nodes_from(range(n))
    Gx.add_edges_from(edges)
    Gf.add_edges_from(edges)
    if attrs:
        for i, (u, v) in enumerate(edges):
            if i % 3 == 0:
                Gx[u][v]["weight"] = float(i)
                Gf[u][v]["weight"] = float(i)
        for node in list(Gx.nodes())[::4]:
            Gx.nodes[node]["color"] = f"c{node}"
            Gf.nodes[node]["color"] = f"c{node}"
    Gx.graph["name"] = "g"
    Gf.graph["name"] = "g"
    return Gx, Gf


def test_toplevel_adjacency_data_matches_nx_and_json_graph():
    for directed in (False, True):
        Gx, Gf = _build_pair(60, 200, 11, directed=directed)
        assert fnx.adjacency_data(Gf) == nx.adjacency_data(Gx)
        assert fnx.adjacency_data(Gf) == fnx.readwrite.json_graph.adjacency_data(Gf)


def test_toplevel_node_link_data_matches_nx_and_json_graph():
    for directed in (False, True):
        Gx, Gf = _build_pair(60, 200, 12, directed=directed)
        assert fnx.node_link_data(Gf, edges="edges") == nx.node_link_data(
            Gx, edges="edges"
        )
        assert fnx.node_link_data(
            Gf, edges="edges"
        ) == fnx.readwrite.json_graph.node_link_data(Gf, edges="edges")


def test_toplevel_node_link_data_custom_fields():
    Gx, Gf = _build_pair(50, 150, 13)
    kw = dict(source="s", target="t", name="nid", edges="E", nodes="N")
    assert fnx.node_link_data(Gf, **kw) == nx.node_link_data(Gx, **kw)


def test_toplevel_multigraph_falls_back():
    MGx = nx.MultiGraph([(0, 1), (0, 1), (1, 2)])
    MGf = fnx.MultiGraph([(0, 1), (0, 1), (1, 2)])
    assert fnx.adjacency_data(MGf) == nx.adjacency_data(MGx)
    assert fnx.node_link_data(MGf, edges="edges") == nx.node_link_data(
        MGx, edges="edges"
    )


def _build_batch_weighted(module, directed):
    # add_weighted_edges_from / add_edges_from commit edge attrs straight into
    # the native CgseValue store and leave the Python edge mirror lazy -- the
    # case the removed native *_simple kernels mis-served by reading the empty
    # mirror.
    G = (module.DiGraph if directed else module.Graph)()
    G.add_nodes_from(range(6))
    G.add_weighted_edges_from([(0, 1, 1.5), (1, 2, 2.5), (2, 3, 3.5), (3, 4, 4.5)])
    G.add_edges_from([(4, 5, {"color": "red", "cap": 7})])
    return G


def test_toplevel_batch_built_edge_attrs_survive_serialization():
    # Regression for the data-loss bug (cc, adjdataedgeattr): the native
    # adjacency_data_simple / node_link_data_simple kernels dropped EVERY edge
    # attribute on graphs built with the bulk edge APIs (the mirror is empty;
    # attrs live in the native store). Both serializers must now be byte-exact
    # with networkx, weights and all.
    for directed in (False, True):
        Gx = _build_batch_weighted(nx, directed)
        Gf = _build_batch_weighted(fnx, directed)

        adj_f = fnx.adjacency_data(Gf)
        assert adj_f == nx.adjacency_data(Gx)
        # the bug manifested as missing 'weight'/'color' keys in adjacency rows
        assert any("weight" in e for row in adj_f["adjacency"] for e in row)

        nld_f = fnx.node_link_data(Gf, edges="edges")
        assert nld_f == nx.node_link_data(Gx, edges="edges")
        assert any("weight" in e for e in nld_f["edges"])

        # json_graph module wrappers must agree with the top-level functions
        assert fnx.readwrite.json_graph.adjacency_data(Gf) == adj_f
        assert (
            fnx.readwrite.json_graph.node_link_data(Gf, edges="edges") == nld_f
        )
