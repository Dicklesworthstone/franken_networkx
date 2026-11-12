import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import time

import franken_networkx as fnx
import networkx as nx


def build_graph():
    nx_graph = nx.barabasi_albert_graph(1500, 4, seed=19)
    fnx_graph = fnx.Graph()
    fnx_graph.add_nodes_from(nx_graph.nodes())
    fnx_graph.add_edges_from(nx_graph.edges())
    return fnx_graph, nx_graph


def s_metric_proof_payload():
    cases = []
    builders = [
        ("ba1500", lambda: nx.barabasi_albert_graph(1500, 4, seed=19)),
        ("path257", nx.path_graph(257)),
        ("cycle256", nx.cycle_graph(256)),
        ("complete80", nx.complete_graph(80)),
        ("selfloop", lambda: nx.Graph([(0, 0), (0, 1), (1, 2), (2, 2)])),
    ]
    for name, builder in builders:
        nx_graph = builder() if callable(builder) else builder
        fnx_graph = fnx.Graph()
        fnx_graph.add_nodes_from(nx_graph.nodes())
        fnx_graph.add_edges_from(nx_graph.edges())
        fnx_value = fnx.s_metric(fnx_graph)
        nx_value = nx.s_metric(nx_graph)
        raw_value = None
        if not any(u == v for u, v in nx_graph.edges()):
            raw_value = fnx._fnx.s_metric(fnx_graph)
        cases.append(
            {
                "name": name,
                "fnx": fnx_value,
                "nx": nx_value,
                "raw": raw_value,
                "matches_nx": fnx_value == nx_value,
                "raw_matches_nx": raw_value is None or raw_value == nx_value,
            }
        )
    blob = json.dumps(cases, sort_keys=True, separators=(",", ":")).encode()
    return {"cases": cases, "sha256": hashlib.sha256(blob).hexdigest()}


def transitivity_proof_payload():
    cases = []
    builders = [
        ("ba1500", lambda: nx.barabasi_albert_graph(1500, 4, seed=23)),
        ("path257", nx.path_graph(257)),
        ("cycle256", nx.cycle_graph(256)),
        ("complete80", nx.complete_graph(80)),
        ("selfloop", lambda: nx.Graph([(0, 0), (0, 1), (1, 2), (2, 2)])),
    ]
    for name, builder in builders:
        nx_graph = builder() if callable(builder) else builder
        fnx_graph = fnx.Graph()
        fnx_graph.add_nodes_from(nx_graph.nodes())
        fnx_graph.add_edges_from(nx_graph.edges())
        fnx_value = fnx.transitivity(fnx_graph)
        nx_value = nx.transitivity(nx_graph)
        raw_value = fnx._fnx.transitivity(fnx_graph)
        cases.append(
            {
                "name": name,
                "fnx": fnx_value,
                "nx": nx_value,
                "raw": raw_value,
                "matches_nx": fnx_value == nx_value,
                "raw_matches_nx": raw_value == nx_value,
            }
        )
    blob = json.dumps(cases, sort_keys=True, separators=(",", ":")).encode()
    return {"cases": cases, "sha256": hashlib.sha256(blob).hexdigest()}


def time_calls(calls, repeats, target):
    fnx_graph, nx_graph = build_graph()
    if target == "s_metric":
        funcs = {
            "fnx_public": lambda: fnx.s_metric(fnx_graph),
            "fnx_raw": lambda: fnx._fnx.s_metric(fnx_graph),
            "nx": lambda: nx.s_metric(nx_graph),
        }
    else:
        funcs = {
            "fnx_public": lambda: fnx.transitivity(fnx_graph),
            "fnx_raw": lambda: fnx._fnx.transitivity(fnx_graph),
            "nx": lambda: nx.transitivity(nx_graph),
        }
    timings = {name: [] for name in funcs}
    for _ in range(repeats):
        for name, func in funcs.items():
            start = time.perf_counter()
            result = None
            for _ in range(calls):
                result = func()
            elapsed = time.perf_counter() - start
            timings[name].append(elapsed / calls)
            if result != funcs["nx"]():
                raise AssertionError(f"{name} result {result!r} differs from NetworkX")
    return {
        name: {
            "samples": values,
            "median": statistics.median(values),
            "mean": statistics.fmean(values),
            "min": min(values),
        }
        for name, values in timings.items()
    }


def profile_calls(calls, output, target):
    fnx_graph, _ = build_graph()
    func = fnx._fnx.s_metric if target == "s_metric" else fnx._fnx.transitivity
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(calls):
        func(fnx_graph)
    profiler.disable()
    with open(output, "w", encoding="utf-8") as handle:
        stats = pstats.Stats(profiler, stream=handle).sort_stats("cumulative")
        stats.print_stats(40)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["proof", "time", "profile", "run"], required=True)
    parser.add_argument("--calls", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=9)
    parser.add_argument("--target", choices=["s_metric", "transitivity"], default="s_metric")
    parser.add_argument("--output")
    args = parser.parse_args()

    if args.mode == "proof":
        payload = (
            s_metric_proof_payload()
            if args.target == "s_metric"
            else transitivity_proof_payload()
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.mode == "time":
        print(
            json.dumps(
                time_calls(args.calls, args.repeats, args.target),
                indent=2,
                sort_keys=True,
            )
        )
    elif args.mode == "profile":
        if args.output is None:
            raise SystemExit("--output is required for profile mode")
        profile_calls(args.calls, args.output, args.target)
    else:
        fnx_graph, _ = build_graph()
        func = fnx.s_metric if args.target == "s_metric" else fnx.transitivity
        for _ in range(args.calls):
            func(fnx_graph)


if __name__ == "__main__":
    main()
