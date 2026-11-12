"""Toggle-collect Ir probe for `(u,v) in G.edges()`.

Fixture is byte-identical to scripts/balanced_square_ab.py::workload_view_reads
(2000 nodes / 8000 edges, seed 11, probe sequence seed 7) so the Ir breakdown
attributes the SAME work the live A/B row times.

Run under:
  valgrind --tool=callgrind --collect-atstart=no \
    --toggle-collect='*EdgeView*__pymethod___contains____*' \
    python ir_probe_edges_contains.py

IR_REPS controls the loop; run it at two values and require per-call Ir to be
flat, which is what proves the toggle really bounds the collected extent.
"""

import hashlib
import os
import random
import sys

import franken_networkx as fnx
import franken_networkx._fnx as ext

REPS = int(os.environ.get("IR_REPS", "20000"))


def build(module, nodes=2000, edges=8000, seed=11):
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
    return graph, (names, [(names[a], names[b]) for a, b in seen])


graph, (names, edges) = build(fnx)
rng = random.Random(7)
probe_edges = [edges[rng.randrange(len(edges))] for _ in range(REPS)]
edgeview = graph.edges

with open(ext.__file__, "rb") as fh:
    elf_sha = hashlib.sha256(fh.read()).hexdigest()
print(f"elf_sha256 {elf_sha}", file=sys.stderr)
print(f"IR_REPS {REPS}", file=sys.stderr)

hits = 0
for p in probe_edges:
    if p in edgeview:
        hits += 1
print(f"hits {hits}", file=sys.stderr)
assert hits == REPS, "probe must be all-hits, matching the live A/B row"
