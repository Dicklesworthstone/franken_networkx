# Quiet-host gap scan + ctor residual analysis (load 7.8, best window)

## Algorithm/linalg surface: overwhelmingly faster than nx
betweenness 0.03x, communicability 0.01x, floyd_warshall 0.01x,
node_connectivity 0.06x, eigenvector 0.21x, all_pairs_sp_len 0.21x,
average_clustering 0.24x, MST 0.40x, pagerank 0.73x, hits 0.79x,
max_matching 0.99x. NO structural >2x gap with meaningful absolute
time remains — the substrate + kernel epochs closed them.

## Remaining >1.5x are all sub-millisecond delegated-fn wrapper tax
dominating_set 1.67x (0.4ms), greedy_color 1.77x (1.4ms),
maximal_independent_set 1.86x (0.8ms). All set-iteration-order-bound
(correctly delegated per reference_parity_blocked_by_set_order); the
ratio is the per-call _fnx_to_nx conversion tax on cheap outputs, not
algorithmic. Optimizing saves microseconds — not Score>=2.0.

## ctor residual decisively quantified (zge63)
Graph(edges) 9.21ms; validate_ctor_edge_list alone 0.52ms = 6%. The
fused validation+absorb kernel (TealSpring's recommended next) caps at
that 6% -> ~1.32x. The other 94% is per-tuple PyO3 extraction
(PyIterator + PyTuple get_item + node_key_to_string x12k) — the
irreducible Python/Rust boundary cost; lever-3 wash already proved
batching doesn't move it. zge63 de-prioritized (annotated on bead).

## Parity: approx namespace + bipartite module = 0 divergences
Pinned test_approx_bipartite_parity.py.

## Next real structural primitive
s2teo: atomic MultiGraph/MultiDiGraph rows+buckets flip (Multi ctor/
copy ~2-3x — the last large gap). TealSpring's lane (rows-first
rejected; batch-local ctor kernel recommended, not yet committed).
