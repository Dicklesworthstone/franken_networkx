import hashlib
import json
import random
import sys

import franken_networkx as fnx


def build_graph():
    rnd = random.Random(1)
    edges = [(rnd.randrange(3000), rnd.randrange(3000)) for _ in range(12000)]
    graph = fnx.Graph()
    for u, v in edges:
        if u != v:
            graph.add_edge(u, v, weight=1 + (u % 5))
    return graph


def digest(result):
    rows = [[repr(node), type(distance).__name__, distance] for node, distance in result.items()]
    payload = json.dumps(rows, sort_keys=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def main():
    graph = build_graph()
    result = dict(fnx.single_source_dijkstra_path_length(graph, 0, weight="weight"))
    print(json.dumps({"len": len(result), "sha256": digest(result)}))


if __name__ == "__main__":
    if len(sys.argv) != 1:
        raise SystemExit("usage: dijkstra_length_once.py")
    main()
