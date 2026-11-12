#!/usr/bin/env python3
"""Proof and timing harness for br-r37-c1-orqgq."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import hmac
import json
import pstats
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
sys.path.insert(0, str(REPO / "python"))

import franken_networkx as fnx
import networkx as nx


def _edges(n: int):
    edges = [((i * 37 + 11) % i, i) for i in range(1, n)]
    edges.extend((i, (i * 97 + 53) % n) for i in range(n) if i != (i * 97 + 53) % n)
    return edges


def _build_sparse_pair(module, n: int):
    left = module.Graph()
    left.add_nodes_from(range(n))
    left.add_edges_from(_edges(n))

    right = module.Graph()
    right.add_nodes_from(range(n // 2, n + n // 2))
    right.add_edges_from(
        (u + n // 2, v + n // 2) for u, v in _edges(n) if u < n // 2 and v < n // 2
    )
    return left, right


def _build_equal_node_pair(module):
    left = module.Graph()
    left.add_edge(0, True)
    left.add_edge(2, 3.0)
    left.add_edge(4.0, 5)

    right = module.Graph()
    right.add_edge(0.0, 1)
    right.add_edge(2.0, 3)
    right.add_edge(4, 5.0)
    return left, right


def _graph_signature(graph):
    return {
        "graph": sorted((repr(k), repr(v)) for k, v in graph.graph.items()),
        "nodes": [repr(node) for node in graph.nodes()],
        "edges": [[repr(u), repr(v)] for u, v in graph.edges()],
    }


def _digest(value) -> str:
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _intersection_sparse(module, n: int):
    left, right = _build_sparse_pair(module, n)
    return module.intersection(left, right)


def _intersection_equal_nodes(module):
    left, right = _build_equal_node_pair(module)
    return module.intersection(left, right)


def proof(label: str, n: int, compare: Path | None) -> None:
    previous = None
    if compare is not None:
        try:
            with compare.open(encoding="utf-8") as fh:
                previous = json.JSONDecoder().decode(fh.read())
        except json.JSONDecodeError as exc:
            raise AssertionError(f"invalid comparison proof json: {compare}") from exc

    cases = {
        "sparse_intersection": (
            _graph_signature(_intersection_sparse(fnx, n)),
            _graph_signature(_intersection_sparse(nx, n)),
        ),
        "equal_node_intersection": (
            _graph_signature(_intersection_equal_nodes(fnx)),
            _graph_signature(_intersection_equal_nodes(nx)),
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
        (
            "sparse_intersection",
            lambda: _intersection_sparse(fnx, n),
            lambda: _intersection_sparse(nx, n),
        ),
        (
            "equal_node_intersection",
            lambda: _intersection_equal_nodes(fnx),
            lambda: _intersection_equal_nodes(nx),
        ),
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
    left, right = _build_sparse_pair(fnx, n)

    def run():
        for _ in range(reps):
            fnx.intersection(left, right)

    profiler = cProfile.Profile()
    profiler.enable()
    run()
    profiler.disable()
    with (ROOT / f"{label}_profile.txt").open("w") as fh:
        pstats.Stats(profiler, stream=fh).strip_dirs().sort_stats("cumtime").print_stats(80)


def _old_two_graph_intersection(left, right):
    R = fnx.Graph()

    node_intersection = set(left.nodes)
    edge_intersection = set(left.edges)
    edge_intersection.update((v, u) for u, v in list(edge_intersection))

    right_nodes = set(right.nodes)
    right_edges = set(right.edges)
    right_edges.update((v, u) for u, v in list(right_edges))

    node_intersection &= right_nodes
    edge_intersection &= right_edges

    R.add_nodes_from(node_intersection)
    R.add_edges_from(list(edge_intersection))
    return fnx._finalize_operator_result(R)


def ab(label: str, n: int, samples: int, reps: int) -> None:
    left, right = _build_sparse_pair(fnx, n)
    old_sig = _graph_signature(_old_two_graph_intersection(left, right))
    new_sig = _graph_signature(fnx.intersection(left, right))
    if old_sig != new_sig:
        raise AssertionError("old and new signatures differ")

    out = {
        "label": label,
        "n": n,
        "reps_per_sample": reps,
        "samples": samples,
        "signature_sha256": _digest(new_sig),
        "cases": {},
    }
    for case_name, func in (
        ("old_intersection_all_two_graphs", lambda: _old_two_graph_intersection(left, right)),
        ("new_intersection_graph_fast_path", lambda: fnx.intersection(left, right)),
    ):
        values = []
        for _ in range(samples):
            start = time.perf_counter()
            for _ in range(reps):
                func()
            values.append(time.perf_counter() - start)
        out["cases"][case_name] = {
            "best_total": min(values),
            "median_total": statistics.median(values),
            "best_per_call": min(values) / reps,
            "median_per_call": statistics.median(values) / reps,
            "samples": values,
        }

    old_case = out["cases"]["old_intersection_all_two_graphs"]
    new_case = out["cases"]["new_intersection_graph_fast_path"]
    out["new_vs_old_best_ratio"] = new_case["best_per_call"] / old_case["best_per_call"]
    out["new_vs_old_median_ratio"] = new_case["median_per_call"] / old_case["median_per_call"]
    out["speedup_best"] = old_case["best_per_call"] / new_case["best_per_call"]
    out["speedup_median"] = old_case["median_per_call"] / new_case["median_per_call"]
    (ROOT / f"{label}_ab.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["proof", "bench", "profile", "ab"])
    parser.add_argument("--label", required=True)
    parser.add_argument("--n", type=int, default=1800)
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--profile-reps", type=int, default=200)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args()
    if args.command == "proof":
        proof(args.label, args.n, args.compare)
    elif args.command == "bench":
        bench(args.label, args.n, args.samples)
    elif args.command == "profile":
        profile(args.label, args.n, args.profile_reps)
    else:
        ab(args.label, args.n, args.samples, args.profile_reps)


if __name__ == "__main__":
    main()
