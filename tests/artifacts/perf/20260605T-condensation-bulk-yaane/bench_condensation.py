"""Benchmark and parity harness for br-r37-c1-yaane condensation work."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from collections.abc import Iterable

import networkx as nx

import franken_networkx as fnx


def dag_edges(n: int, degree: int) -> list[tuple[int, int]]:
    edges: list[tuple[int, int]] = []
    for u in range(n):
        limit = min(n, u + degree + 1)
        for v in range(u + 1, limit):
            edges.append((u, v))
    return edges


def clustered_edges(n: int, degree: int, cluster: int) -> list[tuple[int, int]]:
    edges = dag_edges(n, degree)
    for start in range(0, n, cluster):
        end = min(n, start + cluster)
        if end - start < 2:
            continue
        for u in range(start, end):
            edges.append((u, start + ((u - start + 1) % (end - start))))
    return edges


def seeded_edges(seed: int, n: int) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    edges: set[tuple[int, int]] = set()
    for u in range(n):
        if rng.random() < 0.25:
            edges.add((u, u))
        for _ in range(rng.randint(0, 4)):
            v = rng.randrange(n)
            if rng.random() < 0.65:
                v = min(n - 1, max(0, u + rng.randint(-3, 8)))
            edges.add((u, v))
    return sorted(edges)


def build_graphs(kind: str, n: int, degree: int, seed: int) -> tuple[fnx.DiGraph, nx.DiGraph]:
    if kind == "dag":
        edges = dag_edges(n, degree)
    elif kind == "clustered":
        edges = clustered_edges(n, degree, max(2, degree + 1))
    elif kind == "random":
        edges = seeded_edges(seed, n)
    else:
        raise ValueError(f"unknown kind: {kind}")

    gf = fnx.DiGraph()
    gn = nx.DiGraph()
    gf.add_nodes_from(range(n))
    gn.add_nodes_from(range(n))
    gf.add_edges_from(edges)
    gn.add_edges_from(edges)
    return gf, gn


def sort_key(value: object) -> tuple[str, str]:
    return (type(value).__name__, repr(value))


def normalize(condensed) -> dict[str, object]:
    nodes = list(condensed.nodes())
    edges = list(condensed.edges())
    members = [
        [node, sorted(condensed.nodes[node]["members"], key=sort_key)] for node in nodes
    ]
    mapping = [
        [node, condensed.graph["mapping"][node]]
        for node in sorted(condensed.graph["mapping"], key=sort_key)
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "members": members,
        "mapping": mapping,
    }


def digest_payload(cases: Iterable[dict[str, object]]) -> str:
    blob = json.dumps(list(cases), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def parity(args: argparse.Namespace) -> None:
    cases: list[dict[str, object]] = []
    failures: list[tuple[object, object]] = []
    specs = [
        ("dag", 0, 0, 1),
        ("dag", 1, 0, 1),
        ("dag", 32, 3, 2),
        ("clustered", 64, 2, 3),
        ("clustered", 96, 4, 4),
    ]
    specs.extend(("random", 40 + seed % 20, 3, seed) for seed in range(60))

    for kind, n, degree, seed in specs:
        gf, gn = build_graphs(kind, n, degree, seed)
        cf = fnx.condensation(gf)
        cn = nx.condensation(gn)
        nf = normalize(cf)
        nn = normalize(cn)
        if nf != nn:
            failures.append(((kind, n, degree, seed), {"fnx": nf, "nx": nn}))
        cases.append({"spec": [kind, n, degree, seed], "normalized": nf})

    digest = digest_payload(cases)
    print(f"GOLDEN_CONDENSATION_SHA256: {digest}")
    print(f"cases passed: {len(cases) - len(failures)}, failures: {len(failures)}")
    if failures:
        print(json.dumps(failures[:3], sort_keys=True, default=repr))
        raise SystemExit(1)


def bench(args: argparse.Namespace) -> None:
    gf, gn = build_graphs(args.kind, args.n, args.degree, args.seed)
    if args.impl == "fnx":
        graph = gf
        func = fnx.condensation
    elif args.impl == "fnx_old":
        graph = gf
        func = old_condensation
    else:
        graph = gn
        func = nx.condensation
    start = time.perf_counter()
    total_edges = 0
    total_nodes = 0
    for _ in range(args.repeat):
        result = func(graph)
        total_nodes += result.number_of_nodes()
        total_edges += result.number_of_edges()
    elapsed = time.perf_counter() - start
    print(
        json.dumps(
            {
                "impl": args.impl,
                "kind": args.kind,
                "n": args.n,
                "degree": args.degree,
                "repeat": args.repeat,
                "elapsed_seconds": elapsed,
                "nodes_accum": total_nodes,
                "edges_accum": total_edges,
            },
            sort_keys=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("parity")
    p.set_defaults(func=parity)

    b = sub.add_parser("bench")
    b.add_argument("--impl", choices=("fnx", "fnx_old", "nx"), required=True)
    b.add_argument("--kind", choices=("dag", "clustered", "random"), default="dag")
    b.add_argument("--n", type=int, default=3000)
    b.add_argument("--degree", type=int, default=4)
    b.add_argument("--seed", type=int, default=0)
    b.add_argument("--repeat", type=int, default=3)
    b.set_defaults(func=bench)

    args = parser.parse_args()
    args.func(args)


def old_condensation(graph: fnx.DiGraph) -> fnx.DiGraph:
    components = [set(component) for component in fnx.strongly_connected_components(graph)]
    mapping = {}
    members = {}
    for idx, component in enumerate(components):
        members[idx] = component
        for node in component:
            mapping[node] = idx

    cond_dg = fnx.DiGraph()
    cond_dg.add_nodes_from(range(len(components)))
    for idx, member_set in members.items():
        cond_dg.nodes[idx]["members"] = member_set
    for u, v in graph.edges():
        cu = mapping[u]
        cv = mapping[v]
        if cu != cv:
            cond_dg.add_edge(cu, cv)
    cond_dg.graph["mapping"] = mapping
    return cond_dg


if __name__ == "__main__":
    main()
