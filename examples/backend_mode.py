#!/usr/bin/env python3
"""NetworkX backend dispatch example."""

from __future__ import annotations

import json

import networkx as nx


def main() -> int:
    nx.config.backend_priority = ["franken_networkx"]
    nx.config.warnings_to_ignore.add("cache")

    path_graph = nx.path_graph(8)
    cycle_graph = nx.cycle_graph(6)

    path = nx.shortest_path(path_graph, 0, 7, backend="franken_networkx")
    pagerank = nx.pagerank(cycle_graph, backend="franken_networkx")
    components = [sorted(component) for component in nx.connected_components(path_graph, backend="franken_networkx")]

    if path != list(range(8)):
        raise RuntimeError(f"unexpected backend shortest path: {path}")
    if len(components) != 1:
        raise RuntimeError(f"unexpected backend component count: {components}")
    if abs(sum(pagerank.values()) - 1.0) >= 1e-9:
        raise RuntimeError("backend pagerank scores must sum to 1")

    print(
        json.dumps(
            {
                "path": path,
                "component_count": len(components),
                "pagerank_nodes": len(pagerank),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
