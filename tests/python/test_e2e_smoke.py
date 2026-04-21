#!/usr/bin/env python3
"""FrankenNetworkX E2E smoke test — comprehensive integration test suite.

Exercises the full Python -> Rust -> Python pipeline with detailed logging.
Can be run standalone: python tests/python/test_e2e_smoke.py
Or via pytest: pytest tests/python/test_e2e_smoke.py -v

Minimum 50 test assertions across all major API surfaces.
"""

import logging
import pickle
import sys
import time
from functools import wraps

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fnx_e2e")

# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------
_pass_count = 0
_fail_count = 0


def check(name: str, condition: bool, detail: str = ""):
    """Assert a condition, log result."""
    global _pass_count, _fail_count
    if condition:
        _pass_count += 1
        log.info("[PASS] %s%s", name, f" — {detail}" if detail else "")
    else:
        _fail_count += 1
        log.error("[FAIL] %s%s", name, f" — {detail}" if detail else "")


def timed(func):
    """Decorator to log elapsed time."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        t0 = time.monotonic()
        result = func(*args, **kwargs)
        elapsed = (time.monotonic() - t0) * 1000
        log.info("  elapsed: %.1fms", elapsed)
        return result
    return wrapper


# ---------------------------------------------------------------------------
# Pytest fixture: pre-built weighted triangle graph for tests that need G
# ---------------------------------------------------------------------------
try:
    import pytest

    @pytest.fixture
    def G(fnx):
        """Build the same 3-node weighted triangle used by standalone main()."""
        g = fnx.Graph()
        g.add_node("a", color="red")
        g.add_node("b")
        g.add_node("c")
        g.add_edge("a", "b", weight=1.0)
        g.add_edge("b", "c", weight=2.5)
        g.add_edge("a", "c", weight=10.0)
        return g
except ImportError:
    pass


# ===========================================================================
# Test: Import and version
# ===========================================================================
@timed
def test_import():
    log.info("--- test_import ---")
    import franken_networkx as fnx
    check("module imports", True)
    check("version is string", isinstance(fnx.__version__, str))
    check("version is non-empty", len(fnx.__version__) > 0)


# ===========================================================================
# Test: Graph lifecycle
# ===========================================================================
@timed
def test_graph_lifecycle(fnx):
    log.info("--- test_graph_lifecycle ---")
    G = fnx.Graph()

    # Empty graph properties
    check("empty graph len == 0", len(G) == 0)
    check("empty graph node count", G.number_of_nodes() == 0)
    check("empty graph edge count", G.number_of_edges() == 0)
    check("empty graph bool is False", not bool(G))

    # Add nodes
    G.add_node("a", color="red")
    G.add_node("b")
    G.add_node("c")
    check("3 nodes after add", G.number_of_nodes() == 3)
    check("has_node works", G.has_node("a"))
    check("'a' in G", "a" in G)
    check("'z' not in G", "z" not in G)

    # Add edges
    G.add_edge("a", "b", weight=1.0)
    G.add_edge("b", "c", weight=2.5)
    G.add_edge("a", "c", weight=10.0)
    check("3 edges after add", G.number_of_edges() == 3)
    check("has_edge works", G.has_edge("a", "b"))
    check("has_edge reverse", G.has_edge("b", "a"))
    check("has_edge negative", not G.has_edge("a", "z"))

    # Neighbors
    neighbors = G.neighbors("b")
    check("neighbors returns list", isinstance(neighbors, list))
    check("b has 2 neighbors", len(neighbors) == 2)

    # Mutation
    G.add_node("d")
    G.add_edge("c", "d")
    check("4 nodes after mutation", G.number_of_nodes() == 4)
    check("4 edges after mutation", G.number_of_edges() == 4)

    G.remove_edge("c", "d")
    check("3 edges after remove_edge", G.number_of_edges() == 3)

    G.remove_node("d")
    check("3 nodes after remove_node", G.number_of_nodes() == 3)

    # Predicates
    check("is_directed is False", not G.is_directed())
    check("is_multigraph is False", not G.is_multigraph())

    # __str__ and __repr__
    check("str(G) works", "Graph" in str(G))
    check("repr(G) works", "Graph" in repr(G))


@timed
def test_multigraph_lifecycle(fnx):
    log.info("--- test_multigraph_lifecycle ---")
    G = fnx.MultiGraph()

    key0 = G.add_edge("a", "b", weight=1.0)
    key1 = G.add_edge("a", "b", weight=2.0)
    check("multigraph key allocation increments", (key0, key1) == (0, 1))
    check("multigraph edge count counts parallels", G.number_of_edges() == 2)
    check("multigraph edge count between pair", G.number_of_edges("a", "b") == 2)
    check("multigraph has keyed edge", G.has_edge("a", "b", key=1))
    check("multigraph adjacency is keyed", sorted(G["a"]["b"].keys()) == [0, 1])

    G.remove_edge("a", "b", key=0)
    check("multigraph remove keyed edge", G.number_of_edges("a", "b") == 1)


@timed
def test_multidigraph_lifecycle(fnx):
    log.info("--- test_multidigraph_lifecycle ---")
    G = fnx.MultiDiGraph()
    G.graph["name"] = "mdg"
    G.add_nodes_from([("solo", {"color": "blue"})])

    key0 = G.add_edge("a", "b", weight=1.0)
    key1 = G.add_edge("a", "b", weight=2.0)
    G.add_edge("b", "a", weight=3.0)
    G.add_edges_from([("b", "c", {"weight": 4.0}), ("c", "a", 7, {"weight": 5.0})])

    check("multidigraph key allocation increments", (key0, key1) == (0, 1))
    check("multidigraph edge count counts directions", G.number_of_edges() == 5)
    check("multidigraph edge count between pair", G.number_of_edges("a", "b") == 2)
    check("multidigraph size sums weights", abs(G.size(weight="weight") - 15.0) < 1e-9)
    check("multidigraph has node", G.has_node("solo"))
    check("multidigraph successors work", G.successors("a") == ["b"])
    check("multidigraph predecessors work", G.predecessors("b") == ["a"])
    check("multidigraph adjacency is keyed", sorted(G["a"]["b"].keys()) == [0, 1])
    check("multidigraph repr includes name", "name='mdg'" in repr(G))
    G.remove_node("solo")
    check("multidigraph remove_node updates membership", not G.has_node("solo"))
    G.clear_edges()
    check("multidigraph clear_edges preserves nodes", G.number_of_nodes() == 3)
    check("multidigraph clear_edges removes all edges", G.number_of_edges() == 0)


@timed
def test_backend_multigraph_conversion_roundtrip(fnx):
    log.info("--- test_backend_multigraph_conversion_roundtrip ---")
    import importlib.util
    import networkx as nx
    from pathlib import Path

    backend_path = Path(__file__).resolve().parents[2] / "python" / "franken_networkx" / "backend.py"
    spec = importlib.util.spec_from_file_location("fnx_repo_backend", backend_path)
    backend = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(backend)
    BackendInterface = backend.BackendInterface

    mg = nx.MultiGraph()
    mg.graph["name"] = "mg"
    mg.add_node("a", color="red")
    mg.add_edge("a", "b", key=7, weight=2.5)
    mg.add_edge("a", "b", key=9, capacity=4)

    fnx_mg = BackendInterface.convert_from_nx(mg)
    check("backend converts nx.MultiGraph to fnx.MultiGraph", isinstance(fnx_mg, fnx.MultiGraph))
    check(
        "backend can_run accepts multigraph shortest_path",
        BackendInterface.can_run("shortest_path", (mg,), {}),
    )
    check("backend preserves multigraph edge count", fnx_mg.number_of_edges("a", "b") == 2)
    check("backend preserves multigraph keys", sorted(fnx_mg["a"]["b"].keys()) == [7, 9])

    mg_roundtrip = BackendInterface.convert_to_nx(fnx_mg)
    check("backend roundtrips to nx.MultiGraph", isinstance(mg_roundtrip, nx.MultiGraph))
    check("backend preserves graph attrs", mg_roundtrip.graph["name"] == "mg")
    check(
        "backend preserves keyed edge attrs",
        abs(float(mg_roundtrip["a"]["b"][7]["weight"]) - 2.5) < 1e-9,
    )
    check("backend preserves second keyed edge attrs", mg_roundtrip["a"]["b"][9]["capacity"] == 4)

    mixed_nodes = fnx.MultiGraph()
    mixed_nodes.add_edge(1, "b", key=3, weight=9.0)
    mixed_roundtrip = BackendInterface.convert_to_nx(mixed_nodes)
    check(
        "backend converts undirected multigraphs with mixed node types",
        isinstance(mixed_roundtrip, nx.MultiGraph),
    )
    check(
        "backend keeps mixed-type multigraph edge attrs",
        abs(float(mixed_roundtrip[1]["b"][3]["weight"]) - 9.0) < 1e-9,
    )

    mdg = nx.MultiDiGraph()
    mdg.graph["name"] = "mdg"
    mdg.add_edge("x", "y", key=1, weight=3.0)
    mdg.add_edge("x", "y", key=4, cost=8)
    mdg.add_edge("y", "x", key=2, weight=5.0)

    fnx_mdg = BackendInterface.convert_from_nx(mdg)
    check(
        "backend converts nx.MultiDiGraph to fnx.MultiDiGraph",
        isinstance(fnx_mdg, fnx.MultiDiGraph),
    )
    check(
        "backend can_run accepts multidigraph shortest_path",
        BackendInterface.can_run("shortest_path", (mdg,), {}),
    )
    check("backend preserves directed multiedge count", fnx_mdg.number_of_edges("x", "y") == 2)
    check("backend preserves directed key ordering", sorted(fnx_mdg["x"]["y"].keys()) == [1, 4])

    mdg_roundtrip = BackendInterface.convert_to_nx(fnx_mdg)
    check("backend roundtrips to nx.MultiDiGraph", isinstance(mdg_roundtrip, nx.MultiDiGraph))
    check("backend preserves reverse directed edge", mdg_roundtrip.has_edge("y", "x", key=2))
    check(
        "backend preserves directed edge attrs",
        abs(float(mdg_roundtrip["x"]["y"][1]["weight"]) - 3.0) < 1e-9,
    )
    check("backend preserves graph attrs on digraph", mdg_roundtrip.graph["name"] == "mdg")


@timed
def test_networkx_backend_dispatch_entrypoints():
    log.info("--- test_networkx_backend_dispatch_entrypoints ---")
    import importlib.metadata
    import networkx as nx

    backend_eps = importlib.metadata.entry_points(group="networkx.backends")
    backend_info_eps = importlib.metadata.entry_points(group="networkx.backend_info")
    check(
        "backend entry point is installed",
        any(entry_point.name == "franken_networkx" for entry_point in backend_eps),
    )
    check(
        "backend_info entry point is installed",
        any(entry_point.name == "franken_networkx" for entry_point in backend_info_eps),
    )
    check(
        "shortest_path advertises franken_networkx backend",
        "franken_networkx" in nx.shortest_path.backends,
    )
    check(
        "pagerank advertises franken_networkx backend",
        "franken_networkx" in nx.pagerank.backends,
    )

    path_graph = nx.path_graph(5)
    path = nx.shortest_path(path_graph, 0, 4, backend="franken_networkx")
    check("networkx shortest_path dispatches via franken_networkx", path == [0, 1, 2, 3, 4])

    cycle_graph = nx.cycle_graph(6)
    pagerank = nx.pagerank(cycle_graph, backend="franken_networkx")
    check("networkx pagerank dispatch sums to 1", abs(sum(pagerank.values()) - 1.0) < 1e-9)

    components = list(nx.connected_components(path_graph, backend="franken_networkx"))
    check("networkx connected_components dispatches", len(components) == 1)


@timed
def test_multigraph_extended_surface(fnx):
    log.info("--- test_multigraph_extended_surface ---")

    g = fnx.MultiGraph()
    g.graph["name"] = "mg-extended"
    g.add_nodes_from([("a", {"color": "red"}), "b", "c"])
    g.add_weighted_edges_from([("a", "b", 1.5), ("a", "b", 2.5)])

    assert len(g.nodes) == 3
    assert "a" in g.nodes
    assert any(node == "a" and attrs["color"] == "red" for node, attrs in g.nodes(data=True))

    keyed_edges = list(g.edges(keys=True))
    assert keyed_edges == [("a", "b", 0), ("a", "b", 1)]
    keyed_data_edges = list(g.edges(data=True, keys=True))
    assert abs(float(keyed_data_edges[0][3]["weight"]) - 1.5) < 1e-9
    assert abs(float(keyed_data_edges[1][3]["weight"]) - 2.5) < 1e-9

    assert g.degree["a"] == 2
    assert list(g.degree) == [("a", 2), ("b", 2), ("c", 0)]
    assert sorted(g.adj["a"]["b"].keys()) == [0, 1]
    assert [(node, sorted(neighbors.keys())) for node, neighbors in g.adjacency()] == [
        ("a", ["b"]),
        ("b", ["a"]),
        ("c", []),
    ]

    copied = g.copy()
    copied.remove_edge("a", "b", key=0)
    assert copied.number_of_edges("a", "b") == 1
    assert g.number_of_edges("a", "b") == 2

    sub = g.subgraph(["a", "b"])
    assert sub.number_of_nodes() == 2
    assert sub.number_of_edges("a", "b") == 2

    edge_sub = g.edge_subgraph([("a", "b", 1)])
    assert edge_sub.number_of_nodes() == 2
    assert edge_sub.number_of_edges("a", "b") == 1
    assert edge_sub.has_edge("a", "b", key=1)

    same_kind = g.to_undirected()
    assert isinstance(same_kind, fnx.MultiGraph)
    assert same_kind.number_of_edges("a", "b") == 2

    directed_graph = g.to_directed()
    assert isinstance(directed_graph, fnx.MultiDiGraph)
    assert directed_graph.is_directed()
    assert directed_graph.number_of_edges() == 2 * g.number_of_edges()

    g.update(edges=[("b", "c", {"weight": 4.0})], nodes=[("d", {"shape": "square"})])
    assert g.has_node("d")
    assert g.number_of_edges("b", "c") == 1
    assert g.number_of_edges_between("a", "b") == 2
    assert "mg-extended" in repr(g)


@timed
def test_multidigraph_extended_surface(fnx):
    log.info("--- test_multidigraph_extended_surface ---")

    g = fnx.MultiDiGraph()
    g.graph["name"] = "mdg-extended"
    g.add_nodes_from([("a", {"kind": "src"}), "b", "c"])
    g.add_weighted_edges_from([("a", "b", 1.0), ("a", "b", 2.0), ("b", "a", 3.0)])

    assert len(g.nodes) == 3
    assert "a" in g.nodes
    assert any(node == "a" and attrs["kind"] == "src" for node, attrs in g.nodes(data=True))

    keyed_edges = list(g.edges(keys=True))
    assert keyed_edges == [("a", "b", 0), ("a", "b", 1), ("b", "a", 0)]
    keyed_data_edges = list(g.edges(data=True, keys=True))
    assert abs(float(keyed_data_edges[0][3]["weight"]) - 1.0) < 1e-9
    assert abs(float(keyed_data_edges[1][3]["weight"]) - 2.0) < 1e-9
    assert abs(float(keyed_data_edges[2][3]["weight"]) - 3.0) < 1e-9

    assert g.degree["a"] == 3
    assert g.in_degree["a"] == 1
    assert g.out_degree["a"] == 2
    assert list(g.degree) == [("a", 3), ("b", 3), ("c", 0)]
    assert list(g.in_degree) == [("a", 1), ("b", 2), ("c", 0)]
    assert list(g.out_degree) == [("a", 2), ("b", 1), ("c", 0)]
    assert sorted(g.succ["a"]["b"].keys()) == [0, 1]
    assert sorted(g.pred["a"]["b"].keys()) == [0]

    copied = g.copy()
    copied.remove_edge("a", "b", key=0)
    assert copied.number_of_edges("a", "b") == 1
    assert g.number_of_edges("a", "b") == 2

    sub = g.subgraph(["a", "b"])
    assert sub.number_of_nodes() == 2
    assert sub.number_of_edges() == 3

    edge_sub = g.edge_subgraph([("a", "b", 1)])
    assert edge_sub.number_of_nodes() == 2
    assert edge_sub.number_of_edges("a", "b") == 1
    assert edge_sub.has_edge("a", "b", key=1)

    directed_copy = g.to_directed()
    assert isinstance(directed_copy, fnx.MultiDiGraph)
    assert directed_copy.number_of_edges() == g.number_of_edges()

    reversed_graph = g.reverse()
    assert reversed_graph.has_edge("b", "a", key=0)
    assert reversed_graph.has_edge("b", "a", key=1)
    assert reversed_graph.has_edge("a", "b", key=0)

    undirected_graph = g.to_undirected()
    assert isinstance(undirected_graph, fnx.MultiGraph)
    assert not undirected_graph.is_directed()
    # "a"->"b" key=0 and "b"->"a" key=0 merge into a single undirected edge.
    assert undirected_graph.number_of_edges() == 2

    g.update(edges=[("c", "a", {"weight": 4.0})], nodes=[("d", {"shape": "sink"})])
    assert g.has_node("d")
    assert g.number_of_edges("c", "a") == 1
    assert "mdg-extended" in repr(g)


# ===========================================================================
# Test: View objects
# ===========================================================================
@timed
def test_views(fnx, G):
    log.info("--- test_views ---")

    # NodeView
    nodes = G.nodes
    check("nodes view has len", len(nodes) == 3)
    check("'a' in nodes", "a" in nodes)
    check("nodes iterable", len(list(nodes)) == 3)

    # EdgeView
    edges = G.edges
    check("edges view has len", len(edges) == 3)
    check("edges iterable", len(list(edges)) == 3)

    # DegreeView
    degree = G.degree
    check("degree view has len", len(degree) == 3)
    check("degree['a'] is int", isinstance(degree["a"], int))
    check("degree['a'] == 2", degree["a"] == 2)

    # AdjacencyView
    adj = G.adj
    check("adj view has len", len(adj) == 3)
    check("'a' in adj", "a" in adj)


# ===========================================================================
# Test: Shortest path family
# ===========================================================================
@timed
def test_shortest_path(fnx, G):
    log.info("--- test_shortest_path ---")
    path = fnx.shortest_path(G, "a", "c")
    check("shortest_path returns list", isinstance(path, list))
    check("shortest_path a->c is [a,c] (direct)", path == ["a", "c"])

    length = fnx.shortest_path_length(G, "a", "c")
    check("shortest_path_length is 1", length == 1)

    check("has_path a->c", fnx.has_path(G, "a", "c"))

    dp = fnx.dijkstra_path(G, "a", "c", weight="weight")
    check("dijkstra_path returns list", isinstance(dp, list))
    check("dijkstra_path is [a,b,c] (weighted)", dp == ["a", "b", "c"])

    bf = fnx.bellman_ford_path(G, "a", "c", weight="weight")
    check("bellman_ford_path returns list", isinstance(bf, list))
    check("bellman_ford matches dijkstra", bf == dp)

    avg = fnx.average_shortest_path_length(G)
    check("avg_shortest_path is float", isinstance(avg, float))
    check("avg_shortest_path > 0", avg > 0)


# ===========================================================================
# Test: Connectivity algorithms
# ===========================================================================
@timed
def test_connectivity(fnx, G):
    log.info("--- test_connectivity ---")
    check("is_connected", fnx.is_connected(G))

    comps = fnx.connected_components(G)
    check("connected_components returns list", isinstance(comps, list))
    check("1 connected component", len(comps) == 1)

    check("number_connected_components == 1", fnx.number_connected_components(G) == 1)

    nc = fnx.node_connectivity(G)
    check("node_connectivity is int", isinstance(nc, int))

    ap = fnx.articulation_points(G)
    check("articulation_points returns list", isinstance(ap, list))

    br = fnx.bridges(G)
    check("bridges returns list", isinstance(br, list))


# ===========================================================================
# Test: Centrality algorithms
# ===========================================================================
@timed
def test_centrality(fnx, G):
    log.info("--- test_centrality ---")
    dc = fnx.degree_centrality(G)
    check("degree_centrality returns dict", isinstance(dc, dict))
    check("degree_centrality has all nodes", len(dc) == G.number_of_nodes())

    cc = fnx.closeness_centrality(G)
    check("closeness_centrality returns dict", isinstance(cc, dict))

    bc = fnx.betweenness_centrality(G)
    check("betweenness_centrality returns dict", isinstance(bc, dict))

    pr = fnx.pagerank(G)
    check("pagerank returns dict", isinstance(pr, dict))
    check("pagerank sums to ~1.0", abs(sum(pr.values()) - 1.0) < 0.01)

    hubs, auths = fnx.hits(G)
    check("hits returns two dicts", isinstance(hubs, dict) and isinstance(auths, dict))

    kc = fnx.katz_centrality(G)
    check("katz_centrality returns dict", isinstance(kc, dict))

    ec = fnx.eigenvector_centrality(G)
    check("eigenvector_centrality returns dict", isinstance(ec, dict))

    hc = fnx.harmonic_centrality(G)
    check("harmonic_centrality returns dict", isinstance(hc, dict))

    ebc = fnx.edge_betweenness_centrality(G)
    check("edge_betweenness_centrality returns dict", isinstance(ebc, dict))

    and_result = fnx.average_neighbor_degree(G)
    check("average_neighbor_degree returns dict", isinstance(and_result, dict))

    dac = fnx.degree_assortativity_coefficient(G)
    check("degree_assortativity_coefficient is float", isinstance(dac, float))

    vr = fnx.voterank(G)
    check("voterank returns list", isinstance(vr, list))


# ===========================================================================
# Test: Clustering algorithms
# ===========================================================================
@timed
def test_clustering(fnx, G):
    log.info("--- test_clustering ---")
    cl = fnx.clustering(G)
    check("clustering returns dict", isinstance(cl, dict))

    ac = fnx.average_clustering(G)
    check("average_clustering is float", isinstance(ac, float))

    tr = fnx.transitivity(G)
    check("transitivity is float", isinstance(tr, float))

    tri = fnx.triangles(G)
    check("triangles returns dict", isinstance(tri, dict))

    sq = fnx.square_clustering(G)
    check("square_clustering returns dict", isinstance(sq, dict))

    cliques = fnx.find_cliques(G)
    check("find_cliques returns list", isinstance(cliques, list))

    cn = fnx.graph_clique_number(G)
    check("graph_clique_number is int", isinstance(cn, int))
    check("clique number >= 1", cn >= 1)


# ===========================================================================
# Test: Matching algorithms
# ===========================================================================
@timed
def test_matching(fnx, G):
    log.info("--- test_matching ---")
    mm = fnx.maximal_matching(G)
    check("maximal_matching returns list", isinstance(mm, list))
    check("matching is non-empty", len(mm) > 0)

    mwm = fnx.max_weight_matching(G, weight="weight")
    check("max_weight_matching returns list", isinstance(mwm, list))

    minwm = fnx.min_weight_matching(G, weight="weight")
    check("min_weight_matching returns list", isinstance(minwm, list))

    mec = fnx.min_edge_cover(G)
    check("min_edge_cover returns list", isinstance(mec, list))
    check("edge cover covers all nodes", len(mec) >= 1)


# ===========================================================================
# Test: Flow algorithms
# ===========================================================================
@timed
def test_flow(fnx, G):
    log.info("--- test_flow ---")
    mf = fnx.maximum_flow_value(G, "a", "c", capacity="weight")
    check("maximum_flow_value is float", isinstance(mf, float))
    check("max flow > 0", mf > 0)

    mc = fnx.minimum_cut_value(G, "a", "c", capacity="weight")
    check("minimum_cut_value is float", isinstance(mc, float))
    check("min cut > 0", mc > 0)


# ===========================================================================
# Test: Distance measures
# ===========================================================================
@timed
def test_distance(fnx, G):
    log.info("--- test_distance ---")
    d = fnx.density(G)
    check("density is float", isinstance(d, float))
    check("density in [0,1]", 0 <= d <= 1)

    ecc = fnx.eccentricity(G)
    check("eccentricity returns dict", isinstance(ecc, dict))

    dia = fnx.diameter(G)
    check("diameter is int", isinstance(dia, int))

    rad = fnx.radius(G)
    check("radius is int", isinstance(rad, int))
    check("radius <= diameter", rad <= dia)

    ctr = fnx.center(G)
    check("center returns list", isinstance(ctr, list))

    per = fnx.periphery(G)
    check("periphery returns list", isinstance(per, list))


# ===========================================================================
# Test: Tree, bipartite, coloring, core
# ===========================================================================
@timed
def test_tree_bipartite(fnx):
    log.info("--- test_tree_bipartite ---")

    # Build a tree for is_tree test
    T = fnx.Graph()
    T.add_edge("a", "b")
    T.add_edge("b", "c")
    T.add_edge("c", "d")
    check("path graph is_tree", fnx.is_tree(T))
    check("path graph is_forest", fnx.is_forest(T))
    check("path graph is_bipartite", fnx.is_bipartite(T))
    broadcast_time, broadcast_center = fnx.tree_broadcast_center(T)
    check("tree_broadcast_center returns int", isinstance(broadcast_time, int))
    check("tree_broadcast_center returns set", isinstance(broadcast_center, set))
    check("tree_broadcast_time is int", isinstance(fnx.tree_broadcast_time(T), int))

    sets = fnx.bipartite_sets(T)
    check("bipartite_sets returns tuple of 2", len(sets) == 2)
    check("bipartite sets cover all nodes", len(sets[0]) + len(sets[1]) == T.number_of_nodes())

    coloring = fnx.greedy_color(T)
    check("greedy_color returns dict", isinstance(coloring, dict))
    check("coloring covers all nodes", len(coloring) == T.number_of_nodes())

    cn = fnx.core_number(T)
    check("core_number returns dict", isinstance(cn, dict))

    # MST
    W = fnx.Graph()
    W.add_edge("a", "b", weight=1.0)
    W.add_edge("b", "c", weight=2.0)
    W.add_edge("a", "c", weight=10.0)
    mst = fnx.minimum_spanning_tree(W, weight="weight")
    check("MST is a Graph", isinstance(mst, fnx.Graph))
    check("MST has same node count", mst.number_of_nodes() == W.number_of_nodes())
    check("MST has n-1 edges", mst.number_of_edges() == W.number_of_nodes() - 1)


# ===========================================================================
# Test: Euler algorithms
# ===========================================================================
@timed
def test_euler(fnx):
    log.info("--- test_euler ---")

    # Build an Eulerian graph (K3 — complete on 3 nodes, all even degree)
    E = fnx.Graph()
    E.add_edge("a", "b")
    E.add_edge("b", "c")
    E.add_edge("a", "c")
    check("K3 is_eulerian", fnx.is_eulerian(E))
    check("K3 has_eulerian_path", fnx.has_eulerian_path(E))

    circuit = fnx.eulerian_circuit(E)
    check("eulerian_circuit returns list", isinstance(circuit, list))
    check("circuit has 3 edges", len(circuit) == 3)

    # Semi-Eulerian (path graph has exactly 2 odd-degree vertices)
    P = fnx.Graph()
    P.add_edge("a", "b")
    P.add_edge("b", "c")
    check("path is semi-Eulerian", fnx.is_semieulerian(P))

    ep = fnx.eulerian_path(P)
    check("eulerian_path returns list", isinstance(ep, list))
    check("path has 2 edges", len(ep) == 2)


# ===========================================================================
# Test: Paths, cycles, efficiency
# ===========================================================================
@timed
def test_paths_cycles_efficiency(fnx, G):
    log.info("--- test_paths_cycles_efficiency ---")
    paths = fnx.all_simple_paths(G, "a", "c")
    check("all_simple_paths returns list", isinstance(paths, list))
    check("at least 1 simple path", len(paths) >= 1)

    cycles = fnx.cycle_basis(G)
    check("cycle_basis returns list", isinstance(cycles, list))

    pe = fnx.efficiency(G, "a", "c")
    check("efficiency is float", isinstance(pe, float))
    check("efficiency in [0,1]", 0 <= pe <= 1)

    ge = fnx.global_efficiency(G)
    check("global_efficiency is float", isinstance(ge, float))
    check("global_efficiency in [0,1]", 0 <= ge <= 1)

    le = fnx.local_efficiency(G)
    check("local_efficiency is float", isinstance(le, float))


# ===========================================================================
# Test: Exception types
# ===========================================================================
@timed
def test_exceptions(fnx):
    log.info("--- test_exceptions ---")

    G = fnx.Graph()
    G.add_node("a")
    G.add_node("b")
    # No edge between a and b

    # NetworkXNoPath
    try:
        fnx.shortest_path(G, "a", "b")
        check("NetworkXNoPath raised", False)
    except fnx.NetworkXNoPath:
        check("NetworkXNoPath raised", True)

    # NodeNotFound
    try:
        fnx.shortest_path(G, "a", "nonexistent")
        check("NodeNotFound raised", False)
    except fnx.NodeNotFound:
        check("NodeNotFound raised", True)

    # Exception hierarchy
    check("NetworkXNoPath is subclass of NetworkXUnfeasible",
          issubclass(fnx.NetworkXNoPath, fnx.NetworkXUnfeasible))
    check("NetworkXUnfeasible is subclass of NetworkXError",
          issubclass(fnx.NetworkXUnfeasible, fnx.NetworkXError))
    check("NodeNotFound is subclass of NetworkXError",
          issubclass(fnx.NodeNotFound, fnx.NetworkXError))


# ===========================================================================
# Test: Pickle round-trip
# ===========================================================================
@timed
def test_pickle(fnx):
    log.info("--- test_pickle ---")
    G = fnx.Graph()
    G.add_node("x", label="hello")
    G.add_edge("x", "y", weight=3.14)
    G.add_edge("y", "z")

    data = pickle.dumps(G)
    check("pickle.dumps succeeds", isinstance(data, bytes))

    G2 = pickle.loads(data)
    check("pickle.loads returns Graph", isinstance(G2, fnx.Graph))
    check("round-trip node count", G2.number_of_nodes() == G.number_of_nodes())
    check("round-trip edge count", G2.number_of_edges() == G.number_of_edges())
    check("round-trip has_node", G2.has_node("x"))
    check("round-trip has_edge", G2.has_edge("x", "y"))


# ===========================================================================
# Test: Copy and subgraph
# ===========================================================================
@timed
def test_copy_subgraph(fnx):
    log.info("--- test_copy_subgraph ---")
    G = fnx.Graph()
    G.add_edge("a", "b")
    G.add_edge("b", "c")
    G.add_edge("c", "d")

    G2 = G.copy()
    check("copy has same node count", G2.number_of_nodes() == G.number_of_nodes())
    check("copy has same edge count", G2.number_of_edges() == G.number_of_edges())

    # Mutating copy doesn't affect original
    G2.add_node("e")
    check("copy is independent", G.number_of_nodes() == 4)

    sub = G.subgraph(["a", "b", "c"])
    check("subgraph has 3 nodes", sub.number_of_nodes() == 3)
    check("subgraph has 2 edges", sub.number_of_edges() == 2)

    esub = G.edge_subgraph([("a", "b"), ("c", "d")])
    check("edge_subgraph has correct edges", esub.number_of_edges() == 2)


# ===========================================================================
# Test: Batch mutations
# ===========================================================================
@timed
def test_batch_mutations(fnx):
    log.info("--- test_batch_mutations ---")
    G = fnx.Graph()
    G.add_nodes_from(["a", "b", "c", "d"])
    check("add_nodes_from", G.number_of_nodes() == 4)

    G.add_edges_from([("a", "b"), ("b", "c"), ("c", "d")])
    check("add_edges_from", G.number_of_edges() == 3)

    G.add_weighted_edges_from([("a", "c", 5.0)], weight="weight")
    check("add_weighted_edges_from", G.number_of_edges() == 4)

    G.remove_edges_from([("a", "b")])
    check("remove_edges_from", G.number_of_edges() == 3)

    G.remove_nodes_from(["d"])
    check("remove_nodes_from", G.number_of_nodes() == 3)

    G.clear_edges()
    check("clear_edges", G.number_of_edges() == 0)
    check("clear_edges keeps nodes", G.number_of_nodes() == 3)

    G.clear()
    check("clear", G.number_of_nodes() == 0)


# ===========================================================================
# Runner
# ===========================================================================
def main():
    log.info("=" * 60)
    log.info("FrankenNetworkX E2E Smoke Test")
    log.info("=" * 60)

    t0 = time.monotonic()

    fnx = test_import()
    G = test_graph_lifecycle(fnx)
    test_backend_multigraph_conversion_roundtrip(fnx)
    test_networkx_backend_dispatch_entrypoints()
    test_views(fnx, G)
    test_shortest_path(fnx, G)
    test_connectivity(fnx, G)
    test_centrality(fnx, G)
    test_clustering(fnx, G)
    test_matching(fnx, G)
    test_flow(fnx, G)
    test_distance(fnx, G)
    test_tree_bipartite(fnx)
    test_euler(fnx)
    test_paths_cycles_efficiency(fnx, G)
    test_exceptions(fnx)
    test_pickle(fnx)
    test_copy_subgraph(fnx)
    test_batch_mutations(fnx)

    elapsed = (time.monotonic() - t0) * 1000

    log.info("=" * 60)
    log.info("SUMMARY: %d/%d passed, %d failed (%.1fms total)",
             _pass_count, _pass_count + _fail_count, _fail_count, elapsed)
    log.info("=" * 60)

    if _fail_count > 0:
        sys.exit(1)
    log.info("All tests passed.")


if __name__ == "__main__":
    main()
