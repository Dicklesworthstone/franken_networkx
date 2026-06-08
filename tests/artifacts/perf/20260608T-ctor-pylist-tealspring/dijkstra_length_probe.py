import cProfile
import hashlib
import json
import pstats
import random
import sys
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


def build_graphs():
    rnd = random.Random(1)
    edges = [(rnd.randrange(3000), rnd.randrange(3000)) for _ in range(12000)]
    gf = fnx.Graph()
    gn = nx.Graph()
    for u, v in edges:
        if u != v:
            weight = 1 + (u % 5)
            gf.add_edge(u, v, weight=weight)
            gn.add_edge(u, v, weight=weight)
    return gf, gn


def normalize(result):
    return [
        [repr(node), type(distance).__name__, distance]
        for node, distance in result.items()
    ]


def digest(result):
    payload = json.dumps(normalize(result), sort_keys=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def time_case(func, repeat):
    samples = []
    checksum = 0
    for _ in range(repeat):
        start = time.perf_counter()
        result = func()
        samples.append(time.perf_counter() - start)
        checksum += len(result)
    ordered = sorted(samples)
    return {
        "checksum": checksum,
        "mean_s": sum(samples) / len(samples),
        "median_s": ordered[len(ordered) // 2],
        "min_s": ordered[0],
        "samples_s": samples,
    }


def profile_case(func, repeat, path):
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(repeat):
        func()
    profiler.disable()
    with path.open("w") as handle:
        stats = pstats.Stats(profiler, stream=handle).sort_stats("cumtime")
        stats.print_stats(40)


def main():
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    gf, gn = build_graphs()

    raw = getattr(fnx, "_raw_single_source_dijkstra_path_length", None)

    fnx_public = lambda: dict(
        fnx.single_source_dijkstra_path_length(gf, 0, weight="weight")
    )
    nx_public = lambda: dict(
        nx.single_source_dijkstra_path_length(gn, 0, weight="weight")
    )
    raw_native = (
        None
        if raw is None
        else lambda: dict(raw(gf, 0, weight="weight"))
    )

    fnx_result = fnx_public()
    nx_result = nx_public()
    raw_result = None if raw_native is None else raw_native()

    proof = {
        "fnx_sha256": digest(fnx_result),
        "nx_sha256": digest(nx_result),
        "raw_sha256": None if raw_result is None else digest(raw_result),
        "fnx_matches_nx": normalize(fnx_result) == normalize(nx_result),
        "raw_matches_nx": None if raw_result is None else normalize(raw_result) == normalize(nx_result),
        "fnx_head": normalize(fnx_result)[:12],
        "nx_head": normalize(nx_result)[:12],
        "raw_head": None if raw_result is None else normalize(raw_result)[:12],
    }

    bench = {
        "fnx_public": time_case(fnx_public, 25),
        "nx_public": time_case(nx_public, 25),
    }
    if raw_native is not None:
        bench["raw_native"] = time_case(raw_native, 25)

    profile_case(fnx_public, 80, out_dir / "fresh_dijkstra_fnx_public_profile.txt")
    if raw_native is not None:
        profile_case(raw_native, 80, out_dir / "fresh_dijkstra_raw_native_profile.txt")

    (out_dir / "fresh_dijkstra_proof.json").write_text(
        json.dumps(proof, indent=2) + "\n"
    )
    (out_dir / "fresh_dijkstra_bench.json").write_text(
        json.dumps(bench, indent=2) + "\n"
    )
    print(json.dumps({"proof": proof, "bench": bench}, indent=2))


if __name__ == "__main__":
    main()
