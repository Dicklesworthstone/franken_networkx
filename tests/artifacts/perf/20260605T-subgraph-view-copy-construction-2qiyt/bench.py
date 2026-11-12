from __future__ import annotations

import json
import statistics
import sys
import time

import franken_networkx as fnx
import networkx as nx


def _legacy_copy_induced_simple_fast(self):
    if (
        self.is_multigraph()
        or not self._filter_edge_is_default
        or type(self._graph) not in (fnx.Graph, fnx.DiGraph)
    ):
        return None
    raw_neighbors = fnx._raw_neighbors_dispatch(self._graph)
    if raw_neighbors is None:
        return None

    nodes = list(self)
    node_set = set(nodes)
    result = self._copy_type()()
    result.graph.update(dict(self.graph))
    result.add_nodes_from(
        (node, dict(fnx._node_attrs_for_view_graph(self._graph, node)))
        for node in nodes
    )

    edge_rows = []
    get_edge_data = self._graph.get_edge_data
    if self.is_directed():
        for source in nodes:
            for target in raw_neighbors(self._graph, source):
                if target in node_set:
                    edge_rows.append((source, target, dict(get_edge_data(source, target))))
    else:
        seen = set()
        for source in nodes:
            for target in raw_neighbors(self._graph, source):
                if target in seen or target not in node_set:
                    continue
                edge_rows.append((source, target, dict(get_edge_data(source, target))))
            seen.add(source)
    result.add_edges_from(edge_rows)
    return result


def _build(module, n: int, extra_edges: int):
    graph = module.Graph()
    graph.add_nodes_from(range(n))
    graph.add_edges_from((i, i + 1) for i in range(n - 1))
    for i in range(extra_edges):
        u = (i * 37 + 11) % n
        v = (i * 53 + 97) % n
        if u != v:
            graph.add_edge(u, v, weight=i % 7)
    return graph


def _time_copy(module, n: int, keep_size: int, extra_edges: int, copies: int):
    graph = _build(module, n, extra_edges)
    keep = [(i * 41 + 7) % n for i in range(keep_size)]
    for _ in range(3):
        graph.subgraph(keep).copy()
    samples = []
    edge_count = None
    node_order = None
    for _ in range(9):
        start = time.perf_counter()
        for _ in range(copies):
            copied = graph.subgraph(keep).copy()
        elapsed = time.perf_counter() - start
        samples.append(elapsed)
        edge_count = copied.number_of_edges()
        node_order = list(copied.nodes())[:12]
    return {
        "module": module.__name__,
        "n": n,
        "keep_size": keep_size,
        "extra_edges": extra_edges,
        "copies": copies,
        "min_s": min(samples),
        "median_s": statistics.median(samples),
        "p95_s": sorted(samples)[int(len(samples) * 0.95) - 1],
        "edge_count": edge_count,
        "node_order_head": node_order,
    }


def main() -> None:
    args = list(sys.argv[1:])
    module_name = "both"
    if "--legacy-node-attrs-fnx" in args:
        args.remove("--legacy-node-attrs-fnx")
        fnx._FilteredGraphView._copy_induced_simple_fast = (
            _legacy_copy_induced_simple_fast
        )
    if "--module" in args:
        index = args.index("--module")
        module_name = args[index + 1]
        del args[index : index + 2]
    n = int(args[0]) if len(args) > 0 else 2000
    keep_size = int(args[1]) if len(args) > 1 else 50
    extra_edges = int(args[2]) if len(args) > 2 else 8000
    copies = int(args[3]) if len(args) > 3 else 20
    modules = {"nx": nx, "fnx": fnx}
    selected = [nx, fnx] if module_name == "both" else [modules[module_name]]
    print(
        json.dumps(
            [_time_copy(module, n, keep_size, extra_edges, copies) for module in selected],
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
