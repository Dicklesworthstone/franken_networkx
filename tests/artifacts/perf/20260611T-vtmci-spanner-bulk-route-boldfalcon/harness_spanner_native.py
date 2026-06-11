"""Baseline/proof harness for br-r37-c1-va1lb native spanner residual.

Spanner parity is structural: Baswana-Sen is randomized and tie-broken by
implementation-specific edge identities, so the proof is "valid spanner with
the requested stretch and preserved edge attributes" rather than exact edge-set
identity.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import random
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import franken_networkx as fnx
import networkx as nx
import networkx.algorithms.sparsifiers as nsp

from franken_networkx.backend import _fnx_to_nx


def bench(fn, repeats: int = 7) -> dict[str, float]:
    fn()
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000.0)
    ordered = sorted(samples)
    return {
        "best_ms": ordered[0],
        "median_ms": ordered[len(ordered) // 2],
        "mean_ms": sum(samples) / len(samples),
    }


def build_graph(n: int, p: float, seed: int, weighted: bool = False):
    base = nx.gnp_random_graph(n, p, seed=seed)
    graph = fnx.Graph()
    graph.add_nodes_from(base.nodes())
    if weighted:
        rng = random.Random(seed)
        graph.add_edges_from(
            (u, v, {"weight": rng.randint(1, 9)}) for u, v in base.edges()
        )
    else:
        graph.add_edges_from(base.edges())
    return base, graph, _fnx_to_nx(graph)


def graph_to_nx(graph, weight: str | None = None):
    out = nx.Graph()
    out.add_nodes_from(graph.nodes())
    if weight is None:
        out.add_edges_from(graph.edges())
    else:
        out.add_edges_from(
            (u, v, {weight: graph[u][v][weight]}) for u, v in graph.edges()
        )
    return out


def valid_spanner(original, candidate, stretch: int, weight: str | None = None) -> bool:
    if set(original.nodes()) != set(candidate.nodes()):
        return False
    for u, v in candidate.edges():
        if not original.has_edge(u, v):
            return False
        if weight is not None and candidate[u][v][weight] != original[u][v][weight]:
            return False
    for source in original.nodes():
        if weight is None:
            original_lengths = nx.single_source_shortest_path_length(original, source)
            candidate_lengths = nx.single_source_shortest_path_length(candidate, source)
        else:
            original_lengths = nx.single_source_dijkstra_path_length(
                original, source, weight=weight
            )
            candidate_lengths = nx.single_source_dijkstra_path_length(
                candidate, source, weight=weight
            )
        for target, original_length in original_lengths.items():
            if candidate_lengths.get(target, float("inf")) > (
                stretch * original_length + 1e-9
            ):
                return False
    return True


def error_type(fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - this records public API parity.
        return type(exc).__name__
    return None


def run_algo_on_graph(mode: str, graph, genuine_graph, stretch: int, seed: int, weighted: bool):
    weight = "weight" if weighted else None
    if mode == "public":
        return fnx.spanner(graph, stretch, weight=weight, seed=seed)
    if mode == "raw":
        return fnx._raw_spanner(graph, stretch, weight=weight, seed=seed)
    if mode == "nx":
        return nsp.spanner(genuine_graph, stretch, weight=weight, seed=seed)
    raise ValueError(mode)


def run_once(mode: str, n: int, p: float, stretch: int, seed: int, weighted: bool):
    _, graph, genuine_graph = build_graph(n, p, seed, weighted=weighted)
    return run_algo_on_graph(mode, graph, genuine_graph, stretch, seed, weighted)


def run_bench(args):
    specs = [
        ("n400", 400, 0.04, 3, 42, False),
        ("n800", 800, 0.02, 3, 42, False),
        ("n1500", 1500, 0.01, 3, 42, False),
    ]
    out = {}
    for name, n, p, stretch, seed, weighted in specs:
        _, graph, genuine_graph = build_graph(n, p, seed, weighted=weighted)
        out[name] = {}
        for mode in ("raw", "public", "nx"):
            out[name][mode] = bench(
                lambda mode=mode, graph=graph, genuine_graph=genuine_graph, stretch=stretch, seed=seed, weighted=weighted: run_algo_on_graph(
                    mode, graph, genuine_graph, stretch, seed, weighted
                ),
                repeats=args.repeats,
            )
    return out


def run_proof():
    out: dict[str, object] = {
        "contracts": {
            "public_directed": error_type(lambda: fnx.spanner(fnx.DiGraph([(0, 1)]), 2)),
            "public_multigraph": error_type(
                lambda: fnx.spanner(fnx.MultiGraph([(0, 1), (0, 1)]), 2)
            ),
            "public_stretch0": error_type(lambda: fnx.spanner(fnx.path_graph(5), 0)),
            "public_empty": error_type(lambda: fnx.spanner(fnx.Graph(), 2)),
            "public_submodule_routed": fnx.sparsifiers.spanner is not nsp.spanner,
        },
        "validity": {},
    }
    validity = {}
    for mode in ("raw", "public", "nx"):
        invalid = 0
        checks = 0
        for seed in range(12):
            for n, p in ((50, 0.16), (70, 0.10), (90, 0.07)):
                for stretch in (3, 5, 7):
                    base, graph, genuine = build_graph(n, p, seed)
                    result = run_once(mode, n, p, stretch, seed, weighted=False)
                    candidate = result if mode == "nx" else graph_to_nx(result)
                    checks += 1
                    if not valid_spanner(genuine if mode != "nx" else base, candidate, stretch):
                        invalid += 1
        for seed in range(8):
            _, graph, genuine = build_graph(50, 0.12, seed, weighted=True)
            result = run_once(mode, 50, 0.12, 4, seed, weighted=True)
            candidate = result if mode == "nx" else graph_to_nx(result, weight="weight")
            checks += 1
            if not valid_spanner(genuine, candidate, 4, weight="weight"):
                invalid += 1
        validity[mode] = {"checks": checks, "invalid": invalid}
    out["validity"] = validity
    return out


def stable_json_sha(payload) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def run_profile(args):
    _, graph, genuine_graph = build_graph(args.n, args.p, args.seed, weighted=args.weighted)
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.repeats):
        run_algo_on_graph(
            args.single_mode, graph, genuine_graph, args.stretch, args.seed, args.weighted
        )
    profiler.disable()
    stats = pstats.Stats(profiler, stream=sys.stdout)
    stats.strip_dirs().sort_stats("cumtime").print_stats(30)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["bench", "proof", "profile", "single"], required=True)
    parser.add_argument("--algo", dest="single_mode", choices=["raw", "public", "nx"])
    parser.add_argument("--n", type=int, default=1500)
    parser.add_argument("--p", type=float, default=0.01)
    parser.add_argument("--stretch", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--weighted", action="store_true")
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.mode == "bench":
        payload = run_bench(args)
    elif args.mode == "proof":
        payload = run_proof()
        payload["sha256"] = stable_json_sha(payload)
    elif args.mode == "profile":
        if args.single_mode is None:
            raise SystemExit("--algo is required for --mode profile")
        run_profile(args)
        return
    else:
        if args.single_mode is None:
            raise SystemExit("--algo is required for --mode single")
        result = run_once(
            args.single_mode, args.n, args.p, args.stretch, args.seed, args.weighted
        )
        payload = {
            "algo": args.single_mode,
            "nodes": result.number_of_nodes(),
            "edges": result.number_of_edges(),
        }

    text = json.dumps(payload, indent=2, sort_keys=True)
    print(text)
    if args.output is not None:
        args.output.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
