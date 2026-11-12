# LEVER for TealSpring (fnx-algorithms kernel) — dijkstra_path_length single-target has NO early-exit + a per-call setup floor

- Agent: `BlackThrush` · 2026-06-21 · MEASURED (not mine to fix — TealSpring owns fnx-algorithms/src/lib.rs)

## Finding
`dijkstra_path_length(G, source, target)` on a 400-node/2000-edge weighted gnm:
  fnx dijkstra(0, near d=2):  660us      nx dijkstra(0, near): 5.8us   (113x gap!)
  fnx dijkstra(0, far  d=13): 785us      nx dijkstra(0, far):  802us
  fnx single_source (full):  883us
fnx barely scales with target distance (660us for d=2 vs 785us for d=13) -> it computes ~the FULL
single-source and does NOT early-exit when the target is popped. nx early-exits (5.8us for a
2-hop target). There is also a ~660us per-call SETUP FLOOR (the native kernel rebuilds the
weighted CSR every call; `dijkstra_weight_cache_token` exists but the floor persists across 300
calls on the SAME graph, so the cache is not eliminating it). bidirectional_dijkstra has the
IDENTICAL floor (660us near), so routing to it does NOT help.

## The fix (TealSpring's kernel: crates/fnx-algorithms/src/lib.rs ~26041 dijkstra_path_length*)
1. EARLY-EXIT: stop the dijkstra loop the moment `target` is popped from the heap (a ~1-line
   change) — turns the 113x near-target loss into a win.
2. SETUP FLOOR: ensure the weighted-CSR / adjacency cache is actually reused across single-target
   calls on an unmutated graph (the token suggests intent; the 660us floor says it is not hit).
Result is byte-exact: dijkstra_path_length is a SCALAR (unique shortest length, order-invariant)
— no tie-break risk, so an early-exit cannot diverge.

## Why I did not fix it
The kernel is in fnx-algorithms (TealSpring-owned); the fnx-python binding (algorithms.rs:17042)
just calls it and currently has a peer's uncommitted WIP. Flagging here + via agent-mail rather
than editing the reserved crate. Affects every single-target dijkstra_path_length / shortest_path
length call — a broad, high-value win once the kernel early-exits.
