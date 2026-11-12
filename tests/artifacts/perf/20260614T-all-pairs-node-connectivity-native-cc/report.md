# Native approximation all_pairs_node_connectivity — delegated → 0.72–0.74x (beats nx)

Bead: br-r37-c1-qango
Agent: cc / 2026-06-14

## Problem

`fnx.approximation.all_pairs_node_connectivity` had no concrete method on
`_ApproximationNamespace`, so the generic `__getattr__` wrapper round-tripped the
graph through `_networkx_graph_for_parity` (fnx→nx) and then ran nx's O(V²)
White–Newman pairwise loop on nx views — every one of the V² local calls paying
AtlasView access. ~parity with nx (1.02x) but leaving the whole sweep on the slow
path.

## Fix (one-time native snapshot + pure-dict pairwise BFS)

Added a concrete `all_pairs_node_connectivity` method that snapshots the
adjacency ONCE via the native key binding (`_native_adjacency_keys`) into plain
Python `int→list` dicts, then runs every pair's bidirectional-BFS over those
dicts (`_approx_local_node_connectivity_dict` — the same helper introduced for
global `node_connectivity` in f7c5baba9). Pure-dict traversal beats nx's view
access, so the O(V²) sweep drops below nx.

- Mirrors nx exactly: `nbunch=None → list(adj)` (node order); else `list(set(
  nbunch))` (== nx's `set(nbunch)` iteration order); `combinations(nb, 2)`;
  `all_pairs[u][v]=all_pairs[v][u]=k`. Result dict key order is byte-identical.
- `cutoff` flows through to the local helper.
- Directed / multigraph / out-of-graph nbunch / non-native-storage delegate to nx
  (directed kept on nx's reference pairwise approximation).

## Proof

- 40-seed sweep × {full, random 5-node nbunch, cutoff=2} comparing the
  dict-of-dicts vs nx: **0 value mismatches AND 0 key-order mismatches** (golden
  `repr` matches nx exactly). Docstring cycle example matches.
- Golden (gnp 40,0.2,seed=7): `74c20bce0a6d951a…`, matches nx's repr exactly.
- Targeted (`-k 'connectivity or approximation'`): 557 passed. Full suite: only
  the known pre-existing failures.

## Timing (min-of-5)

| op | before (delegated) | after (fnx) | nx | now vs nx |
|----|--------------------|-------------|-----|-----------|
| all_pairs_node_connectivity (120,0.05) | ~221ms | 167ms | 234ms | **0.72x** |
| all_pairs_node_connectivity (180,0.04) | — | 625ms | 798ms | **0.74x** |

Pure-Python. Completes the approximation node-connectivity family
(local / node / all_pairs all native and at-or-beating nx).
