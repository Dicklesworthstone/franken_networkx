"""vs-incumbent Ir for the br-r37-c1-predrow-8vytj table.

The bead's four rows are a self-contained control design: DiGraph.predecessors was
0.383x while the SAME class's successors (0.819x) and the OTHER class's predecessors
(0.775x) were both about twice as fast, which is what localised the cost to that one
binding rather than to predecessors or to directedness.

Reproduced here in instructions rather than nanoseconds because host_quiet_check has
refused this host continuously and no wall-clock row is admissible. Whole program, so
the fnx and nx arms have the SAME scope (Python frame included); pools pinned, since an
OpenBLAS spin thread reached via networkx -> scipy otherwise contributes wall-time
dependent counts; slope over two rep counts, so the fixture build is not charged per
call.

Keys are REUSED objects, matching the bead's own probe shape (build from a name list,
then index with that list). That choice is load-bearing for key-length questions - see
the fresh-vs-reused axis - but these rows are all at one short key length, where the two
shapes agree.
"""

import os
import sys

import networkx as nx

REPS = int(os.environ.get("IR_REPS", "4000"))
CLS = os.environ.get("FNX_CLS", "DiGraph")
OP = os.environ.get("FNX_OP", "predecessors")
EDGES = int(os.environ.get("FNX_E", "400"))

if os.environ.get("FNX_MOD", "fnx") == "nx":
    mod = nx
else:
    import franken_networkx as mod

NODES = EDGES // 4
names = [f"n{i}" for i in range(NODES)]
g = getattr(mod, CLS)()
g.add_nodes_from(names)
for i in range(NODES):
    for d in (1, 2, 3, 4):
        g.add_edge(names[i], names[(i + d) % NODES])

fn = getattr(g, OP)
probe = [names[i % NODES] for i in range(REPS)]
print(f"mod {mod.__name__} cls {CLS} op {OP} reps {REPS} edges {g.number_of_edges()}", file=sys.stderr)

total = 0
for n in probe:
    total += len(list(fn(n)))
print(f"visited {total}", file=sys.stderr)
assert total == REPS * 4, f"degree not constant: {total} != {REPS * 4}"
