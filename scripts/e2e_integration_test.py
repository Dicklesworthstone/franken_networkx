#!/usr/bin/env python3
"""Structured end-to-end integration runner for FrankenNetworkX."""

from __future__ import annotations

import importlib.metadata
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx
from franken_networkx.backend import BackendInterface


STRESS_NODES = int(os.environ.get("FNX_E2E_STRESS_NODES", "10000"))
STRESS_ATTACH = int(os.environ.get("FNX_E2E_STRESS_ATTACH", "3"))
STRESS_TIMEOUT_SECONDS = float(os.environ.get("FNX_E2E_STRESS_TIMEOUT_SECONDS", "60"))


def emit(event: str, test: str, level: str = "INFO", **fields) -> None:
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event,
        "level": level,
        "test": test,
    }
    record.update(fields)
    print(json.dumps(record, sort_keys=True), flush=True)


def fail(message: str) -> None:
    raise AssertionError(message)


def expect(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def normalize_mapping(mapping: dict) -> dict:
    return {repr(key): value for key, value in mapping.items()}


def sorted_component_lists(components) -> list[list[str]]:
    return sorted(sorted(repr(node) for node in component) for component in components)


def sorted_edge_records(graph) -> list[tuple]:
    if graph.is_multigraph():
        return sorted(
            (repr(u), repr(v), key, tuple(sorted(data.items())))
            for u, v, key, data in graph.edges(keys=True, data=True)
        )
    return sorted(
        (repr(u), repr(v), tuple(sorted(data.items())))
        for u, v, data in graph.edges(data=True)
    )


def expected_undirected_edges(graph) -> list[tuple[str, str]]:
    return sorted(tuple(sorted((repr(u), repr(v)))) for u, v in graph.edges())


def graph_summary(graph) -> dict:
    return {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "directed": graph.is_directed(),
        "multigraph": graph.is_multigraph(),
    }


def run_case(name: str, func) -> tuple[bool, float]:
    emit("start", name)
    start = time.monotonic()
    try:
        summary = func() or {}
    except Exception as exc:  # pragma: no cover - exercised in CI on failure
        elapsed = time.monotonic() - start
        emit("finish", name, level="ERROR", ok=False, elapsed_s=round(elapsed, 3), error=str(exc))
        return False, elapsed
    elapsed = time.monotonic() - start
    emit("finish", name, ok=True, elapsed_s=round(elapsed, 3), summary=summary)
    return True, elapsed


def standalone_workflow() -> dict:
    graph = fnx.barabasi_albert_graph(1000, 3, seed=7)
    graph.add_edge(0, 999, weight=1.0)
    graph.add_edge(1, 998, weight=2.0)

    first_path = fnx.shortest_path(graph, 0, 500)
    second_path = fnx.shortest_path(graph, 0, 500)
    expect(first_path == second_path, "shortest_path must be deterministic on repeated calls")

    first_pagerank = fnx.pagerank(graph, alpha=0.85)
    second_pagerank = fnx.pagerank(graph, alpha=0.85)
    expect(
        normalize_mapping(first_pagerank) == normalize_mapping(second_pagerank),
        "pagerank output drifted across repeated runs",
    )

    components = list(fnx.connected_components(graph))
    expect(len(components) == 1, "standalone graph should remain connected")

    community_graph = fnx.karate_club_graph()
    communities = tuple(next(fnx.girvan_newman(community_graph)))
    expect(len(communities) >= 2, "girvan_newman should split the graph into communities")

    roundtrip = fnx.node_link_graph(fnx.node_link_data(graph))
    expect(
        graph_summary(roundtrip) == graph_summary(graph),
        "node-link roundtrip changed graph shape",
    )
    expect(sorted_edge_records(roundtrip) == sorted_edge_records(graph), "node-link roundtrip changed edges")

    return {
        "graph": graph_summary(graph),
        "path_len": len(first_path),
        "components": len(components),
        "communities": len(communities),
    }


def backend_dispatch_workflow() -> dict:
    entry_points = importlib.metadata.entry_points(group="networkx.backends")
    expect(
        any(entry_point.name == "franken_networkx" for entry_point in entry_points),
        "networkx backend entry point for franken_networkx is not installed",
    )
    backend_info_points = importlib.metadata.entry_points(group="networkx.backend_info")
    expect(
        any(entry_point.name == "franken_networkx" for entry_point in backend_info_points),
        "networkx backend_info entry point for franken_networkx is not installed",
    )

    expect("franken_networkx" in getattr(nx.shortest_path, "backends", set()), "shortest_path backend not registered")
    expect("franken_networkx" in getattr(nx.pagerank, "backends", set()), "pagerank backend not registered")
    expect(
        "franken_networkx" in getattr(nx.connected_components, "backends", set()),
        "connected_components backend not registered",
    )

    nx_graph = nx.path_graph(8)
    path = nx.shortest_path(nx_graph, 0, 7, backend="franken_networkx")
    expect(path == list(range(8)), "backend shortest_path returned unexpected path")

    cycle_graph = nx.cycle_graph(6)
    pagerank = nx.pagerank(cycle_graph, backend="franken_networkx")
    expect(abs(sum(pagerank.values()) - 1.0) < 1e-9, "backend pagerank must sum to 1")

    components = list(nx.connected_components(nx_graph, backend="franken_networkx"))
    expect(len(components) == 1, "backend connected_components expected a single component")

    fnx_graph = BackendInterface.convert_from_nx(nx_graph)
    expect(isinstance(fnx_graph, fnx.Graph), "backend conversion did not produce fnx.Graph")
    expect(BackendInterface.can_run("shortest_path", (fnx_graph, 0, 7), {}), "backend cannot run shortest_path")
    expect(BackendInterface.should_run("pagerank", (fnx_graph,), {}), "backend should_run rejected pagerank")

    roundtrip = BackendInterface.convert_to_nx(fnx_graph)
    expect(isinstance(roundtrip, nx.Graph), "backend convert_to_nx did not return nx.Graph")
    expect(list(roundtrip.nodes()) == list(nx_graph.nodes()), "backend roundtrip changed node order")

    return {
        "path_len": len(path),
        "pagerank_nodes": len(pagerank),
        "components": len(components),
    }


def digraph_workflow() -> dict:
    graph = fnx.DiGraph()
    graph.add_edges_from(
        [
            ("prep", "build"),
            ("build", "lint"),
            ("build", "test"),
            ("lint", "package"),
            ("test", "package"),
            ("package", "deploy"),
            ("cycle_a", "cycle_b"),
            ("cycle_b", "cycle_a"),
        ]
    )

    dag = fnx.DiGraph()
    dag.add_edges_from(
        [
            ("prep", "build"),
            ("build", "lint"),
            ("build", "test"),
            ("lint", "package"),
            ("test", "package"),
            ("package", "deploy"),
        ]
    )

    topo = list(fnx.topological_sort(dag))
    expect(topo[0] == "prep", "topological_sort should start with the root task")

    tc = fnx.transitive_closure(dag)
    expect(tc.has_edge("build", "deploy"), "transitive_closure missed reachable edge")

    scc = sorted_component_lists(fnx.strongly_connected_components(graph))
    expected_graph = BackendInterface.convert_to_nx(graph)
    expected_scc = sorted_component_lists(nx.strongly_connected_components(expected_graph))
    expect(scc == expected_scc, "strongly_connected_components drifted from NetworkX")

    condensation = fnx.condensation(graph)
    expect(condensation.number_of_nodes() == len(expected_scc), "condensation node count mismatch")

    return {
        "topo_len": len(topo),
        "scc_count": len(scc),
        "condensation_nodes": condensation.number_of_nodes(),
    }


def multigraph_workflow() -> dict:
    multigraph = fnx.MultiGraph()
    multigraph.graph["name"] = "roads"
    multigraph.add_edge("a", "b", key=7, weight=1.5, color="red")
    multigraph.add_edge("a", "b", key=9, weight=2.0, color="blue")
    multigraph.add_edge("b", "c", key=11, weight=1.0)

    expect(multigraph.number_of_edges("a", "b") == 2, "parallel multiedges were not preserved")
    expect(sorted(multigraph["a"]["b"].keys()) == [7, 9], "multigraph keys drifted")
    expect(fnx.shortest_path(multigraph, "a", "c") == ["a", "b", "c"], "multigraph shortest path mismatch")

    multidigraph = fnx.MultiDiGraph()
    multidigraph.add_edge("x", "y", key=1, capacity=3)
    multidigraph.add_edge("x", "y", key=2, capacity=5)
    multidigraph.add_edge("y", "z", key=4, capacity=8)
    multidigraph.add_edge("z", "x", key=6, capacity=13)

    expect(multidigraph.number_of_edges("x", "y") == 2, "multidigraph parallel edges drifted")
    expect(multidigraph.successors("x") == ["y"], "multidigraph successors mismatch")

    return {
        "multigraph_edges": multigraph.number_of_edges(),
        "multidigraph_edges": multidigraph.number_of_edges(),
    }


def large_graph_stress_workflow() -> dict:
    start = time.monotonic()
    graph = fnx.barabasi_albert_graph(STRESS_NODES, STRESS_ATTACH, seed=11)
    pagerank = fnx.pagerank(graph, alpha=0.85, max_iter=100)
    elapsed_pagerank = time.monotonic() - start
    expect(len(pagerank) == STRESS_NODES, "pagerank size mismatch on stress graph")

    path_start = time.monotonic()
    path = fnx.shortest_path(graph, 0, STRESS_NODES - 1)
    elapsed_path = time.monotonic() - path_start
    total_elapsed = time.monotonic() - start

    expect(len(path) >= 2, "stress shortest_path returned an invalid path")
    expect(total_elapsed <= STRESS_TIMEOUT_SECONDS, "stress workflow exceeded timeout budget")

    top_node = max(pagerank, key=pagerank.get)
    return {
        "stress_nodes": STRESS_NODES,
        "stress_edges": graph.number_of_edges(),
        "pagerank_s": round(elapsed_pagerank, 3),
        "shortest_path_s": round(elapsed_path, 3),
        "shortest_path_len": len(path),
        "top_pagerank_node": repr(top_node),
    }


def serialization_roundtrip_workflow() -> dict:
    graph = fnx.Graph()
    graph.graph["name"] = "io-demo"
    graph.add_node("alpha", color="red")
    graph.add_node("beta", color="blue")
    graph.add_node("gamma", color="green")
    graph.add_edge("alpha", "beta", weight=1.5, label="ab")
    graph.add_edge("beta", "gamma", weight=2.0, label="bg")

    with tempfile.TemporaryDirectory(prefix="fnx-e2e-") as temp_dir:
        root = Path(temp_dir)

        edgelist_path = root / "graph.edgelist"
        fnx.write_edgelist(graph, edgelist_path)
        edge_roundtrip = fnx.read_edgelist(edgelist_path)
        expect(expected_undirected_edges(edge_roundtrip) == expected_undirected_edges(graph), "edgelist mismatch")

        adjlist_path = root / "graph.adjlist"
        fnx.write_adjlist(graph, adjlist_path)
        adj_roundtrip = fnx.read_adjlist(adjlist_path)
        expect(expected_undirected_edges(adj_roundtrip) == expected_undirected_edges(graph), "adjlist mismatch")

        graphml_path = root / "graph.graphml"
        fnx.write_graphml(graph, graphml_path)
        graphml_roundtrip = fnx.read_graphml(graphml_path)
        expect(graphml_roundtrip.nodes["alpha"]["color"] == "red", "graphml node attrs drifted")
        expect(float(graphml_roundtrip["alpha"]["beta"]["weight"]) == 1.5, "graphml edge attrs drifted")

        gml_path = root / "graph.gml"
        fnx.write_gml(graph, gml_path)
        gml_roundtrip = fnx.read_gml(gml_path)
        expect(gml_roundtrip.graph.get("name") == "io-demo", "gml graph attrs drifted")

        payload = fnx.node_link_data(graph)
        json_path = root / "graph.json"
        json_path.write_text(json.dumps(payload), encoding="utf-8")
        try:
            json_payload = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(f"node-link JSON decode failed: {exc}")
        json_roundtrip = fnx.node_link_graph(json_payload)
        expect(sorted_edge_records(json_roundtrip) == sorted_edge_records(graph), "node-link JSON mismatch")

    return {
        "formats": ["edgelist", "adjlist", "graphml", "gml", "node_link_json"],
        "graph": graph_summary(graph),
    }


def main() -> int:
    emit(
        "config",
        "runner",
        stress_nodes=STRESS_NODES,
        stress_attach=STRESS_ATTACH,
        stress_timeout_s=STRESS_TIMEOUT_SECONDS,
        python=sys.version.split()[0],
        networkx=nx.__version__,
        fnx=fnx.__version__,
    )

    cases = [
        ("standalone_workflow", standalone_workflow),
        ("backend_dispatch_workflow", backend_dispatch_workflow),
        ("digraph_workflow", digraph_workflow),
        ("multigraph_workflow", multigraph_workflow),
        ("large_graph_stress_workflow", large_graph_stress_workflow),
        ("serialization_roundtrip_workflow", serialization_roundtrip_workflow),
    ]

    results = [run_case(name, func) for name, func in cases]
    failures = sum(1 for ok, _ in results if not ok)
    total_elapsed = round(sum(elapsed for _, elapsed in results), 3)
    emit("summary", "runner", ok=failures == 0, failures=failures, total_elapsed_s=total_elapsed)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
