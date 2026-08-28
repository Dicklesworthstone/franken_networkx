"""minimum_branching: the published fixture is EMPTY-EDGE; measure the real one too.

br-r37-c1-p80x1.14. The README publishes minimum_branching at 3.9768x. The recovered
fixture behind it is n=800, m=4000, weights 1..20 - and the bead records that it "returns
800 nodes and zero edges". That is not incidental: a minimum branching over ALL-POSITIVE
weights is empty by definition, because selecting no edge costs 0 and every edge adds cost.
So the published row times an algorithm that returns an empty graph.

The bead says so itself: "This exact row may only support the empty-edge workload. Any
claim about a non-empty minimum branching needs a separately preregistered fixture with at
least one selected edge and its own complete parity and timing evidence."

FNX_NEG=1 selects that fixture - identical shape, weights negated, so the branching
actually selects edges.

Whole program, pools pinned, slope over two rep counts.
"""

import os
import random
import sys

import networkx as nx

REPS = int(os.environ.get("IR_REPS", "2"))
N = int(os.environ.get("FNX_N", "400"))
NEG = os.environ.get("FNX_NEG") == "1"

if os.environ.get("FNX_MOD", "fnx") == "nx":
    mod = nx
else:
    import franken_networkx as mod

rng = random.Random(11)
# FNX_UNDIR=1 builds the same shape as an undirected Graph. networkx accepts one and
# returns an (also empty, for positive weights) result, so the two classes are directly
# comparable - and the census found them landing on opposite sides of 1.0x.
g = mod.Graph() if os.environ.get("FNX_UNDIR") == "1" else mod.DiGraph()
g.add_nodes_from(range(N))
for i in range(N):
    for _ in range(5):
        j = rng.randrange(N)
        if i != j:
            w = rng.randint(1, 20)
            g.add_edge(i, j, weight=float(-w if NEG else w))

print(f"mod {mod.__name__} N {N} neg {NEG} reps {REPS} edges {g.number_of_edges()}", file=sys.stderr)
out = None
for _ in range(REPS):
    out = mod.minimum_branching(g)
print(f"result nodes {out.number_of_nodes()} edges {out.number_of_edges()}", file=sys.stderr)
