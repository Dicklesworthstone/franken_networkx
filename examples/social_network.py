#!/usr/bin/env python3
"""Social network analysis example."""

from __future__ import annotations

import json

import franken_networkx as fnx


def main() -> int:
    graph = fnx.karate_club_graph()
    leaders = sorted(fnx.pagerank(graph).items(), key=lambda item: item[1], reverse=True)[:5]
    communities = [sorted(group) for group in next(fnx.girvan_newman(graph))]

    if len(leaders) != 5:
        raise RuntimeError(f"unexpected leader set: {leaders}")
    if len(communities) < 2:
        raise RuntimeError(f"unexpected community split: {communities}")

    print(
        json.dumps(
            {
                "node_count": graph.number_of_nodes(),
                "edge_count": graph.number_of_edges(),
                "top_pagerank_nodes": leaders,
                "first_split_sizes": sorted(len(group) for group in communities),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
