# Sparse Edge Index Cache Benchmark

Bead: `br-r37-c1-5lpag`

Target: `fnx.to_scipy_sparse_array(Graph, weight="weight", dtype=None, format="csr")`
on BA(8000, 4, seed=42), weighted with deterministic float weights.

## Baseline

Baseline artifacts were captured via `rch` before the lever:

- `maturin_develop_baseline.rch.log`
- `baseline_to_scipy_weighted_both.jsonl`
- `baseline_adjacency_weighted_both.jsonl`
- `hyperfine_baseline_to_scipy_weighted.json`
- `profile_baseline_to_scipy_weighted_fnx.txt`

Baseline focused samples:

- `to_scipy_weighted` FNX mean: `0.01818513319788811s`
- `to_scipy_weighted` NetworkX mean: `0.025153126934310422s`
- `adjacency_weighted` FNX mean: `0.01930183919224267s`
- `adjacency_weighted` NetworkX mean: `0.025820571067743003s`
- CSR digest: `12d41580d0336461201dbaa08fecc5250eab75162c958f5a91da80875db1ab37`

Baseline profile:

- `to_scipy_sparse_array`: `0.228s` cumulative over 12 calls
- native `adjacency_default_order_typed_arrays`: `0.124s` cumulative over 12 calls

Baseline hyperfine command envelope:

- `906.2 ms +/- 32.6 ms` for five conversions plus graph construction

## Lever

One lever: add a safe-Rust edge endpoint index cache to `Graph`, keep it in
sync across edge/node mutations, and consume it in
`adjacency_default_order_typed_arrays`.

The helper no longer walks node rows, resolves row/column names, and hashes
back into edge attrs for every coordinate. It streams storage-order edge
endpoint indices and the borrowed edge attr map directly, emitting the symmetric
CSR coordinate pair for undirected graphs.

## After

After artifacts were captured via `rch`:

- `maturin_develop_after_retry.rch.log`
- `after_confirm_to_scipy_weighted_both.jsonl`
- `after_confirm_adjacency_weighted_both.jsonl`
- `hyperfine_after_confirm_to_scipy_weighted.json`
- `profile_after_confirm_to_scipy_weighted_fnx.txt`

After focused samples:

- `to_scipy_weighted` FNX mean: `0.015764172266547877s`
- `to_scipy_weighted` NetworkX mean: `0.02666092007032906s`
- `adjacency_weighted` FNX mean: `0.016892281001977s`
- `adjacency_weighted` NetworkX mean: `0.02857413613431466s`
- CSR digest: `12d41580d0336461201dbaa08fecc5250eab75162c958f5a91da80875db1ab37`

After profile:

- `to_scipy_sparse_array`: `0.169s` cumulative over 12 calls
- native `adjacency_default_order_typed_arrays`: `0.070s` cumulative over 12 calls

After hyperfine command envelope:

- `876.4 ms +/- 36.4 ms` for five conversions plus graph construction

## Result

- Focused `to_scipy_weighted` win:
  `0.01818513319788811s -> 0.015764172266547877s` (`1.15x`)
- Focused `adjacency_weighted` win:
  `0.01930183919224267s -> 0.016892281001977s` (`1.14x`)
- Native helper win: `0.124s -> 0.070s` cumulative over 12 calls (`1.77x`)
- Whole command hyperfine win:
  `0.9062393700799999s -> 0.87641544944s` (`1.03x`) with noise because
  graph construction dominates the five-conversion process envelope.
- Score: `Impact 3 * Confidence 4 / Effort 2 = 6.0`, keep.
