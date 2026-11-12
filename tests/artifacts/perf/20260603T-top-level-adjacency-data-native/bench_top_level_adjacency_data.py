import argparse
import cProfile
import hashlib
import io
import json
import pstats
import random
import statistics
import time

import networkx as nx

import franken_networkx as fnx


def build_pair(n, m, seed, *, directed=False):
    rnd = random.Random(seed)
    edges = []
    seen = set()
    while len(edges) < m:
        a = rnd.randrange(n)
        b = rnd.randrange(n)
        if a == b:
            continue
        key = (a, b) if directed else (min(a, b), max(a, b))
        if key in seen:
            continue
        seen.add(key)
        edges.append((a, b))

    graph_type = nx.DiGraph if directed else nx.Graph
    fnx_type = fnx.DiGraph if directed else fnx.Graph
    gx = graph_type()
    gf = fnx_type()
    gx.add_nodes_from(range(n))
    gf.add_nodes_from(range(n))
    gx.add_edges_from(edges)
    gf.add_edges_from(edges)

    for i, (u, v) in enumerate(edges):
        if i % 3 == 0:
            gx[u][v]["weight"] = float(i)
            gf[u][v]["weight"] = float(i)
        if i % 5 == 0:
            gx[u][v]["label"] = f"e{i}"
            gf[u][v]["label"] = f"e{i}"
    for node in list(gx.nodes())[::4]:
        gx.nodes[node]["color"] = f"c{node}"
        gf.nodes[node]["color"] = f"c{node}"
    gx.graph["name"] = "g"
    gf.graph["name"] = "g"
    return gx, gf


def digest(payload):
    blob = json.dumps(
        payload,
        sort_keys=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(blob).hexdigest()


def bench_case(directed, samples):
    gx, gf = build_pair(1500, 12000, 8675309, directed=directed)
    nx_payload = nx.readwrite.json_graph.adjacency_data(gx)
    fnx_payload = fnx.adjacency_data(gf)
    assert nx_payload == fnx_payload

    timings = []
    for _ in range(samples):
        start = time.perf_counter()
        fnx.adjacency_data(gf)
        timings.append(time.perf_counter() - start)

    return {
        "case": "digraph" if directed else "graph",
        "n": gf.number_of_nodes(),
        "m": gf.number_of_edges(),
        "samples": samples,
        "mean_seconds": statistics.mean(timings),
        "median_seconds": statistics.median(timings),
        "min_seconds": min(timings),
        "max_seconds": max(timings),
        "sha256": digest(fnx_payload),
        "nx_equal": True,
    }


def profile_case(repeats):
    _, gf = build_pair(1500, 12000, 8675309, directed=True)
    profile = cProfile.Profile()
    profile.enable()
    for _ in range(repeats):
        fnx.adjacency_data(gf)
    profile.disable()
    stream = io.StringIO()
    pstats.Stats(profile, stream=stream).strip_dirs().sort_stats("cumtime").print_stats(15)
    print(stream.getvalue(), end="")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["bench", "profile"], default="bench")
    parser.add_argument("--samples", type=int, default=25)
    parser.add_argument("--profile-repeats", type=int, default=30)
    args = parser.parse_args()
    if args.mode == "profile":
        profile_case(args.profile_repeats)
        return
    print(json.dumps(bench_case(False, args.samples), sort_keys=True))
    print(json.dumps(bench_case(True, args.samples), sort_keys=True))


if __name__ == "__main__":
    main()
