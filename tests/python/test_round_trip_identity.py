import os
import tempfile
import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    nx = None
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")

GRAPH_TYPES = [
    fnx.Graph,
    fnx.DiGraph,
    fnx.MultiGraph,
    fnx.MultiDiGraph,
]

FORMATS = [
    "gml",
    "graphml",
    "json",
    "edgelist",
    "adjlist",
    "pajek",
    "gexf",
]

BEHAVIOR_FORMATS = [
    "gml",
    "graphml",
    "json",
    "edgelist",
    "adjlist",
    "pajek",
]

def populate_graph(G, fmt):
    if fmt not in ("adjlist", "edgelist", "graph6", "sparse6"):
        G.graph["name"] = "test_graph"
        G.graph["global_attr"] = 42

    if fmt in ("adjlist", "edgelist"):
        # adjlist and edgelist don't handle node attributes natively well
        G.add_node("n1")
        G.add_node("n2")
        G.add_node("n3")
    else:
        G.add_node("n1", color="red", weight=1.5)
        G.add_node("n2", color="blue", weight=2.0)
        G.add_node("n3", color="green")

    if G.is_multigraph():
        if fmt in ("adjlist", "edgelist"):
            G.add_edge("n1", "n2", key=1)
            G.add_edge("n1", "n2", key=2)
            G.add_edge("n2", "n3", key=0)
        else:
            G.add_edge("n1", "n2", key=1, weight=2.5, edge_type="A")
            G.add_edge("n1", "n2", key=2, weight=1.0, edge_type="B")
            G.add_edge("n2", "n3", key=0, weight=3.0)
    else:
        if fmt in ("adjlist",):
            G.add_edge("n1", "n2")
            G.add_edge("n2", "n3")
        elif fmt == "edgelist":
            G.add_edge("n1", "n2", weight=2.5)
            G.add_edge("n2", "n3", weight=3.0)
        else:
            G.add_edge("n1", "n2", weight=2.5, edge_type="A")
            G.add_edge("n2", "n3", weight=3.0)
        
    return G


def _sort_key(value):
    return repr(value)


def _normalize_components(components):
    normalized = [
        tuple(sorted(component, key=_sort_key))
        for component in components
    ]
    return tuple(sorted(normalized, key=lambda component: (len(component), component)))


def _normalize_distance_matrix(distances):
    if hasattr(distances, "items"):
        iterator = distances.items()
    else:
        iterator = distances

    normalized_rows = []
    for source, lengths in iterator:
        normalized_lengths = tuple(
            sorted(lengths.items(), key=lambda item: _sort_key(item[0]))
        )
        normalized_rows.append((source, normalized_lengths))

    return tuple(sorted(normalized_rows, key=lambda row: _sort_key(row[0])))


def _degree_value(G, node):
    try:
        return G.degree(node)
    except TypeError:
        return G.degree[node]


def _behavior_signature(module, G):
    nodes = tuple(sorted(G.nodes(), key=_sort_key))
    signature = {
        "degrees": tuple((node, _degree_value(G, node)) for node in nodes),
        "neighbors_n2": tuple(sorted(G.neighbors("n2"), key=_sort_key)),
        "shortest_path_n1_n3": tuple(module.shortest_path(G, "n1", "n3")),
        "shortest_path_length_n1_n3": module.shortest_path_length(G, "n1", "n3"),
    }

    if G.is_directed():
        signature.update(
            {
                "ancestors_n3": tuple(sorted(module.ancestors(G, "n3"), key=_sort_key)),
                "descendants_n1": tuple(sorted(module.descendants(G, "n1"), key=_sort_key)),
                "predecessors_n3": tuple(sorted(G.predecessors("n3"), key=_sort_key)),
                "successors_n1": tuple(sorted(G.successors("n1"), key=_sort_key)),
                "strong_components": _normalize_components(
                    module.strongly_connected_components(G)
                ),
                "topological_sort": tuple(module.topological_sort(G)),
                "weak_components": _normalize_components(
                    module.weakly_connected_components(G)
                ),
            }
        )
    else:
        signature.update(
            {
                "all_pairs_shortest_path_length": _normalize_distance_matrix(
                    module.all_pairs_shortest_path_length(G)
                ),
                "connected_components": _normalize_components(
                    module.connected_components(G)
                ),
            }
        )

    return signature


def _reference_graph(graph_type, fmt):
    nx_graph_types = {
        fnx.Graph: nx.Graph,
        fnx.DiGraph: nx.DiGraph,
        fnx.MultiGraph: nx.MultiGraph,
        fnx.MultiDiGraph: nx.MultiDiGraph,
    }
    return populate_graph(nx_graph_types[graph_type](), fmt)

