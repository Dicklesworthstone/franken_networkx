"""Parity for the native `node_link_data` fast path (json_graph).

`franken_networkx.readwrite.json_graph.node_link_data` routes exact simple
`Graph` / `DiGraph` inputs through the native `_fnx.node_link_data_simple`
kernel, which builds the `nodes` + `edges` arrays in Rust (copying live attr
dicts, appending the id / source / target fields) instead of walking the
per-edge EdgeView in Python. The undirected edge loop replicates nx's
`G.edges()` dedup order (seen-set of finished source nodes) rather than the
attr-cloning `edges_ordered()` materializer.

Both graphs are built from an identical explicit node + edge sequence so node
and edge iteration order match nx.
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


def _jg(G, **kw):
    return fnx.readwrite.json_graph.node_link_data(G, **kw)


def test_native_fast_path_is_registered():
    assert hasattr(fnx._fnx, "node_link_data_simple")


def test_undirected_with_attrs_parity():
    Gx, Gf = _build_pair(80, 300, 11)
    assert nx.readwrite.json_graph.node_link_data(Gx, edges="edges") == _jg(
        Gf, edges="edges"
    )


def test_directed_with_attrs_parity():
    Gx, Gf = _build_pair(80, 300, 12, directed=True)
    assert nx.readwrite.json_graph.node_link_data(Gx, edges="edges") == _jg(
        Gf, edges="edges"
    )


def test_no_attrs_parity():
    Gx, Gf = _build_pair(40, 100, 13, attrs=False)
    assert nx.readwrite.json_graph.node_link_data(Gx, edges="edges") == _jg(
        Gf, edges="edges"
    )


def test_custom_field_names_parity():
    Gx, Gf = _build_pair(50, 150, 14)
    kw = dict(source="s", target="t", name="nid", edges="E", nodes="N")
    assert nx.readwrite.json_graph.node_link_data(Gx, **kw) == _jg(Gf, **kw)


def test_singleton_and_tiny_graphs():
    for n, m, d in [(1, 0, False), (2, 1, False), (2, 1, True), (5, 4, False)]:
        Gx, Gf = _build_pair(n, m, 100 + n, directed=d)
        assert nx.readwrite.json_graph.node_link_data(Gx, edges="edges") == _jg(
            Gf, edges="edges"
        )


def test_attr_named_like_endpoint_is_overwritten():
    # Edge attr named "source"/"target" and node attr named "id" must be
    # overwritten by the spread (nx puts the endpoint/id fields last).
    Gx = nx.Graph()
    Gf = fnx.Graph()
    Gx.add_node(0, id="keep?")
    Gf.add_node(0, id="keep?")
    Gx.add_edge(0, 1, source="x", target="y", weight=3)
    Gf.add_edge(0, 1, source="x", target="y", weight=3)
    assert nx.readwrite.json_graph.node_link_data(Gx, edges="edges") == _jg(
        Gf, edges="edges"
    )


def test_duplicate_field_names_raise_like_nx():
    Gf = fnx.Graph([(0, 1)])
    try:
        _jg(Gf, source="x", target="x")
    except fnx.NetworkXError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected NetworkXError for non-unique field names")


def test_multigraph_falls_back():
    Gx = nx.MultiGraph([(0, 1), (0, 1), (1, 2)])
    Gf = fnx.MultiGraph([(0, 1), (0, 1), (1, 2)])
    assert nx.readwrite.json_graph.node_link_data(Gx, edges="edges") == _jg(
        Gf, edges="edges"
    )


def test_native_does_not_mutate_stored_attrs():
    Gf = fnx.Graph()
    Gf.add_edge(0, 1, weight=2.0)
    _jg(Gf, edges="edges")
    assert "source" not in Gf[0][1] and "target" not in Gf[0][1]
    assert dict(Gf[0][1]) == {"weight": 2.0}
