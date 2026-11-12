#!/usr/bin/env python3
"""Standalone FrankenNetworkX usage example."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import franken_networkx as fnx


def main() -> int:
    graph = fnx.Graph()
    graph.add_edge("a", "b", weight=1.0)
    graph.add_edge("b", "c", weight=2.5)
    graph.add_edge("a", "c", weight=10.0)

    path = fnx.shortest_path(graph, "a", "c", weight="weight")
    pagerank = fnx.pagerank(graph)
    components = [sorted(component) for component in fnx.connected_components(graph)]

    payload = fnx.node_link_data(graph)
    restored = fnx.node_link_graph(payload)

    with tempfile.TemporaryDirectory() as tmpdir:
        edge_path = Path(tmpdir) / "graph.edgelist"
        fnx.write_edgelist(graph, edge_path)
        reloaded = fnx.read_edgelist(edge_path)
        reloaded_edges = reloaded.number_of_edges()

    if path != ["a", "b", "c"]:
        raise RuntimeError(f"unexpected shortest path: {path}")
    if len(components) != 1:
        raise RuntimeError(f"unexpected component count: {components}")
    if restored.number_of_edges() != graph.number_of_edges():
        raise RuntimeError("node-link roundtrip changed edge count")
    if reloaded_edges != graph.number_of_edges():
        raise RuntimeError("edgelist roundtrip changed edge count")

    print(
        json.dumps(
            {
                "path": path,
                "components": components,
                "pagerank_sum": round(sum(pagerank.values()), 6),
                "roundtrip_edges": restored.number_of_edges(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
