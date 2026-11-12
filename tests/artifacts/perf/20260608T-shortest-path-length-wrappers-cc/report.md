# dijkstra_path_length + bellman_ford_path_length: drop redundant/stale recompute (br-r37-c1-djkpathlen2x / br-r37-c1-bfpathnative)

## dijkstra_path_length — removed a redundant 2nd Dijkstra
Ran the native Dijkstra TWICE: `_raw_dijkstra_path_length` (result DISCARDED, used
only as the no-path probe) then the public `dijkstra_path` wrapper (which
re-coerces, re-runs the delegation scan, re-hashes, re-checks node membership) —
then summed the path. Now calls `_raw_dijkstra_path` directly once (every guard
already ran) and sums. NOISE-INVARIANT proof: interleaved `dijkstra_path_length`
vs `dijkstra_path` is now 1.00x (was ~2x) — i.e. it does exactly one Dijkstra.

## bellman_ford_path_length — routed off the stale nx delegation
Delegated to nx unconditionally (full fnx->nx conversion + nx Bellman-Ford) under
the stale "Rust returns incorrect paths/lengths" note. The native single-pair
kernel is path-correct (see bellman_ford_path: 240 pairs 0 mismatch). Now computes
the path natively and sums it, with the wrapper owning nx's error contract
(NodeNotFound / NetworkXNoPath "node ... not reachable from ..." / NetworkXUnbounded
/ source==target -> 0; callable/NaN/inf/non-numeric weight delegate, negatives
allowed). Eliminates the O(V+E) conversion every call.

## Proof (behavior parity — absolute)
- 1028 calls across both functions (directed/undirected/multigraph, int + float
  weights for length-type preservation, negative weights, all error cases,
  unhashable nodes): 0 mismatches on value, value-type, and error type+message.
- `pytest -k "bellman or dijkstra"`: 718 passed.

## Perf note (host-noise caveat)
Measured during host load average ~15 (swarm saturation), which inflates fnx's
native-extension calls relative to nx's in-interpreter Python and makes a clean
steady-state vs-nx ratio unobtainable this window. The wins are STRUCTURAL and
load-independent: dijkstra_path_length now does ONE Dijkstra not two (verified
1.00x vs dijkstra_path, noise-invariant); bellman_ford_path_length drops the
per-call fnx->nx conversion. On a lighter-load window earlier this session the
identical bellman single-pair kernel (bellman_ford_path) measured 2.1-2.2x faster
than nx, and dijkstra_path measured 0.37-0.59x (faster).
