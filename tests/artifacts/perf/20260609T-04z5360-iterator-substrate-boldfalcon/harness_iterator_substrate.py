import argparse
import cProfile
import hashlib
import io
import json
import pstats
import statistics
import time

import franken_networkx as fnx
import networkx as nx


def build_graph(n):
    graph = fnx.Graph()
    graph.add_nodes_from(range(n))
    return graph


def build_nx_graph(n):
    graph = nx.Graph()
    graph.add_nodes_from(range(n))
    return graph


def time_call(fn, repeats):
    samples = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        result = fn()
        elapsed = time.perf_counter_ns() - start
        samples.append(elapsed)
        if len(result) == 0:
            raise AssertionError("empty timing result")
    return {
        "median_ns": int(statistics.median(samples)),
        "mean_ns": int(statistics.mean(samples)),
        "min_ns": min(samples),
        "max_ns": max(samples),
        "samples_ns": samples,
    }


def mutation_outcome(graph, operation):
    iterator = iter(graph)
    first = next(iterator)
    try:
        operation(graph)
        second = next(iterator)
        return {"first": first, "second": second, "error": None}
    except Exception as exc:
        return {
            "first": first,
            "second": None,
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }


def proof_payload():
    cases = {}
    for ctor_name, ctor in (("fnx", fnx.Graph), ("nx", nx.Graph)):
        graph = ctor()
        graph.add_nodes_from([0, 0.0, True, "0", 2])
        graph.add_edge(0, 2)
        graph.add_edge(0.0, "0")
        cases[ctor_name] = {
            "list": [repr(node) for node in graph],
            "set_repr_sorted": sorted(repr(node) for node in set(graph)),
            "edges": [tuple(repr(part) for part in edge) for edge in graph.edges()],
            "iter_type": type(iter(graph)).__name__,
            "add_new": mutation_outcome(graph.copy(), lambda g: g.add_node("new")),
            "remove": mutation_outcome(graph.copy(), lambda g: g.remove_node(2)),
            "remove_add_same_size": mutation_outcome(
                graph.copy(),
                lambda g: (g.remove_node(2), g.add_node("replacement")),
            ),
            "add_existing_edge": mutation_outcome(graph.copy(), lambda g: g.add_edge(0, 2)),
            "clear": mutation_outcome(graph.copy(), lambda g: g.clear()),
        }
    return cases


def cmd_proof(args):
    payload = proof_payload()
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    result = {
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "payload": payload,
    }
    print(json.dumps(result, indent=2, sort_keys=True))


def cmd_direct(args):
    graph = build_graph(args.nodes)
    nx_graph = build_nx_graph(args.nodes)
    result = {
        "nodes": args.nodes,
        "repeats": args.repeats,
        "fnx_list": time_call(lambda: list(graph), args.repeats),
        "fnx_set": time_call(lambda: set(graph), args.repeats),
        "fnx_native_tuple": time_call(lambda: graph._native_node_keys(), args.repeats),
        "nx_list": time_call(lambda: list(nx_graph), args.repeats),
        "nx_set": time_call(lambda: set(nx_graph), args.repeats),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


def cmd_profile(args):
    graph = build_graph(args.nodes)

    def run():
        for _ in range(args.loops):
            set(graph)

    profile = cProfile.Profile()
    profile.enable()
    run()
    profile.disable()
    stream = io.StringIO()
    pstats.Stats(profile, stream=stream).sort_stats("tottime").print_stats(args.limit)
    print(stream.getvalue())


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    proof = sub.add_parser("proof")
    proof.set_defaults(func=cmd_proof)
    direct = sub.add_parser("direct")
    direct.add_argument("--nodes", type=int, default=1500)
    direct.add_argument("--repeats", type=int, default=41)
    direct.set_defaults(func=cmd_direct)
    profile = sub.add_parser("profile")
    profile.add_argument("--nodes", type=int, default=1500)
    profile.add_argument("--loops", type=int, default=200)
    profile.add_argument("--limit", type=int, default=25)
    profile.set_defaults(func=cmd_profile)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
