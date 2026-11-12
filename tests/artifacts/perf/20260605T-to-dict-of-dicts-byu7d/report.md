# br-r37-c1-byu7d to_dict_of_dicts cache proof

Target: generated exact `Graph` with empty edge attrs, `to_dict_of_dicts(G)` repeated 200x on `gnp_random_graph(2000, 0.002, seed=17)`.

Kept lever: cache NetworkX-style adjacency row templates on `PyGraph` behind `(nodes_seq, edges_seq)` and return fresh `dict.copy()` rows per call. This replaces repeated per-edge rebuilds with row-level shallow copies while preserving live edge-attr dict values.

Rejected levers before this keep:
- Pre-materializing missing live edge dicts in the conversion loop: `870.1 ms -> 1037.0 ms`, rejected.
- Integer neighbor iteration plus node-key cache only: `870.1 ms -> 933.8 ms`, rejected.

Benchmark:
- Baseline fnx hyperfine: `870.1 ms +/- 226.2`.
- After fnx hyperfine: `575.8 ms +/- 61.0`.
- NetworkX comparator after: `554.8 ms +/- 15.1`.
- Mean speedup vs baseline: `1.51x`.
- Score: Impact `3.0` x Confidence `0.8` / Effort `1.0` = `2.4`, keep.

Profile:
- Baseline native `_fnx.to_dict_of_dicts_undirected`: `0.254 s` over 200 calls.
- After native `_fnx.to_dict_of_dicts_undirected`: `0.045 s` over 200 calls.

Golden output:
- Baseline fnx digest: `68911148adaa1ecee8bb9a5e0ad549762668eab1633b139f6b31ce688fa3aca3`, `alias_pairs=0`, `mutation_live=false`.
- NetworkX digest: `0b1ba7022cacc99d754e1cbb120fd79bbe1343cf533f3ccb67ad905cfec7d87f`, `alias_pairs=8124`, `mutation_live=true`.
- After fnx digest: `0b1ba7022cacc99d754e1cbb120fd79bbe1343cf533f3ccb67ad905cfec7d87f`, `alias_pairs=8124`, `mutation_live=true`.

Isomorphism proof:
- Ordering: rows still follow `inner.nodes_ordered()`; neighbor rows still follow existing adjacency order.
- Tie-breaking: no algorithmic tie-break path touched.
- Floating point: no floating-point operations touched.
- RNG: graph generation remains unchanged; the cache only observes generated graph storage.
- Mutation: cache invalidates on node/edge structural changes via `nodes_seq`/`edges_seq`; edge-attr dict mutations stay live through shared `PyDict` references, matching NetworkX shallow-copy semantics.

Artifact SHA-256:
- `baseline_hyperfine_repeats200.json`: `5855e5480fe229dbaebf816d6a6f3747de9164c0f8bf82c6ae58514ae1a0a2ae`
- `after_dod_cache_final_hyperfine_repeats200.json`: `f3c13eca8baf5230c19eaadce209098e61e70877befa142ac1b9fc11c302ada8`
- `baseline_profile_fnx.stdout`: `de296d6a31acf97e80eac572877e7e54fa5199b63a0441769dce0ff106068363`
- `baseline_profile_nx.stdout`: `b5907541e5545ee25c8f5d5fd1d0ffffbe0d72ae442830d69940f011a6e54b01`
- `after_dod_cache_final_profile_fnx.stdout`: `463c35a80b2a906ffc25038c7f27343f025a8c1b47f050f0ac05094bfb062b49`
- `after_dod_cache_final_profile_fnx.stderr`: `3e290c490ae6c56164f5269971cb8185dd8c79e81a030aff47e0a8da6aded5c4`
