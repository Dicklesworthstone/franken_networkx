"""Parity for the TOP-LEVEL `adjacency_data` / `node_link_data` native paths.

br-r37-c1-9kpev: the top-level `fnx.adjacency_data` and `fnx.node_link_data`
(what `nx.adjacency_data` / `nx.node_link_data` resolve to) now route exact
simple `Graph` / `DiGraph` through the same native `_fnx.adjacency_data_simple`
/ `_fnx.node_link_data_simple` kernels used by the json_graph module wrappers,
instead of the per-edge AdjacencyView / EdgeView Python loops.

These tests pin the top-level functions to networkx and to the json_graph
module path, and confirm multigraphs still fall back.
"""

import io
import json
import random

import networkx as nx
import pytest

import franken_networkx as fnx


GRAPH_TYPES = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")


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


def _node_link_example(lib, graph_type):
    graph = getattr(lib, graph_type)()
    graph.graph["description"] = "node-link roundtrip"
    graph.add_node("isolated", color="gray")
    graph.add_node(("tuple", 1), color="blue")
    if graph.is_multigraph():
        graph.add_edge(("tuple", 1), "target", key="first", weight=2)
        graph.add_edge(("tuple", 1), "target", key=7, weight=3)
        graph.add_edge("target", "target", key="loop", weight=4)
    else:
        graph.add_edge(("tuple", 1), "target", weight=2)
        graph.add_edge("target", "target", weight=4)
    return graph


def _node_link_snapshot(graph):
    return (
        graph.is_directed(), graph.is_multigraph(), graph.graph,
        list(graph.nodes(data=True)),
        list(graph.edges(keys=True, data=True)) if graph.is_multigraph()
        else list(graph.edges(data=True)),
    )


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize(
    "fields",
    (
        {"source": "id"},
        {"target": "id"},
        {"name": "key"},
        {"source": "node", "name": "node", "nodes": "vertices", "edges": "links"},
    ),
)
def test_node_link_names_are_scoped_to_node_and_edge_records(graph_type, fields):
    expected_graph = _node_link_example(nx, graph_type)
    actual_graph = _node_link_example(fnx, graph_type)
    expected_data = nx.node_link_data(expected_graph, **fields)
    actual_data = fnx.node_link_data(actual_graph, **fields)
    assert actual_data == expected_data
    assert fnx.readwrite.json_graph.node_link_data(actual_graph, **fields) == expected_data
    actual = fnx.node_link_graph(actual_data, **fields)
    expected = nx.node_link_graph(expected_data, **fields)
    assert _node_link_snapshot(actual) == _node_link_snapshot(expected)
    assert _node_link_snapshot(
        fnx.readwrite.json_graph.node_link_graph(actual_data, **fields)
    ) == _node_link_snapshot(expected)
    assert _node_link_snapshot(
        fnx.node_link_graph(json.loads(json.dumps(actual_data)), **fields)
    ) == _node_link_snapshot(
        nx.node_link_graph(json.loads(json.dumps(expected_data)), **fields)
    )


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize(
    "fields",
    (
        {"source": "same", "target": "same"},
        {"source": "key"},
        {"target": "key"},
        {"source": None},
        {"target": None},
    ),
)
def test_node_link_edge_field_collisions_match_networkx(graph_type, fields):
    expected_graph = _node_link_example(nx, graph_type)
    actual_graph = _node_link_example(fnx, graph_type)
    try:
        expected = nx.node_link_data(expected_graph, **fields)
    except nx.NetworkXError as error:
        with pytest.raises(fnx.NetworkXError) as actual:
            fnx.node_link_data(actual_graph, **fields)
        assert actual.value.args == error.args
    else:
        assert fnx.node_link_data(actual_graph, **fields) == expected


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
def test_node_link_roundtrip_shares_only_graph_metadata_mapping(graph_type):
    graph = _node_link_example(fnx, graph_type)
    shared = []
    graph.nodes["isolated"]["nested"] = shared
    payload = fnx.node_link_data(graph)
    assert payload["graph"] is graph.graph
    restored = fnx.node_link_graph(payload)
    assert restored.graph is graph.graph
    payload["graph"]["from_payload"] = 1
    restored.graph["from_restored"] = 2
    assert graph.graph["from_payload"] == 1
    assert graph.graph["from_restored"] == 2
    assert restored.nodes["isolated"] is not graph.nodes["isolated"]
    assert restored.nodes["isolated"]["nested"] is shared
    restored.nodes["isolated"]["color"] = "new"
    assert graph.nodes["isolated"]["color"] == "gray"
    # Native and Python storage must still agree after a JSON reconstruction.
    assert fnx.shortest_path(restored, ("tuple", 1), "target") == [("tuple", 1), "target"]
    assert restored.copy().graph == graph.graph


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("metadata", ({"custom": []}, [("custom", [])], None))
def test_node_link_graph_preserves_metadata_object_without_coercion(graph_type, metadata):
    payload = {
        "directed": "DiGraph" in graph_type,
        "multigraph": graph_type.startswith("Multi"),
        "graph": metadata,
        "nodes": [{"id": 0}], "edges": [],
    }
    expected = nx.node_link_graph(payload)
    actual = fnx.node_link_graph(payload)
    assert actual.graph is expected.graph is metadata
    assert fnx.node_link_data(actual)["graph"] is metadata


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
def test_copy_preserves_assigned_graph_metadata_shallowly(graph_type):
    graph = getattr(fnx, graph_type)()
    graph.add_edge(0, 1)
    nested = []
    graph.graph = {"assigned": nested}
    copied = graph.copy()
    assert copied.graph == graph.graph
    assert copied.graph is not graph.graph
    assert copied.graph["assigned"] is nested
    copied.graph["copied_only"] = True
    assert "copied_only" not in graph.graph


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
def test_copy_reads_node_link_metadata_provider_before_topology(graph_type):
    def run(lib):
        class Metadata(dict):
            on_read = None

            def __iter__(self):
                return super().__iter__()

            def keys(self):
                if self.on_read is not None:
                    self.on_read()
                return super().keys()

        metadata = Metadata(description="live metadata")
        graph = lib.node_link_graph({
            "directed": "DiGraph" in graph_type,
            "multigraph": graph_type.startswith("Multi"),
            "graph": metadata, "nodes": [{"id": 0}], "edges": [],
        })
        metadata.on_read = lambda: graph.add_node("added_by_metadata")
        copied = graph.copy()
        return list(copied), dict(copied.graph)

    assert run(fnx) == run(nx) == ([0, "added_by_metadata"], {"description": "live metadata"})


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("format_name", ("json", "gml", "graphml"))
@pytest.mark.parametrize("attribute_shape", ("plain", "edge_attrs", "node_attrs"))
def test_node_link_metadata_survives_copy_and_serialization(
    graph_type, format_name, attribute_shape
):
    source = getattr(nx, graph_type)()
    source.graph["description"] = "initial metadata"
    source.add_node(2, **({"color": "isolated"} if attribute_shape == "node_attrs" else {}))
    source.add_edge(0, 1, **({"weight": 3} if attribute_shape != "plain" else {}))
    if source.is_multigraph():
        source.add_edge(
            0, 1, key="parallel", **({"weight": 7} if attribute_shape != "plain" else {})
        )
    payload = nx.node_link_data(source)
    graph = fnx.node_link_graph(payload)
    payload["graph"]["description"] = "updated through payload"
    payload["graph"]["version"] = 4

    def serialized_snapshot(lib, candidate):
        if format_name == "json":
            data = json.loads(json.dumps(lib.node_link_data(candidate)))
            restored = nx.node_link_graph(data)
        else:
            stream = io.BytesIO()
            getattr(lib, "write_" + format_name)(candidate, stream)
            stream.seek(0)
            restored = getattr(nx, "read_" + format_name)(stream)
        return _node_link_snapshot(restored)

    expected = serialized_snapshot(nx, source)
    assert serialized_snapshot(fnx, graph) == expected
    assert serialized_snapshot(fnx, graph.copy()) == expected


