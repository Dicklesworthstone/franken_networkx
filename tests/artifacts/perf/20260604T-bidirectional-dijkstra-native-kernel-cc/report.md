# perf: native undirected bidirectional_dijkstra CSR kernel (br-r37-c1-k4p0b)

## Lever
The in-process Python port (`_bidirectional_dijkstra_local`) reconstructed nx's
algorithm but accessed `G.adj[v].items()` (an AtlasView building a per-edge
PyDict) for every explored node — ~30µs/node of pure PyO3 tax, leaving it
~6-10x slower than nx on single-pair queries. Replaced the undirected path with
an all-Rust kernel (`bidirectional_dijkstra_undirected`) over integer CSR
adjacency (`neighbors_indices`) + `edge_weight_or_default`, porting the Python
algorithm 1:1 (two fringes, shared FIFO counter, plain `<` comparisons,
identical finaldist/meetnode update + path reconstruction). DiGraph keeps the
in-process port (no in-neighbour CSR accessor).

## Correctness (byte-exact)
480-case differential, native == local == nx on (length, numeric TYPE, path),
0 mismatches. Graphs built from identical edge sequences (n up to 150,
unit/int/float/mixed weights, 6 seeds, 5 source/target pairs each) + string
nodes, NodeNotFound, bool weights. golden sha 86dca111...
nx preserves Python int arithmetic (int length iff every path weight is
int/bool, else float); the kernel returns `all_int` computed from inner
`CgseValue` variants so the wrapper coerces the type WITHOUT touching `G[u][v]`
(which would mark the graph attr-dirty and force an O(n) resync).

## Avoiding the sync tax
Edge weights live in the Rust inner `AttrMap`, populated at `add_edge(weight=)`
and re-synced only on post-creation mutation. The wrapper runs the edge-only,
dirty-gated `_fnx_sync_edge_attrs_to_inner` (a no-op for unmutated graphs)
instead of the heavyweight whole-graph `_fnx_sync_attrs_to_inner`, which
unconditionally re-synced all node attrs O(n) every call and dominated cost.

## Perf (warm min-of-40, weighted, deg≈4; host is noisy ~2.5x)
| n    | native  | old in-proc | nx     | self-speedup | vs nx |
|------|---------|-------------|--------|--------------|-------|
| 500  | 0.231ms | 1.510ms     | 0.249ms| 6.5x         | 1.08x |
| 1000 | 0.353ms | 1.417ms     | 0.229ms| 4.0x         | 0.65x |
| 3000 | 0.998ms | 3.008ms     | 0.492ms| 3.0x         | 0.49x |

Native is 1.2-6.5x faster than the prior in-process port (byte-exact) and
reaches/beats nx on small graphs. The remaining large-n gap is the dispatcher's
O(E) `_should_delegate_dijkstra_to_networkx` weight pre-scan (a separate lever,
filed as follow-up) — the kernel search itself is now microseconds.
