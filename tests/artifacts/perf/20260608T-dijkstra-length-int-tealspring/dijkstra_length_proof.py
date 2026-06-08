import hashlib
import json
import math
import random
import sys
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


def normalize(result):
    return [[repr(node), type(distance).__name__, distance] for node, distance in result.items()]


def digest(result):
    payload = json.dumps(normalize(result), sort_keys=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def build_ba_graphs():
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


def build_tie_graphs(factory_f, factory_n):
    gf = factory_f()
    gn = factory_n()
    weighted_edges = [
        ("s", "a", 1),
        ("s", "b", 1),
        ("a", "c", 1),
        ("b", "d", 1),
        ("c", "z", 1),
        ("d", "z", 1),
        ("s", "float", 1.5),
        ("float", "mix", 2),
    ]
    for u, v, w in weighted_edges:
        gf.add_edge(u, v, weight=w)
        gn.add_edge(u, v, weight=w)
    return gf, gn


def call_result(func):
    try:
        value = func()
    except Exception as exc:
        return {
            "ok": False,
            "type": type(exc).__name__,
            "message": str(exc),
        }
    return {
        "ok": True,
        "sha256": digest(dict(value)),
        "rows": normalize(dict(value)),
    }


def time_case(func, repeat):
    samples = []
    checksum = 0
    for _ in range(repeat):
        start = time.perf_counter()
        result = dict(func())
        samples.append(time.perf_counter() - start)
        checksum += len(result)
    samples_sorted = sorted(samples)
    return {
        "checksum": checksum,
        "mean_s": sum(samples) / len(samples),
        "median_s": samples_sorted[len(samples_sorted) // 2],
        "min_s": samples_sorted[0],
        "samples_s": samples,
    }


def raw_length(fnx_graph, source, cutoff=None):
    raw = fnx._raw_single_source_dijkstra_path_length
    if cutoff is None:
        return raw(fnx_graph, source, weight="weight")
    return raw(fnx_graph, source, cutoff=cutoff, weight="weight")


def main():
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    gf, gn = build_ba_graphs()

    public_result = dict(fnx.single_source_dijkstra_path_length(gf, 0, weight="weight"))
    nx_result = dict(nx.single_source_dijkstra_path_length(gn, 0, weight="weight"))
    raw_result = dict(fnx._raw_single_source_dijkstra_path_length(gf, 0, weight="weight"))

    cases = {
        "ba_public": normalize(public_result)[:24],
        "ba_nx": normalize(nx_result)[:24],
        "ba_raw": normalize(raw_result)[:24],
        "ba_public_sha256": digest(public_result),
        "ba_nx_sha256": digest(nx_result),
        "ba_raw_sha256": digest(raw_result),
        "ba_public_matches_nx": normalize(public_result) == normalize(nx_result),
        "ba_raw_matches_nx": normalize(raw_result) == normalize(nx_result),
    }

    for graph_name, fnx_factory, nx_factory in (
        ("undirected", fnx.Graph, nx.Graph),
        ("directed", fnx.DiGraph, nx.DiGraph),
    ):
        tf, tn = build_tie_graphs(fnx_factory, nx_factory)
        for cutoff in (None, 1, 2, -1, math.nan, math.inf):
            suffix = "none" if cutoff is None else repr(cutoff)
            key = f"{graph_name}_cutoff_{suffix}"
            cases[key] = {
                "fnx": call_result(
                    lambda tf=tf, cutoff=cutoff: fnx.single_source_dijkstra_path_length(
                        tf, "s", cutoff=cutoff, weight="weight"
                    )
                ),
                "nx": call_result(
                    lambda tn=tn, cutoff=cutoff: nx.single_source_dijkstra_path_length(
                        tn, "s", cutoff=cutoff, weight="weight"
                    )
                ),
                "raw": call_result(lambda tf=tf, cutoff=cutoff: raw_length(tf, "s", cutoff=cutoff)),
            }

    negative_f, negative_n = fnx.Graph(), nx.Graph()
    negative_f.add_edge("s", "a", weight=-1)
    negative_n.add_edge("s", "a", weight=-1)
    nonnumeric_f, nonnumeric_n = fnx.Graph(), nx.Graph()
    nonnumeric_f.add_edge("s", "a", weight={})
    nonnumeric_n.add_edge("s", "a", weight={})
    infinite_f, infinite_n = fnx.Graph(), nx.Graph()
    infinite_f.add_edge("s", "a", weight=math.inf)
    infinite_n.add_edge("s", "a", weight=math.inf)
    cases["delegation"] = {
        "negative_should_delegate": fnx._should_delegate_dijkstra_to_networkx(negative_f, "weight"),
        "negative_fnx": call_result(
            lambda: fnx.single_source_dijkstra_path_length(negative_f, "s", weight="weight")
        ),
        "negative_nx": call_result(
            lambda: nx.single_source_dijkstra_path_length(negative_n, "s", weight="weight")
        ),
        "nonnumeric_should_delegate": fnx._should_delegate_dijkstra_to_networkx(
            nonnumeric_f, "weight"
        ),
        "nonnumeric_fnx": call_result(
            lambda: fnx.single_source_dijkstra_path_length(nonnumeric_f, "s", weight="weight")
        ),
        "nonnumeric_nx": call_result(
            lambda: nx.single_source_dijkstra_path_length(nonnumeric_n, "s", weight="weight")
        ),
        "infinite_should_delegate": fnx._should_delegate_dijkstra_to_networkx(infinite_f, "weight"),
        "infinite_fnx": call_result(
            lambda: fnx.single_source_dijkstra_path_length(infinite_f, "s", weight="weight")
        ),
        "infinite_nx": call_result(
            lambda: nx.single_source_dijkstra_path_length(infinite_n, "s", weight="weight")
        ),
    }

    bench = {
        "fnx_public": time_case(lambda: fnx.single_source_dijkstra_path_length(gf, 0, weight="weight"), 30),
        "raw_native": time_case(lambda: fnx._raw_single_source_dijkstra_path_length(gf, 0, weight="weight"), 30),
        "nx_public": time_case(lambda: nx.single_source_dijkstra_path_length(gn, 0, weight="weight"), 30),
    }

    proof = {"cases": cases, "bench": bench}
    (out_dir / "proof.json").write_text(json.dumps(proof, indent=2, allow_nan=True) + "\n")
    print(json.dumps(proof, indent=2, allow_nan=True))


if __name__ == "__main__":
    main()
