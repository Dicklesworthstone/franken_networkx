#!/usr/bin/env python3
"""Profile/proof harness for the cubic k_components certificate pass."""

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


CASE_BUILDERS: dict[str, tuple[Callable[[], object], Callable[[], object]]] = {
    "petersen": (fnx.petersen_graph, nx.petersen_graph),
    "gp_7_2": (
        lambda: fnx.generalized_petersen_graph(7, 2),
        lambda: nx.generalized_petersen_graph(7, 2),
    ),
    "gp_8_3": (
        lambda: fnx.generalized_petersen_graph(8, 3),
        lambda: nx.generalized_petersen_graph(8, 3),
    ),
    "gp_10_2": (
        lambda: fnx.generalized_petersen_graph(10, 2),
        lambda: nx.generalized_petersen_graph(10, 2),
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


def build_two_cut_graph(mod) -> object:
    graph = mod.Graph()
    graph.add_edges_from(
        [
            (0, 1),
            (0, 2),
            (0, 3),
            (1, 2),
            (1, 3),
            (4, 6),
            (4, 7),
            (5, 6),
            (5, 7),
            (6, 7),
            (2, 4),
            (3, 5),
        ]
    )
    return graph


def proof() -> dict[str, object]:
    cases: dict[str, dict[str, object]] = {}
    for name, (fnx_builder, nx_builder) in CASE_BUILDERS.items():
        fnx_graph = fnx_builder()
        nx_graph = nx_builder()
        fnx_result = fnx.k_components(fnx_graph)
        nx_result = nx.k_components(nx_graph)
        fnx_payload = canonical_components(fnx_result)
        nx_payload = canonical_components(nx_result)
        cases[name] = {
            "nodes": len(fnx_graph),
            "edges": fnx_graph.number_of_edges(),
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
            mod.k_components(mod.generalized_petersen_graph(7, 2), flow_func=fail_flow)
        except Exception as exc:  # noqa: BLE001 - exception type is part of proof payload.
            custom_flow[mod_name] = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
        else:
            custom_flow[mod_name] = {"type": None, "message": None}

    fnx_two_cut = fnx.k_components(build_two_cut_graph(fnx))
    nx_two_cut = nx.k_components(build_two_cut_graph(nx))
    two_cut_payload = {
        "fnx": canonical_components(fnx_two_cut),
        "nx": canonical_components(nx_two_cut),
    }
    two_cut_payload["match"] = two_cut_payload["fnx"] == two_cut_payload["nx"]

    payload = {
        "cases": cases,
        "custom_flow": custom_flow,
        "two_cut": two_cut_payload,
        "ordering": "dict keys preserve NetworkX order; one set component per k",
        "floating_point": "not applicable",
        "rng": "not applicable",
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
            nx.k_components(nx_graph)
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
    parser.add_argument("--mode", choices=("proof", "time", "profile"), required=True)
    parser.add_argument("--case", default="gp_10_2")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.mode == "proof":
        result: object = proof()
    elif args.mode == "time":
        result = time_case(args.repeats)
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
