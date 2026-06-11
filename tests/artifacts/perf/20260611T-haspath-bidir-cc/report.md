# perf: has_path (directed) — integer-index bidirectional BFS

Bead vein: small-input / String-keyed-adjacency tax. Directed `has_path` used a
String-keyed `HashSet<&str>` one-directional BFS over the whole forward reachable
set, while undirected already used integer-index BFS. nx's `has_path` uses
`bidirectional_shortest_path` (meet-in-the-middle).

## Lever (ONE)
Replace `has_path_directed_fast` (fnx-algorithms/src/lib.rs) with an integer-index
**bidirectional** BFS using `successors_indices` / `predecessors_indices` and
`vec![false; n]` visited arrays. Expands the smaller frontier each round.

## Proof (byte-exact)
- Golden SHA over 3241 (s,t) pairs across 8 diverse directed graphs (gnp sparse/dense,
  gn DAG, scale-free, directed cycle/path, complete, disconnected): UNCHANGED.
- GOLDEN_SHA = a9cf60d7b61f486f71b0012ea0a14cfcb8a3789ea9ddce6819fad922326b1499
- has_path returns bool (reachability) → order-invariant; identical result every pair.
- Focused pytest (has_path/reachability/shortest_path): 1091 passed, 6 skipped.

## Benchmark (n=2000 directed gnp p=0.004, min-of-2000)
| pair      | nx (ms) | fnx before (ms) | fnx after (ms) | before vs nx | after vs nx |
|-----------|---------|-----------------|----------------|--------------|-------------|
| 0->1500   | 0.026   | 0.479           | 0.0024         | 18.3x slower | 10.7x faster|
| 0->1999   | 0.014   | 0.148           | 0.0019         | 10.9x slower | 7.3x faster |
| 123->456  | 0.017   | 0.286           | 0.0021         | 16.8x slower | 8.3x faster |

Self-speedup ~140-200x; vs-nx ~16x-slower -> ~8-11x-faster. Byte-exact.
