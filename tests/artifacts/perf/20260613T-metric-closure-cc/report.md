# metric_closure + non_randomness perf investigation (cc, 2026-06-13)

Fresh broad gap sweep (n=250 connected_watts_strogatz, value-returning fns,
vs-nx ratio = nx_time/fnx_time, <1.0 = fnx slower). Surface is at-or-above nx
everywhere except construction/spectral-locked cases:

    0.63x non_randomness   0.71x min_edge_cover   0.81x kernighan_lin
    (everything else >=0.95x; many 4x-755x FASTER: second_order 755x,
     communicability 133x, katz_numpy 54x, estrada 34x, clustering 34x ...)

## non_randomness 0.63x — NOT A GAP (eigvals dgeev-order locked)

Profiled: 95% of runtime is `np.linalg.eigvals(to_numpy_array(G))` (126ms fnx
/ 138ms nx on n=250 — at parity; the 0.63x was host noise). to_numpy_array
0.38ms, label_prop 7.7ms are negligible.

The matrix is SYMMETRIC, so `eigvalsh` would be 43x faster (2.9ms vs 126ms).
BUT nx computes `nr = real(sum(eigvals(A)[:k]))` — the FIRST k eigenvalues in
LAPACK dgeev's arbitrary return order, NOT sorted. Verified empirically:
`eigvals(A)[:k]` equals the k-LARGEST only for small k and only by luck of
dgeev ordering; at k=34 it matches neither k-largest nor k-smallest
(seed1/n40). The order is matrix-dependent and not a sort, so it cannot be
reproduced from `eigvalsh`'s sorted output. fnx already mirrors nx's exact
`np.linalg.eigvals` call → byte-identical and at parity. No parity-preserving
lever exists short of a bit-identical safe-Rust dgeev (different shift/deflation
order → still wouldn't match numpy's LAPACK). **Do not re-chase.**

## metric_closure 2.6x-slower vs-nx — CONSTRUCTION-BOUND (native route is 1.00x)

nx's metric_closure = `all_pairs_dijkstra` (distance+path) + build complete
graph M (O(n^2) edges, each with a `path` list). Tried: route the all-pairs
Dijkstra through native `_raw_all_pairs_dijkstra` (byte-exact distances AND
paths — order-sensitive golden `5f35e09d…`, 11 graph shapes incl. weighted,
node/edge insertion order + attrs all identical) and build M via a single
`add_edges_from`.

Clean interleaved warm bench (min-of-10):

    n     TRUE-OLD(_from_nx_graph)   NEW(native+add_edges_from)   self
    150        107.2ms                     110.1ms               0.97x
    300        503.8ms                     502.3ms               1.00x
    500       1534.8ms                    1542.1ms               1.00x

**No win.** The native dijkstra only replaced a ~41ms slice; the dominant cost
is building the dense fnx.Graph with per-edge `{distance, path}` dicts —
identical whether via `_from_nx_graph(nx_M)` or `add_edges_from`. This is the
O(n^2) attributed-edge construction tax (br-r37-c1-71x9k). Change reverted.

## Conclusion / next target

The value-returning algorithmic surface is saturated (at/above nx). The real
remaining lever is the construction substrate — bulk attributed-edge
construction (br-r37-c1-71x9k) and live-view materialization
(br-r37-c1-4b5ie) — which gates metric_closure, johnson, and every dense
graph-returning fn. That is the next swing; target = beat nx on
`add_edges_from` for attributed edges (currently ~1.4x slower/edge).
