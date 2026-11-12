#!/usr/bin/env python3
"""Focused proof and benchmark harness for br-r37-c1-p34di."""

from __future__ import annotations

import argparse
import cProfile
import gc
import hashlib
import json
import pickle  # nosec B403 - local parity harness only; no untrusted input
import pstats
import statistics
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


ARTIFACT_DIR = Path(__file__).resolve().parent
_TRUSTED_PICKLE_DUMPS = pickle.dumps
_TRUSTED_PICKLE_LOADS = pickle.loads


def render_obj(value):
    return {
        "type": f"{type(value).__module__}.{type(value).__qualname__}",
        "repr": repr(value),
    }


def render_mapping(mapping):
    return [(render_obj(key), render_obj(value)) for key, value in mapping.items()]


def make_graph(module, directed=False, nodes=2048):
    cls = module.DiGraph if directed else module.Graph
    graph = cls()
    graph.add_edge(0, 1, weight=1)
    graph[0][1]["live"] = True
    for node in range(2, nodes):
        graph.add_edge(0, node)
    for node in range(1, min(nodes - 1, 128)):
        graph.add_edge(node, node + 1)
    graph.add_edge("s", "t", label="str")
    graph.add_edge(12.0, 12, label="mixed")
    return graph


def capture_error(func):
    try:
        func()
    except Exception as exc:  # noqa: BLE001 - exact observable exception capture
        return {
            "type": f"{type(exc).__module__}.{type(exc).__qualname__}",
            "args": [repr(arg) for arg in getattr(exc, "args", ())],
            "str": str(exc),
        }
    return None


def iterator_mutation_error(graph):
    iterator = iter(graph.adj[0])
    try:
        first = next(iterator)
    except StopIteration:
        first = None
    error = capture_error(lambda: (graph.add_edge(0, "new-neighbor"), next(iterator)))
    return {"first": render_obj(first), "error": error}


def graph_surface(module, directed=False):
    graph = make_graph(module, directed=directed, nodes=64)
    row = graph.adj[0]
    attrs = graph[0][1]
    attrs["mutated"] = "yes"
    copy_graph = graph.copy()
    # Trusted in-process roundtrip: this harness verifies NetworkX pickle parity
    # for objects it just constructed, never for external bytes.
    pickled = _TRUSTED_PICKLE_LOADS(_TRUSTED_PICKLE_DUMPS(graph))  # nosec B301
    surface = {
        "directed": directed,
        "nodes": [render_obj(node) for node in list(graph)[:12]],
        "adj_iter_type": type(iter(graph.adj)).__name__,
        "adj_nodes": [render_obj(node) for node in list(graph.adj)[:12]],
        "row_iter_type": type(iter(row)).__name__,
        "row_neighbors": [render_obj(node) for node in list(row)[:12]],
        "getitem_row_iter_type": type(iter(graph[0])).__name__,
        "getitem_row_neighbors": [render_obj(node) for node in list(graph[0])[:12]],
        "neighbors_iter_type": type(graph.neighbors(0)).__name__,
        "neighbors": [render_obj(node) for node in list(graph.neighbors(0))[:12]],
        "live_attr_alias": graph[0][1].get("mutated"),
        "row_copy": render_mapping(row.copy()),
        "graph_copy_neighbors": [render_obj(node) for node in list(copy_graph.neighbors(0))[:12]],
        "pickle_neighbors": [render_obj(node) for node in list(pickled.neighbors(0))[:12]],
        "missing_error": capture_error(lambda: graph.adj["missing"]),
        "mutation_error": iterator_mutation_error(make_graph(module, directed=directed, nodes=64)),
    }
    if directed:
        surface.update(
            {
                "succ_iter_type": type(iter(graph.succ[0])).__name__,
                "succ_neighbors": [render_obj(node) for node in list(graph.succ[0])[:12]],
                "pred_iter_type": type(iter(graph.pred[12])).__name__,
                "pred_neighbors": [render_obj(node) for node in list(graph.pred[12])[:12]],
                "successors_iter_type": type(graph.successors(0)).__name__,
                "predecessors_iter_type": type(graph.predecessors(12)).__name__,
                "successors": [render_obj(node) for node in list(graph.successors(0))[:12]],
                "predecessors": [render_obj(node) for node in list(graph.predecessors(12))[:12]],
            }
        )
    return surface


