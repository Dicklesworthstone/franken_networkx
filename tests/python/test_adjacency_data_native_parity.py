"""Parity for the native `adjacency_data` fast path (json_graph).

`franken_networkx.readwrite.json_graph.adjacency_data` routes exact simple
`Graph` / `DiGraph` inputs through the native `_fnx.adjacency_data_simple`
kernel, which builds the `nodes` + `adjacency` arrays in Rust (copying the
live attr dicts and appending the `id_` field) instead of walking the
per-edge AdjacencyView in Python. This pins the native output to nx's
`adjacency_data` across the shapes that exercise the kernel, and confirms
multigraphs / subclasses still fall back to the general wrapper.

Both graphs are built from an identical explicit node + edge sequence so
node-insertion order and per-node adjacency order match (otherwise nx's
original-insertion order and a reconstructed-from-edges order diverge, which
is a construction artifact, not an adjacency_data bug).
"""

import random

import networkx as nx

import franken_networkx as fnx


def _build_pair(n, m, seed, *, directed=False, attrs=True):
    rnd = random.Random(seed)
    edges = []
    seen = set()
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
            if i % 5 == 0:
                Gx[u][v]["label"] = f"e{i}"
                Gf[u][v]["label"] = f"e{i}"
        for node in list(Gx.nodes())[::4]:
            Gx.nodes[node]["color"] = f"c{node}"
            Gf.nodes[node]["color"] = f"c{node}"
    Gx.graph["name"] = "g"
    Gf.graph["name"] = "g"
    return Gx, Gf


def _adj(G):
    return fnx.readwrite.json_graph.adjacency_data(G)


def test_native_fast_path_is_registered():
    assert hasattr(fnx._fnx, "adjacency_data_simple")


def test_undirected_with_attrs_parity():
    Gx, Gf = _build_pair(60, 200, 11)
    assert nx.readwrite.json_graph.adjacency_data(Gx) == _adj(Gf)


def test_directed_with_attrs_parity():
    Gx, Gf = _build_pair(60, 200, 12, directed=True)
    assert nx.readwrite.json_graph.adjacency_data(Gx) == _adj(Gf)


def test_no_attrs_parity():
    Gx, Gf = _build_pair(40, 100, 13, attrs=False)
    assert nx.readwrite.json_graph.adjacency_data(Gx) == _adj(Gf)


def test_custom_id_field_parity():
    Gx, Gf = _build_pair(50, 150, 14)
    kw = {"attrs": {"id": "_id", "key": "_k"}}
    assert nx.readwrite.json_graph.adjacency_data(
        Gx, **kw
    ) == fnx.readwrite.json_graph.adjacency_data(Gf, **kw)


def test_singleton_and_empty_graphs():
    for n, m in [(1, 0), (2, 1), (5, 4)]:
        Gx, Gf = _build_pair(n, m, 100 + n)
        assert nx.readwrite.json_graph.adjacency_data(Gx) == _adj(Gf)


def test_isolated_node_keeps_empty_adjacency():
    Gx = nx.Graph([(0, 1), (1, 2)])
    Gx.add_node(7)
    Gf = fnx.Graph([(0, 1), (1, 2)])
    Gf.add_node(7)
    assert nx.readwrite.json_graph.adjacency_data(Gx) == _adj(Gf)


def test_attr_named_id_is_overwritten_like_nx():
    # Edge/node attr literally named "id" must be overwritten by the id field
    # (nx's {**d, id_: n} spread puts id_ last).
    Gx = nx.Graph()
    Gf = fnx.Graph()
    Gx.add_node(0, id="keep?")
    Gf.add_node(0, id="keep?")
    Gx.add_edge(0, 1, id="edge?")
    Gf.add_edge(0, 1, id="edge?")
    assert nx.readwrite.json_graph.adjacency_data(Gx) == _adj(Gf)


def test_multigraph_falls_back_to_general_wrapper():
    Gx = nx.MultiGraph([(0, 1), (0, 1), (1, 2)])
    Gf = fnx.MultiGraph([(0, 1), (0, 1), (1, 2)])
    assert nx.readwrite.json_graph.adjacency_data(Gx) == _adj(Gf)


def test_native_does_not_mutate_stored_attrs():
    Gf = fnx.Graph()
    Gf.add_edge(0, 1, weight=2.0)
    _adj(Gf)
    # The live edge attr dict must NOT have gained an "id" key.
    assert "id" not in Gf[0][1]
    assert dict(Gf[0][1]) == {"weight": 2.0}
