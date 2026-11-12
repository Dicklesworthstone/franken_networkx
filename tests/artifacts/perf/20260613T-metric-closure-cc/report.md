# metric_closure native all_pairs_dijkstra route (cc, 2026-06-13)

## SHIPPED: 2.18-3.49x self-speedup, byte-exact, closes the vs-nx gap

`fnx.approximation.metric_closure` resolved through the generic
`_ApproximationNamespace.__getattr__` wrapper: round-trip the graph through
`_networkx_graph_for_parity` then run nx's pure-Python `all_pairs_dijkstra`
(distance + path) to build the dense complete graph — ~2.7-2.9x slower than nx.

**Lever** (one): add a concrete `_ApproximationNamespace.metric_closure`
method that routes the all-pairs Dijkstra through the native
`_raw_all_pairs_dijkstra` kernel (byte-exact distances AND paths) and
assembles the complete graph with a single `add_edges_from`, reproducing nx's
exact edge-insertion order (`set(G)` iteration, first-node-first). Same
de-delegation pattern as min_weighted_vertex_cover / randomized_partitioning
(reference_approx_namespace_conversion_tax).

### Before / after (connected_watts_strogatz, weight="weight", min-of-12 warm)

    n     OLD(delegate)   NEW(native)   self-speedup   NEW vs nx   (was)
    150      108.6ms        31.1ms         3.49x        1.39x      0.40x
    300      500.4ms       192.8ms         2.60x        0.89x      0.34x
    500     1584.8ms       726.6ms         2.18x        0.77x      0.35x

The gap vs nx goes from ~2.5-3x-slower to nx-parity (faster at n<=150). Score
= Impact(high: 2-3.5x + real gap closed) x Confidence(high) / Effort(low) >> 2.

### Proof

- `proof_final.py` → `proof_final.json`: NEW concrete method ==
  exact OLD delegating path, order-sensitive (node order, UNSORTED edge
  insertion order, per-edge distance + path, attr keys, graph attrs) across 10
  shapes incl weighted (wkarate). all_match=True, golden
  `fbd2579308a9a1b32640c1542ee6760494ea1ebd4a228a0038e707a85dce13c3`.
- `pytest test_tsp_approximation_conformance.py test_approximation_signature_parity.py`
  → 118 passed (incl metric_closure distance-parity vs nx, disconnected-raise
  message parity, signature parity).
- None-weight / directed / multigraph / nx-typed inputs keep the delegating path.

## METHODOLOGY NOTE (important)

An earlier pass this session WRONGLY concluded this lever was a "1.00x wash"
because the local site-packages install was stale (`rch maturin develop`
builds on the remote worker; pip skips refreshing same-version .py, and the
local .so was 4 days behind HEAD). After syncing repo HEAD .py + the fresh
repo `_fnx.abi3.so` into site-packages, the native route's `add_edges_from`
is much faster (HEAD construction-tax wins) and the speedup is real. Always
verify the installed module == HEAD before trusting any benchmark.

## Ruled out (still valid, build-independent)

- non_randomness 0.63x is NOT a gap: `eigvals(A)[:k]` is dgeev-order-locked
  (not the k-largest, cannot use the 43x-faster symmetric eigvalsh); fnx
  already mirrors nx's exact `np.linalg.eigvals` and is at parity (~130ms,
  both eigvals-bound).