def assert_graphs_equal(G1, G2, format_name):
    if format_name in ("pajek", "adjlist", "edgelist"):
        pass
    else:
        assert type(G1) is type(G2)
        assert G1.is_directed() == G2.is_directed()
        assert G1.is_multigraph() == G2.is_multigraph()
    
    assert set(G1.nodes()) == set(G2.nodes())
    for n in G1.nodes():
        if format_name in ("gml", "pajek"):
            assert set(G1.nodes[n].keys()) == set(G2.nodes[n].keys())
        elif format_name == "gexf":
            g1_keys = set(G1.nodes[n].keys())
            g2_keys = set(G2.nodes[n].keys()) - {"label"} # gexf adds default label
            assert g1_keys == g2_keys
        elif format_name not in ("adjlist", "edgelist"):
            assert G1.nodes[n] == G2.nodes[n]
        
    if G1.is_multigraph():
        assert sorted(G1.edges(keys=True)) == sorted(G2.edges(keys=True))
        for u, v, k in G1.edges(keys=True):
            if format_name in ("gml", "pajek"):
                assert set(G1[u][v][k].keys()) == set(G2[u][v][k].keys())
            elif format_name == "gexf":
                g1_keys = set(G1[u][v][k].keys())
                g2_keys = set(G2[u][v][k].keys()) - {"id"} # gexf adds edge id
                assert g1_keys == g2_keys
            elif format_name not in ("adjlist", "edgelist"):
                assert G1[u][v][k] == G2[u][v][k]
    else:
        assert sorted(G1.edges()) == sorted(G2.edges())
        for u, v in G1.edges():
            if format_name in ("gml", "pajek"):
                assert set(G1[u][v].keys()) == set(G2[u][v].keys())
            elif format_name == "gexf":
                g1_keys = set(G1[u][v].keys())
                g2_keys = set(G2[u][v].keys()) - {"id"} # gexf adds edge id
                assert g1_keys == g2_keys
            elif format_name == "edgelist":
                pass # skip edge attr check for edgelist
            elif format_name not in ("adjlist",):
                assert G1[u][v] == G2[u][v]
            
    if format_name not in ("gml", "graphml", "adjlist", "edgelist", "pajek", "gexf"):
        assert G1.graph == G2.graph
    elif format_name == "graphml":
        g2_filtered = {k: v for k, v in G2.graph.items() if k not in ("node_default", "edge_default")}
        assert G1.graph == g2_filtered

def round_trip(G, fmt):
    if fmt == "json":
        data = fnx.node_link_data(G)
        return fnx.node_link_graph(data)
    elif fmt == "gml":
        if G.is_multigraph():
            pytest.skip("fnx.write_gml does not support MultiGraph")
        with tempfile.NamedTemporaryFile(suffix=".gml", delete=False) as f:
            path = f.name
        try:
            fnx.write_gml(G, path)
            return fnx.read_gml(path)
        finally:
            os.unlink(path)
    elif fmt == "graphml":
        if G.is_multigraph():
            pytest.skip("fnx.write_graphml does not support MultiGraph")
        with tempfile.NamedTemporaryFile(suffix=".graphml", delete=False) as f:
            path = f.name
        try:
            fnx.write_graphml(G, path)
            return fnx.read_graphml(path)
        finally:
            os.unlink(path)
    elif fmt == "edgelist":
        with tempfile.NamedTemporaryFile(suffix=".edgelist", delete=False) as f:
            path = f.name
        try:
            if G.is_multigraph():
                pytest.skip("write_edgelist does not support MultiGraph in franken_networkx without losing parallel edges")
            fnx.write_edgelist(G, path)
            G_parsed = fnx.read_edgelist(path)
            return G_parsed
        finally:
            os.unlink(path)
    elif fmt == "adjlist":
        with tempfile.NamedTemporaryFile(suffix=".adjlist", delete=False) as f:
            path = f.name
        try:
            if G.is_multigraph():
                pytest.skip("write_adjlist does not support MultiGraph in franken_networkx without losing parallel edges")
            fnx.write_adjlist(G, path)
            G_parsed = fnx.read_adjlist(path)
            return G_parsed
        finally:
            os.unlink(path)
    elif fmt == "pajek":
        with tempfile.NamedTemporaryFile(suffix=".pajek", delete=False) as f:
            path = f.name
        try:
            fnx.write_pajek(G, path)
            G_parsed = fnx.read_pajek(path)
            return G_parsed
        finally:
            os.unlink(path)
    elif fmt == "gexf":
        with tempfile.NamedTemporaryFile(suffix=".gexf", delete=False) as f:
            path = f.name
        try:
            fnx.write_gexf(G, path)
            return fnx.read_gexf(path, node_type=str)
        finally:
            os.unlink(path)
    else:
        raise ValueError(f"Unknown format {fmt}")


