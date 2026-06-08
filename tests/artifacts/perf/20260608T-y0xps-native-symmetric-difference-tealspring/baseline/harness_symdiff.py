import sys

import franken_networkx as fnx
import networkx as nx

N = 1800
PARALLEL = 3
LIB = fnx if sys.argv[1] == "fnx" else nx
CLS = getattr(LIB, sys.argv[2])
REPS = int(sys.argv[3])


def build_pair():
    g = CLS()
    h = CLS()
    g.add_nodes_from(range(N))
    h.add_nodes_from(range(N))
    for u in range(N - 1):
        v = u + 1
        for k in range(PARALLEL):
            g.add_edge(u, v, key=k)
            if (u + k) % 4 == 0:
                h.add_edge(u, v, key=k)
    return g, h


g, h = build_pair()
for _ in range(REPS):
    r = LIB.symmetric_difference(g, h)
    if r.number_of_edges() != 4048:
        raise SystemExit(1)
