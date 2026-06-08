import cProfile
import gc
import hashlib
import io
import json
import pstats
import statistics
import sys
import time

import franken_networkx as fnx
import networkx as nx


N_SET = 1600
N_FOLD = 700
PARALLEL = 3
PARTS = 4


def add_keyed_or_plain(graph, u, v, key):
    if graph.is_multigraph():
        graph.add_edge(u, v, key=key)
    else:
        graph.add_edge(u, v)


def build_intersection_all(lib, class_name):
    cls = getattr(lib, class_name)
    graphs = []
    for part in range(3):
        graph = cls()
        graph.add_nodes_from(range(N_SET))
        for u in range(N_SET - 2):
            common = (u % 2) == 0
            if common:
                for key in range(PARALLEL):
                    add_keyed_or_plain(graph, u, u + 1, key)
            if (u + part) % 3 == 0:
                for key in range(PARALLEL):
                    add_keyed_or_plain(graph, u, u + 2, key)
        graphs.append(graph)
    return graphs


def build_union_all(lib, class_name):
    cls = getattr(lib, class_name)
    graphs = []
    for part in range(PARTS):
        graph = cls()
        offset = part * N_FOLD
        graph.add_nodes_from(range(offset, offset + N_FOLD))
        for u in range(offset, offset + N_FOLD - 2):
            for key in range(PARALLEL):
                add_keyed_or_plain(graph, u, u + 1, key)
            if u % 3 == 0:
                for key in range(PARALLEL):
                    add_keyed_or_plain(graph, u, u + 2, key)
        graphs.append(graph)
    return graphs


def build_compose_all(lib, class_name):
    cls = getattr(lib, class_name)
    graphs = []
    for part in range(PARTS):
        graph = cls()
        graph.add_nodes_from(range(N_FOLD))
        for u in range(N_FOLD - 2):
            v = (u + 1 + part) % N_FOLD
            for key in range(PARALLEL):
                add_keyed_or_plain(graph, u, v, key)
            if u % 4 == part % 4:
                for key in range(PARALLEL):
                    add_keyed_or_plain(graph, u, (u + 2 + part) % N_FOLD, key)
        graphs.append(graph)
    return graphs


BUILDERS = {
    "intersection_all": build_intersection_all,
    "union_all": build_union_all,
    "compose_all": build_compose_all,
}


def run(lib, op_name, class_name):
    graphs = BUILDERS[op_name](lib, class_name)
    return getattr(lib, op_name)(graphs)


def payload(result):
    if result.is_multigraph():
        edges = list(result.edges(keys=True))
    else:
        edges = list(result.edges())
    return {
        "class": result.__class__.__name__,
        "nodes": list(result.nodes()),
        "edges": edges,
        "node_count": result.number_of_nodes(),
        "edge_count": result.number_of_edges(),
    }


def digest(value):
    encoded = json.dumps(value, separators=(",", ":"), sort_keys=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def time_lib(lib, op_name, class_name, reps):
    graphs = BUILDERS[op_name](lib, class_name)
    samples = []
    previous = gc.isenabled()
    gc.disable()
    try:
        for _ in range(3):
            result = getattr(lib, op_name)(graphs)
            if result.number_of_edges() == -1:
                raise AssertionError("unreachable")
        for _ in range(reps):
            start = time.perf_counter()
            result = getattr(lib, op_name)(graphs)
            samples.append(time.perf_counter() - start)
            if result.number_of_edges() == -1:
                raise AssertionError("unreachable")
    finally:
        if previous:
            gc.enable()
    return {
        "median_s": statistics.median(samples),
        "min_s": min(samples),
        "max_s": max(samples),
        "stdev_s": statistics.stdev(samples) if len(samples) > 1 else 0.0,
        "reps": reps,
        "node_count": result.number_of_nodes(),
        "edge_count": result.number_of_edges(),
    }


def direct(out_path):
    cases = {
        "intersection_all": ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"],
        "union_all": ["DiGraph", "MultiGraph", "MultiDiGraph"],
        "compose_all": ["DiGraph", "MultiGraph", "MultiDiGraph"],
    }
    out = {"cases": {}, "n_set": N_SET, "n_fold": N_FOLD, "parallel": PARALLEL}
    for op_name, classes in cases.items():
        out["cases"][op_name] = {}
        for class_name in classes:
            out["cases"][op_name][class_name] = {
                "fnx": time_lib(fnx, op_name, class_name, 20),
                "networkx": time_lib(nx, op_name, class_name, 20),
            }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
        fh.write("\n")


def proof(op_name, class_name, out_path):
    fnx_payload = payload(run(fnx, op_name, class_name))
    nx_payload = payload(run(nx, op_name, class_name))
    out = {
        "op": op_name,
        "class": class_name,
        "equal": fnx_payload == nx_payload,
        "fnx_sha256": digest(fnx_payload),
        "networkx_sha256": digest(nx_payload),
        "ordering": "exact list(result.nodes()) and exact edge list",
        "floating_point": "none",
        "rng": "none",
        "fnx_counts": {
            "nodes": fnx_payload["node_count"],
            "edges": fnx_payload["edge_count"],
        },
    }
    if fnx_payload != nx_payload:
        out["fnx_prefix"] = fnx_payload["edges"][:20]
        out["networkx_prefix"] = nx_payload["edges"][:20]
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
        fh.write("\n")
    if not out["equal"]:
        raise SystemExit(1)


def profile(op_name, class_name, out_path, reps):
    graphs = BUILDERS[op_name](fnx, class_name)
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(reps):
        result = getattr(fnx, op_name)(graphs)
        if result.number_of_edges() == -1:
            raise AssertionError("unreachable")
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumtime").print_stats(45)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(stream.getvalue())


def one(lib_name, op_name, class_name, reps):
    lib = fnx if lib_name == "fnx" else nx
    graphs = BUILDERS[op_name](lib, class_name)
    for _ in range(int(reps)):
        result = getattr(lib, op_name)(graphs)
        if result.number_of_edges() == -1:
            raise AssertionError("unreachable")


def main():
    mode = sys.argv[1]
    if mode == "direct":
        direct(sys.argv[2])
    elif mode == "proof":
        proof(sys.argv[2], sys.argv[3], sys.argv[4])
    elif mode == "profile":
        profile(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]))
    elif mode == "one":
        one(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]))
    else:
        raise SystemExit(f"unknown mode: {mode}")


if __name__ == "__main__":
    main()
