#!/usr/bin/env python3
"""Proof and timing harness for br-r37-c1-zvwgo."""

from __future__ import annotations

import argparse
import cProfile
import hmac
import hashlib
import json
import pstats
import statistics
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


ROOT = Path(__file__).resolve().parent


def _edges(n: int):
    edges = [((i * 37 + 11) % i, i) for i in range(1, n)]
    edges.extend((i, (i * 97 + 53) % n) for i in range(n) if i != (i * 97 + 53) % n)
    return edges


def _build_pair(module, n: int):
    left = module.Graph()
    left.add_nodes_from(range(n))
    left.add_edges_from(_edges(n))

    right = module.Graph()
    right.add_nodes_from(range(n // 2, n + n // 2))
    right.add_edges_from(
        (u + n // 2, v + n // 2) for u, v in _edges(n) if u < n // 2 and v < n // 2
    )
    return left, right


def _graph_signature(graph):
    return {
        "graph": sorted((repr(k), repr(v)) for k, v in graph.graph.items()),
        "nodes": [repr(node) for node in graph.nodes()],
        "edges": [[repr(u), repr(v)] for u, v in graph.edges()],
    }


def _nodes_signature(graph):
    return [repr(node) for node in graph.nodes()]


def _digest(value) -> str:
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _intersection(module, n: int):
    left, right = _build_pair(module, n)
    return module.intersection(left, right)


def _add_int_set(module, n: int):
    graph = module.Graph()
    graph.add_nodes_from(set(range(n // 2, n + n // 2)))
    return graph


def _add_bool_set(module):
    graph = module.Graph()
    graph.add_nodes_from({True, 2, 3})
    return graph


def proof(label: str, n: int, compare: Path | None) -> None:
    previous = None
    if compare is not None:
        try:
            with compare.open(encoding="utf-8") as fh:
                previous = json.JSONDecoder().decode(fh.read())
        except json.JSONDecodeError as exc:
            raise AssertionError(f"invalid comparison proof json: {compare}") from exc
    cases = {
        "intersection": (
            _graph_signature(_intersection(fnx, n)),
            _graph_signature(_intersection(nx, n)),
        ),
        "add_int_set": (
            _nodes_signature(_add_int_set(fnx, n)),
            _nodes_signature(_add_int_set(nx, n)),
        ),
        "add_bool_set_existing_behavior": (
            _nodes_signature(_add_bool_set(fnx)),
            _nodes_signature(_add_bool_set(nx)),
        ),
    }

    out = {"label": label, "n": n, "cases": {}}
    for name, (actual, expected) in cases.items():
        if actual != expected:
            raise AssertionError(f"{name}: signature differs")
        actual_sha = _digest(actual)
        case_out = {
            "fnx_sha256": actual_sha,
            "nx_sha256": _digest(expected),
            "fnx_matches_nx": True,
        }
        if previous is not None:
            baseline_sha = previous["cases"][name]["fnx_sha256"]
            sha_equal = hmac.compare_digest(actual_sha, baseline_sha)
            case_out["baseline_fnx_sha256"] = baseline_sha
            case_out["baseline_fnx_sha256_equal"] = sha_equal
            if not sha_equal:
                raise AssertionError(f"{name}: golden sha changed")
        out["cases"][name] = case_out

    proof_path = ROOT / f"{label}_proof.json"
    proof_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    (ROOT / f"{label}_proof.sha256").write_text(
        hashlib.sha256(proof_path.read_bytes()).hexdigest() + "\n"
    )


def bench(label: str, n: int, samples: int) -> None:
    out = {"label": label, "n": n, "samples": samples, "cases": {}}
    for case_name, fnx_fn, nx_fn in (
        ("intersection", lambda: _intersection(fnx, n), lambda: _intersection(nx, n)),
        ("add_int_set", lambda: _add_int_set(fnx, n), lambda: _add_int_set(nx, n)),
    ):
        case_out = {}
        for lib_name, func in (("fnx", fnx_fn), ("nx", nx_fn)):
            values = []
            for _ in range(samples):
                start = time.perf_counter()
                func()
                values.append(time.perf_counter() - start)
            case_out[lib_name] = {
                "best": min(values),
                "median": statistics.median(values),
                "samples": values,
            }
        case_out["fnx_vs_nx_best_ratio"] = (
            case_out["fnx"]["best"] / case_out["nx"]["best"]
        )
        case_out["fnx_vs_nx_median_ratio"] = (
            case_out["fnx"]["median"] / case_out["nx"]["median"]
        )
        out["cases"][case_name] = case_out
    (ROOT / f"{label}_direct.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")


def profile(label: str, n: int, reps: int) -> None:
    left, right = _build_pair(fnx, n)
    node_set = set(range(n // 2, n + n // 2))

    def run():
        for _ in range(reps):
            fnx.intersection(left, right)
        for _ in range(reps):
            graph = fnx.Graph()
            graph.add_nodes_from(node_set)

    profiler = cProfile.Profile()
    profiler.enable()
    run()
    profiler.disable()
    with (ROOT / f"{label}_profile.txt").open("w") as fh:
        pstats.Stats(profiler, stream=fh).strip_dirs().sort_stats("cumtime").print_stats(80)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["proof", "bench", "profile"])
    parser.add_argument("--label", required=True)
    parser.add_argument("--n", type=int, default=1800)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--profile-reps", type=int, default=150)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args()
    if args.command == "proof":
        proof(args.label, args.n, args.compare)
    elif args.command == "bench":
        bench(args.label, args.n, args.samples)
    else:
        profile(args.label, args.n, args.profile_reps)


if __name__ == "__main__":
    main()
