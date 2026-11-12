# Benchmark Report: sparse default-order node cache

Bead: `br-r37-c1-04z53.33`

## Profile Target

`tests/artifacts/perf/20260603T-current-sparse-export-sweep/profile_to_scipy_weighted_fnx.txt` showed `to_scipy_sparse_array(Graph, weight="weight", dtype=None, format="csr")` spending most native time in `_fnx.adjacency_default_order_typed_arrays`:

- `to_scipy_weighted`: FrankenNetworkX `0.031079s`, NetworkX `0.025097s`, ratio `1.238x`.
- cProfile: 11 calls, `to_scipy_sparse_array` cumulative `0.315s`; native `adjacency_default_order_typed_arrays` cumulative `0.224s`.

## Lever

Cache the insertion-ordered node-name vector once in the default-order sparse array helpers, then reuse it for row and column names. This was intended to avoid per-neighbor `IndexMap::get_index` lookups in `get_node_name`.

Opportunity score before implementation: Impact 2 x Confidence 3 / Effort 1 = 6.0.

## Results

Direct rch sample, `bench_sparse_dtype_none.py sample --case to_scipy_weighted --impl fnx --repeats 10 --n 8000 --m 4`:

- Baseline: `0.028606187307741494s`
- After candidate: `0.028917891200399025s`
- Speedup: `0.989x` (slight regression)

Hyperfine via rch, 15 runs, 5 repeats per process:

- Baseline: `0.9830521996733333s +/- 0.04490716646346996s`
- After candidate: `0.9870441347333332s +/- 0.0523008174112034s`
- Speedup: `0.996x`

Golden digest remained unchanged: `12d41580d0336461201dbaa08fecc5250eab75162c958f5a91da80875db1ab37`.

## Verdict

Rejected. The candidate preserved behavior but failed to produce a real win and therefore did not satisfy the Score>=2.0 shipping gate. Source was restored and the extension was rebuilt from restored code.