def networkx_round_trip(G, fmt):
    if fmt == "json":
        data = nx.node_link_data(G)
        return nx.node_link_graph(data)
    elif fmt == "gml":
        if G.is_multigraph():
            pytest.skip("networkx.write_gml does not support MultiGraph")
        with tempfile.NamedTemporaryFile(suffix=".gml", delete=False) as f:
            path = f.name
        try:
            nx.write_gml(G, path)
            return nx.read_gml(path)
        finally:
            os.unlink(path)
    elif fmt == "graphml":
        if G.is_multigraph():
            pytest.skip("networkx.write_graphml does not support MultiGraph")
        with tempfile.NamedTemporaryFile(suffix=".graphml", delete=False) as f:
            path = f.name
        try:
            nx.write_graphml(G, path)
            return nx.read_graphml(path)
        finally:
            os.unlink(path)
    elif fmt == "edgelist":
        if G.is_multigraph():
            pytest.skip("networkx.write_edgelist does not preserve MultiGraph parallel edges")
        with tempfile.NamedTemporaryFile(suffix=".edgelist", delete=False) as f:
            path = f.name
        try:
            nx.write_edgelist(G, path)
            return nx.read_edgelist(path)
        finally:
            os.unlink(path)
    elif fmt == "adjlist":
        if G.is_multigraph():
            pytest.skip("networkx.write_adjlist does not preserve MultiGraph parallel edges")
        with tempfile.NamedTemporaryFile(suffix=".adjlist", delete=False) as f:
            path = f.name
        try:
            nx.write_adjlist(G, path)
            return nx.read_adjlist(path)
        finally:
            os.unlink(path)
    elif fmt == "pajek":
        with tempfile.NamedTemporaryFile(suffix=".pajek", delete=False) as f:
            path = f.name
        try:
            nx.write_pajek(G, path)
            return nx.read_pajek(path)
        finally:
            os.unlink(path)
    else:
        raise ValueError(f"Unknown format {fmt}")


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("fmt", FORMATS)
def test_round_trip_identity(graph_type, fmt):
    G = graph_type()
    G = populate_graph(G, fmt)

    try:
        G2 = round_trip(G, fmt)
    except Exception as e:
        if fmt == "gexf" and "not implemented" in str(e).lower():
            pytest.skip(f"GEXF not fully supported: {e}")
        raise

    if fmt == "pajek":
        if not HAS_NX:
            pytest.skip("networkx not installed")
        expected = networkx_round_trip(_reference_graph(graph_type, fmt), fmt)
        assert_graphs_equal(expected, G2, fmt)
        return

    assert_graphs_equal(G, G2, fmt)


@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
def test_nodeview_get_matches_mapping_contract(graph_type):
    G = graph_type()
    G.add_node("n1", color="red")

    attrs = G.nodes.get("n1")
    assert isinstance(attrs, dict)
    assert attrs == {"color": "red"}
    assert G.nodes.get("missing") is None
    assert G.nodes.get("missing", {}) == {}


@needs_nx
@pytest.mark.parametrize("graph_type", GRAPH_TYPES)
@pytest.mark.parametrize("fmt", BEHAVIOR_FORMATS)
def test_round_trip_behavior_matches_networkx(graph_type, fmt):
    G = populate_graph(graph_type(), fmt)
    G_reference = _reference_graph(graph_type, fmt)

    try:
        G_round_trip = round_trip(G, fmt)
    except Exception as e:
        if fmt == "gexf" and "not implemented" in str(e).lower():
            pytest.skip(f"GEXF not fully supported: {e}")
        raise

    G_reference_round_trip = networkx_round_trip(G_reference, fmt)

    original_signature = _behavior_signature(fnx, G)
    round_trip_signature = _behavior_signature(fnx, G_round_trip)
    reference_signature = _behavior_signature(nx, G_reference)
    reference_round_trip_signature = _behavior_signature(nx, G_reference_round_trip)

    assert original_signature == reference_signature
    assert round_trip_signature == reference_round_trip_signature