@pytest.mark.parametrize("source_type", GRAPH_TYPES)
@pytest.mark.parametrize("target_type", GRAPH_TYPES)
def test_node_link_metadata_survives_graph_constructors(source_type, target_type):
    source = getattr(nx, source_type)()
    source.graph.update(description="initial metadata", nested=[])
    source.add_node(2)
    source.add_edge(0, 1)
    if source.is_multigraph():
        source.add_edge(0, 1, key="parallel")
    payload = nx.node_link_data(source)
    graph = fnx.node_link_graph(payload)
    payload["graph"]["revision"] = 2

    expected = getattr(nx, target_type)(source, description="constructor metadata")
    actual = getattr(fnx, target_type)(graph, description="constructor metadata")
    assert _node_link_snapshot(actual) == _node_link_snapshot(expected)
    assert actual.graph is not payload["graph"]
    assert actual.graph["nested"] is payload["graph"]["nested"]


@pytest.mark.parametrize("target_type", GRAPH_TYPES)
def test_constructor_reads_node_link_metadata_before_node_attributes(target_type):
    def run(lib):
        graph = lib.Graph()
        graph.add_node(0, state="before")
        graph.add_edge(0, 1, weight=1)

        class Metadata:
            def keys(self):
                graph.nodes[0]["state"] = "after"
                graph.edges[0, 1]["weight"] = 2
                return ["description"]

            def __getitem__(self, key):
                return "live metadata"

        payload = lib.node_link_data(graph)
        payload["graph"] = Metadata()
        graph = lib.node_link_graph(payload)
        return _node_link_snapshot(getattr(lib, target_type)(graph))

    assert run(fnx) == run(nx)


