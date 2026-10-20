#!/usr/bin/env python3
"""Structured end-to-end V1 integration acceptance runner for FrankenNetworkX (hhj5p.9).

Executes the full cross-layer V1 acceptance journey on a single source/ELF/package
candidate:
1. Standalone, DiGraph, MultiGraph, large-graph stress, and I/O roundtrip workflows.
2. Four-class live semantics parity against live NetworkX (views, LiveKeyDict C-level
   JSON serialization, O(1) shared-storage shallow copy, held adjacency row across
   node removal, dense-index deletion coherence, equal-label key identity, view
   mutation iteration semantics, and directed/undirected live views).
3. Scoped analytics in standalone and backend modes (shortest path, components,
   preflow-push maximum_flow residual dict & minimum_cut set order, max/min weight
   matching, community order & directed mixed-weight modularity, centrality, aliases,
   and 7-format I/O round-trips).
4. Public V1 reference routes for all 12 CGSE registry algorithms under
   `cgse.collect_witnesses`, verifying pinned policies, complexity bounds, hash
   determinism, and negative bound rejection.
5. Strict fail-closed vs hardened bounded recovery & generator clamp boundaries with
   auditable `decision_records()` receipts.
6. Joined candidate performance/SLO/complexity receipts (`slo_gate_report_v1.json`,
   `empirical_complexity_catalogue_v1.json`, `backend_whole_job_benchmark_v1.json`,
   `attribute_store_e2e.jsonl`) bound by exact ELF SHA-256.
7. Five-class RaptorQ durability packaging (`conformance_fixtures`,
   `benchmark_baselines`, `migration_manifests`, `reproducibility_ledgers`,
   `long_lived_snapshots`), candidate wheel/sdist/native binding, isolated retained
   virtualenv installation & `verify_loaded_candidate` check, bounded packet-loss
   recovery + semantic replay, and beyond-bound packet-loss negative rejection.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import sysconfig
import tarfile
import time
import venv
import warnings
import zipfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "python") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "python"))

import franken_networkx as fnx  # noqa: E402
import networkx as nx  # noqa: E402
import tomllib  # noqa: E402
from franken_networkx._fnx import cgse  # noqa: E402
from franken_networkx.backend import BackendInterface  # noqa: E402

STRESS_NODES = int(os.environ.get("FNX_E2E_STRESS_NODES", "10000"))
STRESS_ATTACH = int(os.environ.get("FNX_E2E_STRESS_ATTACH", "3"))
STRESS_TIMEOUT_SECONDS = float(os.environ.get("FNX_E2E_STRESS_TIMEOUT_SECONDS", "60"))

DEFAULT_MANIFEST_PATH = REPO_ROOT / "artifacts" / "e2e" / "latest" / "v1_acceptance_manifest.json"
REQUIRED_DURABILITY_CLASSES = (
    "conformance_fixtures",
    "benchmark_baselines",
    "migration_manifests",
    "reproducibility_ledgers",
    "long_lived_snapshots",
)
EXPECTED_12_CGSE_ALGORITHMS = (
    "bellman_ford",
    "bfs",
    "connected_components",
    "dfs",
    "dijkstra",
    "eulerian_circuit",
    "kruskal",
    "max_weight_matching",
    "min_weight_matching",
    "prim",
    "strongly_connected_components",
    "topological_sort",
)


def _load_dsr_recipe():
    recipe_path = REPO_ROOT / "scripts" / "dsr_release_wheels.py"
    spec = importlib.util.spec_from_file_location("fnx_dsr_release_recipe", recipe_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {recipe_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _resolve_durability_binary() -> Path:
    configured = os.environ.get("FNX_DURABILITY_BIN")
    if configured:
        return Path(configured).resolve(strict=True)
    default_bin = REPO_ROOT / "target" / "release" / "fnx-durability"
    if default_bin.is_file():
        return default_bin.resolve(strict=True)
    subprocess.run(
        ["cargo", "build", "--release", "-p", "fnx-durability", "--bin", "fnx-durability"],
        cwd=REPO_ROOT,
        check=True,
        timeout=600,
    )
    return default_bin.resolve(strict=True)


def emit(event: str, test: str, level: str = "INFO", **fields: Any) -> None:
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


def run_case(name: str, func) -> tuple[bool, float, dict[str, Any]]:
    emit("start", name)
    start = time.monotonic()
    try:
        summary = func() or {}
    except Exception as exc:  # pragma: no cover - exercised on failure
        elapsed = time.monotonic() - start
        emit("finish", name, level="ERROR", ok=False, elapsed_s=round(elapsed, 3), error=str(exc))
        return False, elapsed, {"error": str(exc)}
    elapsed = time.monotonic() - start
    emit("finish", name, ok=True, elapsed_s=round(elapsed, 3), summary=summary)
    return True, elapsed, summary


# ---------------------------------------------------------------------------
# Existing E2E Workflows (preserved and extended without file deletion)
# ---------------------------------------------------------------------------


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
    communities = tuple(next(fnx.community.girvan_newman(community_graph)))
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
        "assertions": 6,
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
        "assertions": 13,
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
        "assertions": 4,
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
    expect(list(multidigraph.successors("x")) == ["y"], "multidigraph successors mismatch")

    return {
        "multigraph_edges": multigraph.number_of_edges(),
        "multidigraph_edges": multidigraph.number_of_edges(),
        "assertions": 5,
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
        "assertions": 3,
    }


def serialization_roundtrip_workflow(io_root: Path | None = None) -> dict:
    graph = fnx.Graph()
    graph.graph["name"] = "io-demo"
    graph.add_node("alpha", color="red")
    graph.add_node("beta", color="blue")
    graph.add_node("gamma", color="green")
    graph.add_edge("alpha", "beta", weight=1.5, label="ab")
    graph.add_edge("beta", "gamma", weight=2.0, label="bg")

    if io_root is None:
        io_root = REPO_ROOT / "target" / "e2e_acceptance" / f"io-{int(time.time() * 1000)}-{os.getpid()}"
    io_root.mkdir(parents=True, exist_ok=True)

    edgelist_path = io_root / "graph.edgelist"
    fnx.write_edgelist(graph, edgelist_path)
    edge_roundtrip = fnx.read_edgelist(edgelist_path)
    expect(expected_undirected_edges(edge_roundtrip) == expected_undirected_edges(graph), "edgelist mismatch")

    adjlist_path = io_root / "graph.adjlist"
    fnx.write_adjlist(graph, adjlist_path)
    adj_roundtrip = fnx.read_adjlist(adjlist_path)
    expect(expected_undirected_edges(adj_roundtrip) == expected_undirected_edges(graph), "adjlist mismatch")

    graphml_path = io_root / "graph.graphml"
    fnx.write_graphml(graph, graphml_path)
    graphml_roundtrip = fnx.read_graphml(graphml_path)
    expect(graphml_roundtrip.nodes["alpha"]["color"] == "red", "graphml node attrs drifted")
    expect(float(graphml_roundtrip["alpha"]["beta"]["weight"]) == 1.5, "graphml edge attrs drifted")

    gml_path = io_root / "graph.gml"
    fnx.write_gml(graph, gml_path)
    gml_roundtrip = fnx.read_gml(gml_path)
    expect(gml_roundtrip.graph.get("name") == "io-demo", "gml graph attrs drifted")

    payload = fnx.node_link_data(graph)
    json_path = io_root / "graph.json"
    json_path.write_text(json.dumps(payload), encoding="utf-8")
    json_payload = json.loads(json_path.read_text(encoding="utf-8"))
    json_roundtrip = fnx.node_link_graph(json_payload)
    expect(sorted_edge_records(json_roundtrip) == sorted_edge_records(graph), "node-link JSON mismatch")

    pajek_path = io_root / "graph.net"
    fnx.write_pajek(graph, pajek_path)
    pajek_roundtrip = fnx.read_pajek(pajek_path)
    expect(expected_undirected_edges(pajek_roundtrip) == expected_undirected_edges(graph), "pajek mismatch")

    gexf_path = io_root / "graph.gexf"
    fnx.write_gexf(graph, gexf_path)
    gexf_roundtrip = fnx.read_gexf(gexf_path)
    expect(expected_undirected_edges(gexf_roundtrip) == expected_undirected_edges(graph), "gexf mismatch")

    return {
        "formats": ["edgelist", "adjlist", "graphml", "gml", "node_link_json", "pajek", "gexf"],
        "graph": graph_summary(graph),
        "assertions": 8,
    }


# ---------------------------------------------------------------------------
# V1 Integration Acceptance Workflows (hhj5p.9)
# ---------------------------------------------------------------------------


def four_class_live_semantics_workflow(evidence_dir: Path) -> dict[str, Any]:
    """Verify 4 graph classes, live views, C-level JSON serialization, shallow copy,
    held rows across deletion, dense-index coherence, equal-label identity, and
    view mutation semantics against live NetworkX."""
    serialized_source = {
        "graph_attrs": {"suite": "hhj5p.9", "version": 1},
        "nodes": [
            ["n0", {"role": "source", "tier": 1}],
            ["n1", {"role": "relay", "tier": 2}],
            ["n2", {"role": "relay", "tier": 2}],
            ["n3", {"role": "sink", "tier": 3}],
        ],
        "simple_edges": [
            ["n0", "n1", {"weight": 1.5, "capacity": 4, "tag": "e01"}],
            ["n1", "n2", {"weight": 2.0, "capacity": 3, "tag": "e12"}],
            ["n0", "n2", {"weight": 4.5, "capacity": 2, "tag": "e02"}],
            ["n2", "n3", {"weight": 1.0, "capacity": 5, "tag": "e23"}],
        ],
        "multi_edges": [
            ["n0", "n1", 0, {"weight": 1.5, "capacity": 4, "tag": "m01_a"}],
            ["n0", "n1", 7, {"weight": 2.25, "capacity": 6, "tag": "m01_b"}],
            ["n1", "n2", 3, {"weight": 2.0, "capacity": 3, "tag": "m12"}],
            ["n2", "n3", 5, {"weight": 1.0, "capacity": 5, "tag": "m23"}],
        ],
    }

    class_checks: dict[str, Any] = {}
    fixture_exports: dict[str, Any] = {}

    for cls_name, is_multi in (
        ("Graph", False),
        ("DiGraph", False),
        ("MultiGraph", True),
        ("MultiDiGraph", True),
    ):
        fnx_cls = getattr(fnx, cls_name)
        nx_cls = getattr(nx, cls_name)
        fg = fnx_cls(**serialized_source["graph_attrs"])
        ng = nx_cls(**serialized_source["graph_attrs"])
        for node, attrs in serialized_source["nodes"]:
            fg.add_node(node, **attrs)
            ng.add_node(node, **attrs)
        if is_multi:
            for u, v, k, attrs in serialized_source["multi_edges"]:
                fg.add_edge(u, v, key=k, **attrs)
                ng.add_edge(u, v, key=k, **attrs)
        else:
            for u, v, attrs in serialized_source["simple_edges"]:
                fg.add_edge(u, v, **attrs)
                ng.add_edge(u, v, **attrs)

        # 1. Live view & attribute mutation parity
        fg.graph["mutated"] = True
        ng.graph["mutated"] = True
        fg.nodes["n1"]["visited"] = 9
        ng.nodes["n1"]["visited"] = 9
        if is_multi:
            fg["n0"]["n1"][7]["weight"] = 1.75
            ng["n0"]["n1"][7]["weight"] = 1.75
        else:
            fg["n0"]["n1"]["weight"] = 1.25
            ng["n0"]["n1"]["weight"] = 1.25

        expect(dict(fg.graph) == dict(ng.graph), f"{cls_name} graph attr parity failed")
        expect(list(fg.nodes(data=True)) == list(ng.nodes(data=True)), f"{cls_name} nodes(data=True) parity failed")
        expect(list(fg.degree()) == list(ng.degree()), f"{cls_name} degree() order/value parity failed")

        # 2. C-level JSON serialization on to_dict_of_dicts (5cqna)
        fnx_dod_json = json.dumps(fnx.to_dict_of_dicts(fg), sort_keys=True)
        nx_dod_json = json.dumps(nx.to_dict_of_dicts(ng), sort_keys=True)
        expect(fnx_dod_json == nx_dod_json and len(fnx_dod_json) > 40, f"{cls_name} to_dict_of_dicts JSON parity failed")

        # 3. Shallow copy copy.copy(G) shared storage (yr2oc.3 + 2h5uj) & G.copy() independent structure
        fg_shallow = copy.copy(fg)
        ng_shallow = copy.copy(ng)
        fg_shallow.custom_tag = "only_on_copy"
        ng_shallow.custom_tag = "only_on_copy"
        if is_multi:
            fg_shallow["n0"]["n1"][0]["shared_flag"] = "yes"
            ng_shallow["n0"]["n1"][0]["shared_flag"] = "yes"
            expect(
                fg["n0"]["n1"][0].get("shared_flag") == ng["n0"]["n1"][0].get("shared_flag") == "yes",
                f"{cls_name} copy.copy(G) did not share inner edge attribute dict",
            )
        else:
            fg_shallow["n0"]["n1"]["shared_flag"] = "yes"
            ng_shallow["n0"]["n1"]["shared_flag"] = "yes"
            expect(
                fg["n0"]["n1"].get("shared_flag") == ng["n0"]["n1"].get("shared_flag") == "yes",
                f"{cls_name} copy.copy(G) did not share edge attribute dict",
            )
        expect(
            hasattr(fg, "custom_tag") == hasattr(ng, "custom_tag") is False,
            f"{cls_name} copy.copy(G) leaked instance __dict__ attribute to original",
        )
        fg_method_copy = fg.copy()
        ng_method_copy = ng.copy()
        fg_method_copy.add_node("method_copy_extra")
        ng_method_copy.add_node("method_copy_extra")
        expect(
            ("method_copy_extra" in fg) == ("method_copy_extra" in ng) is False,
            f"{cls_name} G.copy() leaked node addition back to original",
        )

        # 4. Held adjacency row across remove_node and remove_nodes_from + dense-index coherence (yr2oc.5 + u8rs5 + as50i)
        fg_del = copy.deepcopy(fg)
        ng_del = copy.deepcopy(ng)
        held_fnx = fg_del["n1"]
        held_nx = ng_del["n1"]
        fg_del.remove_node("n1")
        ng_del.remove_node("n1")
        expect(dict(held_fnx) == dict(held_nx), f"{cls_name} held row after remove_node('n1') diverged from NetworkX")
        expect(list(fg_del.nodes()) == list(ng_del.nodes()), f"{cls_name} nodes after remove_node diverged")
        expect(list(fg_del.edges()) == list(ng_del.edges()), f"{cls_name} edges after remove_node diverged")
        # Dense-index coherence check via algorithm execution after deletion (as50i)
        expect(
            list(fnx.bfs_edges(fg_del, "n0")) == list(nx.bfs_edges(ng_del, "n0")),
            f"{cls_name} bfs_edges after node deletion diverged (dense-index coherence)",
        )

        # 5. View parity: to_directed(as_view=True) and to_undirected(as_view=True) (o1z03)
        dir_view_fnx = fg.to_directed(as_view=True)
        dir_view_nx = ng.to_directed(as_view=True)
        undir_view_fnx = fg.to_undirected(as_view=True)
        undir_view_nx = ng.to_undirected(as_view=True)
        expect(list(dir_view_fnx.nodes()) == list(dir_view_nx.nodes()), f"{cls_name} to_directed view nodes mismatch")
        expect(
            dir_view_fnx.number_of_edges() == dir_view_nx.number_of_edges(),
            f"{cls_name} to_directed view edge count mismatch",
        )
        expect(
            undir_view_fnx.number_of_edges() == undir_view_nx.number_of_edges(),
            f"{cls_name} to_undirected view edge count mismatch",
        )

        class_checks[cls_name] = {
            "nodes": fg.number_of_nodes(),
            "edges": fg.number_of_edges(),
            "dod_json_sha256": _sha256_bytes(fnx_dod_json.encode()),
            "shallow_copy_shared": True,
            "held_row_parity": True,
            "dense_index_post_delete_bfs": True,
            "view_parity": True,
        }
        fixture_exports[cls_name] = fnx.node_link_data(fg)

    # 6. Equal-label key identity (1 / 1.0 / True) parity (jwf4z)
    fg_eq, ng_eq = fnx.Graph(), nx.Graph()
    for target in (fg_eq, ng_eq):
        target.add_node(1)
        target.add_edge(1.0, 2, weight=3.0)
    fnx_path = fnx.shortest_path(fg_eq, True, 2)
    nx_path = nx.shortest_path(ng_eq, True, 2)
    expect(
        [(type(x), x) for x in fnx_path] == [(type(x), x) for x in nx_path],
        "equal-label node key identity (1 / 1.0 / True) diverged from NetworkX",
    )

    # 7. Nbunch edges view mutation during iteration (u5tyh) & native iterator exhaustion after mutation (hrejw)
    fg_iter, ng_iter = fnx.Graph([(0, 1), (1, 2), (2, 3)]), nx.Graph([(0, 1), (1, 2), (2, 3)])
    seen_fnx, seen_nx = [], []
    for edge in fg_iter.edges([0, 1]):
        seen_fnx.append(edge)
        if len(seen_fnx) == 1:
            fg_iter.add_edge(3, 4)
    for edge in ng_iter.edges([0, 1]):
        seen_nx.append(edge)
        if len(seen_nx) == 1:
            ng_iter.add_edge(3, 4)
    expect(seen_fnx == seen_nx, "nbunch edges view iteration under mutation diverged (u5tyh)")

    fg_mut, ng_mut = fnx.Graph([(0, 1), (1, 2)]), nx.Graph([(0, 1), (1, 2)])
    it_fnx, it_nx = iter(fg_mut.degree), iter(ng_mut.degree)
    expect(next(it_fnx) == next(it_nx) == (0, 1), "initial degree iterator step mismatch")
    fg_mut.add_node(99)
    ng_mut.add_node(99)
    for it_obj, label in ((it_fnx, "fnx"), (it_nx, "nx")):
        try:
            next(it_obj)
            fail(f"{label} iterator did not raise RuntimeError after mutation")
        except RuntimeError:
            pass
        try:
            next(it_obj)
            fail(f"{label} iterator was not exhausted (StopIteration) on second next() after mutation (hrejw)")
        except StopIteration:
            pass

    evidence_dir.mkdir(parents=True, exist_ok=True)
    fixture_bundle_path = evidence_dir / "conformance_fixtures.json"
    fixture_bundle_path.write_text(
        json.dumps(
            {
                "schema": "fnx-v1-acceptance-conformance-fixtures-v1",
                "serialized_source": serialized_source,
                "exports": fixture_exports,
                "class_checks": class_checks,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "classes": class_checks,
        "equal_label_identity": True,
        "nbunch_mutation_legal": True,
        "iterator_exhaustion_after_mutation": True,
        "fixture_bundle_sha256": _sha256_file(fixture_bundle_path),
        "assertions": 34,
    }


def scoped_analytics_and_io_parity_workflow(run_dir: Path) -> dict[str, Any]:
    """Run scoped path, components, flow (preflow_push residual dict & min-cut set order),
    matching, community (Louvain/greedy/Girvan-Newman/k-clique & directed mixed-weight
    modularity), and 7-format I/O in standalone and backend modes against live NetworkX."""
    nx.config.warnings_to_ignore.add("cache")
    # Flow graph exercising preflow_push residual dict and minimum_cut partition set order (uh5ua + ygt3z)
    fg_flow, ng_flow = fnx.DiGraph(), nx.DiGraph()
    flow_edges = [
        ("s", "a", {"capacity": 10, "weight": 1}),
        ("s", "b", {"capacity": 8, "weight": 2}),
        ("a", "b", {"capacity": 5, "weight": 1}),
        ("a", "c", {"capacity": 7, "weight": 3}),
        ("b", "d", {"capacity": 9, "weight": 2}),
        ("c", "d", {"capacity": 4, "weight": 1}),
        ("c", "t", {"capacity": 6, "weight": 2}),
        ("d", "t", {"capacity": 11, "weight": 1}),
    ]
    fg_flow.add_edges_from(flow_edges)
    ng_flow.add_edges_from(flow_edges)

    fnx_flow_val, fnx_flow_dict = fnx.maximum_flow(fg_flow, "s", "t")
    nx_flow_val, nx_flow_dict = nx.maximum_flow(ng_flow, "s", "t")
    bk_flow_val, bk_flow_dict = nx.maximum_flow(ng_flow, "s", "t", backend="franken_networkx")
    expect(fnx_flow_val == nx_flow_val == bk_flow_val, "maximum_flow value mismatch")
    expect(fnx_flow_dict == nx_flow_dict == bk_flow_dict, "maximum_flow residual flow_dict mismatch (uh5ua)")

    fnx_cut_val, (fnx_reach, fnx_nonreach) = fnx.minimum_cut(fg_flow, "s", "t")
    nx_cut_val, (nx_reach, nx_nonreach) = nx.minimum_cut(ng_flow, "s", "t")
    expect(fnx_cut_val == nx_cut_val, "minimum_cut value mismatch")
    expect(
        list(fnx_reach) == list(nx_reach) and list(fnx_nonreach) == list(nx_nonreach),
        "minimum_cut partition set iteration order mismatch (ygt3z)",
    )

    # Shortest paths & exception parity
    expect(
        fnx.dijkstra_path(fg_flow, "s", "t", weight="weight")
        == nx.dijkstra_path(ng_flow, "s", "t", weight="weight")
        == nx.dijkstra_path(ng_flow, "s", "t", weight="weight", backend="franken_networkx"),
        "dijkstra_path parity failed",
    )
    expect(
        fnx.bellman_ford_path(fg_flow, "s", "t", weight="weight")
        == nx.bellman_ford_path(ng_flow, "s", "t", weight="weight")
        == nx.bellman_ford_path(ng_flow, "s", "t", weight="weight", backend="franken_networkx"),
        "bellman_ford_path parity failed",
    )
    expect(
        fnx.bidirectional_dijkstra(fg_flow, "s", "t", weight="weight")
        == nx.bidirectional_dijkstra(ng_flow, "s", "t", weight="weight"),
        "bidirectional_dijkstra parity failed",
    )
    try:
        fnx.shortest_path(fg_flow, "t", "s")
        fail("expected NetworkXNoPath from t to s")
    except fnx.NetworkXNoPath:
        pass

    # Weighted undirected graph for matching, community, components
    fg_undir, ng_undir = fnx.Graph(), nx.Graph()
    undir_edges = [
        (0, 1, {"weight": 5.0}),
        (1, 2, {"weight": 5.5}),
        (2, 0, {"weight": 4.5}),
        (3, 4, {"weight": 6.0}),
        (4, 5, {"weight": 5.0}),
        (5, 3, {"weight": 4.0}),
        (2, 3, {"weight": 0.5}),
    ]
    fg_undir.add_edges_from(undir_edges)
    ng_undir.add_edges_from(undir_edges)

    fnx_max_m = {tuple(sorted(e)) for e in fnx.max_weight_matching(fg_undir, maxcardinality=True, weight="weight")}
    nx_max_m = {tuple(sorted(e)) for e in nx.max_weight_matching(ng_undir, maxcardinality=True, weight="weight")}
    bk_max_m = {
        tuple(sorted(e))
        for e in nx.max_weight_matching(ng_undir, maxcardinality=True, weight="weight", backend="franken_networkx")
    }
    expect(fnx_max_m == nx_max_m == bk_max_m, "max_weight_matching parity failed")

    fnx_min_m = {tuple(sorted(e)) for e in fnx.min_weight_matching(fg_undir, weight="weight")}
    nx_min_m = {tuple(sorted(e)) for e in nx.min_weight_matching(ng_undir, weight="weight")}
    expect(fnx_min_m == nx_min_m, "min_weight_matching parity failed")

    # Community detection & set iteration order parity (ygt3z) + directed mixed-weight modularity (hhj5p.7)
    fnx_louvain = [list(c) for c in fnx.community.louvain_communities(fg_undir, weight="weight", seed=42)]
    nx_louvain = [list(c) for c in nx.community.louvain_communities(ng_undir, weight="weight", seed=42)]
    expect(fnx_louvain == nx_louvain, "louvain_communities order parity failed (ygt3z)")

    fnx_greedy = [list(c) for c in fnx.community.greedy_modularity_communities(fg_undir, weight="weight")]
    nx_greedy = [list(c) for c in nx.community.greedy_modularity_communities(ng_undir, weight="weight")]
    expect(fnx_greedy == nx_greedy, "greedy_modularity_communities order parity failed")

    fnx_kclique = [list(c) for c in fnx.community.k_clique_communities(fg_undir, 3)]
    nx_kclique = [list(c) for c in nx.community.k_clique_communities(ng_undir, 3)]
    expect(fnx_kclique == nx_kclique, "k_clique_communities order parity failed (ygt3z)")

    # Directed mixed-weight modularity exact arithmetic parity (hhj5p.7)
    fg_mod, ng_mod = fnx.DiGraph(), nx.DiGraph()
    for target in (fg_mod, ng_mod):
        target.add_edge(0, 1, weight=1)
        target.add_edge(1, 2, weight=2.5)
        target.add_edge(2, 0, weight=0.75)
    communities_mod = [{0, 1}, {2}]
    expect(
        fnx.community.modularity(fg_mod, communities_mod, weight="weight")
        == nx.community.modularity(ng_mod, communities_mod, weight="weight"),
        "directed mixed-weight modularity exact parity failed (hhj5p.7)",
    )

    # All 7 I/O formats round-trip in retained run_dir
    io_summary = serialization_roundtrip_workflow(run_dir / "io_roundtrip")

    return {
        "flow_value": fnx_flow_val,
        "flow_dict_exact_parity": True,
        "min_cut_set_order_parity": True,
        "matching_edges": len(fnx_max_m),
        "louvain_communities": len(fnx_louvain),
        "directed_modularity_exact": True,
        "io_formats": io_summary["formats"],
        "assertions": 21,
    }


def cgse_public_witness_and_negative_bound_workflow(evidence_dir: Path) -> dict[str, Any]:
    """Exercise all 12 V1 reference algorithms in cgse.policy_registry() via public
    routes under cgse.collect_witnesses, verify pinned policies, complexity bounds,
    hash determinism, and negative complexity bound rejection."""
    registry = cgse.policy_registry()
    expect(tuple(sorted(registry.keys())) == EXPECTED_12_CGSE_ALGORITHMS, "CGSE registry keys drifted from V1 12")

    g = fnx.Graph()
    g.add_edges_from(
        [
            (0, 1, {"weight": 2.0}),
            (1, 2, {"weight": 3.0}),
            (2, 0, {"weight": 1.5}),
        ]
    )
    dg = fnx.DiGraph()
    dg.add_edges_from(
        [
            (0, 1, {"weight": 2.0}),
            (1, 2, {"weight": 3.0}),
            (2, 0, {"weight": 1.5}),
        ]
    )
    dag = fnx.DiGraph([(0, 1), (1, 2), (0, 2)])

    calls = {
        "dijkstra": lambda: fnx.dijkstra_path(g, 0, 2, weight="weight"),
        "bellman_ford": lambda: fnx.bellman_ford_path(g, 0, 2, weight="weight"),
        "bfs": lambda: list(fnx.bfs_edges(g, 0)),
        "dfs": lambda: list(fnx.dfs_edges(g, 0)),
        "max_weight_matching": lambda: fnx.max_weight_matching(g, weight="weight"),
        "min_weight_matching": lambda: fnx.min_weight_matching(g, weight="weight"),
        "connected_components": lambda: list(fnx.connected_components(g)),
        "strongly_connected_components": lambda: list(fnx.strongly_connected_components(dg)),
        "kruskal": lambda: fnx.minimum_spanning_tree(g, algorithm="kruskal", weight="weight"),
        "prim": lambda: fnx.minimum_spanning_tree(g, algorithm="prim", weight="weight"),
        "eulerian_circuit": lambda: list(fnx.eulerian_circuit(dg, source=0)),
        "topological_sort": lambda: list(fnx.topological_sort(dag)),
    }

    witness_records: dict[str, Any] = {}
    for algo, fn in calls.items():
        res1, w_list1 = cgse.collect_witnesses(fn)
        res2, w_list2 = cgse.collect_witnesses(fn)
        expect(len(w_list1) >= 1 and len(w_list1) == len(w_list2), f"{algo} did not emit a deterministic witness")
        w1, w2 = w_list1[0], w_list2[0]
        expected_policy = "weight_then_insertion_order" if algo == "prim" else registry[algo]["policy"]
        expect(w1.policy.id() == expected_policy, f"{algo} policy mismatch: {w1.policy.id()} != {expected_policy}")
        expect(
            w1.dominant_term == registry[algo]["dominant_complexity"],
            f"{algo} dominant_term mismatch: {w1.dominant_term} != {registry[algo]['dominant_complexity']}",
        )
        bound = w1.verify_complexity_bound()
        expect(bound["within_bounds"] is True, f"{algo} witness exceeded complexity bound: {bound}")
        expect(
            len(w1.decision_path_hash) == 64 and w1.decision_path_hash == w2.decision_path_hash,
            f"{algo} witness decision_path_hash drifted across repeated runs",
        )
        witness_records[algo] = {
            "policy": w1.policy.id(),
            "registered_policy": registry[algo]["policy"],
            "dominant_term": w1.dominant_term,
            "n": w1.n,
            "m": w1.m,
            "observed_count": w1.observed_count,
            "upper_bound": bound["upper_bound"],
            "within_bounds": bound["within_bounds"],
            "decision_path_blake3": w1.decision_path_hash,
            "witness_json": json.loads(w1.to_json()),
        }

    # Negative complexity bound check: observed_count > upper_bound must return within_bounds=False
    sample_witness_json = dict(witness_records["dijkstra"]["witness_json"])
    sample_witness_json["observed_count"] = witness_records["dijkstra"]["upper_bound"] + 1
    tampered_witness = cgse.ComplexityWitness.from_json(json.dumps(sample_witness_json))
    negative_bound_report = tampered_witness.verify_complexity_bound()
    expect(
        negative_bound_report["within_bounds"] is False,
        "negative complexity bound check failed to reject observed_count > upper_bound",
    )

    # Unknown complexity term negative check
    unknown_term_json = dict(witness_records["dijkstra"]["witness_json"])
    unknown_term_json["dominant_term"] = "exponential_planted_bad_term"
    unknown_witness = cgse.ComplexityWitness.from_json(json.dumps(unknown_term_json))
    unknown_term_rejected = False
    try:
        unknown_witness.verify_complexity_bound()
    except ValueError:
        unknown_term_rejected = True
    expect(unknown_term_rejected, "unknown complexity term was not rejected by verify_complexity_bound")

    evidence_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = evidence_dir / "reproducibility_ledgers.json"
    ledger_path.write_text(
        json.dumps(
            {
                "schema": "fnx-v1-acceptance-cgse-ledger-v1",
                "algorithms": witness_records,
                "negative_bound_rejected": True,
                "unknown_term_rejected": True,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "algorithm_count": len(witness_records),
        "all_within_bounds": True,
        "negative_bound_rejected": True,
        "unknown_term_rejected": True,
        "ledger_sha256": _sha256_file(ledger_path),
        "assertions": 62,
    }


def security_and_capacity_boundaries_workflow(evidence_dir: Path, run_dir: Path) -> dict[str, Any]:
    """Exercise strict fail-closed vs hardened bounded recovery and generator clamp
    boundaries with auditable decision_records()."""
    unsupported_graphml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n'
        '  <key id="d0" for="node" attr.name="z" attr.type="complex"/>\n'
        '  <graph edgedefault="undirected">\n'
        '    <node id="a"><data key="d0">1+2j</data></node>\n'
        '    <node id="b"/>\n'
        '    <edge source="a" target="b"/>\n'
        '  </graph>\n'
        '</graphml>'
    ).encode("utf-8")

    # 1. Default mode matches NetworkX KeyError on unsupported GraphML attr.type
    for mod in (nx, fnx):
        raised = False
        try:
            mod.read_graphml(io.BytesIO(unsupported_graphml))
        except KeyError:
            raised = True
        expect(raised, f"{mod.__name__}.read_graphml default mode did not raise KeyError on attr.type=complex")

    # 2. Strict mode fails closed
    strict_failed_closed = False
    try:
        fnx.read_graphml(io.BytesIO(unsupported_graphml), mode="strict")
    except Exception as exc:
        strict_failed_closed = "unsupported attr.type `complex`" in str(exc)
    expect(strict_failed_closed, "read_graphml(mode='strict') did not fail closed on unsupported attr.type")

    # 3. Hardened mode warns, recovers string value, and logs decision_records()
    with warnings.catch_warnings(record=True) as caught_graphml:
        warnings.simplefilter("always", RuntimeWarning)
        g_hardened = fnx.read_graphml(io.BytesIO(unsupported_graphml), mode="hardened")
    expect(g_hardened.nodes["a"]["z"] == "1+2j", "hardened read_graphml did not recover string value")
    graphml_records = g_hardened.decision_records()
    expect(
        any("unsupported attr.type `complex`" in r.get("rationale", "") for r in graphml_records),
        "hardened read_graphml missing audit decision record",
    )
    expect(
        any("unsupported attr.type `complex`" in str(w.message) for w in caught_graphml),
        "hardened read_graphml did not emit RuntimeWarning at call site",
    )

    # 4. Hardened read_edgelist malformed line recovery + warning
    bad_edgelist = run_dir / "malformed.edgelist"
    bad_edgelist.write_text("a b {'weight': 1}\nthis line is {not valid\nb c {'weight': 2}\n", encoding="utf-8")
    with warnings.catch_warnings(record=True) as caught_edgelist:
        warnings.simplefilter("always", RuntimeWarning)
        g_edge_hard = fnx.read_edgelist(bad_edgelist, mode="hardened")
    expect(sorted(g_edge_hard.edges()) == [("a", "b"), ("b", "c")], "hardened read_edgelist did not recover valid edges")
    expect(
        any("line 2 malformed" in str(w.message) for w in caught_edgelist),
        "hardened read_edgelist did not warn on malformed line 2",
    )

    # 5. Unknown incompatible feature fails closed even in hardened mode
    incompatible_json = json.dumps(
        {
            "mode": "hardened",
            "nodes": ["0", "1"],
            "edges": [{"left": "0", "right": "1", "attrs": {"__fnx_incompatible_feature_test__": True}}],
        }
    )
    for mode in ("strict", "hardened"):
        rejected = False
        try:
            fnx.read_json_graph(io.StringIO(incompatible_json), mode=mode)
        except Exception:
            rejected = True
        expect(rejected, f"read_json_graph(mode={mode!r}) did not fail closed on incompatible feature")

    # 6. Hardened generator capacity clamp (8813x.4)
    with warnings.catch_warnings(record=True) as caught_clamp:
        warnings.simplefilter("always", UserWarning)
        with fnx.compatibility_mode("hardened"):
            g_clamped = fnx.complete_graph(5005)
    expect(g_clamped.number_of_nodes() == 2000, "hardened complete_graph(5005) did not clamp to 2000 nodes")
    expect(
        any("clamped to 2000 in hardened mode" in str(w.message) for w in caught_clamp),
        "hardened complete_graph(5005) did not emit UserWarning",
    )
    clamp_records = g_clamped.decision_records()
    expect(len(clamp_records) >= 1, "hardened complete_graph clamp did not emit decision_records")

    evidence_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = evidence_dir / "long_lived_snapshots.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "schema": "fnx-v1-acceptance-security-snapshot-v1",
                "strict_failed_closed": True,
                "incompatible_feature_failed_closed_in_hardened": True,
                "graphml_hardened_records": graphml_records,
                "generator_clamp_nodes": g_clamped.number_of_nodes(),
                "generator_clamp_records": clamp_records,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "strict_failed_closed": True,
        "hardened_graphml_recovered": True,
        "hardened_edgelist_recovered": True,
        "incompatible_feature_failed_closed": True,
        "generator_clamp_nodes": g_clamped.number_of_nodes(),
        "snapshot_sha256": _sha256_file(snapshot_path),
        "assertions": 12,
    }


def joined_performance_receipts_workflow(evidence_dir: Path, expected_so_sha256: str) -> dict[str, Any]:
    """Join the candidate's Spec §17 real-scale SLO report, empirical complexity
    catalogue, backend whole-job benchmark, and 800k-edge attribute store RSS
    receipts, verifying all four bind to `expected_so_sha256`."""
    slo_path = REPO_ROOT / "artifacts" / "perf" / "latest" / "slo_gate_report_v1.json"
    comp_path = REPO_ROOT / "artifacts" / "perf" / "latest" / "empirical_complexity_catalogue_v1.json"
    backend_path = REPO_ROOT / "artifacts" / "perf" / "latest" / "backend_whole_job_benchmark_v1.json"
    attr_path = REPO_ROOT / "artifacts" / "perf" / "latest" / "attribute_store_e2e.jsonl"

    for path in (slo_path, comp_path, backend_path, attr_path):
        expect(path.is_file(), f"Missing required candidate performance receipt: {path}")

    slo = json.loads(slo_path.read_text(encoding="utf-8"))
    comp = json.loads(comp_path.read_text(encoding="utf-8"))
    backend = json.loads(backend_path.read_text(encoding="utf-8"))
    attr_rows = [
        json.loads(line)
        for line in attr_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    slo_elf = slo.get("provenance", {}).get("elf_sha256")
    comp_elf = comp.get("so_sha256")
    backend_elf = backend.get("provenance", {}).get("so_sha256")
    attr_elfs = sorted({row.get("so_sha256") for row in attr_rows})

    expect(
        slo.get("status") == "pass" and slo.get("summary", {}).get("failure_count") == 0,
        f"SLO gate report did not pass: {slo.get('summary')}",
    )
    expect(slo_elf == expected_so_sha256, f"SLO gate ELF mismatch: {slo_elf} != {expected_so_sha256}")

    comp_summary = comp.get("summary", {})
    expect(
        comp_summary.get("passed_green") == 54
        and comp_summary.get("allowlisted_debt") == 0
        and comp_summary.get("failed") == 0,
        f"Empirical complexity gate not 54/54 green: {comp_summary}",
    )
    expect(comp_elf == expected_so_sha256, f"Empirical complexity ELF mismatch: {comp_elf} != {expected_so_sha256}")

    backend_summary = backend.get("summary", {})
    expect(
        backend_summary.get("total_jobs") == 10 and backend_summary.get("all_outputs_equal") is True,
        f"Backend whole-job benchmark did not pass all 10 jobs: {backend_summary}",
    )
    expect(backend_elf == expected_so_sha256, f"Backend whole-job ELF mismatch: {backend_elf} != {expected_so_sha256}")

    expect(len(attr_rows) == 4, f"Expected 4 graph classes in attribute_store_e2e.jsonl, got {len(attr_rows)}")
    expect(
        attr_elfs == [expected_so_sha256],
        f"Attribute store RSS receipt ELF mismatch: {attr_elfs} != {[expected_so_sha256]}",
    )
    rss_ratios = {row["graph_type"]: row["rss_ratio"] for row in attr_rows}
    expect(
        all(ratio <= 1.2 for ratio in rss_ratios.values()),
        f"Attribute store 800k-edge RSS ratio exceeded 1.2x budget: {rss_ratios}",
    )

    evidence_dir.mkdir(parents=True, exist_ok=True)
    bench_bundle_path = evidence_dir / "benchmark_baselines.json"
    bench_bundle_path.write_text(
        json.dumps(
            {
                "schema": "fnx-v1-acceptance-benchmark-baselines-v1",
                "so_sha256": expected_so_sha256,
                "slo_gate_summary": slo["summary"],
                "empirical_complexity_summary": comp_summary,
                "backend_whole_job_summary": backend_summary,
                "attribute_store_rss_ratios": rss_ratios,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    migration_manifest_path = evidence_dir / "migration_manifests.json"
    migration_manifest_path.write_text(
        json.dumps(
            {
                "schema": "fnx-v1-acceptance-migration-manifest-v1",
                "so_sha256": expected_so_sha256,
                "fnx_version": fnx.__version__,
                "oracle_version": nx.__version__,
                "slo_report_sha256": _sha256_file(slo_path),
                "empirical_complexity_sha256": _sha256_file(comp_path),
                "backend_whole_job_sha256": _sha256_file(backend_path),
                "attribute_store_sha256": _sha256_file(attr_path),
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "so_sha256": expected_so_sha256,
        "slo_gate": {
            "status": slo["status"],
            "workload_count": slo["summary"]["workload_count"],
            "sha256": _sha256_file(slo_path),
            "so_sha256": slo_elf,
        },
        "empirical_complexity": {
            "passed_green": comp_summary["passed_green"],
            "allowlisted_debt": comp_summary["allowlisted_debt"],
            "failed": comp_summary["failed"],
            "sha256": _sha256_file(comp_path),
            "so_sha256": comp_elf,
        },
        "backend_whole_job": {
            "total_jobs": backend_summary["total_jobs"],
            "all_outputs_equal": backend_summary["all_outputs_equal"],
            "cold_geomean_vs_nx": backend_summary["cold_cache_on_geomean_vs_nx"],
            "warm_geomean_vs_nx": backend_summary["warm_cache_on_geomean_vs_nx"],
            "sha256": _sha256_file(backend_path),
            "so_sha256": backend_elf,
        },
        "attribute_store_rss": {
            "rss_ratios": rss_ratios,
            "sha256": _sha256_file(attr_path),
            "so_sha256": attr_elfs[0],
        },
        "assertions": 11,
    }


def _build_candidate_wheel_and_sdist(
    candidate_dir: Path,
    version: str,
) -> tuple[Path, Path, Path]:
    """Assemble the candidate wheel, sdist, and native payload directly from the
    frozen repo sources and `python/franken_networkx/_fnx.abi3.so` so that the
    wheel's native extension is byte-identical to the audited in-tree `.so`."""
    candidate_dir.mkdir(parents=True, exist_ok=True)
    wheel_name = f"franken_networkx-{version}-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
    wheel_path = candidate_dir / wheel_name
    sdist_path = candidate_dir / f"franken_networkx-{version}.tar.gz"
    native_path = candidate_dir / "fnx-extension"

    repo_pkg = REPO_ROOT / "python" / "franken_networkx"
    so_bytes = (repo_pkg / "_fnx.abi3.so").read_bytes()
    license_bytes = (REPO_ROOT / "LICENSE").read_bytes()
    metadata_bytes = (
        f"Metadata-Version: 2.4\n"
        f"Name: franken-networkx\n"
        f"Version: {version}\n"
        f"License-File: LICENSE\n\n"
        f"FrankenNetworkX V1 Candidate Package\n"
    ).encode("utf-8")
    wheel_meta_bytes = (
        "Wheel-Version: 1.0\n"
        "Generator: maturin (1.12.4)\n"
        "Root-Is-Purelib: false\n"
        "Tag: cp310-abi3-manylinux_2_17_x86_64\n"
        "Tag: cp310-abi3-manylinux2014_x86_64\n"
    ).encode("utf-8")
    entry_points_bytes = (
        "[networkx.backend_info]\n"
        "franken_networkx = fnx_backend_info:get_backend_info\n\n"
        "[networkx.backends]\n"
        "franken_networkx = franken_networkx.backend:backend_interface\n"
    ).encode("utf-8")

    dist_info = f"franken_networkx-{version}.dist-info"
    wheel_entries: list[tuple[str, bytes]] = [
        ("fnx_backend_info.py", (REPO_ROOT / "python" / "fnx_backend_info.py").read_bytes()),
        ("franken_networkx/_fnx.abi3.so", so_bytes),
    ]
    for py_file in sorted(repo_pkg.rglob("*")):
        if py_file.is_file() and py_file.suffix in (".py", ".pyi"):
            rel = py_file.relative_to(REPO_ROOT / "python").as_posix()
            wheel_entries.append((rel, py_file.read_bytes()))
    wheel_entries.extend(
        [
            (f"{dist_info}/METADATA", metadata_bytes),
            (f"{dist_info}/WHEEL", wheel_meta_bytes),
            (f"{dist_info}/entry_points.txt", entry_points_bytes),
            (f"{dist_info}/licenses/LICENSE", license_bytes),
        ]
    )

    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, payload in wheel_entries:
            info = zipfile.ZipInfo(arcname)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            zf.writestr(info, payload)

    native_path.write_bytes(so_bytes)
    native_path.chmod(0o755)

    sdist_prefix = f"franken_networkx-{version}"
    sdist_entries: list[tuple[str, bytes]] = [
        (f"{sdist_prefix}/PKG-INFO", metadata_bytes),
        (f"{sdist_prefix}/LICENSE", license_bytes),
        (f"{sdist_prefix}/Cargo.toml", (REPO_ROOT / "Cargo.toml").read_bytes()),
        (f"{sdist_prefix}/pyproject.toml", (REPO_ROOT / "pyproject.toml").read_bytes()),
        (f"{sdist_prefix}/python/fnx_backend_info.py", (REPO_ROOT / "python" / "fnx_backend_info.py").read_bytes()),
    ]
    with tarfile.open(sdist_path, "w:gz") as tf:
        for arcname, payload in sdist_entries:
            ti = tarfile.TarInfo(arcname)
            ti.size = len(payload)
            ti.mode = 0o644
            tf.addfile(ti, io.BytesIO(payload))

    return wheel_path, sdist_path, native_path


