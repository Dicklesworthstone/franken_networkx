"""Key-length slope of DiGraph.neighbors, in instructions (br-r37-c1-sznaj).

The bead's own instrument is the K=2 vs K=2000 slope: Graph/MultiGraph/MultiDiGraph
are FLAT in node-key length and DiGraph was SLOPED, which localises the cost to the
canonicalisation on this one path rather than to row construction.

Measured here in Ir instead of ns so it is decidable at any host load. Toggle on
'*PyDiGraph>::successors*', the kernel `neighbors` delegates to.

FNX_K   node-key byte length
IR_REPS neighbors() calls; run at two values and take the slope, since building the
        fixture also enters this kernel and would otherwise be charged per-call.
"""

import hashlib
import os
import sys

import franken_networkx as fnx
import franken_networkx._fnx as ext

# FNX_MOD=nx runs the INCUMBENT through the identical probe. networkx has no Rust
# symbol to toggle on, so the fnx-vs-nx comparison is made on WHOLE-PROGRAM Ir with
# the slope over two rep counts isolating the per-call cost - the same scope for
# both, including the interpreter frame, which is what the bead's ns table measured.
MOD = os.environ.get("FNX_MOD", "fnx")
if MOD == "nx":
    import networkx as fnx

K = int(os.environ.get("FNX_K", "2"))
REPS = int(os.environ.get("IR_REPS", "2000"))
NODES = int(os.environ.get("FNX_NODES", "200"))
DEG = 4

# Keys of the requested BYTE length, made distinct by a fixed-width base-36 PREFIX
# so the distinguishing bytes sit at the same offset for every K. A naive
# f"{i:02d}"[:K] collides (10 and 100 both shorten to "10"); the distinctness
# assert below caught that and the K=2 arm collected nothing until it was fixed.
ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"


def _b36(n, width):
    out = []
    while n:
        n, r = divmod(n, 36)
        out.append(ALPHABET[r])
    return "".join(reversed(out)).rjust(width, "0")


_width = 1
while 36**_width < NODES:
    _width += 1
assert K >= _width, f"K={K} too small to hold {NODES} distinct keys"
names = [(_b36(i, _width) + "x" * K)[:K] for i in range(NODES)]
assert len({len(n) for n in names}) == 1, "all keys must share one length"
assert len(set(names)) == NODES, "keys must be distinct"

g = fnx.DiGraph()
g.add_nodes_from(names)
for i, n in enumerate(names):
    for d in range(1, DEG + 1):
        g.add_edge(n, names[(i + d) % NODES])

with open(ext.__file__, "rb") as fh:
    print(f"elf_sha256 {hashlib.sha256(fh.read()).hexdigest()[:16]}", file=sys.stderr)
print(f"mod {MOD} K {len(names[0])} REPS {REPS} nodes {NODES}", file=sys.stderr)

nbr = g.neighbors
# FNX_FRESH=1 passes keys that are EQUAL but not IDENTICAL to the ones the graph
# was built from. Reusing the same str objects lets any object-keyed lookaside hit
# on pointer identity and lets CPython settle dict equality by identity, so the
# byte length never has to be looked at - a probe that reuses them cannot see a
# key-length slope even if one exists. Fresh copies are what an ordinary caller
# supplies (a key read from a file, built by str.format, or returned by another
# library). Built outside the timed region; the toggle counts only what runs
# inside the pymethod.
if os.environ.get("FNX_FRESH") == "1":
    probe = ["".join(names[i % NODES]) for i in range(REPS)]
    assert all(p is not n for p, n in zip(probe, [names[i % NODES] for i in range(REPS)]))
else:
    probe = [names[i % NODES] for i in range(REPS)]
total = 0
for n in probe:
    total += len(list(nbr(n)))
print(f"visited {total}", file=sys.stderr)
assert total == REPS * DEG, f"degree not constant: {total} != {REPS * DEG}"
