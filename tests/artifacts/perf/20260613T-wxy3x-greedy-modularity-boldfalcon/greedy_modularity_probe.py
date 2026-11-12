from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import sys
from pathlib import Path
from typing import Callable

import networkx as nx

import franken_networkx as fnx


def _copy_to_fnx(graph: nx.Graph) -> fnx.Graph:
    out = fnx.Graph()
    out.add_nodes_from(graph.nodes(data=True))
    out.add_edges_from(graph.edges(data=True))
    return out


def _normalize(partition):
    return [
        {
            "type": type(community).__name__,
            "nodes": sorted(repr(node) for node in community),
        }
        for community in partition
    ]


def _partition_key(partition):
    return tuple(tuple(item["nodes"]) for item in _normalize(partition))


def _surface(partition):
    return {
        "container": type(partition).__name__,
        "communities": [type(community).__name__ for community in partition],
    }


def _builders() -> dict[str, Callable[[], nx.Graph]]:
    return {
        "barbell_5_1": lambda: nx.barbell_graph(5, 1),
        "karate": nx.karate_club_graph,
        "watts_strogatz_150": lambda: nx.watts_strogatz_graph(150, 6, 0.23, seed=37),
        "watts_strogatz_300": lambda: nx.watts_strogatz_graph(300, 8, 0.19, seed=41),
        "path_12": lambda: nx.path_graph(12),
        "cycle_18": lambda: nx.cycle_graph(18),
        "complete_9": lambda: nx.complete_graph(9),
        "disconnected_components": lambda: nx.disjoint_union(
            nx.path_graph(5), nx.cycle_graph(6)
        ),
        "zero_edge_7": lambda: nx.empty_graph(7),
    }


def _edge_attr_graph() -> nx.Graph:
    graph = nx.Graph()
    graph.add_weighted_edges_from(
        [
            (0, 1, 0.25),
            (0, 2, 3),
            (1, 2, 3),
            (1, 3, 3),
            (2, 3, 3),
            (2, 4, 0.5),
            (3, 4, 2),
            (3, 5, 0.25),
        ]
    )
    return graph


def _fnx_public(graph: nx.Graph):
    return fnx.community.greedy_modularity_communities(_copy_to_fnx(graph))


def _fnx_raw(graph: nx.Graph, *, weight: str = "__fnx_missing_unit_weight__"):
    return [
        frozenset(c)
        for c in fnx._raw_greedy_modularity_communities(_copy_to_fnx(graph), 1.0, weight)
    ]


def _nx_public(graph: nx.Graph, *, weight: str | None = None):
    return nx.community.greedy_modularity_communities(graph, weight=weight)


def golden(path: Path) -> int:
    records = []
    failed = False
    for name, build in _builders().items():
        graph = build()
        nx_result = _nx_public(graph)
        fnx_public = _fnx_public(graph)
        raw_result = _fnx_raw(graph)
        record = {
            "case": name,
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "nx": _normalize(nx_result),
            "fnx_public": _normalize(fnx_public),
            "fnx_raw": _normalize(raw_result),
            "nx_surface": _surface(nx_result),
            "fnx_public_surface": _surface(fnx_public),
            "raw_as_frozenset_surface": _surface(raw_result),
            "public_matches_nx": _partition_key(fnx_public) == _partition_key(nx_result),
            "raw_matches_nx": _partition_key(raw_result) == _partition_key(nx_result),
        }
        if not record["public_matches_nx"] or not record["raw_matches_nx"]:
            failed = True
        records.append(record)

    weighted = _edge_attr_graph()
    weighted_fnx = _copy_to_fnx(weighted)
    default_nx = _nx_public(weighted)
    explicit_weighted_nx = _nx_public(weighted, weight="weight")
    raw_default_unit = _fnx_raw(weighted)
    raw_weighted = _fnx_raw(weighted, weight="weight")
    parity_graph = fnx._networkx_graph_for_parity(weighted_fnx)
    default_fallback = nx.community.greedy_modularity_communities(
        parity_graph, weight=None
    )
    weighted_fallback = nx.community.greedy_modularity_communities(
        parity_graph, weight="weight"
    )
    records.append(
        {
            "case": "weighted_edge_attr_guard",
            "nodes": weighted.number_of_nodes(),
            "edges": weighted.number_of_edges(),
            "nx_default_unweighted": _normalize(default_nx),
            "nx_explicit_weighted": _normalize(explicit_weighted_nx),
            "fnx_parity_fallback_default": _normalize(default_fallback),
            "fnx_parity_fallback_weighted": _normalize(weighted_fallback),
            "fnx_raw_default_unit": _normalize(raw_default_unit),
            "fnx_raw_weighted": _normalize(raw_weighted),
            "raw_default_matches_default_nx": _partition_key(raw_default_unit)
            == _partition_key(default_nx),
            "raw_weighted_matches_weighted_nx": _partition_key(raw_weighted)
            == _partition_key(explicit_weighted_nx),
            "fallback_default_matches_default_nx": _partition_key(default_fallback)
            == _partition_key(default_nx),
            "fallback_weighted_matches_weighted_nx": _partition_key(weighted_fallback)
            == _partition_key(explicit_weighted_nx),
            "weighted_differs_from_default": _partition_key(explicit_weighted_nx)
            != _partition_key(default_nx),
        }
    )

    payload = {
        "python": sys.version,
        "networkx": nx.__version__,
        "records": records,
    }
    encoded = json.dumps(payload, sort_keys=True, indent=2).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    path.write_bytes(encoded)
    path.with_suffix(".sha256").write_text(f"{digest}  {path.name}\n")
    print(digest)
    return 1 if failed else 0


def bench(which: str, graph_name: str, repeat: int) -> None:
    graph = _builders()[graph_name]()
    if which == "fnx_public":
        call = lambda: _fnx_public(graph)
    elif which == "fnx_raw":
        call = lambda: _fnx_raw(graph)
    elif which == "nx":
        call = lambda: _nx_public(graph)
    else:
        raise ValueError(which)
    for _ in range(repeat):
        call()


def profile(which: str, graph_name: str, repeat: int, path: Path) -> None:
    profiler = cProfile.Profile()
    profiler.enable()
    bench(which, graph_name, repeat)
    profiler.disable()
    with path.open("w") as fh:
        stats = pstats.Stats(profiler, stream=fh)
        stats.strip_dirs().sort_stats("cumtime").print_stats(40)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("golden")
    g.add_argument("path", type=Path)
    b = sub.add_parser("bench")
    b.add_argument("which", choices=["fnx_public", "fnx_raw", "nx"])
    b.add_argument("graph_name", choices=sorted(_builders()))
    b.add_argument("--repeat", type=int, default=1)
    p = sub.add_parser("profile")
    p.add_argument("which", choices=["fnx_public", "fnx_raw", "nx"])
    p.add_argument("graph_name", choices=sorted(_builders()))
    p.add_argument("path", type=Path)
    p.add_argument("--repeat", type=int, default=20)
    args = parser.parse_args()
    if args.cmd == "golden":
        return golden(args.path)
    if args.cmd == "bench":
        bench(args.which, args.graph_name, args.repeat)
        return 0
    profile(args.which, args.graph_name, args.repeat, args.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