def proof_payload():
    fnx_graph = graph_surface(fnx, directed=False)
    nx_graph = graph_surface(nx, directed=False)
    fnx_digraph = graph_surface(fnx, directed=True)
    nx_digraph = graph_surface(nx, directed=True)
    payload = {
        "ordering_tie_breaking": "node order, adjacency row order, G[u] row order, succ/pred row order, copy, pickle, and mixed hash-equal display surfaces included",
        "floating_point": "no floating-point algorithm output; 12.0/12 hash-equal display surface included",
        "rng": "no RNG",
        "surfaces": {
            "graph_fnx": fnx_graph,
            "graph_nx": nx_graph,
            "digraph_fnx": fnx_digraph,
            "digraph_nx": nx_digraph,
        },
        "matches_nx": {
            "graph": fnx_graph == nx_graph,
            "digraph": fnx_digraph == nx_digraph,
        },
    }
    digest_source = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["golden_sha256"] = hashlib.sha256(digest_source).hexdigest()
    return payload


def make_bench_graph(kind, nodes):
    if kind == "graph":
        return make_graph(fnx, directed=False, nodes=nodes)
    if kind == "digraph":
        return make_graph(fnx, directed=True, nodes=nodes)
    raise ValueError(kind)


def run_case(case, loops, nodes):
    graph_kind, op = case.split(":", 1)
    graph = make_bench_graph(graph_kind, nodes)

    def graph_neighbors():
        total = 0
        for _ in range(loops):
            total += len(list(graph.neighbors(0)))
        return total

    def graph_adj_row():
        total = 0
        for _ in range(loops):
            total += len(list(graph.adj[0]))
        return total

    def graph_getitem_row():
        total = 0
        for _ in range(loops):
            total += len(list(graph[0]))
        return total

    def graph_adjacency_snapshot():
        total = 0
        for _ in range(loops):
            total += sum(len(row) for _, row in graph.adjacency())
        return total

    def digraph_successors():
        total = 0
        for _ in range(loops):
            total += len(list(graph.successors(0)))
        return total

    def digraph_predecessors():
        total = 0
        for _ in range(loops):
            total += len(list(graph.predecessors(12)))
        return total

    def digraph_adj_row():
        total = 0
        for _ in range(loops):
            total += len(list(graph.adj[0]))
        return total

    def digraph_pred_row():
        total = 0
        for _ in range(loops):
            total += len(list(graph.pred[12]))
        return total

    cases = {
        "graph:neighbors": graph_neighbors,
        "graph:adj_row": graph_adj_row,
        "graph:getitem_row": graph_getitem_row,
        "graph:adjacency_snapshot": graph_adjacency_snapshot,
        "digraph:successors": digraph_successors,
        "digraph:predecessors": digraph_predecessors,
        "digraph:adj_row": digraph_adj_row,
        "digraph:pred_row": digraph_pred_row,
    }
    return cases[case]()


def time_case(case, loops, nodes, runs):
    samples = []
    checksum = None
    for _ in range(runs):
        gc.collect()
        start = time.perf_counter()
        checksum = run_case(case, loops, nodes)
        samples.append(time.perf_counter() - start)
    return {
        "case": case,
        "loops": loops,
        "nodes": nodes,
        "runs": runs,
        "checksum": checksum,
        "best_s": min(samples),
        "mean_s": statistics.fmean(samples),
        "median_s": statistics.median(samples),
        "samples_s": samples,
    }


def write_phase(phase, loops, nodes, runs):
    proof = proof_payload()
    proof_path = ARTIFACT_DIR / f"{phase}_proof.json"
    proof_path.write_text(json.dumps(proof, sort_keys=True) + "\n")
    (ARTIFACT_DIR / f"{phase}_golden.sha256").write_text(
        f"{proof['golden_sha256']}  {proof_path.name}\n"
    )
    cases = [
        "graph:neighbors",
        "graph:adj_row",
        "graph:getitem_row",
        "graph:adjacency_snapshot",
        "digraph:successors",
        "digraph:predecessors",
        "digraph:adj_row",
        "digraph:pred_row",
    ]
    bench = [time_case(case, loops, nodes, runs) for case in cases]
    (ARTIFACT_DIR / f"{phase}_bench.json").write_text(
        json.dumps({"phase": phase, "bench": bench}, sort_keys=True, indent=2) + "\n"
    )
    profile = cProfile.Profile()
    profile.enable()
    run_case("graph:neighbors", loops * 2, nodes)
    profile.disable()
    with (ARTIFACT_DIR / f"{phase}_profile.txt").open("w") as handle:
        stats = pstats.Stats(profile, stream=handle).sort_stats("cumtime")
        stats.print_stats(40)
    print(json.dumps({"phase": phase, "golden_sha256": proof["golden_sha256"]}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["phase", "case"])
    parser.add_argument("--phase", default="baseline")
    parser.add_argument("--case", default="graph:neighbors")
    parser.add_argument("--loops", type=int, default=32)
    parser.add_argument("--nodes", type=int, default=8192)
    parser.add_argument("--runs", type=int, default=9)
    args = parser.parse_args()
    if args.command == "phase":
        write_phase(args.phase, args.loops, args.nodes, args.runs)
    else:
        print(run_case(args.case, args.loops, args.nodes))


if __name__ == "__main__":
    main()
