"""G.has_node: verify the published 0.41x LOSS (br-r37-c1-p80x1).

The README publishes has_node at 0.41x, and the claim-coverage audit lists it among three
published LOSSES that are "still unverified numbers". Two later beads disagree with each
other about it: br-r37-c1-fov4a records "has_node 0.5114x to 0.7701x and STILL A LOSS",
while br-r37-c1-native-method-attribute-lookup-tax-w7wjs concludes "has_edge/has_node/
neighbors are at parity or better once measured honestly". This measures it.

The accessor is a few hundred instructions, so the loop and the attribute lookup would
dominate a naive probe. The method is BOUND ONCE outside the loop and the probe list is
built outside the loop, so the slope over two rep counts isolates the call itself.

FNX_KEY=str|int selects the node-key type - br-r37-c1-node_key_type_is_a_measured_axis
records that as a real fnx axis (+38-53%) while networkx is flat, so a single key type
would measure the better half.
FNX_MISS=1 probes ABSENT keys, where networkx raises and catches internally.
"""

import os
import sys

import networkx as nx

REPS = int(os.environ.get("IR_REPS", "200000"))
N = int(os.environ.get("FNX_N", "2000"))
KEY = os.environ.get("FNX_KEY", "str")
MISS = os.environ.get("FNX_MISS") == "1"

if os.environ.get("FNX_MOD", "fnx") == "nx":
    mod = nx
else:
    import franken_networkx as mod

names = [f"n{i}" for i in range(N)] if KEY == "str" else list(range(N))
g = mod.Graph()
g.add_nodes_from(names)
for i in range(0, N - 1, 2):
    g.add_edge(names[i], names[i + 1])

if MISS:
    probe = [f"zz{i}" for i in range(N)] if KEY == "str" else [-(i + 1) for i in range(N)]
else:
    probe = names

has_node = g.has_node  # bound once: the attribute lookup is not what is under test
# The probe list is a FIXED size and is iterated REPS//len(probe) times. Building a
# REPS-long list here would scale the INPUT CONSTRUCTION with the rep count, so it would
# land in the slope and dominate it - that inflated a first run of this probe to ~3100
# Ir/call for what is a dict lookup.
rounds = max(1, REPS // len(probe))

print(f"mod {mod.__name__} key {KEY} miss {MISS} reps {REPS} n {N}", file=sys.stderr)
hits = 0
for _ in range(rounds):
    for k in probe:
        if has_node(k):
            hits += 1
print(f"hits {hits}", file=sys.stderr)
assert hits == (0 if MISS else rounds * len(probe)), f"probe class impure: {hits}"
