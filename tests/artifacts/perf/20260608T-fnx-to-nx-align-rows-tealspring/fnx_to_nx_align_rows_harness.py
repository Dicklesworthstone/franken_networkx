from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import random
import statistics
import time

import franken_networkx as fnx
from franken_networkx import backend


def _old_fnx_to_nx(fg):
    import networkx as nx

    if fg.is_multigraph():
        G = nx.MultiDiGraph() if fg.is_directed() else nx.MultiGraph()
    elif fg.is_directed():
        G = nx.DiGraph()
    else:
        G = nx.Graph()

    node_view = getattr(fg, "nodes", None)
    if node_view is not None:
        G.add_nodes_from((node, dict(node_view[node])) for node in fg)
    else:
        G.add_nodes_from(fg)

    if fg.is_multigraph():
        for u, v in backend._topo_emit_edges_by_adj(fg):
            G.add_edges_from(
                (u, v, key, dict(attrs)) for key, attrs in fg[u][v].items()
            )
    else:
        directed = fg.is_directed()
        bulk = (
            backend._native_fnx_to_nx_adjacency(fg)
            if (
                backend._native_fnx_to_nx_adjacency is not None
                and type(fg) in (fnx.Graph, fnx.DiGraph)
            )
            else None
        )
        if bulk is not None:
            display_nodes = list(fg)
            canon_to_obj = {
                canon: obj for (canon, _nbrs), obj in zip(bulk, display_nodes)
            }
            edges_in_order = []
            if directed:
                for node, nbrs in bulk:
                    onode = canon_to_obj[node]
                    for nbr, attrs in nbrs:
                        edges_in_order.append((onode, canon_to_obj[nbr], dict(attrs)))
            else:
                seen_undirected = set()
                for node, nbrs in bulk:
                    onode = canon_to_obj[node]
                    for nbr, attrs in nbrs:
                        onbr = canon_to_obj[nbr]
                        pair = frozenset((onode, onbr))
                        if pair in seen_undirected:
                            continue
                        seen_undirected.add(pair)
                        edges_in_order.append((onode, onbr, dict(attrs)))
        else:
            attrs_by_pair = {}
            for u, nbrs in fg._adj.items():
                for v, attrs in nbrs.items():
                    attrs_by_pair[(u, v) if directed else frozenset((u, v))] = attrs
            edges_in_order = []
            for u, v in backend._topo_emit_edges_by_adj(fg):
                key = (u, v) if directed else frozenset((u, v))
                edges_in_order.append((u, v, dict(attrs_by_pair.get(key, {}))))
        G.add_edges_from(edges_in_order)

    def _align_rows(nx_rows, fg_rows):
        for x in fg:
            src = list(fg_rows[x])
            row = nx_rows[x]
            if len(row) != len(src) or any(a is not b for a, b in zip(row, src)):
                nx_rows[x] = {o: row[o] for o in src}

    if fg.is_directed():
        _align_rows(G._succ, fg.adj)
        _align_rows(G._pred, fg.pred)
    else:
        _align_rows(G._adj, fg.adj)
    G.graph.update(dict(fg.graph))
    return G


def _converter(name):
    if name == "old":
        return _old_fnx_to_nx
    if name == "new":
        return backend._fnx_to_nx
    raise ValueError(name)


def _dense_graph(n, directed=False):
    cls = fnx.DiGraph if directed else fnx.Graph
    g = cls()
    g.add_nodes_from(range(n))
    width = 17
    for u in range(n):
        for step in range(1, width + 1):
            v = (u + step) % n
            if directed or u < v:
                g.add_edge(u, v, weight=(u * 131 + v * 17) % 23)
    return g


def _z6uka_graphs():
    cases = []

    g = fnx.Graph()
    g.add_node(0)
    g.add_node(1.0)
    g.add_edge(0, 1)
    cases.append(("graph_int_cell_float_node", g))

    g = fnx.Graph()
    g.add_edge(0, 1.0)
    g.add_edge(0, 1)
    cases.append(("graph_existing_float_cell", g))

    d = fnx.DiGraph()
    d.add_node(0)
    d.add_node(1.0)
    d.add_edge(0, 1)
    d.add_edge(1, 0)
    cases.append(("digraph_succ_pred_mixed", d))

    d = fnx.DiGraph()
    d.add_edge(12.0, 12)
    d.add_edge(12, 0)
    cases.append(("digraph_mixed_self_loop", d))

    return cases


def _random_graph(seed, directed):
    rng = random.Random(seed)
    cls = fnx.DiGraph if directed else fnx.Graph
    g = cls()
    nodes = list(range(rng.randint(0, 28)))
    rng.shuffle(nodes)
    for node in nodes:
        if rng.random() < 0.3:
            g.add_node(node, color=f"n{node}", rank=node % 5)
        else:
            g.add_node(node)
    for _ in range(rng.randint(0, max(1, len(nodes) * 3))):
        if not nodes:
            break
        u = rng.choice(nodes)
        v = rng.choice(nodes)
        if rng.random() < 0.4:
            g.add_edge(u, v, weight=(u + 2 * v) % 13, tag=f"{u}:{v}")
        else:
            g.add_edge(u, v)
    return g


