# Sparse Edge Index Cache Benchmark

Bead: `br-r37-c1-5lpag`

Target: `fnx.to_scipy_sparse_array(Graph, weight="weight", dtype=None, format="csr")`
on BA(8000, 4, seed=42), weighted with deterministic float weights.

## Baseline

Baseline artifacts were captured via `rch` before the lever:

- `maturin_develop_baseline.rch.log`
- `baseline_to_scipy_weighted_both.jsonl`
- `hyperfine_baseline_to_scipy_weighted.json`
- `profile_baseline_to_scipy_weighted_fnx.txt`

Baseline focused sample:

- FNX mean: `0.01818513319788811s`
- NetworkX mean: `0.025153126934310422s`
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

- `maturin_develop_after.rch.log`
- `after_to_scipy_weighted_both.jsonl`
- `hyperfine_after_to_scipy_weighted.json`
- `profile_after_to_scipy_weighted_fnx.txt`

After focused sample:

- FNX mean: `0.015818153199506923s`
- NetworkX mean: `0.028397863468853757s`
- CSR digest: `12d41580d0336461201dbaa08fecc5250eab75162c958f5a91da80875db1ab37`

After profile:

- `to_scipy_sparse_array`: `0.182s` cumulative over 12 calls
- native `adjacency_default_order_typed_arrays`: `0.075s` cumulative over 12 calls

After hyperfine command envelope:

- `905.4 ms +/- 29.3 ms` for five conversions plus graph construction

## Result

- Focused per-conversion win: `0.01818513319788811s -> 0.015818153199506923s`
  (`1.15x`)
- Native helper win: `0.124s -> 0.075s` cumulative over 12 calls (`1.65x`)
- Whole command hyperfine is neutral because graph construction dominates the
  benchmark envelope; the isolated target sample and cProfile hotspot both move
  in the same direction.
- Score: `Impact 2 * Confidence 5 / Effort 2 = 5.0`, keep.
