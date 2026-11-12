"""Whole-program Ir SLOPE for `(u,v) in G.edges()`, either library.

Run the identical probe at two rep counts under plain callgrind (no toggle) and
take the slope: (Ir_2 - Ir_1) / (reps_2 - reps_1). The fixed cost — interpreter
startup, module import, fixture build — is identical in both runs and cancels,
so the slope is per-probe instructions with no toggle and no symbol assumptions.
That makes it directly comparable BETWEEN libraries, which a toggle-collect on
a Rust pymethod cannot be (networkx has no such symbol).

  LIB=networkx|franken_networkx IR_REPS=N python ir_slope_edges_contains.py
"""

import os
import random
import sys

LIB = os.environ.get("LIB", "franken_networkx")
REPS = int(os.environ.get("IR_REPS", "20000"))

if LIB == "networkx":
    import networkx as module
else:
    import franken_networkx as module


def build(nodes=2000, edges=8000, seed=11):
    rng = random.Random(seed)
    graph = module.Graph()
    names = [f"n{i}" for i in range(nodes)]
    graph.add_nodes_from((n, {"color": "r", "rank": i}) for i, n in enumerate(names))
    seen = set()
    while len(seen) < edges:
        a, b = rng.randrange(nodes), rng.randrange(nodes)
        if a == b:
            continue
        pair = (min(a, b), max(a, b))
        if pair in seen:
            continue
        seen.add(pair)
        graph.add_edge(names[pair[0]], names[pair[1]], weight=1.0)
    return graph, [(names[a], names[b]) for a, b in seen]


graph, edges = build()
rng = random.Random(7)
probe_edges = [edges[rng.randrange(len(edges))] for _ in range(REPS)]
edgeview = graph.edges

print(f"lib {LIB} reps {REPS}", file=sys.stderr)
if os.environ.get("NO_PROBE"):
    # Control arm: the same per-rep list build and generator loop WITHOUT the
    # membership test, so its slope is the harness cost both libraries share.
    hits = sum(1 for p in probe_edges if p is not None)
else:
    hits = sum(1 for p in probe_edges if p in edgeview)
assert hits == REPS, "probe must be all-hits"