def _row_payload(h):
    if h.is_directed():
        rows = {
            repr(node): {
                "succ": [repr(nbr) for nbr in h.succ[node]],
                "pred": [repr(nbr) for nbr in h.pred[node]],
            }
            for node in h
        }
    else:
        rows = {
            repr(node): [repr(nbr) for nbr in h.adj[node]]
            for node in h
        }
    edges = [
        [repr(u), repr(v), sorted((str(k), repr(vv)) for k, vv in attrs.items())]
        for u, v, attrs in h.edges(data=True)
    ]
    return {
        "directed": h.is_directed(),
        "nodes": [repr(node) for node in h],
        "rows": rows,
        "edges": edges,
        "graph": sorted((str(k), repr(v)) for k, v in h.graph.items()),
    }


def _digest(payloads):
    encoded = json.dumps(payloads, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def proof():
    cases = []
    cases.extend(_z6uka_graphs())
    for seed in range(400):
        cases.append((f"graph_random_{seed}", _random_graph(seed * 17 + 3, False)))
        cases.append((f"digraph_random_{seed}", _random_graph(seed * 19 + 5, True)))

    mismatches = []
    payloads = []
    for name, graph in cases:
        old_payload = _row_payload(_old_fnx_to_nx(graph))
        new_payload = _row_payload(backend._fnx_to_nx(graph))
        if old_payload != new_payload:
            mismatches.append(name)
        payloads.append({"name": name, "payload": new_payload})
    return {
        "cases": len(cases),
        "mismatches": mismatches,
        "sha256": _digest(payloads),
        "z6uka_case_names": [name for name, _graph in _z6uka_graphs()],
        "has_native_gates": {
            "graph": hasattr(fnx.Graph(), "_native_has_adj_py_keys"),
            "digraph_succ": hasattr(fnx.DiGraph(), "_native_has_succ_py_keys"),
            "digraph_pred": hasattr(fnx.DiGraph(), "_native_has_pred_py_keys"),
        },
    }


def bench(converter_name, directed=False, repeat=25, n=700):
    converter = _converter(converter_name)
    graph = _dense_graph(n, directed=directed)
    samples = []
    for _ in range(repeat):
        start = time.perf_counter()
        h = converter(graph)
        samples.append(time.perf_counter() - start)
        if h.number_of_nodes() != graph.number_of_nodes():
            raise AssertionError("node count changed")
    return {
        "converter": converter_name,
        "directed": directed,
        "repeat": repeat,
        "n": n,
        "mean": statistics.fmean(samples),
        "median": statistics.median(samples),
        "best": min(samples),
        "worst": max(samples),
        "samples": samples,
    }


def profile(converter_name, directed=False, repeat=20, n=700):
    converter = _converter(converter_name)
    graph = _dense_graph(n, directed=directed)
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(repeat):
        converter(graph)
    profiler.disable()
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats("cumtime")
    stats.print_stats(25)
    return stream.getvalue()


def planarity(converter_name, repeat=10, n=700):
    converter = _converter(converter_name)
    graph = _dense_graph(n, directed=False)
    original = backend._fnx_to_nx
    backend._fnx_to_nx = converter
    try:
        samples = []
        for _ in range(repeat):
            start = time.perf_counter()
            result = fnx.check_planarity(graph)[0]
            samples.append(time.perf_counter() - start)
            if result is not False:
                raise AssertionError("dense witness should be non-planar")
    finally:
        backend._fnx_to_nx = original
    return {
        "converter": converter_name,
        "repeat": repeat,
        "n": n,
        "mean": statistics.fmean(samples),
        "median": statistics.median(samples),
        "best": min(samples),
        "worst": max(samples),
        "samples": samples,
    }


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    bench_p = sub.add_parser("bench")
    bench_p.add_argument("converter", choices=["old", "new"])
    bench_p.add_argument("--directed", action="store_true")
    bench_p.add_argument("--repeat", type=int, default=25)
    bench_p.add_argument("--n", type=int, default=700)

    prof_p = sub.add_parser("profile")
    prof_p.add_argument("converter", choices=["old", "new"])
    prof_p.add_argument("--directed", action="store_true")
    prof_p.add_argument("--repeat", type=int, default=20)
    prof_p.add_argument("--n", type=int, default=700)

    planarity_p = sub.add_parser("planarity")
    planarity_p.add_argument("converter", choices=["old", "new"])
    planarity_p.add_argument("--repeat", type=int, default=10)
    planarity_p.add_argument("--n", type=int, default=700)

    sub.add_parser("proof")

    args = parser.parse_args()
    if args.cmd == "bench":
        print(json.dumps(bench(args.converter, args.directed, args.repeat, args.n), indent=2))
    elif args.cmd == "profile":
        print(profile(args.converter, args.directed, args.repeat, args.n))
    elif args.cmd == "planarity":
        print(json.dumps(planarity(args.converter, args.repeat, args.n), indent=2))
    elif args.cmd == "proof":
        print(json.dumps(proof(), indent=2))


if __name__ == "__main__":
    main()