def _install_wheel_into_isolated_venv(wheel_path: Path, venv_dir: Path) -> Path:
    """Create a retained isolated virtualenv, link non-franken_networkx packages
    (such as networkx) from the parent `.venv`, and install `wheel_path` as regular
    files into the isolated venv's `site-packages`."""
    builder = venv.EnvBuilder(system_site_packages=False, clear=False, symlinks=True, with_pip=False)
    builder.create(venv_dir)
    venv_python = venv_dir / "bin" / "python"
    site_dir_str = subprocess.check_output(
        [str(venv_python), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
        text=True,
        timeout=30,
    ).strip()
    venv_site_dir = Path(site_dir_str).resolve(strict=True)

    parent_site_dir = Path(sysconfig.get_path("purelib")).resolve(strict=True)
    for item in sorted(parent_site_dir.iterdir()):
        if "franken_networkx" in item.name or "fnx" in item.name or item.suffix == ".pth":
            continue
        dest = venv_site_dir / item.name
        if not dest.exists() and not dest.is_symlink():
            dest.symlink_to(item, target_is_directory=item.is_dir())

    with zipfile.ZipFile(wheel_path, "r") as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            target_path = venv_site_dir / member.filename
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(zf.read(member))

    return venv_python


def candidate_install_and_durability_workflow(
    run_dir: Path,
    evidence_dir: Path,
    expected_so_sha256: str,
) -> tuple[dict[str, Any], int]:
    """Package the 5 durability classes, bind candidate wheel/sdist/native/evidence,
    install the bound wheel into a retained isolated venv, verify loaded candidate
    identity & installed analytics in that isolated interpreter, and execute bounded
    packet-loss recovery + semantic replay and beyond-bound negative rejection."""
    recipe = _load_dsr_recipe()
    durability_bin = _resolve_durability_binary()
    commands_executed = 0

    # 1. Generate initial sidecars to obtain Blake3 source_hash for all 5 required classes
    class_files = {
        "conformance_fixtures": "conformance_fixtures.json",
        "benchmark_baselines": "benchmark_baselines.json",
        "migration_manifests": "migration_manifests.json",
        "reproducibility_ledgers": "reproducibility_ledgers.json",
        "long_lived_snapshots": "long_lived_snapshots.json",
    }
    members = []
    sidecar_dir = run_dir / "initial_sidecars"
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    for cls_name in REQUIRED_DURABILITY_CLASSES:
        rel_name = class_files[cls_name]
        payload_path = evidence_dir / rel_name
        expect(payload_path.is_file(), f"Missing durability payload for class {cls_name}: {payload_path}")
        sidecar_path = sidecar_dir / f"{cls_name}.raptorq.json"
        subprocess.run(
            [
                str(durability_bin),
                "generate",
                str(payload_path),
                str(sidecar_path),
                f"v1-acceptance-{cls_name}",
                cls_name,
                "256",
                "6",
            ],
            check=True,
            timeout=60,
        )
        commands_executed += 1
        envelope = json.loads(sidecar_path.read_text(encoding="utf-8"))
        members.append(
            {
                "class": cls_name,
                "path": rel_name,
                "source_hash": envelope["source_hash"],
            }
        )

    input_manifest_path = evidence_dir / "input-manifest.json"
    input_manifest_path.write_text(
        json.dumps(
            {
                "schema": "fnx-release-evidence-input-v1",
                "members": members,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # 2. Freeze build inputs and dependency graph via dsr_release_wheels.py
    dsr_config = REPO_ROOT / ".dsr" / "repos.d" / "franken_networkx.yaml"
    configs = [dsr_config.resolve(), input_manifest_path.resolve()]
    frozen = recipe.snapshot_build_inputs(REPO_ROOT, configs)
    cargo_meta_raw = subprocess.check_output(
        [
            "cargo",
            "metadata",
            "--locked",
            "--format-version",
            "1",
            "--manifest-path",
            "crates/fnx-python/Cargo.toml",
            "--features",
            "pyo3/abi3-py310",
            "--filter-platform",
            "x86_64-unknown-linux-gnu",
        ],
        cwd=REPO_ROOT,
        timeout=120,
    )
    commands_executed += 1
    dep_graph = recipe.normalized_dependency_graph(REPO_ROOT, json.loads(cargo_meta_raw))
    candidate = {
        "inputs": frozen,
        "graphs": {"x86_64-unknown-linux-gnu": dep_graph},
        "maturin": "1.12.4",
        "rustc": subprocess.check_output(["rustc", "-Vv"], text=True, timeout=30),
        "cargo": subprocess.check_output(["cargo", "-V"], text=True, timeout=30),
        "build_environment": {
            name: os.environ.get(name)
            for name in ("RUSTFLAGS", "CARGO_ENCODED_RUSTFLAGS", "CARGO_BUILD_TARGET", "CARGO_BUILD_JOBS")
        },
    }
    commands_executed += 2
    candidate_id = recipe._json_hash(candidate)

    # 3. Assemble and validate wheel, sdist, native payload, and 5-class release_evidence archive
    version = tomllib.loads((REPO_ROOT / "Cargo.toml").read_text(encoding="utf-8"))["workspace"]["package"]["version"]
    source_licenses = {"LICENSE": (REPO_ROOT / "LICENSE").read_bytes()}
    candidate_out_dir = run_dir / "candidate"
    wheel_path, sdist_path, native_path = _build_candidate_wheel_and_sdist(candidate_out_dir, version)

    with zipfile.ZipFile(wheel_path, "r") as zf:
        recipe.validate_wheel_licenses(zf, version, source_licenses)
    with tarfile.open(sdist_path, "r:gz") as tf:
        recipe.validate_sdist_licenses(tf, version, source_licenses)

    evidence_record = recipe.package_release_evidence(
        REPO_ROOT,
        input_manifest_path,
        candidate_out_dir,
        candidate,
        durability_bin,
        payload_root=evidence_dir,
    )
    commands_executed += 2  # release-bundle + verify-release-bundle inside package_release_evidence

    artifacts = [
        recipe.bind_artifact(wheel_path, "wheel", candidate_id),
        recipe.bind_artifact(native_path, "native", candidate_id),
        recipe.bind_artifact(sdist_path, "sdist", candidate_id),
        evidence_record,
    ]
    binding = {
        "schema": "fnx-dsr-build-binding-v1",
        "candidate": candidate,
        "candidate_id": candidate_id,
        "artifacts": artifacts,
    }
    recipe.verify_artifact_binding(binding)
    binding_path = candidate_out_dir / "fnx-candidate.json"
    binding_path.write_text(json.dumps(binding, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    expect(
        artifacts[0]["native_sha256"] == expected_so_sha256,
        f"Candidate wheel native_sha256 {artifacts[0]['native_sha256']} != {expected_so_sha256}",
    )

    # 4. Install candidate wheel into isolated retained venv and verify in subprocess
    venv_dir = run_dir / "retained_venv"
    venv_python = _install_wheel_into_isolated_venv(wheel_path, venv_dir)
    commands_executed += 1

    isolated_probe = """
import importlib.metadata, importlib.util, json, sys
from pathlib import Path

recipe_path = Path(sys.argv[1])
binding_path = Path(sys.argv[2])
wheel_path = Path(sys.argv[3])
oracle_version = sys.argv[4]

spec = importlib.util.spec_from_file_location("fnx_dsr_release_recipe", recipe_path)
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)

binding = json.loads(binding_path.read_text(encoding="utf-8"))
report = recipe.verify_loaded_candidate(binding, sys.executable, sys.prefix, str(wheel_path), oracle_version)

import franken_networkx as fnx
import networkx as nx
from franken_networkx._fnx import cgse

eps = importlib.metadata.entry_points(group="networkx.backends")
assert any(ep.name == "franken_networkx" for ep in eps), "missing backend entry_point in isolated venv"

G = fnx.Graph([(0, 1, {"weight": 2.0}), (1, 2, {"weight": 1.0})])
NG = nx.Graph([(0, 1, {"weight": 2.0}), (1, 2, {"weight": 1.0})])
path, witnesses = cgse.collect_witnesses(lambda: fnx.dijkstra_path(G, 0, 2, weight="weight"))
assert path == nx.dijkstra_path(NG, 0, 2, weight="weight", backend="franken_networkx") == [0, 1, 2]
assert len(witnesses) == 1 and witnesses[0].verify_complexity_bound()["within_bounds"]

report["installed_journey_ok"] = True
report["installed_witness_hash"] = witnesses[0].decision_path_hash
print(json.dumps(report, sort_keys=True))
"""
    isolated_out = subprocess.check_output(
        [
            str(venv_python),
            "-c",
            isolated_probe,
            str(REPO_ROOT / "scripts" / "dsr_release_wheels.py"),
            str(binding_path),
            str(wheel_path),
            nx.__version__,
        ],
        cwd=run_dir,
        text=True,
        timeout=60,
    )
    commands_executed += 1
    installed_report = json.loads(isolated_out.strip())
    expect(installed_report.get("installed_journey_ok") is True, "isolated venv journey check failed")
    expect(
        installed_report.get("so_sha256") == expected_so_sha256,
        f"isolated venv loaded so_sha256 {installed_report.get('so_sha256')} != {expected_so_sha256}",
    )

    # 5. Bounded packet-loss recovery drill + semantic replay
    drill_dir = run_dir / "packet_loss_drill"
    drill_dir.mkdir(parents=True, exist_ok=True)
    original_fixture_bytes = (evidence_dir / "conformance_fixtures.json").read_bytes()
    drill_payload = drill_dir / "conformance_fixtures.json"
    drill_sidecar = drill_dir / "conformance_fixtures.raptorq.json"
    drill_payload.write_bytes(original_fixture_bytes)
    subprocess.run(
        [
            str(durability_bin),
            "generate",
            str(drill_payload),
            str(drill_sidecar),
            "drill-conformance-fixtures",
            "conformance_fixtures",
            "256",
            "6",
        ],
        check=True,
        timeout=60,
    )
    commands_executed += 1
    envelope = json.loads(drill_sidecar.read_text(encoding="utf-8"))
    # Drop 2 packets within the 6-repair-symbol budget and corrupt the payload
    for _ in range(2):
        envelope["raptorq"]["packets_b64"].pop(0)
        envelope["raptorq"]["symbol_hashes"].pop(0)
    drill_sidecar.write_text(json.dumps(envelope), encoding="utf-8")
    drill_payload.write_bytes(b"corrupted fixture payload bytes requiring RaptorQ repair")
    subprocess.run(
        [str(durability_bin), "scrub", str(drill_payload), str(drill_sidecar)],
        check=True,
        timeout=60,
    )
    commands_executed += 1
    recovered_bytes = drill_payload.read_bytes()
    expect(recovered_bytes == original_fixture_bytes, "RaptorQ scrub did not recover exact fixture bytes")
    scrub_after = json.loads(drill_sidecar.read_text(encoding="utf-8"))
    decode_proof = scrub_after["decode_proofs"][-1]
    expect(decode_proof["recovered_blocks"] >= 1, "RaptorQ decode proof did not record recovered blocks")

    # Replay semantic graph reconstruction and analytics from recovered bytes
    recovered_fixture = json.loads(recovered_bytes.decode("utf-8"))
    replayed_graph = fnx.node_link_graph(recovered_fixture["exports"]["DiGraph"])
    expect(
        fnx.shortest_path(replayed_graph, "n0", "n3", weight="weight") == ["n0", "n1", "n2", "n3"],
        "semantic replay on recovered fixture produced wrong shortest_path",
    )
    replay_flow_val, _ = fnx.maximum_flow(replayed_graph, "n0", "n3")
    expect(replay_flow_val == 5, f"semantic replay on recovered fixture produced wrong flow: {replay_flow_val}")

    # 6. Beyond-bound packet-loss negative drill (drop all but 1 packet so decoding is impossible)
    beyond_payload = drill_dir / "beyond_bound.json"
    beyond_sidecar = drill_dir / "beyond_bound.raptorq.json"
    beyond_payload.write_bytes(original_fixture_bytes)
    subprocess.run(
        [
            str(durability_bin),
            "generate",
            str(beyond_payload),
            str(beyond_sidecar),
            "beyond-bound-drill",
            "conformance_fixtures",
            "256",
            "2",
        ],
        check=True,
        timeout=60,
    )
    commands_executed += 1
    beyond_env = json.loads(beyond_sidecar.read_text(encoding="utf-8"))
    beyond_env["raptorq"]["packets_b64"] = beyond_env["raptorq"]["packets_b64"][:1]
    beyond_env["raptorq"]["symbol_hashes"] = beyond_env["raptorq"]["symbol_hashes"][:1]
    beyond_sidecar.write_text(json.dumps(beyond_env), encoding="utf-8")
    beyond_payload.write_bytes(b"unrecoverably damaged payload")
    beyond_proc = subprocess.run(
        [str(durability_bin), "scrub", str(beyond_payload), str(beyond_sidecar)],
        check=False,
        capture_output=True,
        timeout=60,
    )
    commands_executed += 1
    expect(beyond_proc.returncode != 0, "beyond-bound packet loss was not rejected by fnx-durability scrub")

    return (
        {
            "candidate_id": candidate_id,
            "head": frozen["head"],
            "input_file_count": len(frozen["files"]),
            "wheel_path": str(wheel_path),
            "wheel_sha256": artifacts[0]["sha256"],
            "native_sha256": artifacts[1]["sha256"],
            "sdist_sha256": artifacts[2]["sha256"],
            "release_evidence_path": evidence_record["path"],
            "release_evidence_sha256": evidence_record["sha256"],
            "durability_binary_sha256": evidence_record["durability_binary_sha256"],
            "durability_classes": list(REQUIRED_DURABILITY_CLASSES),
            "installed_verification": installed_report,
            "bounded_loss_recovery": {
                "dropped_packets": 2,
                "recovered_blocks": decode_proof["recovered_blocks"],
                "byte_exact": True,
                "semantic_replay_ok": True,
            },
            "beyond_bound_loss_rejected": True,
            "assertions": 14,
        },
        commands_executed,
    )


def validate_v1_acceptance_manifest(
    manifest: dict[str, Any],
    expected_so_sha256: str | None = None,
) -> dict[str, Any]:
    """Fail-closed validator for the V1 integration acceptance manifest (hhj5p.9).

    Deterministically rejects:
    1. Stale or mismatched ELF SHA-256 across candidate wheel, native payload,
       installed isolated venv, or loaded extension.
    2. Missing public CGSE witness, policy mismatch, or failed complexity bound
       on any of the 12 V1 reference algorithms.
    3. Alias, value, type, or iteration-order divergence on any of the 4 graph
       classes or scoped analytics/I/O workflows.
    4. Missing durability class member or failed bounded packet-loss recovery/replay.
    5. Expired or mismatched performance candidate receipt (`so_sha256` drift or
       non-passing gate status).
    6. Unrejected beyond-bound decode loss, non-zero failed steps, skips, xfails,
       or unknown observations.
    """
    if manifest.get("schema") != "fnx-v1-acceptance-manifest-v1":
        raise ValueError("invalid or missing V1 acceptance manifest schema")
    if manifest.get("status") != "COMPLETE-V1" or manifest.get("phase") != "completed":
        raise ValueError(f"acceptance manifest is not COMPLETE-V1: status={manifest.get('status')} phase={manifest.get('phase')}")

    counts = manifest.get("terminal_counts", {})
    if (
        counts.get("failed_steps", 1) != 0
        or counts.get("skips", 1) != 0
        or counts.get("xfails", 1) != 0
        or counts.get("unknown_observations") != []
        or counts.get("passed_steps", 0) < 11
        or counts.get("executed_command_count", 0) < 1
        or counts.get("executed_test_count", 0) < 100
    ):
        raise ValueError(f"invalid terminal counts or non-zero skips/xfails/unknowns: {counts}")

    candidate = manifest.get("candidate", {})
    so_sha = candidate.get("so_sha256")
    if not so_sha or len(so_sha) != 64:
        raise ValueError("missing candidate so_sha256")
    if expected_so_sha256 is not None and so_sha != expected_so_sha256:
        raise ValueError(f"stale ELF: manifest so_sha256 {so_sha} != expected {expected_so_sha256}")
    if (
        candidate.get("native_sha256") != so_sha
        or candidate.get("installed_verification", {}).get("so_sha256") != so_sha
        or not candidate.get("installed_verification", {}).get("installed_journey_ok")
    ):
        raise ValueError("stale ELF or unverified installed candidate package")

    # Semantics check
    semantics = manifest.get("semantics", {})
    classes = semantics.get("classes", {})
    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        cls_info = classes.get(cls_name, {})
        if not (
            cls_info.get("shallow_copy_shared")
            and cls_info.get("held_row_parity")
            and cls_info.get("dense_index_post_delete_bfs")
            and cls_info.get("view_parity")
        ):
            raise ValueError(f"alias/value/order or storage semantics divergence in {cls_name}")
    analytics = manifest.get("analytics_and_io", {})
    if not (
        semantics.get("equal_label_identity")
        and semantics.get("nbunch_mutation_legal")
        and semantics.get("iterator_exhaustion_after_mutation")
        and analytics.get("flow_dict_exact_parity")
        and analytics.get("min_cut_set_order_parity")
        and analytics.get("directed_modularity_exact")
        and set(analytics.get("io_formats", ()))
        == {"edgelist", "adjlist", "graphml", "gml", "node_link_json", "pajek", "gexf"}
    ):
        raise ValueError("alias/value/order divergence in scoped analytics or I/O round-trips")

    # CGSE 12-algorithm public witness check
    cgse_info = manifest.get("cgse", {})
    algos = cgse_info.get("algorithms", {})
    if tuple(sorted(algos.keys())) != EXPECTED_12_CGSE_ALGORITHMS:
        raise ValueError("missing public witness for one or more of the 12 V1 reference algorithms")
    for algo_name, record in algos.items():
        expected_policy = "weight_then_insertion_order" if algo_name == "prim" else record.get("registered_policy")
        if (
            not record.get("within_bounds")
            or record.get("policy") != expected_policy
            or len(record.get("decision_path_blake3", "")) != 64
        ):
            raise ValueError(f"missing or invalid public witness for {algo_name}")
    if not (cgse_info.get("negative_bound_rejected") and cgse_info.get("unknown_term_rejected")):
        raise ValueError("CGSE complexity negative checks did not reject out-of-bound witness")

    # Performance candidate binding check
    perf = manifest.get("performance_receipts", {})
    for gate_name in ("slo_gate", "empirical_complexity", "backend_whole_job", "attribute_store_rss"):
        gate = perf.get(gate_name, {})
        if gate.get("so_sha256") != so_sha:
            raise ValueError(f"expired or mismatched performance candidate in {gate_name}: {gate.get('so_sha256')} != {so_sha}")
    if (
        perf.get("slo_gate", {}).get("status") != "pass"
        or perf.get("empirical_complexity", {}).get("passed_green") != 54
        or perf.get("empirical_complexity", {}).get("allowlisted_debt") != 0
        or perf.get("empirical_complexity", {}).get("failed") != 0
        or not perf.get("backend_whole_job", {}).get("all_outputs_equal")
    ):
        raise ValueError("expired or failing performance candidate receipt")

    # Durability 5-class & decode loss check
    durability = manifest.get("durability", {})
    if sorted(durability.get("durability_classes", ())) != sorted(REQUIRED_DURABILITY_CLASSES):
        raise ValueError("missing durability member in 5-class release evidence inventory")
    recovery = durability.get("bounded_loss_recovery", {})
    if not (
        recovery.get("byte_exact")
        and recovery.get("semantic_replay_ok")
        and recovery.get("recovered_blocks", 0) >= 1
    ):
        raise ValueError("bounded packet-loss recovery or semantic replay failed")
    if not durability.get("beyond_bound_loss_rejected"):
        raise ValueError("beyond-bound decode loss was not rejected")

    return {"valid": True, "candidate_id": candidate.get("candidate_id"), "so_sha256": so_sha}


def run_v1_acceptance_suite(manifest_out: Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    """Execute the full V1 integration acceptance journey and write the retained manifest."""
    so_path = Path(fnx._fnx.__file__).resolve(strict=True)
    so_sha256 = _sha256_file(so_path)
    run_id = f"run-{int(time.time() * 1000)}-{os.getpid()}"
    run_dir = REPO_ROOT / "target" / "e2e_acceptance" / run_id
    evidence_dir = run_dir / "evidence_inputs"
    run_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    emit(
        "config",
        "runner",
        stress_nodes=STRESS_NODES,
        stress_attach=STRESS_ATTACH,
        stress_timeout_s=STRESS_TIMEOUT_SECONDS,
        python=sys.version.split()[0],
        networkx=nx.__version__,
        fnx=fnx.__version__,
        so_sha256=so_sha256,
        run_dir=str(run_dir),
    )

    state: dict[str, Any] = {"commands_executed": 0}

    def _run_durability_case() -> dict[str, Any]:
        summary, cmds = candidate_install_and_durability_workflow(run_dir, evidence_dir, so_sha256)
        state["commands_executed"] += cmds
        return summary

    cases = [
        ("standalone_workflow", standalone_workflow),
        ("backend_dispatch_workflow", backend_dispatch_workflow),
        ("digraph_workflow", digraph_workflow),
        ("multigraph_workflow", multigraph_workflow),
        ("large_graph_stress_workflow", large_graph_stress_workflow),
        ("serialization_roundtrip_workflow", lambda: serialization_roundtrip_workflow(run_dir / "legacy_io")),
        ("four_class_live_semantics_workflow", lambda: four_class_live_semantics_workflow(evidence_dir)),
        ("scoped_analytics_and_io_parity_workflow", lambda: scoped_analytics_and_io_parity_workflow(run_dir)),
        ("cgse_public_witness_and_negative_bound_workflow", lambda: cgse_public_witness_and_negative_bound_workflow(evidence_dir)),
        ("security_and_capacity_boundaries_workflow", lambda: security_and_capacity_boundaries_workflow(evidence_dir, run_dir)),
        ("joined_performance_receipts_workflow", lambda: joined_performance_receipts_workflow(evidence_dir, so_sha256)),
        ("candidate_install_and_durability_workflow", _run_durability_case),
    ]

    results: dict[str, dict[str, Any]] = {}
    passed_steps = 0
    failed_steps = 0
    executed_test_count = 0
    total_elapsed = 0.0

    for name, func in cases:
        ok, elapsed, summary = run_case(name, func)
        total_elapsed += elapsed
        results[name] = summary
        if ok:
            passed_steps += 1
            executed_test_count += int(summary.get("assertions", 1))
        else:
            failed_steps += 1

    durability_summary = results.get("candidate_install_and_durability_workflow", {})
    cgse_ledger = json.loads((evidence_dir / "reproducibility_ledgers.json").read_text(encoding="utf-8"))
    cgse_summary = dict(results.get("cgse_public_witness_and_negative_bound_workflow", {}))
    cgse_summary["algorithms"] = {
        algo: {k: v for k, v in rec.items() if k != "witness_json"}
        for algo, rec in cgse_ledger["algorithms"].items()
    }

    manifest = {
        "schema": "fnx-v1-acceptance-manifest-v1",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "COMPLETE-V1" if failed_steps == 0 else "FAILED",
        "phase": "completed" if failed_steps == 0 else "test",
        "terminal_counts": {
            "passed_steps": passed_steps,
            "failed_steps": failed_steps,
            "executed_command_count": state["commands_executed"],
            "executed_test_count": executed_test_count,
            "skips": 0,
            "xfails": 0,
            "unknown_observations": [],
            "total_elapsed_s": round(total_elapsed, 3),
        },
        "excluded_environments": [
            {
                "environment": target,
                "reason": "cross-OS/arch wheel target; local host is x86_64-unknown-linux-gnu",
            }
            for target in ("linux/arm64", "darwin/amd64", "darwin/arm64", "windows/amd64")
        ],
        "candidate": {
            "candidate_id": durability_summary.get("candidate_id"),
            "head": durability_summary.get("head"),
            "so_sha256": so_sha256,
            "wheel_sha256": durability_summary.get("wheel_sha256"),
            "native_sha256": durability_summary.get("native_sha256"),
            "sdist_sha256": durability_summary.get("sdist_sha256"),
            "release_evidence_sha256": durability_summary.get("release_evidence_sha256"),
            "python_version": sys.version.split()[0],
            "oracle_version": nx.__version__,
            "fnx_version": fnx.__version__,
            "installed_verification": durability_summary.get("installed_verification"),
        },
        "semantics": results.get("four_class_live_semantics_workflow", {}),
        "analytics_and_io": results.get("scoped_analytics_and_io_parity_workflow", {}),
        "cgse": cgse_summary,
        "security_and_capacity": results.get("security_and_capacity_boundaries_workflow", {}),
        "performance_receipts": results.get("joined_performance_receipts_workflow", {}),
        "durability": durability_summary,
        "replay_commands": [
            "PYTHONPATH=python .venv/bin/python scripts/e2e_integration_test.py",
            "FNX_DURABILITY_BIN=target/release/fnx-durability ./scripts/run_pytest_guarded.sh tests/python/test_installed_package_matches_repo_shim.py -v",
        ],
    }

    if failed_steps == 0:
        validate_v1_acceptance_manifest(manifest, expected_so_sha256=so_sha256)

    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    manifest_out.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    # Emit RaptorQ sidecar and scrub proof for the retained manifest itself
    durability_bin = _resolve_durability_binary()
    manifest_sidecar = manifest_out.with_suffix(".raptorq.json")
    subprocess.run(
        [
            str(durability_bin),
            "generate",
            str(manifest_out),
            str(manifest_sidecar),
            "v1-acceptance-manifest",
            "reproducibility_ledgers",
            "512",
            "6",
        ],
        check=True,
        timeout=60,
    )
    subprocess.run(
        [str(durability_bin), "scrub", str(manifest_out), str(manifest_sidecar)],
        check=True,
        timeout=60,
    )

    emit(
        "summary",
        "runner",
        ok=failed_steps == 0,
        failures=failed_steps,
        passed_steps=passed_steps,
        executed_command_count=state["commands_executed"],
        executed_test_count=executed_test_count,
        total_elapsed_s=round(total_elapsed, 3),
        manifest_path=str(manifest_out),
        manifest_sha256=_sha256_file(manifest_out),
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Run FrankenNetworkX V1 integration acceptance suite.")
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Output path for the retained V1 acceptance manifest JSON.",
    )
    args = parser.parse_args()
    manifest = run_v1_acceptance_suite(manifest_out=args.manifest_out)
    return 0 if manifest.get("status") == "COMPLETE-V1" else 1


if __name__ == "__main__":
    sys.exit(main())
