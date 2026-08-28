"""vs-incumbent Ir for effective_size (br-r37-c1-qbj9u).

The bead's lever is a native DIRECTED kernel. That kernel exists in the extension
(effective_size_directed_rust) but is NOT routed to: it diverged from networkx by
~0.2/node and was reverted in the verify phase, so directed graphs go through
_structural_holes_effective_size_matrix instead. Before fixing the kernel, this measures
whether that fallback is actually losing - a lever is only worth a Rust build if the path
it replaces is behind.

UNDIRECTED is the control: it already routes to the native effective_size_rust kernel, so
it shows what the directed case could look like.

FNX_CLS=DiGraph|Graph, FNX_MOD=fnx|nx. Whole program, pools pinned, slope over two rep
counts so the fixture build is not charged per call.
"""

import os
import random
import sys

import networkx as nx

REPS = int(os.environ.get("IR_REPS", "4"))
N = int(os.environ.get("FNX_N", "300"))
CLS = os.environ.get("FNX_CLS", "DiGraph")

if os.environ.get("FNX_MOD", "fnx") == "nx":
    mod = nx
else:
    import franken_networkx as mod

rng = random.Random(5)
g = getattr(mod, CLS)()
g.add_nodes_from(range(N))
for i in range(N):
    for _ in range(4):
        j = rng.randrange(N)
        if i != j:
            g.add_edge(i, j)

print(f"mod {mod.__name__} cls {CLS} N {N} reps {REPS} edges {g.number_of_edges()}", file=sys.stderr)
# FNX_NODES=sub passes an explicit node list, which is the case networkx serves from
# its redundancy LOOP (nodes=None instead takes a scipy matrix path that disagrees with
# that loop on ~83% of random digraphs). fnx currently DELEGATES this case to networkx.
_sub = list(range(0, N, 4)) if os.environ.get("FNX_NODES") == "sub" else None
out = None
for _ in range(REPS):
    _fn = getattr(mod, os.environ.get("FNX_FN", "effective_size"))
    out = _fn(g, nodes=_sub) if _sub is not None else _fn(g)
print(f"nodes {len(out)} sample {sorted(out.items())[0]}", file=sys.stderr)