@pytest.mark.parametrize("graph_type", ("Graph", "MultiGraph"))
@pytest.mark.parametrize("algorithm", ("minimum_spanning_tree", "maximum_spanning_tree"))
def test_node_link_metadata_survives_spanning_trees(graph_type, algorithm):
    source = getattr(nx, graph_type)()
    source.graph.update(description="initial metadata", nested=[])
    source.add_nodes_from(range(4))
    source.add_weighted_edges_from([(0, 1, 3), (1, 2, 1), (0, 2, 2)])
    if source.is_multigraph():
        source.add_edge(0, 1, key="parallel", weight=0)
    payload = nx.node_link_data(source)
    graph = fnx.node_link_graph(payload)
    payload["graph"]["description"] = "updated through payload"

    expected = getattr(nx, algorithm)(source)
    actual = getattr(fnx, algorithm)(graph)
    assert _node_link_snapshot(actual) == _node_link_snapshot(expected)
    assert actual.graph is not payload["graph"]
    assert actual.graph["nested"] is payload["graph"]["nested"]


@pytest.mark.parametrize("graph_type", ("Graph", "MultiGraph"))
def test_spanning_tree_reads_node_link_metadata_before_topology(graph_type):
    def run(lib):
        graph = getattr(lib, graph_type)()
        graph.add_weighted_edges_from([(0, 1, 3), (1, 2, 2)])

        class Metadata:
            def keys(self):
                graph.add_edge(0, 2, weight=0)
                graph.add_edge(2, 3, weight=1)
                return ["description"]

            def __getitem__(self, key):
                return "live metadata"

        payload = lib.node_link_data(graph)
        payload["graph"] = Metadata()
        graph = lib.node_link_graph(payload)
        return _node_link_snapshot(lib.minimum_spanning_tree(graph))

    assert run(fnx) == run(nx)


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
def test_node_link_decodes_nonstring_attribute_names_and_typed_edge_keys(graph_type):
    graph = _node_link_example(nx, graph_type)
    graph.nodes["isolated"][42] = "node attribute"
    edge = ("target", "target", "loop") if graph.is_multigraph() else ("target", "target")
    graph.edges[edge][43] = "edge attribute"
    if graph.is_multigraph():
        graph.add_edge("target", "isolated", key=("tuple-key", 8), weight=9)
    payload = nx.node_link_data(graph)
    expected = nx.node_link_graph(payload)
    actual = fnx.node_link_graph(payload)
    assert _node_link_snapshot(actual) == _node_link_snapshot(expected)
    assert actual.nodes["isolated"]["42"] == "node attribute"
    assert actual.edges[edge]["43"] == "edge attribute"


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
def test_node_link_node_insertion_precedes_later_record_decoding(graph_type):
    def run(lib):
        later = {"id": "later", "color": "before"}

        class Node:
            def __hash__(self):
                later["color"] = "after"
                return 383

        graph = lib.node_link_graph({
            "directed": "DiGraph" in graph_type,
            "multigraph": graph_type.startswith("Multi"),
            "nodes": [{"id": Node()}, later], "edges": [],
        })
        return graph.nodes["later"]["color"]

    assert run(fnx) == run(nx) == "after"


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
def test_node_link_edge_insertion_precedes_later_record_decoding(graph_type):
    def run(lib):
        later = {"source": 0, "target": 1, "weight": 2}

        class Node:
            def __hash__(self):
                later["weight"] = 9
                return 383

        graph = lib.node_link_graph({
            "directed": "DiGraph" in graph_type,
            "multigraph": graph_type.startswith("Multi"),
            "nodes": [], "edges": [{"source": Node(), "target": "other"}, later],
        })
        edge = (0, 1, 0) if graph.is_multigraph() else (0, 1)
        return graph.edges[edge]["weight"]

    assert run(fnx) == run(nx) == 9


@pytest.mark.parametrize("multigraph", (False, True))
def test_node_link_export_uses_live_public_graph_providers(multigraph):
    def run(lib):
        events = []
        attributes = {0: {"color": "red"}, 1: {"color": "before"}}

        class Edges(list):
            def _materialize(self):
                raise AssertionError("private edge snapshot must not be used")

            def __iter__(self):
                events.append("edges-iter")
                return super().__iter__()

        class Nodes:
            def __getitem__(self, node):
                events.append(("node-data", node))
                return attributes[node]

        class Provider:
            graph = {"description": "live public graph"}
            nodes = Nodes()

            def __iter__(self):
                events.append("graph-iter")
                yield 0
                attributes[1]["color"] = "after"
                events.append("next-node")
                yield 1

            def is_directed(self):
                events.append("directed")
                return True

            def is_multigraph(self):
                events.append("multigraph")
                return multigraph

            def edges(self, **kwargs):
                events.append(("edges", kwargs))
                edge = (0, 1, "first", {"weight": 3}) if multigraph else (0, 1, {"weight": 3})
                return Edges([edge])

        graph = Provider()
        result = lib.node_link_data(graph)
        assert result["graph"] is graph.graph
        return result, events

    assert run(fnx) == run(nx)
