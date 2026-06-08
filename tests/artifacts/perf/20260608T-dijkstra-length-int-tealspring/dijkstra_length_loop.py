import hashlib
import json
import random
import sys

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


def digest(result):
    rows = [[repr(node), type(distance).__name__, distance] for node, distance in result.items()]
    payload = json.dumps(rows, sort_keys=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def main():
    mode = sys.argv[1]
    repeat = int(sys.argv[2])
    gf, gn = build_graphs()
    checksum = 0
    sha256 = None
    for _ in range(repeat):
        if mode == "old":
            result, _ = fnx.single_source_dijkstra(gf, 0, weight="weight")
        elif mode == "new":
            result = fnx.single_source_dijkstra_path_length(gf, 0, weight="weight")
        elif mode == "raw":
            result = fnx._raw_single_source_dijkstra_path_length(gf, 0, weight="weight")
        elif mode == "nx":
            result = nx.single_source_dijkstra_path_length(gn, 0, weight="weight")
        else:
            raise SystemExit("usage: dijkstra_length_loop.py old|new|raw|nx repeat")
        result = dict(result)
        checksum += len(result)
        sha256 = digest(result)
    print(json.dumps({"mode": mode, "repeat": repeat, "checksum": checksum, "sha256": sha256}))


if __name__ == "__main__":
    main()
