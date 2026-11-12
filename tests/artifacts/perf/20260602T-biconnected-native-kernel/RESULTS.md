# biconnected_components — fix native low-link bug, drop nx delegation (br-r37-c1-bccdisc)

## Problem
`biconnected_components(G)` was **4.73x SLOWER than NetworkX** (14.5ms vs 3.07ms
@ N=1500 BA m=3) because the Python wrapper delegated to nx: it converted the
fnx graph to a full networkx graph (`_call_networkx_for_parity`) and then ran
nx's pure-Python DFS. The delegation existed because the native Rust kernel
mis-split at articulation points (the "bowtie": two triangles sharing one
vertex returned ONE merged component instead of nx's two).

## Root cause (one-line low-link bug)
The Rust edge-stack DFS folded back edges into the low-link using `low[w]`
instead of `discovery[w]`. nx's `_biconnected_dfs` does
`low[parent] = min(low[parent], discovery[child])`. On the bowtie the shared
articulation vertex carries `low < disc` (it has its own back edge), so using
`low[w]` propagated a too-deep ancestor and defeated the `low >= disc[parent]`
component-split test, merging two biconnected components.

## Lever (one change in crates/fnx-algorithms/src/lib.rs)
`let w_low = low[w];` -> `let w_disc = discovery[w];` in the back-edge branch of
`biconnected_component_edges`. Then drop the nx delegation in the Python wrapper
and route to the fixed native kernel `_raw_biconnected_components`.

## Behavior parity (absolute)
Native kernel output is byte-identical to the prior nx-delegation path — node-set
components AND component sequence order — verified:
- 400 random graphs (gnp / BA / trees / triangle-chains / WS) native-vs-delegation:
  set_fail=0, seq_fail=0
- 500 graphs fnx-vs-nx (built on identical adjacency ordering): 500/500 exact match
- corners: empty / single node / no-edge / self-loop / one-edge all match
- 262 existing biconnected/articulation tests pass
GOLDEN_SHA256 = 584d28cc33893faf0cba67ab85e0e99474723d60086936acdb2c91c7423751a2

NOTE: comparing fnx output to nx run on a SEPARATELY-built nx graph can show
sequence differences — that is a graph-construction adjacency-order artifact
(fnx `add_edges_from` orders a node's neighbors differently than nx for some
inputs), NOT a biconnected bug. Both DFS faithfully follow their own graph's
adjacency. Parity is defined against nx running on fnx's adjacency (the
delegation path), which the native kernel matches exactly.

## Benchmark (p-min, BA m=3, generator fully materialized)
| N    | before (delegation) | after (native) | nx       | self-speedup |
|------|--------------------|-----------------|----------|--------------|
| 800  |             ~7 ms  |       1.44 ms   | 1.57 ms  |   ~5x        |
| 1500 |            14.5 ms |       2.87 ms   | 3.05 ms  |   5.06x      |
| 3000 |              —     |       6.24 ms   | 6.24 ms  |   —          |

Self-speedup @ N=1500: 14.5ms -> 2.87ms = **5.06x** (Score >= 2.0).
Gap closed: was 4.73x SLOWER than nx, now at parity / marginally faster.
