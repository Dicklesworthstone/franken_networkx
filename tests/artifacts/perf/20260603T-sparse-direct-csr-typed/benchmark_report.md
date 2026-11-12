# Benchmark Report: sparse typed arrays read edge attrs once

Bead: `br-r37-c1-04z53.34`

## Profile Target

Fresh rch sweep after `br-r37-c1-04z53.33`:

- `adjacency_matrix(Graph, weight="weight")`, BA(8000, 4, seed=42)
- FrankenNetworkX mean: `0.03178882242978683s`
- NetworkX mean: `0.023546784858418896s`
- Ratio: `1.350x`
- Digest: `12d41580d0336461201dbaa08fecc5250eab75162c958f5a91da80875db1ab37`

Profile before this change:

- Total profile time for 8 measured calls: `0.253s`
- Native `_fnx.adjacency_default_order_typed_arrays`: `0.180s`
- `numpy.asarray`: `0.028s`
- `_sync_rust_edge_attrs`: `0.020s`

## Lever

Read each simple undirected edge's attrs once from the graph edge store, then emit both symmetric COO entries. This removes repeated per-directed-neighbor `get_node_name` plus `edge_attrs` lookups inside the profiled native helper.

Opportunity score: Impact 3 x Confidence 4 / Effort 2 = 6.0.

Alien primitive match: cache-local sparse construction / compact graph traversal. The hot loop now streams the edge store once and avoids redundant map lookups while retaining the same sparse matrix contract.

## Results

Direct rch sample, `bench_sparse_dtype_none.py sample --case adjacency_weighted --impl fnx --repeats 10 --n 8000 --m 4`:

- Baseline: `0.0300155875942437s`
- After: `0.018259779902291485s`
- Speedup: `1.644x`

Hyperfine rch, 15 runs, 5 repeats per process:

- Baseline: `0.9596849066s +/- 0.034440180876045536s`
- After: `0.8675781678200001s +/- 0.026439515980669393s`
- Speedup: `1.106x`

Profile after:

- Total profile time for 8 measured calls: `0.146s`
- Native `_fnx.adjacency_default_order_typed_arrays`: `0.076s`

## Verdict

Kept. The candidate exceeded the Score>=2.0 gate, preserved the sparse golden digest, and shifted the native helper from `0.180s` to `0.076s` in the profiled call path.
