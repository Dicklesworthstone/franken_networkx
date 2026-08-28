"""vs-incumbent Ir for the MultiDiGraph SSSP sibling spread (br-r37-c1-kacb2 handover).

The handover ranks these three sibling calls on ONE class as spanning 0.30x to 8.2x -
dijkstra_path 0.33x, bellman_ford_path_length 0.30x, dijkstra_path_length 8.2x - and
reads that spread as one spelling reaching a fast path its neighbours miss. Those were
explicitly SINGLE-RUN SCREENING numbers whose stated job was to rank targets, so this
re-measures them on HEAD before anything is acted on.

Instructions, not nanoseconds: host_quiet_check has refused this host all session. Whole
program so the fnx and nx arms share one scope, pools pinned (an OpenBLAS spin thread via
networkx -> scipy otherwise contributes wall-time-dependent counts), slope over two rep
counts so the fixture build is not charged per call.
"""

import os
import random
import sys

import networkx as nx

REPS = int(os.environ.get("IR_REPS", "10"))
N = int(os.environ.get("FNX_N", "800"))
OP = os.environ.get("FNX_OP", "dijkstra_path")

if os.environ.get("FNX_MOD", "fnx") == "nx":
    mod = nx
else:
    import franken_networkx as mod

rng = random.Random(7)
g = mod.MultiDiGraph()
for i in range(N):
    for d in (1, 2, 3):
        g.add_edge(f"n{i}", f"n{(i + d) % N}", weight=float(rng.randint(1, 9)))

src, dst = "n0", f"n{N // 2}"
# FNX_OP=collapse isolates ONE thing: the per-call multigraph->simple collapse that
# bellman_ford_path_length performs before recursing into the simple kernel. Its
# winning sibling dijkstra_path_length skips this entirely via a raw MultiDiGraph
# kernel, so this probe answers how much of the loss the collapse alone accounts for.
if OP == "collapse":
    _c = mod._multigraph_collapse_min_weight_bellman
    fn = lambda g, s, t, weight="weight": _c(g, weight)[0].number_of_edges()
elif OP == "precollapsed":
    # What a CACHE HIT would cost: do the collapse ONCE outside the timed loop, then
    # call the public wrapper on the resulting simple graph. This is the honest
    # measurement of a collapse cached against a revision token - the wrapper, the
    # simple kernel and everything else still run per call; only the collapse does not.
    g = mod._multigraph_collapse_min_weight_bellman(g, "weight")[0]
    fn = mod.bellman_ford_path_length
elif OP == "rawmg":
    # The native kernel applied DIRECTLY to the multigraph, skipping the collapse.
    # The source comment claims this native multigraph path is slow, which is why
    # the collapse exists; this arm measures that claim.
    fn = mod._raw_bellman_ford_path_length
else:
    fn = getattr(mod, OP)
print(f"mod {mod.__name__} op {OP} N {N} reps {REPS}", file=sys.stderr)

out = None
for _ in range(REPS):
    out = fn(g, src, dst, weight="weight")
print(f"result {out if not isinstance(out, list) else 'path len ' + str(len(out))}", file=sys.stderr)
