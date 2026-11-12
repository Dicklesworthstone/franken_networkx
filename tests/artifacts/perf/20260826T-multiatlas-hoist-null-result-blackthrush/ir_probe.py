"""Instruction-count probe for one arm, one op, one repetition count.

Wall-clock on this host is unusable today (peer criterion benchmarks hold ~55-80
cores; control rows moved 0.598x-2.685x under a change that cannot touch them).
Instruction counts are deterministic and load-independent, which is exactly the
"counted mechanism" the ledger contract accepts in place of a timing gate.

Setup cost -- interpreter start, the ~3.3e9-Ir import, fixture construction --
is identical across arms but large, so it is CANCELLED rather than estimated:
this script is run at two repetition counts and Ir-per-call is the SLOPE,
(Ir(N2) - Ir(N1)) / (N2 - N1). Anything that does not scale with N drops out.

usage: FNX_OP=multi_adj FNX_N=20000 valgrind --tool=callgrind python ir_probe.py
"""
import os
import random
import sys

import networkx as nx  # noqa: F401  (asserts the incumbent is importable)
import franken_networkx as fnx

OP = os.environ.get("FNX_OP", "multi_adj")
N = int(os.environ.get("FNX_N", "20000"))

CLS = {
    "multi_adj": "MultiGraph",
    "multidi_adj": "MultiDiGraph",
    "graph_adj": "Graph",
    "digraph_adj": "DiGraph",
}[OP]

rng = random.Random(7)
seen, stream = set(), []
while len(stream) < 4000:
    u, v = rng.randrange(1000), rng.randrange(1000)
    if u == v or (min(u, v), max(u, v)) in seen:
        continue
    seen.add((min(u, v), max(u, v)))
    stream.append((u, v))

G = getattr(fnx, CLS)()
G.add_nodes_from(range(1000))
G.add_edges_from([(u, v, {"weight": 1}) for u, v in stream])

adj = G.adj
pairs = stream[:256]
# Warm every cell once so the measured loop is the STEADY STATE, not first-touch.
for u, v in pairs:
    adj[u][v]

sink = 0
for i in range(N):
    u, v = pairs[i & 255]
    cell = adj[u][v]
    sink += 1

print(f"op={OP} cls={CLS} N={N} sink={sink}", file=sys.stderr)
