# line_graph undirected — native kernel (tuple-key construction tax) br-r37-c1-ez7lx

## Lever
The undirected line_graph built its tuple-keyed L-graph in Python via
`add_edges_from(edges)`, re-canonicalizing both tuple endpoints of every L-edge
(~55% of runtime in `_try_add_edges_from_batch`). Filled in the previously-stubbed
undirected branch of the native `line_graph_fast` kernel (crates/fnx-python/src/
algorithms.rs): each L-node tuple (= a G-edge, carrying the ORIGINAL node objects,
oriented by node index like nx's `tuple(sorted(edge, key=node_index.get))`) is
canonicalized exactly ONCE; L-edges are assembled in Rust as the clique of edges
incident to each node (in a simple graph two distinct edges share at most one
endpoint, so every L-edge is emitted exactly once — no dedup). Bulk-constructed
via `extend_nodes/edges_unrecorded` with `node_key_map` carrying the tuple
objects. Wrapper guard widened from directed-only to any simple, self-loop-free,
create_using-default Graph.

## Correctness
12 graphs (path/ba/gnp/star/complete/cycle/str-nodes/isolated-edges/ws/empty):
node SET + endpoint-normalized edge SET identical to nx — 0 mismatches. Directed
line_graph unaffected. inverse_line_graph round-trip intact. BA800 golden
(normalized) sha a9d2df4863b4b6da == nx.

Order note: the orientation WITHIN each undirected L-edge (which L-node is
reported first by `.edges()`) derives in nx from CPython set-iteration order of
L-node insertion — non-semantic and not replicated natively. Every line_graph
parity site and all graph-product parity tests already compare endpoint-
normalized; aligned the one outlier (test_parity_conformance.py:381) to match.
843 line_graph/operator/utility/conformance tests pass.

## Benchmark (warm min, interleaved before/after) — ratio = nx/fnx
| graph      | BEFORE (Python)   | AFTER (native)    | self-speedup |
|------------|-------------------|-------------------|--------------|
| BA(400,4)  | 50.14ms (0.58x)   | 6.66ms  (4.50x)   | 7.5x         |
| BA(800,4)  | 120.73ms (0.60x)  | 15.62ms (4.65x)   | 7.7x         |
| BA(1500,4) | 258.83ms (0.65x)  | 32.68ms (4.86x)   | 7.9x         |

fnx flipped from 0.58-0.65x SLOWER than nx to 4.50-4.86x FASTER. Score >> 2.0.
