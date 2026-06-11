# br-r37-c1-hf29q — junction_tree in-process de-delegation (1.6-1.7x vs nx)

## Problem
`fnx.junction_tree` delegated via `_call_networkx_for_parity`, so it ran nx's
pure-Python `complete_to_chordal_graph` (~6.5s at n=500) + `chordal_graph_cliques`
(~2.2s) on the converted graph — ~8.9s, at parity with nx (no win).

## Lever
Run nx's exact junction-tree algorithm **in-process**, swapping the dominant
chordal-completion step for fnx's native `complete_to_chordal_graph`, which is
**byte-identical to nx** (same fill edges) but ~2.1x faster (6.5s → 3.1s). The
chordal graph is then handed to nx's exact `chordal_graph_cliques` +
`maximum_spanning_tree` over the clique graph, so the junction tree is
byte-identical (node/edge/type) to nx.

Subtlety: fnx's *native* `chordal_graph_cliques` yields the same clique SET but a
different ORDER, which changes the maximum-spanning-tree tie-breaks → a different
(still valid) junction tree. junction_tree is deterministic and the test asserts
exact node/edge/type match, so the clique ORDER is taken from nx's
`chordal_graph_cliques` on the (byte-identical) converted chordal graph — which
reproduces nx's order exactly (verified 40/40).

## Result (connected_watts_strogatz)
| n   | in-proc | genuine nx | speedup |
|-----|---------|------------|---------|
| 400 | 3.10 s  | 5.28 s     | 1.70x   |
| 500 | 5.49 s  | 8.90 s     | 1.62x   |

Multi-second absolute savings (2-3.4s/call); junction trees / tree decompositions
on real (graphical-model) graphs scale larger.

## Proof
- Byte-exact (sorted nodes+type, sorted edges) vs genuine nx: **270/270 cases**,
  0 fails (50 seeds × 5 sizes undirected + 20 directed); empty graph matches.
- `tests/python test_tree_kcomponents_assortativity_conformance.py -k junction
  or join_trees`: 2 passed.
