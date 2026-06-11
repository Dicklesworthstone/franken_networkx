# perf: lowest_common_ancestor / all_pairs_lowest_common_ancestor — lazy + native predecessor rows

Bead: br-r37-c1-aigcs. Single-pair LCA was 4.26x slower than nx (n=2000 gn_graph).

## Levers (one coherent change: how the ancestor BFS reads adjacency)
1. LAZY snapshots: old code eagerly built `{u: list(G.predecessors(u))}` and
   `{u: list(G.successors(u))}` for ALL n nodes on every call, so a single pair
   paid O(n) wrapper round-trips. Made both memoized-on-first-use.
2. NATIVE predecessor rows: residual was the AdjacencyView wrapper behind
   `G.predecessors(u)` (~8M per-call _private_override/vars checks over a full
   ancestor walk). For fnx DiGraphs read via `_native_predecessor_row_dict(u)`,
   which yields IDENTICAL key order (verified 0/500 mismatches) ~8x cheaper.
   nx-typed graphs fall back to the public API.

## Proof (byte-exact)
- Golden SHA over 968 records (single-pair + all-pairs APIs) across 4 DAG shapes
  (gn tree-DAG, oriented gnp, layered diamonds, binary-tree) UNCHANGED vs baseline
  and equal to nx every record: 22045c53913cbf2b11382e0c4ada1d27f0442aa054b62c5699b7df1b04272b1b
- Ancestor sets built with unchanged predecessor iteration order -> deterministic
  next(iter(common_ancestors)) selection preserved (the db0qr parity contract).
- Focused pytest (lowest_common/ancestor): 70 passed. all-pairs default (n=80) == nx.

## Benchmark (n=2000 gn_graph DAG, min-of-300)
| case            | nx (ms) | fnx before (ms) | fnx after (ms) | before vs nx | after vs nx |
|-----------------|---------|-----------------|----------------|--------------|-------------|
| single pair     | 1.50    | 6.38            | 1.05           | 4.26x slower | 1.42x faster|
| ten pairs       | 1.60    | 6.47            | 1.10           | 4.07x slower | 1.46x faster|

Self-speedup ~6.0x; 4.26x-slower -> 1.42x-faster than nx. Byte-exact. Pure-Python (no rebuild).
