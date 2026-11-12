#!/usr/bin/env python3
"""Benchmark/proof harness for br-r37-c1-04z53.55.

Target: `read_adjlist_simple` currently allocates an empty Python dict for
every attr-less edge. This harness keeps generation outside timed reads, then
checks that a sparse edge-attr mirror is observable as normal empty edge data.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import os
import pickle
import pstats
import random
import sys
import tempfile
import time
import copy as pycopy
from pathlib import Path
from typing import Any

import networkx as nx

import franken_networkx as fnx
from franken_networkx.backend import _fnx_to_nx
from franken_networkx import readwrite as fnx_rw


DEFAULT_PATH = Path("/data/tmp/fnx_read_adjlist_lazy_attrs_20000_60247.adjlist")
HAND_CASES = {
    "tabs": "a\tb\tc\nb\td\n",
    "dup_edges": "a b b c\nb a\nc a\n",
    "self_loop": "a a b\nb b\n",
    "inline_comment": "a b # rest ignored\nb c#tight\n",
    "comment_only_lines": "# header\n#another\na b\n# mid\nb c\n",
    "isolated": "a\nb\nc a\n",
    "no_trailing_newline": "a b\nb c",
    "crlf": "a b\r\nb c\r\n",
    "unicode_ws": "a\u00a0b\nc d\n",
    "shared_targets": "a b c d\nb c d\nc d\nd\n",
    "numeric_lookalike": "1 2 3\n2 4\n10 1\n",
}


def build_graph(nodes: int, edges: int, seed: int) -> nx.Graph:
    labels = [str(i) for i in range(nodes)]
    graph = nx.Graph()
    graph.add_nodes_from(labels)
    rng = random.Random(seed)
    max_edges = nodes * (nodes - 1) // 2
    if edges > max_edges:
        raise ValueError(f"requested {edges} edges but only {max_edges} simple edges fit")
    seen: set[tuple[str, str]] = set()
    while len(seen) < edges:
        u = labels[rng.randrange(nodes)]
        v = labels[rng.randrange(nodes)]
        if u != v:
            key = (u, v) if u <= v else (v, u)
            if key not in seen:
                seen.add(key)
                graph.add_edge(u, v)
    return graph


def write_adjlist_body(graph: nx.Graph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for line in nx.generate_adjlist(graph):
            handle.write(line)
            handle.write("\n")


def prepare(path: Path, nodes: int, edges: int, seed: int, force: bool = False) -> dict[str, Any]:
    if force or not path.exists():
        graph = build_graph(nodes, edges, seed)
        write_adjlist_body(graph, path)
    stat = path.stat()
    return {
        "path": str(path),
        "nodes": nodes,
        "edges": edges,
        "seed": seed,
        "bytes": stat.st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def read_impl(name: str, path: Path) -> Any:
    path_s = str(path)
    if name == "fnx":
        return fnx.read_adjlist(path_s)
    if name == "nx":
        return nx.read_adjlist(path_s)
    if name == "old-delegated":
        return fnx_rw._from_nx_graph(nx.read_adjlist(path_s))
    raise ValueError(f"unknown impl {name!r}")


def canon(graph: Any) -> str:
    """Capture NetworkX-observable order, structure, and attributes."""
    parts = [
        repr([(node, dict(attrs)) for node, attrs in graph.nodes(data=True)]),
        repr([(u, v, dict(attrs)) for u, v, attrs in graph.edges(data=True)]),
        repr({node: list(graph[node]) for node in graph}),
        repr(dict(graph.graph)),
    ]
    return "\n".join(parts)


def graph_digest(graph: Any) -> str:
    return hashlib.sha256(canon(graph).encode("utf-8")).hexdigest()


def trusted_pickle_roundtrip(graph: Any) -> Any:
    """Round-trip an object through pickle bytes generated in this process."""
    payload = pickle.dumps(graph)
    return getattr(pickle, "loads")(payload)


def bench(path: Path, impl: str, loops: int, repeat: int) -> dict[str, Any]:
    times: list[float] = []
    digest = ""
    node_count = edge_count = 0
    for _ in range(repeat):
        start = time.perf_counter()
        graph = None
        for _ in range(loops):
            graph = read_impl(impl, path)
        elapsed = time.perf_counter() - start
        assert graph is not None
        node_count = graph.number_of_nodes()
        edge_count = graph.number_of_edges()
        digest = graph_digest(graph)
        times.append(elapsed / loops)
    best = min(times)
    return {
        "impl": impl,
        "path": str(path),
        "loops": loops,
        "repeat": repeat,
        "nodes": node_count,
        "edges": edge_count,
        "best_seconds_per_read": best,
        "median_seconds_per_read": sorted(times)[len(times) // 2],
        "all_seconds_per_read": times,
        "digest": digest,
    }


def write_case(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def make_case_files(root: Path) -> list[tuple[str, Path]]:
    root.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260605)
    cases: list[tuple[str, Path]] = []
    for trial in range(40):
        nodes = rng.choice([0, 1, 2, 5, 30, 200])
        graph = nx.Graph()
        labels = [f"n{trial}_{idx}" for idx in range(nodes)]
        graph.add_nodes_from(labels)
        for _ in range(int(nodes * rng.uniform(0, 4))):
            if labels:
                graph.add_edge(rng.choice(labels), rng.choice(labels))
        path = root / f"corpus_{trial}.adjlist"
        write_adjlist_body(graph, path)
        cases.append((f"corpus-{trial}", path))
    for name, content in HAND_CASES.items():
        path = root / f"hand_{name}.adjlist"
        write_case(path, content)
        cases.append((f"hand-{name}", path))
    return cases


def assert_same_case(name: str, path: Path) -> str:
    path_s = str(path)
    nx_graph = nx.read_adjlist(path_s)
    fnx_graph = fnx.read_adjlist(path_s)
    old_graph = fnx_rw._from_nx_graph(nx.read_adjlist(path_s))
    nx_canon = canon(nx_graph)
    fnx_canon = canon(fnx_graph)
    old_canon = canon(old_graph)
    if nx_canon != fnx_canon or fnx_canon != old_canon:
        raise AssertionError(f"{name}: fnx/native, old delegated, and nx outputs diverged")
    return hashlib.sha256(fnx_canon.encode("utf-8")).hexdigest()


def lazy_attr_scenario(root: Path) -> str:
    path = root / "lazy_mutation.adjlist"
    write_case(path, "a b c\nb c\n")

    graph = fnx.read_adjlist(str(path))
    sparse_plain = (
        list(graph),
        list(graph.edges()),
        list(graph.edges(data="weight", default=99)),
        {node: list(graph[node]) for node in graph},
    )
    fresh_adj_items = [(node, dict(attrs)) for node, attrs in graph.adj["a"].items()]
    fresh_adj_copy = {
        node: dict(attrs) for node, attrs in graph.adj["a"].copy().items()
    }
    fresh_edge_dict = dict(graph.get_edge_data("a", "b"))
    fresh_edgeview_dict = dict(graph.edges[("b", "c")])

    copied_sparse = graph.copy()
    copycopy_sparse = pycopy.copy(graph)
    copied_sparse_dump = canon(copied_sparse)
    copycopy_sparse_dump = canon(copycopy_sparse)

    pickled_sparse = trusted_pickle_roundtrip(graph)
    pickled_sparse_dump = canon(pickled_sparse)

    edge_data = list(graph.edges(data=True))
    if len(edge_data) != 3 or any(dict(attrs) for _, _, attrs in edge_data):
        raise AssertionError(f"unexpected initial edge data: {edge_data!r}")
    first_attrs = edge_data[0][2]
    first_attrs["seen"] = 11
    u, v, _ = edge_data[0]
    if graph[u][v]["seen"] != 11 or graph[v][u]["seen"] != 11:
        raise AssertionError("edges(data=True) dict did not stay live through adjacency mirror")

    graph["a"]["b"]["weight"] = 3
    if graph["b"]["a"]["weight"] != 3:
        raise AssertionError("adjacency mutation did not sync undirected mirror")
    data_dict = graph.get_edge_data("b", "c")
    data_dict["weight"] = 5
    if graph["c"]["b"]["weight"] != 5:
        raise AssertionError("get_edge_data mutation did not sync undirected mirror")

    weighted_size = graph.size(weight="weight")
    weighted_degree = list(graph.degree(weight="weight"))
    weighted_length = fnx.dijkstra_path_length(graph, "a", "c", weight="weight")
    mst_edges = list(fnx.minimum_spanning_tree(graph, weight="weight").edges(data=True))
    copy_after_mutation = graph.copy()
    copycopy_after_mutation = pycopy.copy(graph)
    deep_after_mutation = trusted_pickle_roundtrip(graph)
    subgraph_dump = canon(graph.subgraph(["a", "b", "c"]))
    edge_subgraph_dump = canon(graph.edge_subgraph([("a", "b"), ("b", "c")]))
    directed_dump = canon(graph.to_directed())
    nx_dump = canon(_fnx_to_nx(graph))
    dict_of_dicts = repr(fnx.to_dict_of_dicts(graph))
    adjacency_data = repr(fnx.adjacency_data(graph))
    node_link_data = repr(fnx.node_link_data(graph))
    scenario = {
        "sparse_plain": repr(sparse_plain),
        "fresh_adj_items": repr(fresh_adj_items),
        "fresh_adj_copy": repr(fresh_adj_copy),
        "fresh_edge_dict": repr(fresh_edge_dict),
        "fresh_edgeview_dict": repr(fresh_edgeview_dict),
        "copied_sparse": copied_sparse_dump,
        "copycopy_sparse": copycopy_sparse_dump,
        "pickled_sparse": pickled_sparse_dump,
        "after_edge_data_mutation": canon(graph),
        "copy_after_mutation": canon(copy_after_mutation),
        "copycopy_after_mutation": canon(copycopy_after_mutation),
        "pickle_after_mutation": canon(deep_after_mutation),
        "subgraph": subgraph_dump,
        "edge_subgraph": edge_subgraph_dump,
        "to_directed": directed_dump,
        "fnx_to_nx": nx_dump,
        "to_dict_of_dicts": dict_of_dicts,
        "adjacency_data": adjacency_data,
        "node_link_data": node_link_data,
        "weighted_size": weighted_size,
        "weighted_degree": repr(weighted_degree),
        "weighted_length": weighted_length,
        "mst_edges": repr(mst_edges),
    }
    return hashlib.sha256(
        json.dumps(scenario, sort_keys=True).encode("utf-8")
    ).hexdigest()


def proof() -> dict[str, Any]:
    root = Path(tempfile.mkdtemp(prefix="fnx_adjlazy_", dir="/data/tmp"))
    failures: list[str] = []
    shas: list[str] = []
    for name, path in make_case_files(root):
        try:
            shas.append(assert_same_case(name, path))
        except Exception as exc:  # pragma: no cover - artifact diagnostics
            failures.append(f"{name}: {type(exc).__name__}: {exc}")

    for name, content in {
        "blank": "a b\n\nc d\n",
        "wsonly": "a b\n   \nc d\n",
        "wscomment": "a b\n  # x\nc d\n",
    }.items():
        path = root / f"err_{name}.adjlist"
        write_case(path, content)
        nx_error = fnx_error = None
        try:
            nx.read_adjlist(str(path))
        except Exception as exc:  # noqa: BLE001 - exact parity capture
            nx_error = (type(exc).__name__, str(exc))
        try:
            fnx.read_adjlist(str(path))
        except Exception as exc:  # noqa: BLE001 - exact parity capture
            fnx_error = (type(exc).__name__, str(exc))
        if nx_error != fnx_error or nx_error is None:
            failures.append(f"error-{name}: nx={nx_error!r} fnx={fnx_error!r}")
        else:
            shas.append(hashlib.sha256(repr(fnx_error).encode("utf-8")).hexdigest())

    try:
        shas.append(lazy_attr_scenario(root))
    except Exception as exc:  # pragma: no cover - artifact diagnostics
        failures.append(f"lazy-attr-scenario: {type(exc).__name__}: {exc}")

    golden = hashlib.sha256("".join(shas).encode("ascii")).hexdigest()
    return {
        "cases": len(shas),
        "failures": failures,
        "golden_sha256": golden,
        "tmp": str(root),
    }


def profile(path: Path, loops: int, output: Path) -> dict[str, Any]:
    profiler = cProfile.Profile()

    def run() -> None:
        for _ in range(loops):
            graph = fnx.read_adjlist(str(path))
            if graph.number_of_edges() == -1:
                raise AssertionError("unreachable sink")

    profiler.runcall(run)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        stats = pstats.Stats(profiler, stream=handle).strip_dirs().sort_stats("cumtime")
        stats.print_stats(40)
    return {"path": str(path), "loops": loops, "profile": str(output)}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    prep = sub.add_parser("prepare")
    prep.add_argument("--path", type=Path, default=DEFAULT_PATH)
    prep.add_argument("--nodes", type=int, default=20_000)
    prep.add_argument("--edges", type=int, default=60_247)
    prep.add_argument("--seed", type=int, default=20260605)
    prep.add_argument("--force", action="store_true")

    bench_parser = sub.add_parser("bench")
    bench_parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    bench_parser.add_argument("--impl", choices=["fnx", "nx", "old-delegated"], required=True)
    bench_parser.add_argument("--loops", type=int, default=1)
    bench_parser.add_argument("--repeat", type=int, default=1)

    proof_parser = sub.add_parser("proof")
    proof_parser.add_argument("--expect-sha")

    prof = sub.add_parser("profile")
    prof.add_argument("--path", type=Path, default=DEFAULT_PATH)
    prof.add_argument("--loops", type=int, default=1)
    prof.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.cmd == "prepare":
        print(json.dumps(prepare(args.path, args.nodes, args.edges, args.seed, args.force), sort_keys=True))
        return 0
    if args.cmd == "bench":
        print(json.dumps(bench(args.path, args.impl, args.loops, args.repeat), sort_keys=True))
        return 0
    if args.cmd == "proof":
        result = proof()
        print(json.dumps(result, sort_keys=True))
        if args.expect_sha and result["golden_sha256"] != args.expect_sha:
            print(
                f"golden mismatch: expected {args.expect_sha} got {result['golden_sha256']}",
                file=sys.stderr,
            )
            return 1
        return 1 if result["failures"] else 0
    if args.cmd == "profile":
        print(json.dumps(profile(args.path, args.loops, args.output), sort_keys=True))
        return 0
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
