#!/usr/bin/env python3
"""Profile/proof harness for the 5-regular k_components certificate pass."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import time
from collections.abc import Callable
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


def genuine_nx_k_components(graph, flow_func=None):
    func = getattr(nx.k_components, "orig_func", nx.k_components)
    return func(graph, flow_func=flow_func)


CASE_BUILDERS: dict[str, tuple[Callable[[], object], Callable[[], object]]] = {
    "rr_5_20_seed7": (
        lambda: fnx.random_regular_graph(5, 20, seed=7),
        lambda: nx.random_regular_graph(5, 20, seed=7),
    ),
    "rr_5_24_seed11": (
        lambda: fnx.random_regular_graph(5, 24, seed=11),
        lambda: nx.random_regular_graph(5, 24, seed=11),
    ),
}


def canonical_node(node: object) -> str:
    return repr(node)


def canonical_components(result: dict[int, list[set[object]]]) -> list[dict[str, object]]:
    rows = []
    for key, components in result.items():
        rows.append(
            {
                "k": key,
                "components": [
                    sorted((canonical_node(node) for node in component))
                    for component in components
                ],
            }
        )
    return rows


def digest_payload(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_two_cut_five_regular_graph(mod) -> object:
    graph = mod.complete_graph(6)
    graph.add_nodes_from(range(6, 12))
    graph.add_edges_from(
        (u, v)
        for u in range(6, 12)
        for v in range(u + 1, 12)
    )
    graph.remove_edge(0, 1)
    graph.remove_edge(6, 7)
    graph.add_edge(0, 6)
    graph.add_edge(1, 7)
    return graph


def proof() -> dict[str, object]:
    cases: dict[str, dict[str, object]] = {}
    for name, (fnx_builder, nx_builder) in CASE_BUILDERS.items():
        fnx_graph = fnx_builder()
        nx_graph = nx_builder()
        fnx_result = fnx.k_components(fnx_graph)
        nx_result = genuine_nx_k_components(nx_graph)
        fnx_payload = canonical_components(fnx_result)
        nx_payload = canonical_components(nx_result)
        cases[name] = {
            "nodes": len(fnx_graph),
            "edges": fnx_graph.number_of_edges(),
            "degree_sequence": sorted(degree for _, degree in fnx_graph.degree()),
            "fnx": fnx_payload,
            "nx": nx_payload,
            "match": fnx_payload == nx_payload,
            "fnx_sha256": digest_payload(fnx_payload),
            "nx_sha256": digest_payload(nx_payload),
        }

    def fail_flow(*_args, **_kwargs):
        raise RuntimeError("custom flow sentinel")

    custom_flow = {}
    for mod_name, mod in (("fnx", fnx), ("nx", nx)):
        try:
            if mod_name == "fnx":
                mod.k_components(mod.random_regular_graph(5, 20, seed=7), flow_func=fail_flow)
            else:
                genuine_nx_k_components(
                    mod.random_regular_graph(5, 20, seed=7),
                    flow_func=fail_flow,
                )
        except Exception as exc:  # noqa: BLE001 - exception type is part of proof payload.
            custom_flow[mod_name] = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
        else:
            custom_flow[mod_name] = {"type": None, "message": None}

    fnx_two_cut = fnx.k_components(build_two_cut_five_regular_graph(fnx))
    nx_two_cut = genuine_nx_k_components(build_two_cut_five_regular_graph(nx))
    two_cut_payload = {
        "fnx": canonical_components(fnx_two_cut),
        "nx": canonical_components(nx_two_cut),
    }
    two_cut_payload["match"] = two_cut_payload["fnx"] == two_cut_payload["nx"]

    payload = {
        "cases": cases,
        "custom_flow": custom_flow,
        "two_cut": two_cut_payload,
        "ordering": "dict keys preserve NetworkX order; one set component per k for certified graphs",
        "floating_point": "not applicable",
        "rng": "seeded graph construction only; output RNG surface not applicable",
    }
    payload["sha256"] = digest_payload(payload)
    return payload


def time_case(repeats: int) -> dict[str, object]:
    rows = []
    for name, (fnx_builder, nx_builder) in CASE_BUILDERS.items():
        fnx_times = []
        nx_times = []
        for _ in range(repeats):
            fnx_graph = fnx_builder()
            start = time.perf_counter()
            fnx.k_components(fnx_graph)
            fnx_times.append(time.perf_counter() - start)

            nx_graph = nx_builder()
            start = time.perf_counter()
            genuine_nx_k_components(nx_graph)
            nx_times.append(time.perf_counter() - start)
        rows.append(
            {
                "case": name,
                "fnx_best_s": min(fnx_times),
                "fnx_mean_s": sum(fnx_times) / len(fnx_times),
                "nx_best_s": min(nx_times),
                "nx_mean_s": sum(nx_times) / len(nx_times),
            }
        )
    return {"repeats": repeats, "rows": rows}


def time_one(which: str, case_name: str, repeats: int) -> dict[str, object]:
    graph = CASE_BUILDERS[case_name][0 if which == "fnx" else 1]()
    func = fnx.k_components if which == "fnx" else genuine_nx_k_components
    result = None
    start = time.perf_counter()
    for _ in range(repeats):
        result = func(graph)
    seconds = time.perf_counter() - start
    return {
        "which": which,
        "case": case_name,
        "nodes": len(graph),
        "edges": graph.number_of_edges(),
        "repeats": repeats,
        "seconds": seconds,
        "seconds_per_call": seconds / repeats,
        "result_sha256": digest_payload(canonical_components(result)),
    }


def profile_case(case_name: str) -> str:
    graph = CASE_BUILDERS[case_name][0]()
    profiler = cProfile.Profile()
    profiler.enable()
    fnx.k_components(graph)
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(20)
    return stream.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("proof", "time", "time-one", "profile"), required=True)
    parser.add_argument("--case", default="rr_5_20_seed7")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--which", choices=("fnx", "nx"), default="fnx")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.mode == "proof":
        result: object = proof()
    elif args.mode == "time":
        result = time_case(args.repeats)
    elif args.mode == "time-one":
        result = time_one(args.which, args.case, args.repeats)
    else:
        result = profile_case(args.case)

    if args.output is None:
        if isinstance(result, str):
            print(result)
        else:
            print(json.dumps(result, indent=2, sort_keys=True))
    else:
        if isinstance(result, str):
            args.output.write_text(result, encoding="utf-8")
        else:
            args.output.write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )


if __name__ == "__main__":
    main()
