#!/usr/bin/env python3
"""Evidence harness for br-r37-c1-wxy3x greedy modularity routing.

The candidate lever is only valid if the native CNM partition matches
NetworkX's public ``greedy_modularity_communities`` result exactly as an
ordered list of communities.  The proof payload keeps both the public fnx
path and the raw Rust binding visible so a route cannot hide a tie-break drift.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import importlib.util
import json
import os
import pstats
import statistics
import sys
import time
from pathlib import Path
from typing import Callable

_PRELOAD_SO = os.environ.get("FNX_PRELOAD_SO")
if _PRELOAD_SO:
    _spec = importlib.util.spec_from_file_location("franken_networkx._fnx", _PRELOAD_SO)
    _module = importlib.util.module_from_spec(_spec)
    sys.modules["franken_networkx._fnx"] = _module
    _spec.loader.exec_module(_module)

import franken_networkx as fnx
import franken_networkx._fnx as raw
import networkx as nx


def _repr_key(value: object) -> str:
    return repr(value)


def _partition_payload(communities) -> list[list[str]]:
    return [
        [_repr_key(node) for node in sorted(community, key=_repr_key)]
        for community in communities
    ]


def _partition_signature(communities) -> list[tuple[str, ...]]:
    return [tuple(part) for part in _partition_payload(communities)]


def _digest(obj: object) -> str:
    encoded = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _with_edges(lib, nodes, edges):
    graph = lib.Graph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    return graph


def _fixtures() -> list[tuple[str, object, object]]:
    fixtures: list[tuple[str, object, object]] = []

    for name, builder in (
        ("karate", lambda lib: lib.karate_club_graph()),
        ("ws150", lambda lib: lib.connected_watts_strogatz_graph(150, 6, 0.2, seed=3)),
        ("ws300", lambda lib: lib.connected_watts_strogatz_graph(300, 6, 0.2, seed=7)),
        ("barbell", lambda lib: lib.barbell_graph(12, 4)),
        ("path20", lambda lib: lib.path_graph(20)),
        ("cycle20", lambda lib: lib.cycle_graph(20)),
        ("lollipop", lambda lib: lib.lollipop_graph(16, 10)),
    ):
        fixtures.append((name, builder(fnx), builder(nx)))

    string_nodes = [f"n{i}" for i in range(12)]
    string_edges = [
        ("n0", "n1"),
        ("n1", "n2"),
        ("n2", "n3"),
        ("n3", "n0"),
        ("n4", "n5"),
        ("n5", "n6"),
        ("n6", "n7"),
        ("n7", "n4"),
        ("n3", "n4"),
        ("n8", "n9"),
        ("n9", "n10"),
        ("n10", "n11"),
    ]
    fixtures.append(
        (
            "string_components",
            _with_edges(fnx, string_nodes, string_edges),
            _with_edges(nx, string_nodes, string_edges),
        )
    )

    empty_nodes = list(range(10))
    fixtures.append(("empty_nodes", _with_edges(fnx, empty_nodes, []), _with_edges(nx, empty_nodes, [])))

    return fixtures


def _public_fnx(graph):
    return list(fnx.community.greedy_modularity_communities(graph))


def _raw_native(graph):
    return [frozenset(part) for part in raw.greedy_modularity_communities(graph, 1.0, "")]


def _nx_ref(graph):
    return list(nx.community.greedy_modularity_communities(graph))


def proof() -> dict[str, object]:
    cases = []
    all_public_match = True
    all_raw_match = True
    for name, f_graph, n_graph in _fixtures():
        public = _public_fnx(f_graph)
        native = _raw_native(f_graph)
        ref = _nx_ref(n_graph)
        public_sig = _partition_signature(public)
        native_sig = _partition_signature(native)
        ref_sig = _partition_signature(ref)
        public_match = public_sig == ref_sig
        native_match = native_sig == ref_sig
        all_public_match = all_public_match and public_match
        all_raw_match = all_raw_match and native_match
        cases.append(
            {
                "case": name,
                "node_count": f_graph.number_of_nodes(),
                "edge_count": f_graph.number_of_edges(),
                "public_match": public_match,
                "raw_match": native_match,
                "public": public_sig,
                "raw": native_sig,
                "networkx": ref_sig,
            }
        )

    payload = {
        "target": "br-r37-c1-wxy3x greedy_modularity_communities",
        "all_public_match": all_public_match,
        "all_raw_match": all_raw_match,
        "cases": cases,
    }
    return {"sha256": _digest(payload), "payload": payload}


def _target_graphs():
    return {
        "ws150": fnx.connected_watts_strogatz_graph(150, 6, 0.2, seed=3),
        "ws300": fnx.connected_watts_strogatz_graph(300, 6, 0.2, seed=7),
    }


def bench(impl: str, repeat: int) -> dict[str, object]:
    graphs = _target_graphs()
    functions: dict[str, Callable[[object], object]] = {
        "public": _public_fnx,
        "raw": _raw_native,
        "nx": lambda graph: _nx_ref(nx.connected_watts_strogatz_graph(
            graph.number_of_nodes(), 6, 0.2, seed=3 if graph.number_of_nodes() == 150 else 7
        )),
    }
    fn = functions[impl]
    results = {}
    for name, graph in graphs.items():
        times = []
        digest_accumulator = []
        for _ in range(repeat):
            start = time.perf_counter()
            communities = fn(graph)
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            digest_accumulator.append(_digest(_partition_payload(communities)))
        ordered = sorted(times)
        results[name] = {
            "repeat": repeat,
            "mean_s": statistics.fmean(times),
            "median_s": statistics.median(times),
            "p95_s": ordered[int((len(ordered) - 1) * 0.95)],
            "min_s": min(times),
            "max_s": max(times),
            "times_s": times,
            "digest_set": sorted(set(digest_accumulator)),
        }
    return {"impl": impl, "results": results}


def profile(impl: str, repeat: int, output: Path) -> dict[str, object]:
    functions: dict[str, Callable[[object], object]] = {
        "public": _public_fnx,
        "raw": _raw_native,
    }
    graph = fnx.connected_watts_strogatz_graph(150, 6, 0.2, seed=3)
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(repeat):
        functions[impl](graph)
    profiler.disable()
    profiler.dump_stats(str(output))
    stats = pstats.Stats(profiler).sort_stats("cumtime")
    rows = []
    for func, stat in stats.stats.items():
        cc, nc, tt, ct, _callers = stat
        filename, line, name = func
        rows.append(
            {
                "function": f"{filename}:{line}:{name}",
                "primitive_calls": cc,
                "total_calls": nc,
                "total_time_s": tt,
                "cum_time_s": ct,
            }
        )
    rows.sort(key=lambda row: row["cum_time_s"], reverse=True)
    return {"impl": impl, "repeat": repeat, "profile": str(output), "top": rows[:25]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["proof", "bench", "profile"], required=True)
    parser.add_argument("--impl", choices=["public", "raw", "nx"], default="public")
    parser.add_argument("--repeat", type=int, default=40)
    parser.add_argument("--profile-out", type=Path, default=Path("profile.prof"))
    args = parser.parse_args()

    if args.mode == "proof":
        result = proof()
    elif args.mode == "bench":
        result = bench(args.impl, args.repeat)
    else:
        result = profile(args.impl, args.repeat, args.profile_out)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
